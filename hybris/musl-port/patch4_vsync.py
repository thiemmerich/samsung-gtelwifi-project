#!/usr/bin/env python3
# Mali renders directly into the single scanout buffer (our HW_FB-linear clean-triangle fix),
# so the panel shows frames mid-draw -> tearing. sprdfb blocks fbdev pan (EINVAL on yres_virtual)
# so we can't page-flip, but it DOES honour FBIO_WAITFORVSYNC. Gate each present on vsync: wait
# for the blanking interval right before the gralloc fb post so a frame settles before the next
# draw begins. No kernel rebuild.
import sys
p = "/home/user/libhybris-musl/hybris/egl/platforms/fbdev/fbdev_window.cpp"
s = open(p).read()
if "_hybris_vsync_fd" in s:
    print("already patched"); sys.exit(0)

# headers
for h in ("<fcntl.h>", "<sys/ioctl.h>", "<linux/fb.h>", "<stdlib.h>"):
    if h not in s:
        s = s.replace('#include "fbdev_window.h"',
                      '#include "fbdev_window.h"\n#include %s' % h, 1)

# lazy-opened fb fd + vsync helper, inserted before queueBuffer
helper = r'''
/* vsync gate: sprdfb honours FBIO_WAITFORVSYNC even though it refuses fbdev panning. */
#ifndef FBIO_WAITFORVSYNC
#define FBIO_WAITFORVSYNC _IOW('F', 0x20, unsigned int)
#endif
static int _hybris_vsync_fd = -2;
static void _hybris_wait_vsync(void)
{
    if (_hybris_vsync_fd == -2)
        _hybris_vsync_fd = open("/dev/fb0", O_RDWR | O_CLOEXEC);
    /* HYBRIS_FB_NOVSYNC=1 skips the gate (faster, but tears) — used for benchmarking. */
    if (_hybris_vsync_fd >= 0 && !getenv("HYBRIS_FB_NOVSYNC")) {
        unsigned int crtc = 0;
        ioctl(_hybris_vsync_fd, FBIO_WAITFORVSYNC, &crtc);
    }
}
'''
marker = "int FbDevNativeWindow::queueBuffer(BaseNativeWindowBuffer* buffer, int fenceFd)"
assert marker in s, "queueBuffer marker not found"
s = s.replace(marker, helper + "\n" + marker, 1)

# wait for vsync immediately before the gralloc post
post = "    int rv = hybris_gralloc_fbdev_post(fbnb->handle);"
assert post in s, "post call marker not found"
s = s.replace(post, "    _hybris_wait_vsync();\n" + post, 1)

open(p, "w").write(s)
print("patched: FBIO_WAITFORVSYNC gate before fb post")
