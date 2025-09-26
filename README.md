# FUSE — The Composable “Best‑of” Programming Language
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-prototype-blue.svg)](#roadmap)
[![Docs](https://img.shields.io/badge/docs-online-informational.svg)](#documentation)

> **TL;DR** FUSE lets you pick the *right* trade‑off **per module** (ownership, GC regions, or unsafe; channels or actors; pure or effectful) and still compile to fast native code (LLVM) or sandboxed WebAssembly — with first‑class interop (C ABI, Python/Node).

---

## Table of Contents
- [Motivation](#motivation)
- [Core Idea](#core-idea)
- [Quick Start](#quick-start)
- [Hello, FUSE](#hello-fuse)
- [Composition Rules (FCR‑1.0)](#composition-rules-fcr-10)
- [Feature Matrix](#feature-matrix)
- [Architecture](#architecture)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [License](#license)

---

## Motivation
One language can't have *only* advantages. FUSE makes the big trade‑offs **explicit and selectable** — so systems code can be Rust‑tight while app code enjoys GC convenience, and everything composes safely.

## Core Idea
FUSE is a small, eager, expression‑oriented core language. Power is added via **policies** and **effects**:
- **Memory policy:** `borrow` (ownership/borrowing), `gc` (region GC), or `unsafe` (explicit).
- **Effects:** `!IO`, `!Async`, `!Time`, `!FFI`, `!Unsafe` — carried in types.
- **Concurrency:** structured `async/await`, with **channels** *and* **actors**.
- **Macros & DSLs:** hygienic, typed macros + compile‑time evaluation.
- **Interop:** C ABI, Python/Node bridges. Targets: **LLVM** and **Wasm**.

---

## Quick Start
```bash
# Run the toy interpreter (tiny subset of the language)
python prototype/fuse_toy.py examples/tour.fuse
```

<details>
<summary><strong>What the toy subset includes</strong></summary>

- Expressions everywhere; `let`, `fn`, calls, tuples.
- `if { } else { }`, `match` with integers & wildcard.
- Builtins: `print`, `len`.
- No static types or ownership yet — those are specified in docs for the full compiler.
</details>

---

## Hello, FUSE
```fuse
// Algebraic data type
type Result[T, E] = Ok(T) | Err(E)

// Borrowed slice in hot path; explicit IO effect
borrow fn sum(xs: &[i64]) -> i64 { /* ... */ }

// Ergonomic GC region for complex graphs (config parser)
gc fn parse_conf(s: Str) -> Map[Str, Str] { /* ... */ }

// Async + channels
async fn fetch_text(url: Str) -> !Async !IO Result[Str, NetErr] { /* ... */ }
let (tx, rx) = channel[Str](capacity = 1024);
```

---

## Composition Rules (FCR‑1.0)
> Full text: see **[docs/RULES.md](docs/RULES.md)**

1. **Module Policy Boundary.** Every module declares a **memory policy** (`borrow` | `gc` | `unsafe`) and **effect budget** (set of allowed effects). The compiler enforces boundaries and inserts policy bridges at call sites.
2. **Effect Algebra.** Functions carry an effect set; calling composes by **set union**; `try/await` and `handle` delimit and reduce effects.
3. **Interop Safety.** FFI functions are marked `!FFI` and typed with capability‑aware buffers; ownership cannot cross FFI without explicit transfer wrappers.
4. **Concurrency Coherence.** Structured scopes own tasks; actors and channels interoperate via adapters; data crossing threads must implement `Send`/`Share` traits.
5. **Macro Hygiene & Phases.** Macros expand in a typed AST, are hygienic by default, and run in `comptime` with no ambient effects.
6. **Type Coherence & Orphans.** Trait implementations obey coherence (no orphan impls without a local type), avoiding ambiguity across packages.
7. **Errors & Cleanup.** Prefer `Result` + `?`; `defer` ensures cleanup; panics are confined to `!Unsafe` or explicitly annotated boundaries.
8. **Packages & SemVer.** Public APIs are typed; effect and policy changes are semver‑significant. Reproducible builds via lockfiles.
9. **Wasm & Sandboxing.** Wasm targets default to `gc` and disallow `!Unsafe` unless explicitly whitelisted.

---

## Feature Matrix
See **[docs/LANGUAGE_MATRIX.md](docs/LANGUAGE_MATRIX.md)** for a detailed table of which languages inspired each feature.

| Domain                  | FUSE Choice                                       | Borrowed From (examples)          |
|-------------------------|----------------------------------------------------|-----------------------------------|
| Memory                  | Ownership + GC regions + Unsafe (opt‑in)          | Rust, Swift ARC, Go, C            |
| Types                   | ADTs, pattern matching, traits/typeclasses, generics | Haskell/OCaml, Rust, Scala        |
| Concurrency             | Structured async, channels, actors                | Kotlin/Swift/C#, Go, Erlang/Elixir|
| Effects                 | Type‑carried effect sets                           | Koka, Eff, Scala ZIO (in spirit)  |
| Macros/DSLs             | Hygienic typed macros + comptime                  | Racket, Zig, D                    |
| Interop                 | C ABI, Python/Node bridges, Wasm/LLVM backends     | C, Python/CFFI, N-API, LLVM, Wasm |
| Tooling                 | LSP, fmt, test, fuzz, docgen                      | Rust (Cargo), Go (tooling)        |

---

## Architecture
```mermaid
flowchart LR
    A[Source .fuse] --> B[Parser]
    B --> C[Typed AST]
    C --> D[Policy & Effect Checks<br/>Ownership / Lifetimes]
    D --> E[Mid‑level IR]
    E --> F1[LLVM Codegen<br/>(Native)]
    E --> F2[Wasm Codegen<br/>(Sandboxed)]
    C --> G[Macro Expander (Hygienic, Typed)]
    C --> H[FFI Stubs (C ABI, Python/Node)]
```

---

## FAQ
**Q: Can FUSE have only advantages?**  
No. Conflicting defaults exist (e.g., GC vs. ownership). FUSE makes them **explicit**, composable choices.

**Q: Is this production‑ready?**  
No — this repo includes a runnable toy subset and detailed specs for the full compiler.

---

## Roadmap
- [ ] Static type checker (ADTs, generics, traits)
- [ ] Borrow checker & lifetime inference
- [ ] Async runtime + channels + actors
- [ ] Macro system + typed DSL demo
- [ ] LLVM & Wasm backends
- [ ] FFI (C ABI) + Python/Node bindings

---

## Documentation
- **Composition Rules:** [`docs/RULES.md`](docs/RULES.md)  
- **Language Inspirations & Feature Matrix:** [`docs/LANGUAGE_MATRIX.md`](docs/LANGUAGE_MATRIX.md)  
- **Toy Subset Usage:** [`README.md`](README.md#quick-start) and examples in `examples/`

---

## License
MIT
