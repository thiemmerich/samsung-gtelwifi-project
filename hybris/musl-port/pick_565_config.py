#!/usr/bin/env python3
# Enumerate all EGLConfigs the Mali blob offers, print their R/G/B/A/buffer sizes, and
# select the first true RGB565 one (B==5, A==0, buffer<=16) so Mali renders 16bpp to match
# the sprdfb panel. Replaces the fixed eglChooseConfig(&ecfg,1) selection.
import sys
p = "/home/user/libhybris-musl/hybris/tests/test_glesv2.cpp"
s = open(p).read()

if "ENUM-CFG" in s:
    print("already patched"); sys.exit(0)

anchor = "\teglChooseConfig((EGLDisplay) display, attr, &ecfg, 1, &num_config);\n"
assert anchor in s, "eglChooseConfig anchor not found"

block = anchor + r'''	{
		EGLConfig cfgs[64]; EGLint total = 0;
		eglGetConfigs(display, cfgs, 64, &total);
		fprintf(stderr, "ENUM-CFG total=%d\n", total);
		int picked = -1;
		for (int ci = 0; ci < total; ci++) {
			EGLint r,g,b,a,bs,rt;
			eglGetConfigAttrib(display, cfgs[ci], EGL_RED_SIZE, &r);
			eglGetConfigAttrib(display, cfgs[ci], EGL_GREEN_SIZE, &g);
			eglGetConfigAttrib(display, cfgs[ci], EGL_BLUE_SIZE, &b);
			eglGetConfigAttrib(display, cfgs[ci], EGL_ALPHA_SIZE, &a);
			eglGetConfigAttrib(display, cfgs[ci], EGL_BUFFER_SIZE, &bs);
			eglGetConfigAttrib(display, cfgs[ci], EGL_RENDERABLE_TYPE, &rt);
			fprintf(stderr, "ENUM-CFG [%2d] R%d G%d B%d A%d buf%d rt0x%x\n", ci,r,g,b,a,bs,rt);
			if (picked < 0 && r==5 && g==6 && b==5 && a==0 && (rt & EGL_OPENGL_ES2_BIT)) {
				picked = ci; ecfg = cfgs[ci];
			}
		}
		fprintf(stderr, "ENUM-CFG picked index %d\n", picked);
		fflush(stderr);
	}
'''
s = s.replace(anchor, block, 1)
open(p, "w").write(s)
print("enumeration + 565 pick injected")
