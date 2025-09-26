# Language Inspirations & Feature Matrix

This document explains **which languages inspired FUSE** and **which features were adopted** (sometimes adapted).

| Area | FUSE Feature | Inspiration | Notes |
|------|--------------|-------------|-------|
| Memory | Ownership/borrowing | **Rust** | Affine types, lifetimes, move semantics |
| Memory | GC regions | **Swift** (ARC), **Go** | Region‑scoped GC for convenience heavy code |
| Memory | Unsafe escape hatch | **C/C++**, **Rust** `unsafe` | Explicit, audited blocks |
| Types | ADTs + pattern matching | **Haskell/OCaml**, **Swift** | Exhaustive matching, sum & product types |
| Types | Traits/typeclasses | **Haskell** (typeclasses), **Rust** (traits) | Associated types, where‑clauses |
| Types | Generics (monomorphized) | **C++** templates, **Rust** | Zero‑cost specialization |
| Records | Row polymorphism | **TypeScript**, **OCaml** (polymorphic variants) | Flexible record evolution |
| Typing | Gradual/dynamic edge | **TypeScript** `any`, **Python** interop | Dynamic FFI boundary and scripting |
| Concurrency | Structured `async/await` | **Kotlin/Swift/C#** | Cancellation with scopes |
| Concurrency | Channels (CSP) | **Go** | Bounded MPSC by default |
| Concurrency | Actors | **Erlang/Elixir** | Supervision trees |
| Effects | Type‑carried effect sets | **Koka**, **Eff**, **Scala ZIO** (in spirit) | Set‑based composition |
| Macros | Hygienic, typed macros | **Racket** | Safe DSL construction |
| Comptime | Compile‑time eval | **Zig**, **D** (CTFE) | Deterministic & sandboxed |
| Interop | C ABI first‑class | **C** | Ubiquitous FFI target |
| Interop | Python/Node bridges | **Python CFFI**, **N‑API** | Tooling planned in `fuse bindgen` |
| Backends | LLVM, WebAssembly | **LLVM**, **Wasm** | Native speed + sandboxed deployment |
| Tooling | LSP/test/fmt/fuzz | **Rust (Cargo)**, **Go** | Developer experience from day 1 |

> “Inspired by” does **not** mean source compatibility; it means design ideas shaped FUSE. See `docs/RULES.md` for how features are made to compose.
