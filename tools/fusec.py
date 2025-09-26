#!/usr/bin/env python3
# FUSE -> C backend (beta)
# Usage:
#   python tools/fusec.py <input.fuse> -o <out_prefix>
# Emits:
#   <out_prefix>.c and <out_prefix>.h
#
# Supported now:
#  ✓ Functions (monomorphic) with explicit param/ret types
#  ✓ Read‑only references: &T  →  const T*
#  ✓ Algebraic Data Types (ADTs), including generic ADTs instantiated at concrete use sites
#  ✓ Pattern matching on ADTs → switch(tag) with safe destructuring
#  ✓ Traits + Impl (monomorphic): trait calls lower to impl functions (e.g., Ord_Int_lt)
#  ✓ Minimal monomorphization of generic functions: specialize at call‑sites when arg types are known
#  ✓ Blocks with local let (explicit type), if, arithmetic/logical ops, function calls
#
# Not yet:
#  - Tuples in C backend (use ADTs instead)
#  - Effects/async at C level (use the interpreter's runtime or host via FFI)
#
# Design principles:
#  - Require explicit types on fn params/ret and local lets (keeps codegen simple and predictable)
#  - For generics: only specialize functions that are actually called with concrete types
#  - ADT codegen: enum tag + union of ctor payload structs with designated initializers
#
# This generator does *not* evaluate the program; it compiles a safe, monomorphic C translation unit.
#
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from prototype.fuse_full import tokenize, Parser, MacroExpander, Program, \
    IntLit, BoolLit, StrLit, UnitLit, Var, TupleLit, IfExpr, UnaryOp, BinaryOp, \
    Call, Block, LetStmt, FnDef, TypeDef, TraitDef, ImplDef, MatchExpr, MatchArm, \
    PWildcard, PInt, PVar, PTuple, PCtor, RefOf, TypeExpr, TEName, TERef, TETuple, TEVar, pretty_print_type_expr

# ---------------- Utilities ----------------
def die(msg):
    raise SystemExit("[fusec] " + msg)

def is_upper(name:str)->bool: return name and name[0].isupper()

# Type rendering / mangling
def c_type_name(texpr: TypeExpr, subst=None) -> str:
    subst = subst or {}
    if isinstance(texpr, TEName):
        if texpr.name == 'Int': return 'int64_t'
        if texpr.name == 'Bool': return 'bool'
        if texpr.name == 'Str': return 'const char*'
        if texpr.name == 'Unit': return 'void'
        # ADT (or nominal type): generate a struct name
        args = [c_type_tag(a, subst) for a in texpr.args]
        if args:
            return f"{texpr.name}__{'__'.join(args)}"
        return texpr.name
    if isinstance(texpr, TERef):
        inner = c_type_name(texpr.inner, subst)
        return f"const {inner}*"
    if isinstance(texpr, TEVar):
        # Substitute generic var if present
        if texpr.name in subst:
            return c_type_name(subst[texpr.name], subst)
        die(f"free type variable in C backend: {texpr.name} (please specialize or annotate)")
    if isinstance(texpr, TETuple):
        die("tuples are not supported in C backend (use ADTs)")
    die("unknown type expr")

def c_type_tag(texpr: TypeExpr, subst=None) -> str:
    subst = subst or {}
    if isinstance(texpr, TEName):
        if texpr.name in ('Int','Bool','Str','Unit'):
            return texpr.name
        if texpr.args:
            return f"{texpr.name}__{'__'.join(c_type_tag(a, subst) for a in texpr.args)}"
        return texpr.name
    if isinstance(texpr, TERef):
        return 'Ref_' + c_type_tag(texpr.inner, subst)
    if isinstance(texpr, TEVar):
        if texpr.name in subst:
            return c_type_tag(subst[texpr.name], subst)
        die(f"free type variable in name mangling: {texpr.name}")
    if isinstance(texpr, TETuple):
        die("tuples not supported in mangling")
    return 'T'

def mangle_fn(name:str, targs:list)->str:
    if not targs: return name
    return f"{name}__{'__'.join(c_type_tag(t) for t in targs)}"

# ---------------- Program model ----------------
class Env:
    def __init__(self):
        self.fns = []          # list[FnDef]
        self.fn_map = {}       # name -> list[FnDef]
        self.types = {}        # name -> TypeDef
        self.ctors = {}        # ctor -> (typename, arg_texprs)
        self.traits = {}       # name -> TraitDef
        self.impls = {}        # (trait, type_tag) -> dict(method->FnDef)
        self.adts_needed = set()   # set of (typename, [arg TypeExpr])
        self.specializations = {}  # (fn_name, tuple(typeargs)) -> SpecializedFn

class SpecializedFn:
    def __init__(self, base:FnDef, targs:list):
        self.base = base
        self.targs = targs  # list[TypeExpr]
        self.name = mangle_fn(base.name, targs)

# ---------------- Collect ----------------
def collect(prog:Program)->Env:
    env = Env()
    for it in prog.items:
        if isinstance(it, TypeDef):
            env.types[it.name] = it
            for cname, cargs in it.ctors:
                env.ctors[cname] = (it.name, cargs)
        elif isinstance(it, TraitDef):
            env.traits[it.name] = it
        elif isinstance(it, ImplDef):
            # register later after collecting fns (we need their bodies too)
            pass
        elif isinstance(it, FnDef):
            env.fns.append(it)
            env.fn_map.setdefault(it.name, []).append(it)
        elif isinstance(it, LetStmt):
            # top-level let not supported in C translation unit (requires globals). Skip for now.
            pass
    # Collect impls (map to their fn bodies)
    for it in prog.items:
        if isinstance(it, ImplDef):
            trait = it.trait
            if trait not in env.traits: die(f"unknown trait in impl: {trait}")
            ttag = c_type_tag(it.tactual)
            method_map = {}
            for name, fn in it.methods.items():
                method_map[name] = fn
            env.impls[(trait, ttag)] = method_map
    return env

# ---------------- ADT codegen helpers ----------------
def need_adt_inst(env:Env, texpr:TypeExpr):
    if isinstance(texpr, TEName) and texpr.name not in ('Int','Bool','Str','Unit'):
        args = []
        for a in texpr.args:
            need_adt_inst(env, a)
            args.append(a)
        env.adts_needed.add( (texpr.name, tuple(args)) )

def emit_adt_defs(env:Env):
    out = []
    emitted = set()
    def emit_one(typename, args):
        key = (typename, tuple(args))
        if key in emitted: return
        emitted.add(key)
        # recursively emit args' defs (for nested ADTs)
        for a in args:
            need_adt_inst(env, a)
        # actual typedef
        tdef = env.types.get(typename)
        if not tdef: die(f"ADT not defined: {typename}")
        tag_enum = f"{typename}__{'__'.join(c_type_tag(a) for a in args)}__tag" if args else f"{typename}__tag"
        struct_base = f"{typename}__{'__'.join(c_type_tag(a) for a in args)}" if args else typename
        out.append(f"typedef enum {{")
        tags = []
        for cname, _ in tdef.ctors:
            tags.append(f"  {struct_base}__{cname}")
        out += tags
        out.append(f"}} {tag_enum};")
        out.append("")
        # payload structs + union
        payload_typedefs = []
        union_members = []
        for cname, cargs in tdef.ctors:
            if cargs:
                fields = []
                for i, te in enumerate(cargs, start=1):
                    cty = c_type_name(subst_texpr(te, tdef.tvars, args))
                    fields.append(f"{cty} _{i};")
                payload_name = f"{struct_base}__{cname}__payload"
                payload_typedefs.append("typedef struct { " + " ".join(fields) + f" }} {payload_name};")
                union_members.append(f"{payload_name} {cname};")
            else:
                # zero-field ctor — no payload struct needed
                union_members.append(f"char __{cname}_empty;")
        out += payload_typedefs
        out.append("typedef union {")
        out += [ "  " + m for m in union_members ]
        out.append(f"}} {struct_base}__union;")
        out.append(f"typedef struct {{ {tag_enum} tag; {struct_base}__union as; }} {struct_base};")
        out.append("")
    # Emit in deterministic order
    for (typename, args) in sorted(env.adts_needed, key=lambda x: (x[0], str(x[1]))):
        emit_one(typename, args)
    return "\n".join(out)

def subst_texpr(texpr:TypeExpr, tvars:list, args:list) -> TypeExpr:
    # substitute generic tvars in texpr with concrete args (by position)
    mapping = { tv: arg for tv, arg in zip(tvars, args) }
    return subst_texpr_map(texpr, mapping)

def subst_texpr_map(texpr:TypeExpr, mapping:dict)->TypeExpr:
    if isinstance(texpr, TEName):
        return TEName(texpr.name, [subst_texpr_map(a, mapping) for a in texpr.args])
    if isinstance(texpr, TERef):
        return TERef(subst_texpr_map(texpr.inner, mapping))
    if isinstance(texpr, TETuple):
        return TETuple([subst_texpr_map(a, mapping) for a in texpr.items])
    if isinstance(texpr, TEVar):
        return mapping.get(texpr.name, texpr)
    return texpr

# ---------------- Simple type environment for codegen ----------------
class CTypeEnv:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}   # name -> TypeExpr
    def get(self, name):
        if name in self.vars: return self.vars[name]
        if self.parent: return self.parent.get(name)
        return None
    def set(self, name, texpr):
        self.vars[name] = texpr

# ---------------- Expression emission ----------------
class CGen:
    def __init__(self, env:Env):
        self.env = env
        self.lines = []
        self.protos = set()
        self.tmp_counter = 0
        self.adts_emitted = False
        self.specializations = {}  # (fn_name, taglist) -> emitted flag

    def temp(self):
        self.tmp_counter += 1
        return f"__t{self.tmp_counter}"

    def emit(self, s): self.lines.append(s)

    # --- Functions, traits, impls ---
    def emit_all(self, prog:Program):
        # Walk to find needed ADT instantiations from explicit types in fn params/ret and local lets
        for it in prog.items:
            if isinstance(it, FnDef):
                # params and ret
                subst = None
                for (pname, ann) in it.params:
                    if ann is None: die(f"param {pname} in {it.name} must have type annotation for C backend")
                    need_adt_inst(self.env, ann)
                if it.ret_ann:
                    need_adt_inst(self.env, it.ret_ann)

        # Emit ADT defs header prelude after we collect concrete instantiations while emitting bodies too
        # We'll collect more while emitting bodies (constructor calls and match target types).
        # So we emit ADTs at the end once.
        for it in prog.items:
            if isinstance(it, TraitDef):
                # no direct C code; impls produce functions later
                pass

        # Emit impl methods as plain C functions with concrete types
        for it in prog.items:
            if isinstance(it, ImplDef):
                self.emit_impl(it)

        # Emit normal and specialized functions
        for it in prog.items:
            if isinstance(it, FnDef):
                self.emit_fn(it)

        # Finally, emit ADT definitions (after seeing bodies)
        adt_defs = emit_adt_defs(self.env)
        self.lines.insert(0, adt_defs)

    def require_proto(self, rett:str, name:str, params:list):
        self.protos.add(f"{rett} {name}(" + ", ".join(params) + ");")

    def emit_impl(self, impl:ImplDef):
        trait = self.env.traits[impl.trait]
        # For each method in trait, materialize a function with substituted types
        targs = impl.tactual
        # Trait methods have types expressed in terms of trait.tvar
        for mname, (mparams, mret) in trait.methods.items():
            if mname not in impl.methods:
                die(f"impl {impl.trait}[{pretty_print_type_expr(targs)}] missing method {mname}")
            fn = impl.methods[mname]
            # Substitute T in param/ret types with targs
            mapping = { trait.tvar: targs }
            mparams_conc = [subst_texpr_map(tp, mapping) for tp in mparams]
            mret_conc = subst_texpr_map(mret, mapping)
            mangled = f"{impl.trait}_{c_type_tag(targs)}_{mname}"
            # Emit as a regular C function
            # Build param list with names; rely on fn.params names count match
            if len(fn.params) != len(mparams_conc):
                die(f"impl method {mname} arity mismatch for {impl.trait}")
            params_c = []
            for (pname,_), tp in zip(fn.params, mparams_conc):
                params_c.append(f"{c_type_name(tp)} {pname}")
            rett = c_type_name(mret_conc)
            self.require_proto(rett, mangled, params_c)
            self.emit(f"{rett} {mangled}(" + ", ".join(params_c) + ") {")
            # Emit body in a local var env seeded with param types
            venv = CTypeEnv()
            for (pname,_), tp in zip(fn.params, mparams_conc):
                venv.set(pname, tp)
            stmts, xret, _ = self.emit_expr(fn.body, venv, expected= mret_conc if rett!='void' else None)
            for s in stmts: self.emit("  " + s)
            if rett == 'void':
                # ensure side effects computed
                if xret: self.emit("  (void)("+xret+");")
                self.emit("  return;")
            else:
                self.emit(f"  return {xret};")
            self.emit("}")
            self.emit("")

    def emit_fn(self, fn:FnDef):
        if fn.tvars:
            # generic: emit specializations lazily from call sites; also allow manual monomorphization by naming convention if never called
            # We'll still skip emitting the unspecialized version.
            return
        if fn.ret_ann is None:
            die(f"fn {fn.name} missing return type annotation")
        for pname, ann in fn.params:
            if ann is None:
                die(f"fn {fn.name} param {pname} missing type annotation")
        rett = c_type_name(fn.ret_ann)
        params_c = [f"{c_type_name(ann)} {pname}" for (pname,ann) in fn.params]
        self.require_proto(rett, fn.name, params_c)
        self.emit(f"{rett} {fn.name}(" + ", ".join(params_c) + ") {")
        venv = CTypeEnv()
        for (pname,ann) in fn.params:
            venv.set(pname, ann)
        stmts, xret, _ = self.emit_expr(fn.body, venv, expected= fn.ret_ann if rett!='void' else None)
        for s in stmts: self.emit("  " + s)
        if rett == 'void':
            if xret: self.emit("  (void)("+xret+");")
            self.emit("  return;")
        else:
            self.emit(f"  return {xret};")
        self.emit("}")
        self.emit("")

    # --- Expressions ---
    def emit_expr(self, e, venv:CTypeEnv, expected:TypeExpr=None):
        # returns (stmts:list[str], expr_str:str, type_hint:TypeExpr)
        if isinstance(e, IntLit): return [], str(e.value), TEName('Int',[])
        if isinstance(e, BoolLit): return [], ('true' if e.value else 'false'), TEName('Bool',[])
        if isinstance(e, StrLit): return [], '"' + e.value.replace('"','\\"') + '"', TEName('Str',[])
        if isinstance(e, UnitLit): return [], '0', TEName('Unit',[])
        if isinstance(e, Var):
            t = venv.get(e.name)
            if t is None:
                die(f"unknown variable in C backend: {e.name}")
            # auto-deref read-only ref
            if isinstance(t, TERef):
                return [], f"*({e.name})", t.inner
            return [], e.name, t
        if isinstance(e, RefOf):
            # only Var allowed by parser
            t = venv.get(e.varname)
            if t is None: die(f"unknown var in &{e.varname}")
            if isinstance(t, TERef):
                # &(&T) is not allowed; but we can return just var
                return [], e.varname, t
            return [], f"&{e.varname}", TERef(t)
        if isinstance(e, UnaryOp):
            s,x,t = self.emit_expr(e.expr, venv, expected=None)
            if e.op == '-': return s, f"(-({x}))", TEName('Int',[])
            if e.op == '+': return s, f"(+({x}))", TEName('Int',[])
            if e.op == '!': return s, f"(!({x}))", TEName('Bool',[])
            die(f"unknown unary {e.op}")
        if isinstance(e, BinaryOp):
            sl, xl, tl = self.emit_expr(e.left, venv, expected=None)
            sr, xr, tr = self.emit_expr(e.right, venv, expected=None)
            op = e.op
            if op in ['+','-','*','/','%']:
                return sl+sr, f"(({xl}) {op} ({xr}))", TEName('Int',[])
            if op in ['<','>','<=','>=','==','!=','&&','||']:
                return sl+sr, f"(({xl}) {op} ({xr}))", TEName('Bool',[])
            die(f"unknown binary {op}")
        if isinstance(e, IfExpr):
            sc, xc, _ = self.emit_expr(e.cond, venv, expected=TEName('Bool',[]))
            st, xt, _ = self.emit_expr(e.then, venv, expected=expected)
            se, xe, _ = self.emit_expr(e.els, venv, expected=expected)
            # turn into ternary
            return sc+st+se, f"(({xc}) ? ({xt}) : ({xe}))", expected
        if isinstance(e, Block):
            local = CTypeEnv(venv)
            stmts = []
            last = ('0', TEName('Unit',[]))
            for item in e.items:
                if isinstance(item, LetStmt):
                    if item.type_ann is None: die("local let must have explicit type in C backend")
                    # track ADT instantiation need
                    need_adt_inst(self.env, item.type_ann)
                    s, x, t = self.emit_expr(item.expr, local, expected=item.type_ann)
                    cty = c_type_name(item.type_ann)
                    stmts += s
                    stmts.append(f"{cty} {item.name} = {x};")
                    local.set(item.name, item.type_ann)
                else:
                    s, x, t = self.emit_expr(item, local, expected=expected)
                    stmts += s
                    last = (x, t)
            return stmts, last[0], last[1]
        if isinstance(e, Call):
            # Macro-expanded already. Could be ctor call, generic fn, or normal fn.
            # ctor?
            if isinstance(e.func, Var) and e.func.name in self.env.ctors:
                return self.emit_ctor_call(e, venv, expected)
            # normal or generic fn
            if isinstance(e.func, Var):
                fname = e.func.name
                fns = self.env.fn_map.get(fname, [])
                if not fns: die(f"unknown function: {fname}")
                # if generic, try specialize
                base = None
                for cand in fns:
                    base = cand
                    break
                # compute arg expressions & their types
                arg_stmts=[]; arg_exprs=[]; arg_types=[]
                for a in e.args:
                    s, x, t = self.emit_expr(a, venv, expected=None)
                    arg_stmts += s; arg_exprs.append(x); arg_types.append(t)
                # if generic
                if base.tvars:
                    # attempt to map type variables from param annotations
                    mapping = {}
                    if any(pann is None for (_,pann) in base.params):
                        die(f"generic function {base.name} must have annotated parameter types for C backend")
                    for (_, pann), targ in zip(base.params, arg_types):
                        extract_mapping(pann, targ, mapping)
                    # build targs list in function tvars order
                    targs = [ mapping.get(tv) or die(f"cannot infer type arg {tv} in call to {base.name}") for tv in base.tvars ]
                    spec = SpecializedFn(base, targs)
                    key = (base.name, tuple(c_type_tag(t) for t in targs))
                    if key not in self.env.specializations:
                        self.env.specializations[key] = spec
                        # emit specialization
                        self.emit_specialized_fn(spec)
                    # ret type from specialized base ret_ann
                    ret_texpr = subst_texpr_map(base.ret_ann, { tv:ta for tv,ta in zip(base.tvars, targs) }) if base.ret_ann else TEName('Unit',[])
                    need_adt_inst(self.env, ret_texpr)
                    # ensure ADT instances for param types
                    for (_,pann) in base.params:
                        need_adt_inst(self.env, subst_texpr_map(pann, { tv:ta for tv,ta in zip(base.tvars, targs) }))
                    call = f"{spec.name}(" + ", ".join(arg_exprs) + ")"
                    return arg_stmts, call, ret_texpr
                else:
                    # monomorphic
                    # Ensure params annotated
                    for (_,ann) in base.params:
                        if ann is None: die(f"function {base.name} parameter missing type for C backend")
                    # evaluate args with expected param types to allow ctor inference
                    arg_stmts=[]; arg_exprs=[]
                    for (_,ann), a in zip(base.params, e.args):
                        s, x, _ = self.emit_expr(a, venv, expected=ann)
                        arg_stmts += s; arg_exprs.append(x)
                    # ret
                    if base.ret_ann is None: die(f"fn {base.name} missing return type")
                    call = f"{base.name}(" + ", ".join(arg_exprs) + ")"
                    return arg_stmts, call, base.ret_ann
            # trait method call: Trait.method[Type](args...)
            if isinstance(e.func, Var) is False and False:
                pass
            die("unsupported complex call")
        if isinstance(e, MatchExpr):
            return self.emit_match(e, venv, expected)
        if isinstance(e, PCtor):
            die("internal: pattern node found in expr")
        if isinstance(e, TraitDef) or isinstance(e, ImplDef):
            die("not an expr")
        if isinstance(e, Var):
            pass
        if isinstance(e, TraitDef):
            pass
        # TraitCall as a separate AST node (from parser: TraitCall)
        if hasattr(e, 'trait') and hasattr(e, 'method') and hasattr(e, 'tactual'):
            # This is TraitCall
            arg_stmts=[]; arg_exprs=[]
            for a in e.args:
                s, x, _ = self.emit_expr(a, venv, expected=None)
                arg_stmts += s; arg_exprs.append(x)
            ttag = c_type_tag(e.tactual)
            mname = f"{e.trait}_{ttag}_{e.method}"
            # find trait method type to determine ret
            trait = self.env.traits.get(e.trait)
            if not trait: die(f"unknown trait {e.trait}")
            if e.method not in trait.methods: die(f"unknown trait method {e.method}")
            mparams, mret = trait.methods[e.method]
            # substitute trait T with tactual
            mapping = { trait.tvar: e.tactual }
            retc = subst_texpr_map(mret, mapping)
            need_adt_inst(self.env, retc)
            return arg_stmts, f"{mname}(" + ", ".join(arg_exprs) + ")", retc

        die("unsupported expression type")

    def emit_ctor_call(self, call:Call, venv:CTypeEnv, expected:TypeExpr):
        # We know target ADT from expected type
        if expected is None:
            die("constructor call requires expected type in C backend (add a type annotation or use in a typed context)")
        if not isinstance(expected, TEName):
            die("constructor expected a concrete ADT type")
        typename = expected.name
        if typename not in self.env.types:
            die(f"constructor call expects ADT type, got {typename}")
        # which ctor?
        cname = call.func.name
        td = self.env.types[typename]
        ctor_args_t = None
        for cn, cargs in td.ctors:
            if cn == cname: ctor_args_t = cargs
        if ctor_args_t is None: die(f"{cname} is not a constructor of {typename}")
        # Substitute tvars in ctor args
        conc_args = [ subst_texpr(tex, td.tvars, expected.args) for tex in ctor_args_t ]
        # Emit args
        if len(conc_args) != len(call.args): die("constructor arity mismatch")
        arg_stmts=[]; field_exprs=[]
        for i,(targ, aexpr) in enumerate(zip(conc_args, call.args), start=1):
            s, x, _ = self.emit_expr(aexpr, venv, expected=targ)
            arg_stmts += s
            field_exprs.append( (i, x) )
        # Record ADT instance
        need_adt_inst(self.env, expected)
        struct_base = c_type_name(expected)
        tag_enum_val = f"{struct_base}__{cname}"
        # Build compound literal
        payload_init = ""
        if field_exprs:
            payload_typedef = f"{struct_base}__{cname}__payload"
            fields = ", ".join(f"._{i} = {x}" for i,x in field_exprs)
            payload_init = f".as.{cname} = ({payload_typedef}){{ {fields} }}"
        else:
            payload_init = f".as.{cname} = 0"
        expr = f"({struct_base}){{ .tag = {tag_enum_val}, {payload_init} }}"
        return arg_stmts, expr, expected

    def emit_match(self, m:MatchExpr, venv:CTypeEnv, expected:TypeExpr):
        # Evaluate target once
        st, xv, ttarget = self.emit_expr(m.target, venv, expected=None)
        if not isinstance(ttarget, TEName) or ttarget.name in ('Int','Bool','Str','Unit'):
            die("match target must be an ADT value")
        need_adt_inst(self.env, ttarget)
        struct_base = c_type_name(ttarget)
        tag_enum = f"{struct_base}__tag" if True else f"{struct_base}__tag"
        tmpv = self.temp()
        stmts = st + [ f"{struct_base} {tmpv} = {xv};" ]
        # Result temporary (if an expression expected)
        result_tmp = None
        result_decl = ""
        if expected and c_type_name(expected) != 'void':
            result_tmp = self.temp()
            result_decl = f"{c_type_name(expected)} {result_tmp};"
            stmts.append(result_decl)
        # Build switch
        stmts.append(f"switch ({tmpv}.tag) {{")
        has_default = False
        for arm in m.arms:
            if isinstance(arm.pattern, PWildcard):
                has_default = True
                stmts.append("  default: {")
                inner_stmts, xexpr, _ = self.emit_expr(arm.expr, venv, expected=expected)
                stmts += [ "    " + s for s in inner_stmts ]
                if result_tmp: stmts.append(f"    {result_tmp} = {xexpr};")
                stmts.append("    break; }")
            elif isinstance(arm.pattern, PCtor):
                cname = arm.pattern.name
                # case label
                stmts.append(f"  case {struct_base}__{cname}: {{")
                # destructure
                if arm.pattern.items:
                    payload_typedef = f"{struct_base}__{cname}__payload"
                    tmp_payload = self.temp()
                    stmts.append(f"    {payload_typedef} {tmp_payload} = {tmpv}.as.{cname};")
                    # bind variables
                    for idx, subpat in enumerate(arm.pattern.items, start=1):
                        if isinstance(subpat, PVar):
                            stmts.append(f"    {c_type_name(ttarget.args[0]) if False else ''}")
                        # compute subpattern binding via recursive pattern emission (limited to vars and wildcards)
                        if isinstance(subpat, PVar):
                            # Need field type; fetch from ADT def
                            # find ctor args types
                            td = self.env.types[ttarget.name]
                            cargs = None
                            for cn, ca in td.ctors:
                                if cn==cname: cargs=ca; break
                            te_field = subst_texpr(cargs[idx-1], td.tvars, ttarget.args)
                            cty = c_type_name(te_field)
                            stmts.append(f"    {cty} {subpat.name} = {tmp_payload}._{idx};")
                        elif isinstance(subpat, PWildcard):
                            pass
                        elif isinstance(subpat, PInt):
                            # We'll just check equality and guard with if; simple path
                            stmts.append(f"    if ({tmp_payload}._{idx} != {subpat.value}) {{ break; }}")
                        else:
                            die("nested complex patterns not supported in C backend yet")
                # body
                inner_stmts, xexpr, _ = self.emit_expr(arm.expr, venv, expected=expected)
                stmts += [ "    " + s for s in inner_stmts ]
                if result_tmp: stmts.append(f"    {result_tmp} = {xexpr};")
                stmts.append("    break; }")
            else:
                die("only wildcard '_' or constructor patterns are supported in C backend")
        if not has_default:
            stmts.append("  default: ;")
        stmts.append("}")  # end switch
        # return as expression
        if result_tmp:
            return stmts, result_tmp, expected
        else:
            return stmts, '0', TEName('Unit',[])

    def emit_specialized_fn(self, spec:SpecializedFn):
        base = spec.base
        tvars = base.tvars
        mapping = { tv: ta for tv, ta in zip(tvars, spec.targs) }
        rett = c_type_name(subst_texpr_map(base.ret_ann, mapping)) if base.ret_ann else 'void'
        params_c = []
        venv = CTypeEnv()
        for (pname, pann) in base.params:
            if pann is None: die("generic function params must be annotated")
            pann_c = subst_texpr_map(pann, mapping)
            need_adt_inst(self.env, pann_c)
            params_c.append(f"{c_type_name(pann_c)} {pname}")
            venv.set(pname, pann_c)
        # declare proto
        self.require_proto(rett, spec.name, params_c)
        # emit body
        self.emit(f"{rett} {spec.name}(" + ", ".join(params_c) + ") {")
        stmts, xret, _ = self.emit_expr(base.body, venv, expected=subst_texpr_map(base.ret_ann, mapping) if base.ret_ann else None)
        for s in stmts: self.emit("  " + s)
        if rett == 'void':
            if xret: self.emit("  (void)("+xret+");")
            self.emit("  return;")
        else:
            self.emit(f"  return {xret};")
        self.emit("}")
        self.emit("")

# Map generic param type pattern to actual type
def extract_mapping(param_t:TypeExpr, arg_t:TypeExpr, mapping:dict):
    if isinstance(param_t, TEVar):
        mapping[param_t.name] = arg_t
        return
    if isinstance(param_t, TEName) and isinstance(arg_t, TEName):
        if param_t.name != arg_t.name and param_t.name not in ('Int','Bool','Str','Unit'):
            die("cannot map different nominal types")
        for pa, aa in zip(param_t.args, arg_t.args):
            extract_mapping(pa, aa, mapping)
        return
    if isinstance(param_t, TERef) and isinstance(arg_t, TERef):
        extract_mapping(param_t.inner, arg_t.inner, mapping)
        return
    # literals vs primitive
    if isinstance(param_t, TEName) and param_t.name in ('Int','Bool','Str','Unit'):
        # ok if arg is same primitive
        return
    die("unsupported mapping case for generics in C backend")

# -------------- Top-level --------------
def generate(prog:Program, out_prefix:str):
    env = collect(prog)
    gen = CGen(env)
    gen.emit_all(prog)

    h_path = out_prefix + ".h"
    c_path = out_prefix + ".c"
    with open(h_path, "w", encoding="utf-8") as h:
        h.write("#pragma once\n#include <stdint.h>\n#include <stdbool.h>\n\n")
        for p in sorted(gen.protos):
            h.write(p + ";\n")
    with open(c_path, "w", encoding="utf-8") as c:
        c.write("#include <stdint.h>\n#include <stdbool.h>\n")
        c.write("#include <stddef.h>\n")
        c.write("#include \"" + os.path.basename(h_path) + "\"\n\n")
        for line in gen.lines:
            c.write(line + "\n")
    print("[fusec] wrote", h_path, "and", c_path)

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/fusec.py <input.fuse> -o <out_prefix>")
        sys.exit(1)
    src_path = sys.argv[1]
    out_prefix = "gen_logic"
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        if i+1 < len(sys.argv):
            out_prefix = sys.argv[i+1]
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    expander = MacroExpander()
    tokens = tokenize(src)
    parser = Parser(tokens, expander.macros)
    prog = parser.parse_program()
    generate(prog, out_prefix)

if __name__ == "__main__":
    main()
