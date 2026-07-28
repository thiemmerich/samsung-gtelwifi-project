#!/usr/bin/env python3
# Add hooks for fortify (_chk) functions + C++ new/delete that the Mali/gralloc blobs import
# but libhybris doesn't hook. Unhooked, they fall through to bionic libc; bionic's fortify path
# calls __vfprintf on a (spurious) check failure -> bionic FILE/pthread lock -> crash on bionic TLS.
# Route them to plain musl equivalents (no fortify machinery, shared musl heap).
import sys
p = "/home/user/libhybris-musl/hybris/common/hooks.c"
s = open(p).read()
if "_hybris_hook___strlen_chk" in s:
    print("already patched"); sys.exit(0)

defs = r'''
static size_t _hybris_hook___strlen_chk(const char *s, size_t s_len) { (void)s_len; return strlen(s); }
static void  *_hybris_hook___memcpy_chk(void *d, const void *s, size_t n, size_t dl) { (void)dl; return memcpy(d, s, n); }
static void  *_hybris_hook___memmove_chk(void *d, const void *s, size_t n, size_t dl) { (void)dl; return memmove(d, s, n); }
static void  *_hybris_hook___memset_chk(void *d, int c, size_t n, size_t dl) { (void)dl; return memset(d, c, n); }
static char  *_hybris_hook___strchr_chk(const char *s, int c, size_t sl) { (void)sl; return strchr(s, c); }
static char  *_hybris_hook___strcpy_chk(char *d, const char *s, size_t dl) { (void)dl; return strcpy(d, s); }
static char  *_hybris_hook___strcat_chk(char *d, const char *s, size_t dl) { (void)dl; return strcat(d, s); }
static void   _hybris_hook___stack_chk_fail(void) { fprintf(stderr, "hybris: __stack_chk_fail (bionic canary; ignored)\n"); }
static void  *_hybris_hook__Znwj(size_t n) { return malloc(n); }
static void  *_hybris_hook__Znaj(size_t n) { return malloc(n); }
static void   _hybris_hook__ZdlPv(void *ptr) { free(ptr); }
static void   _hybris_hook__ZdaPv(void *ptr) { free(ptr); }
'''

md = "static struct _hook hooks_properties[] = {"
assert md in s, "def marker not found"
s = s.replace(md, defs + "\n" + md, 1)

mt = "    HOOK_TO(__android_log_print, _hybris_hook___android_log_print),"
assert mt in s, "table marker (android_log) not found"
entries = mt + "\n" \
    "    HOOK_TO(__strlen_chk, _hybris_hook___strlen_chk),\n" \
    "    HOOK_TO(__memcpy_chk, _hybris_hook___memcpy_chk),\n" \
    "    HOOK_TO(__memmove_chk, _hybris_hook___memmove_chk),\n" \
    "    HOOK_TO(__memset_chk, _hybris_hook___memset_chk),\n" \
    "    HOOK_TO(__strchr_chk, _hybris_hook___strchr_chk),\n" \
    "    HOOK_TO(__strcpy_chk, _hybris_hook___strcpy_chk),\n" \
    "    HOOK_TO(__strcat_chk, _hybris_hook___strcat_chk),\n" \
    "    HOOK_TO(__stack_chk_fail, _hybris_hook___stack_chk_fail),\n" \
    "    HOOK_TO(_Znwj, _hybris_hook__Znwj),\n" \
    "    HOOK_TO(_Znaj, _hybris_hook__Znaj),\n" \
    "    HOOK_TO(_ZdlPv, _hybris_hook__ZdlPv),\n" \
    "    HOOK_TO(_ZdaPv, _hybris_hook__ZdaPv),"
s = s.replace(mt, entries, 1)

open(p, "w").write(s)
print("patched OK")
