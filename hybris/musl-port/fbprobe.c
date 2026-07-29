/* Probe what pixel formats sprdfb actually supports (does line_length/stride follow bpp?). */
#include <stdio.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <sys/ioctl.h>
int main(void){
    int fd = open("/dev/fb0", O_RDWR);
    if (fd < 0){ perror("open"); return 1; }
    struct fb_var_screeninfo v; struct fb_fix_screeninfo f;
    ioctl(fd, FBIOGET_VSCREENINFO, &v); ioctl(fd, FBIOGET_FSCREENINFO, &f);
    printf("BOOT: %ux%u bpp=%u xvirt=%u yvirt=%u line_length=%u\n",
           v.xres, v.yres, v.bits_per_pixel, v.xres_virtual, v.yres_virtual, f.line_length);

    /* try to force 32bpp RGBA8888 */
    v.bits_per_pixel = 32; v.xres_virtual = v.xres; v.yres_virtual = v.yres;
    v.red.offset=0;  v.red.length=8;
    v.green.offset=8;v.green.length=8;
    v.blue.offset=16;v.blue.length=8;
    v.transp.offset=24; v.transp.length=8;
    int r = ioctl(fd, FBIOPUT_VSCREENINFO, &v);
    ioctl(fd, FBIOGET_VSCREENINFO, &v); ioctl(fd, FBIOGET_FSCREENINFO, &f);
    printf("PUT32 rc=%d -> bpp=%u line_length=%u (want 3200 for real 32bpp)\n",
           r, v.bits_per_pixel, f.line_length);

    /* try 16bpp RGB565 */
    v.bits_per_pixel = 16;
    v.red.offset=11; v.red.length=5;
    v.green.offset=5;v.green.length=6;
    v.blue.offset=0; v.blue.length=5;
    v.transp.offset=0; v.transp.length=0;
    r = ioctl(fd, FBIOPUT_VSCREENINFO, &v);
    ioctl(fd, FBIOGET_VSCREENINFO, &v); ioctl(fd, FBIOGET_FSCREENINFO, &f);
    printf("PUT16 rc=%d -> bpp=%u line_length=%u (want 1600 for real 16bpp)\n",
           r, v.bits_per_pixel, f.line_length);
    return 0;
}
