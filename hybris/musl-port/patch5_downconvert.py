#!/usr/bin/env python3
# THE COLOR FIX. The sprdfb panel path is hardwired 16bpp RGB565 (line_length locked 1600) but the
# Mali fbdev blob always renders 32bpp RGBA8888, and the proprietary fb_post does a dumb memcpy with
# no format conversion -> green shows gold, geometry half-width. Fix: render into a linear, CPU-
# readable offscreen RGBA8888 buffer, then do the 8888->565 downconvert ourselves in queueBuffer,
# packing straight into an mmap of /dev/fb0. Full control, correct color, full screen.
import sys
p = "/home/user/libhybris-musl/hybris/egl/platforms/fbdev/fbdev_window.cpp"
s = open(p).read()
if "_hybris_downconvert_to_fb" in s:
    print("already patched"); sys.exit(0)

# 1) need mmap
if "<sys/mman.h>" not in s:
    s = s.replace("#include <fcntl.h>", "#include <fcntl.h>\n#include <sys/mman.h>", 1)

# 2) the downconvert helper, inserted just before queueBuffer
helper = r'''
/* 8888 (Mali) -> 565 (sprdfb panel) software downconvert into an mmap of /dev/fb0. */
static int   _hybris_fbc_fd     = -2;
static void *_hybris_fbc_map    = 0;
static int   _hybris_fbc_stride = 0;   /* fb0 bytes/line (16bpp) */
static int   _hybris_fbc_h      = 0;

static void _hybris_downconvert_to_fb(buffer_handle_t handle, int w, int h, int src_stride_px)
{
    if (_hybris_fbc_fd == -2) {
        _hybris_fbc_fd = open("/dev/fb0", O_RDWR | O_CLOEXEC);
        if (_hybris_fbc_fd >= 0) {
            struct fb_var_screeninfo v; struct fb_fix_screeninfo f;
            ioctl(_hybris_fbc_fd, FBIOGET_VSCREENINFO, &v);
            ioctl(_hybris_fbc_fd, FBIOGET_FSCREENINFO, &f);
            _hybris_fbc_stride = f.line_length;
            _hybris_fbc_h = v.yres;
            _hybris_fbc_map = mmap(0, (size_t)f.line_length * v.yres,
                                   PROT_READ | PROT_WRITE, MAP_SHARED, _hybris_fbc_fd, 0);
            if (_hybris_fbc_map == MAP_FAILED) _hybris_fbc_map = 0;
        }
    }
    if (!_hybris_fbc_map) return;
    void *src = 0;
    if (hybris_gralloc_lock(handle, GRALLOC_USAGE_SW_READ_OFTEN, 0, 0, w, h, &src) != 0 || !src)
        return;
    int rows = (h < _hybris_fbc_h) ? h : _hybris_fbc_h;
    int cols = w;
    if (cols > _hybris_fbc_stride / 2) cols = _hybris_fbc_stride / 2;
    for (int y = 0; y < rows; y++) {
        /* read each pixel as one 32-bit word (RGBA8888 LE: R=b0 G=b1 B=b2) */
        const unsigned int *sw = (const unsigned int *)((const unsigned char *)src
                                                        + (size_t)y * src_stride_px * 4);
        unsigned short *dp = (unsigned short *)((unsigned char *)_hybris_fbc_map
                                                + (size_t)y * _hybris_fbc_stride);
        for (int x = 0; x < cols; x++) {
            unsigned int px = sw[x];
            dp[x] = (unsigned short)(((px & 0xF8) << 8) | ((px & 0xFC00) >> 5) | ((px & 0xF80000) >> 19));
        }
    }
    hybris_gralloc_unlock(handle);
}
'''
marker = "int FbDevNativeWindow::queueBuffer(BaseNativeWindowBuffer* buffer, int fenceFd)"
assert marker in s, "queueBuffer marker missing"
s = s.replace(marker, helper + "\n" + marker, 1)

# 3) replace the dumb fb_post with our downconvert (keep the vsync wait that precedes it)
post = "    int rv = hybris_gralloc_fbdev_post(fbnb->handle);"
assert post in s, "fb_post call missing"
s = s.replace(post,
    "    _hybris_downconvert_to_fb(fbnb->handle, hybris_gralloc_fbdev_width(),\n"
    "                              hybris_gralloc_fbdev_height(), fbnb->stride);\n"
    "    int rv = 0;", 1)

# 4) render target: linear, CPU-readable, 8888 offscreen buffer (NOT HW_FB)
off_usage = "(GRALLOC_USAGE_HW_RENDER | GRALLOC_USAGE_HW_TEXTURE | GRALLOC_USAGE_SW_READ_OFTEN)"
s = s.replace(
    "hybris_gralloc_fbdev_height(), HAL_PIXEL_FORMAT_RGB_565, GRALLOC_USAGE_HW_FB);",
    "hybris_gralloc_fbdev_height(), HAL_PIXEL_FORMAT_RGBA_8888, " + off_usage + ");", 1)
# keep getUsage()/consumer usage consistent
s = s.replace("    m_usage = GRALLOC_USAGE_HW_FB;",
              "    m_usage = " + off_usage + ";", 1)

open(p, "w").write(s)
print("downconvert 8888->565 installed; render target -> linear 8888 offscreen")
