#!/usr/bin/env python3
# The Mali fbdev blob always renders 32-bit RGBA8888; forcing the panel to 16bpp RGB565 made the
# DISPC misread each 32-bit pixel as two 565 pixels (green->gold, half-width). sprdfb's native
# DISPC input is ABGR888 and it derives line_length=width*bpp/8, so pin the fb to 32bpp ABGR8888
# instead: A@24 B@16 G@8 R@0, matching Mali's output and the hardware's native format.
import re
p = "/home/user/libhybris-musl/hybris/common/hooks.c"
s = open(p).read()

old = """        struct fb_var_screeninfo *v = (struct fb_var_screeninfo *)arg;
        v->bits_per_pixel = 16;
        v->red.offset   = 11; v->red.length   = 5;
        v->green.offset = 5;  v->green.length = 6;
        v->blue.offset  = 0;  v->blue.length  = 5;
        v->transp.offset = 0; v->transp.length = 0;"""
new = """        struct fb_var_screeninfo *v = (struct fb_var_screeninfo *)arg;
        v->bits_per_pixel = 32;
        v->red.offset    = 0;  v->red.length    = 8;
        v->green.offset  = 8;  v->green.length  = 8;
        v->blue.offset   = 16; v->blue.length   = 8;
        v->transp.offset = 24; v->transp.length = 8;"""

if "v->bits_per_pixel = 32;" in s:
    print("already 32bpp")
elif old in s:
    s = s.replace(old, new, 1)
    open(p, "w").write(s)
    print("ioctl pin -> 32bpp ABGR8888 (A24 B16 G8 R0)")
else:
    print("MARKER NOT FOUND — inspect hooks.c manually")
