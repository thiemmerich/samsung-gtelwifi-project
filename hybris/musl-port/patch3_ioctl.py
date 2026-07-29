#!/usr/bin/env python3
# sprdfb is really 16bpp RGB565 (stride 1600), but gralloc.sc8830 forces 32bpp via
# FBIOPUT_VSCREENINFO -> GPU renders 32bpp into a 16bpp scanout -> garbled/half-screen.
# Hook ioctl(): intercept FBIOPUT_VSCREENINFO and pin bpp=16 RGB565, so gralloc reads back
# 16bpp, allocates an RGB565 surface, and the Mali render matches the panel. No kernel rebuild.
import sys
p = "/home/user/libhybris-musl/hybris/common/hooks.c"
s = open(p).read()
if "_hybris_hook_ioctl_fb" in s:
    print("already patched"); sys.exit(0)

# ensure ioctl + fb headers are included (anchor on config.h, always present)
if "<linux/fb.h>" not in s:
    s = s.replace('#include "config.h"',
                  '#include "config.h"\n#include <sys/ioctl.h>\n#include <linux/fb.h>', 1)

defs = r'''
/* Pin the framebuffer to 16bpp RGB565: sprdfb hardware is RGB565 but gralloc forces 32bpp. */
static int _hybris_hook_ioctl_fb(int fd, int request, void *arg)
{
    if ((unsigned int)request == FBIOPUT_VSCREENINFO && arg) {
        struct fb_var_screeninfo *v = (struct fb_var_screeninfo *)arg;
        v->bits_per_pixel = 16;
        v->red.offset   = 11; v->red.length   = 5;
        v->green.offset = 5;  v->green.length = 6;
        v->blue.offset  = 0;  v->blue.length  = 5;
        v->transp.offset = 0; v->transp.length = 0;
    }
    return ioctl(fd, request, arg);
}
'''
md = "static struct _hook hooks_properties[] = {"
assert md in s, "def marker not found"
s = s.replace(md, defs + "\n" + md, 1)

mt = "    HOOK_TO(__android_log_print, _hybris_hook___android_log_print),"
assert mt in s, "table marker not found"
s = s.replace(mt, mt + "\n    HOOK_TO(ioctl, _hybris_hook_ioctl_fb),", 1)

open(p, "w").write(s)
print("patched: ioctl hook pins fb to 16bpp RGB565")
