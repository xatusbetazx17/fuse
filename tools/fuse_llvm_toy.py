#!/usr/bin/env python3
# fuse_llvm_toy.py — ultra-small LLVM IR generator (demo)
# Supports: monomorphic functions with Int params/ret and +,-,*,/ plus return.
# Usage:
#   python tools/fuse_llvm_toy.py <input.fuse> -o out.ll
#
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from prototype.fuse_full import tokenize, Parser, MacroExpander, FnDef, IntLit, BoolLit, StrLit, Var, BinaryOp, IfExpr, Block, LetStmt, TEName

def die(m): 
    raise SystemExit("[fuse-llvm-toy] " + m)

def gen_fn(fn: FnDef):
    # Only support Int -> Int functions with Int params
    if fn.ret_ann is None or not (isinstance(fn.ret_ann, TEName) and fn.ret_ann.name=='Int'):
        die(f"only Int return supported in toy: {fn.name}")
    for pname, ann in fn.params:
        if ann is None or not (isinstance(ann, TEName) and ann.name=='Int'):
            die(f"only Int params supported in toy: {fn.name}")
    header = f"define i64 @{fn.name}(" + ", ".join(f"i64 %{p}" for p,_ in fn.params) + ") {{"
    body, last = gen_expr(fn.body, {p: f"%{p}" for p,_ in fn.params}, 0)
    return "\n".join([header] + body + [f"  ret i64 {last}", "}"])

def gen_expr(e, env, n):
    # returns (lines, value_reg)
    if isinstance(e, IntLit): return [], str(e.value)
    if isinstance(e, Var):
        if e.name not in env: die(f"unknown var {e.name}")
        return [], env[e.name]
    if isinstance(e, BinaryOp):
        L = []
        lns, lv = gen_expr(e.left, env, n); L += lns
        rns, rv = gen_expr(e.right, env, n); L += rns
        n1 = len([ln for ln in L if ln.startswith('%')])
        tgt = f"%t{n1+1}"
        op = {'+':'add','-':'sub','*':'mul','/':'sdiv'}.get(e.op)
        if not op: die("only + - * / in toy")
        L.append(f"  {tgt} = {op} i64 {lv}, {rv}")
        return L, tgt
    if isinstance(e, Block):
        lines=[]; local=env.copy(); last='0'
        for it in e.items:
            if isinstance(it, LetStmt):
                lns, lv = gen_expr(it.expr, local, n)
                lines += lns
                local[it.name] = lv
            else:
                lns, lv = gen_expr(it, local, n)
                lines += lns; last=lv
        return lines, last
    if isinstance(e, IfExpr):
        # very naive lowering
        cond_lines, cond_val = gen_expr(e.cond, env, n)
        then_lines, then_val = gen_expr(e.then, env, n)
        else_lines, else_val = gen_expr(e.els, env, n)
        # pretend cond is nonzero => true
        lines = cond_lines + then_lines + else_lines
        # No real control flow for toy; pick then_val (demo only)
        return lines, then_val
    die("unsupported expr in toy")

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/fuse_llvm_toy.py <input.fuse> -o out.ll"); sys.exit(1)
    src_path = sys.argv[1]; out = "out.ll"
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        if i+1 < len(sys.argv): out = sys.argv[i+1]
    with open(src_path, "r", encoding="utf-8") as f: src=f.read()
    tokens = tokenize(src); parser=Parser(tokens, {}); prog = parser.parse_program()
    fns = [it for it in prog.items if isinstance(it, FnDef)]
    lines = ["; FUSE -> LLVM IR (toy)"]
    for fn in fns:
        try:
            lines.append(gen_fn(fn))
        except SystemExit as e:
            # skip unsupported fns
            continue
    with open(out,"w",encoding="utf-8") as outf:
        outf.write("\n\n".join(lines)+"\n")
    print("[fuse-llvm-toy] wrote", out)

if __name__=="__main__":
    main()
