/* Classic Android sync-framework UAPI (linux/sync.h), removed from modern linux-headers.
   Needed to build libhybris libsync for Android <=7 blobs. Install as /usr/include/linux/sync.h */
#ifndef _LINUX_SYNC_H
#define _LINUX_SYNC_H
#include <linux/types.h>
#include <linux/ioctl.h>
struct sync_merge_data { __s32 fd2; char name[32]; __s32 fence; };
struct sync_pt_info { __u32 len; char obj_name[32]; char driver_name[32]; __s32 status; __u64 timestamp_ns; __u8 driver_data[0]; };
struct sync_fence_info_data { __u32 len; char name[32]; __s32 status; __u8 pt_info[0]; };
#define SYNC_IOC_MAGIC (char)0x3e
#define SYNC_IOC_WAIT _IOW(SYNC_IOC_MAGIC, 0, __s32)
#define SYNC_IOC_MERGE _IOWR(SYNC_IOC_MAGIC, 1, struct sync_merge_data)
#define SYNC_IOC_FENCE_INFO _IOWR(SYNC_IOC_MAGIC, 2, struct sync_fence_info_data)
#endif
