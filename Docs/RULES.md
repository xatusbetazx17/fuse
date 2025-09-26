# FUSE Composition Rules (FCR‑1.0)

> These rules make feature **combination** predictable and safe across modules, runtimes, and FFI.

## 1. Module Policies
Every module declares:
- **Memory policy:** `borrow` | `gc` | `unsafe`
- **Effect budget:** a set like `{IO, Async, Time, FFI, Unsafe}`

**Rule 1.1 — Boundary:** Calls from caller policy **P** to callee policy **Q** require a **bridge**. Bridges are compiler‑generated shims that adapt ownership & allocation rules.

**Rule 1.2 — Defaults:** If unspecified, policy is `borrow` and effect budget is `{}` (pure).

```fuse
// module math @policy(borrow) @effects({})
// module conf @policy(gc) @effects({IO})
```

## 2. Effect Algebra
- Functions have an **effect set**. Example: `fn read() -> !IO Result[Str, Err]`.
- **Composition:** Calling `f: !A` inside `g: !B` yields `g` with effects `A ∪ B`.
- **Handling:** `handle { ... } catch !IO with ...` can **discharge** effects locally.
- **Async:** `await` is only legal in a `!Async` context.

## 3. Memory Interop
- **Borrow→GC:** Borrowed slices/refs are **viewed** into GC regions with lifetime tied to the call.
- **GC→Borrow:** Only **owned** values cross into `borrow` modules; GC references cannot outlive the callee without copying.
- **Unsafe:** `unsafe` blocks mark regions where invariants are caller‑proven; all effects include `!Unsafe` while inside.

## 4. Concurrency Semantics
- **Structured scopes** own tasks; leaving a scope cancels unfinished children unless joined.
- Crossing threads requires `Send` (move‑only) or `Share` (concurrent read) traits.
- **Channels** are MPSC by default; bounded by capacity; send/recv are `!Async` unless using blocking variants.
- **Actors** process messages serially; supervision trees may restart actors on failure.

## 5. Type System & Coherence
- Parametric generics are **monomorphized**.
- Traits/typeclasses support associated types and where‑clauses.
- **Coherence rule:** An impl must be **local** to either the trait or the type (no orphan impls) to avoid ambiguity.
- **Row polymorphism** for records; **exhaustive** pattern matching enforced.

## 6. Macros & Compile Time
- **Hygienic, typed** macros operate on typed AST; they cannot capture caller bindings unless explicitly spliced.
- `comptime` blocks run with **no ambient side effects** except deterministic IO (e.g., reading constant files with hashes in build graph).
- Macro expansions must **preserve effects** of generated code.

## 7. FFI
- FFI functions are annotated `!FFI` and must use **explicit** ownership annotations (e.g., `borrow *const T`, `take *mut T`).
- Errors map to `Result`; panics/exceptions are caught and translated at boundary.
- Pointers from FFI cannot be stored in GC regions without **pin** wrappers.

## 8. Error Handling & Cleanup
- Primary mechanism: `Result` + `?` propagation.
- `defer` schedules scope‑exit actions; guaranteed to run unless process aborts.
- `panic` is fatal by default and confined to `!Unsafe` unless explicitly allowed.

## 9. Packaging & Versioning
- Public function types include effect sets and are part of **SemVer**. Changing effects or policy is a **breaking** change.
- Builds are reproducible with content‑addressed package store and lockfiles.

## 10. Wasm Sandboxing
- Default Wasm policy is `gc` with `{}` effects; host capabilities are **explicitly provided** as imports.
- `!Unsafe` is disallowed on Wasm unless the embedder opts in.

---

These rules give you a deterministic way to **combine** paradigms without undefined corners.
