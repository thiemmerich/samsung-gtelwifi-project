# fbdev linear-buffer fix (removes the Mali tile grid) — THE CLEAN-TRIANGLE FIX

Mali-400 is tile-based; when gralloc allocates the fb window buffer with HW_RENDER|HW_TEXTURE
(usage 0x602 set by the Mali driver), Mali writes a *tiled* layout → sprdfb scans linearly →
regular black/white grid over solid fills.

Fix in `hybris/egl/platforms/fbdev/fbdev_window.cpp`, `FbDevNativeWindow::reallocateBuffers()`:
force the fb window buffer to a LINEAR scanout allocation (HW_FB only), not Mali's tiled one:

    -   new FbDevNativeWindowBuffer(... hybris_gralloc_fbdev_format(), m_usage|GRALLOC_USAGE_HW_FB);
    +   new FbDevNativeWindowBuffer(... hybris_gralloc_fbdev_format(), GRALLOC_USAGE_HW_FB);

Rebuild eglplatform_fbdev.so AND reinstall to /usr/local/lib/libhybris/ (libhybris loads the
platform from the compiled-in pkglibdir = /usr/local, NOT the build dir). Result: clean,
artifact-free GPU render — crisp full-screen triangles. 🔺
