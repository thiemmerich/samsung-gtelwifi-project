/* Classic Android sw_sync UAPI (linux/sw_sync.h), removed from modern linux-headers.
   Needed to build libhybris libsync for Android <=7 blobs. Install as /usr/include/linux/sw_sync.h */
#ifndef _LINUX_SW_SYNC_H
#define _LINUX_SW_SYNC_H
#include <linux/types.h>
#include <linux/ioctl.h>
struct sw_sync_create_fence_data { __u32 value; char name[32]; __s32 fence; };
#define SW_SYNC_IOC_MAGIC (char)0x57
#define SW_SYNC_IOC_CREATE_FENCE _IOWR(SW_SYNC_IOC_MAGIC, 0, struct sw_sync_create_fence_data)
#define SW_SYNC_IOC_INC _IOW(SW_SYNC_IOC_MAGIC, 1, __u32)
#endif
