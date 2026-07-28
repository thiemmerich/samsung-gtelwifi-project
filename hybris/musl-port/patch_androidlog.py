#!/usr/bin/env python3
# Add __android_log_* hooks to libhybris hooks.c so the Mali blobs' logging calls route to
# our stderr instead of falling through to bionic liblog (which crashes on bionic TLS).
import sys
p = "/home/user/libhybris-musl/hybris/common/hooks.c"
s = open(p).read()
if "_hybris_hook___android_log_print" in s:
    print("already patched"); sys.exit(0)

defs = r'''
static int _hybris_hook___android_log_vprint(int prio, const char *tag, const char *fmt, va_list ap)
{
    fprintf(stderr, "[droid:%s] ", tag ? tag : "-");
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    return 1;
}
static int _hybris_hook___android_log_print(int prio, const char *tag, const char *fmt, ...)
{
    va_list ap; int r;
    va_start(ap, fmt);
    r = _hybris_hook___android_log_vprint(prio, tag, fmt, ap);
    va_end(ap);
    return r;
}
static int _hybris_hook___android_log_write(int prio, const char *tag, const char *text)
{
    fprintf(stderr, "[droid:%s] %s\n", tag ? tag : "-", text ? text : "");
    return 1;
}
static void _hybris_hook___android_log_assert(const char *cond, const char *tag, const char *fmt, ...)
{
    fprintf(stderr, "[droid:ASSERT:%s] %s\n", tag ? tag : "-", cond ? cond : "");
    abort();
}
'''

md = "static struct _hook hooks_properties[] = {"
assert md in s, "def marker not found"
s = s.replace(md, defs + "\n" + md, 1)

mt = "    HOOK_DIRECT_NO_DEBUG(strerror_r),"
assert mt in s, "table marker not found"
entries = mt + "\n" \
    "    HOOK_TO(__android_log_print, _hybris_hook___android_log_print),\n" \
    "    HOOK_TO(__android_log_vprint, _hybris_hook___android_log_vprint),\n" \
    "    HOOK_TO(__android_log_write, _hybris_hook___android_log_write),\n" \
    "    HOOK_TO(__android_log_assert, _hybris_hook___android_log_assert),"
s = s.replace(mt, entries, 1)

open(p, "w").write(s)
print("patched OK")
