#!/usr/bin/env python3
# Binary-patch bionic /system/lib/libc.so: turn the mutex entry points into `return 0` stubs
# (ARM: mov r0,#0 ; bx lr). Bionic's internal pthread-mutex calls crash on our musl main thread
# (they read TPIDRURO for TLS, which musl owns -> null pthread_internal_t -> deref crash). The
# mutexes protect essentially single-threaded init here, so no-op'ing them is a safe bring-up hack.
import sys, shutil, os
LIBC = "/system/lib/libc.so"
BAK  = "/system/lib/libc.so.orig"
STUB = bytes([0x00,0x00,0xa0,0xe3, 0x1e,0xff,0x2f,0xe1])  # ARM: mov r0,#0 ; bx lr
# offsets from readelf (ARM entries)
OFF = {
    "pthread_mutex_init":     0xe6d0,
    "pthread_mutex_lock":     0xe8f4,
    "pthread_mutex_unlock":   0xe9f8,
    "pthread_mutex_trylock":  0xeae4,
    "pthread_mutex_destroy":  0xed80,
}
if not os.path.exists(BAK):
    shutil.copy2(LIBC, BAK); print("backed up ->", BAK)
data = bytearray(open(LIBC,"rb").read())
for name,off in OFF.items():
    data[off:off+8] = STUB
    print(f"stubbed {name} @ {hex(off)}")
open(LIBC,"wb").write(data)
print("patched", LIBC)
