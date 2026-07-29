# Bionic TLS Bridge — Implementation Plan (the last piece of the GPU-desktop dream)

**Status:** DEFERRED. The stub (`stub_pthread.py`) keeps single-threaded GPU working (~23 fps);
this bridge is what unlocks *multithreaded* GL → a libhybris-EGL Wayland compositor → a fully
GPU-composited desktop. Pick this up when ready to chase Path B again.

## The problem (diagnosed — commits c5668bc, b66d1ca)
- Removing the stub crashes at bionic `libc.so +0xe7c4`: `ldr r3,[r0,#0x20]` with **r0 = 0** — a
  null **bionic thread pointer** deref, inside the `pthread_mutex_init`(0xe6d0)/`_lock`(0xe8f4) region.
- Reached through MANY intra-libc frames (gdb stack is all bionic-libc addresses) → **bionic libc
  needs a valid thread pointer of its own**; there's no single external caller to hook.
- Root cause: our port **never sets up bionic TLS** (no `__set_tls`/`TLS_SLOT` in the tree) and the
  bundled linker (`common/jb/linker.c:1607`) only skips libc.so's *constructors* (which would init it)
  — yet still **loads** bionic `libc.so` and binds some symbols to it.

## Ruled out
- **Blanket-hook remaining libc/libm to musl** (`patch6_libc_hooks.py`, kept local, NOT committed):
  moved the crash past the pthread deref (good signal) but caused a `pc=0` null-call at startup and
  regressed even the stubbed baseline. Too blunt. Do NOT just re-add patch6.

## Two candidate approaches (investigate 2A first — likely the clean answer)

### 2A — Don't load bionic libc.so at all (the upstream libhybris model) ← START HERE
Mature libhybris never loads Android's `libc.so`/`libm.so`/`libdl.so`; it marks them "already
provided" and resolves ALL their symbols via the hook table (→ host libc/musl). If bionic libc never
loads, its TLS-dependent internals never run → no bridge needed.
- **Investigate:** does `common/jb/linker.c` have an `is_system_library`/"provided libs" list (upstream
  has one)? The current code *loads* libc.so and only skips its ctors. Find where DT_NEEDED libs are
  loaded (`find_library`/`load_library`) and add a short-circuit: for `libc.so`,`libm.so`,`libdl.so`,
  `libstdc++.so`, return a synthetic soinfo whose symbols resolve purely through `_get_hooked_symbol`
  (like the existing `libdl_info` at linker.c:91).
- **Then:** ensure 100% hook coverage of the libc/libm symbols the Android libs import (blob needs
  118; also audit `gralloc.sc8830.so`, `hwcomposer.sc8830.so`). Union of their UND symbols must all be
  hooked. Use `readelf --dyn-syms` diffs like `tls-bridge-recon/`.
- **Watch out:** `libGLES_trace.so` started loading during the patch6 attempt and is implicated in the
  `pc=0` crash — check why the Android EGL loader pulls it in (property `debug.egl.trace`?) and
  suppress it. `fstat`/LFS and macro'd symbols need real wrapper funcs, not bare `HOOK_DIRECT_NO_DEBUG`.

### 2B — Actually set up minimal bionic per-thread TLS (fallback if 2A is infeasible)
Give each thread that runs bionic code a valid bionic TLS block.
- Bionic ARM TLS (KitKat, `bionic/libc/private/bionic_tls.h`): thread register `TPIDRURO` (read via
  `__get_tls()`) → array of `void*` slots: `SELF=0, THREAD_ID=1, ERRNO=2, OPENGL_API=3, OPENGL=4,
  STACK_GUARD=5, DLERROR=6, BIONIC_PREINIT=7`. `pthread_self()` returns `__get_tls()[THREAD_ID]` →
  `pthread_internal_t*`; the crash reads that +0x20.
- **The hard part:** musl ALSO uses `TPIDRURO` for its TCB → can't naively overwrite. Options: a
  per-thread bionic block whose layout satisfies bionic's positive slot reads while musl's TP still
  points where musl expects; or swap `TPIDRURO` around bionic-call boundaries (heavy). Study how
  upstream libhybris reconciles this (its linker `__set_tls` + `pthread_create` wrapper).
- Populate at least SELF/THREAD_ID (→ a minimal fake `pthread_internal_t` with the fields bionic reads),
  ERRNO, STACK_GUARD. Blob-created threads already become musl threads via
  `_hybris_hook_pthread_create` — extend that wrapper to also install the bionic block.

## Reference
- Upstream libhybris: `hybris/common/*/linker.c` (system-lib faking) + its pthread/TLS handling.
- Our recon artifacts: `hybris/musl-port/tls-bridge-recon/` (UND diffs, worklist).
- Repro: drop stub (`sudo cp /system/lib/libc.so.orig /system/lib/libc.so`), run `gpu_cube` with
  `NOCRASH=1` under `gdb -x /tmp/g.gdb`; restore with `sudo python3 stub_pthread.py`.

## Test plan (definition of done)
1. Drop the stub; `gpu_cube` still renders (single-threaded regression pass).
2. A NEW multithreaded GLES test (render from a worker thread with its own EGL context) runs clean.
3. No bionic-libc code executes (2A) or bionic TLS reads resolve (2B) — verify via gdb.
4. Then: minimal libhybris-EGL Wayland compositor bring-up.
