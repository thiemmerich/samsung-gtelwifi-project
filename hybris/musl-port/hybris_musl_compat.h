#ifndef HYBRIS_MUSL_COMPAT_H
#define HYBRIS_MUSL_COMPAT_H
/* musl >=1.2.4 dropped LFS64 aliases (off_t is already 64-bit). Map *64 -> base,
   and supply the few GNU extensions libhybris hooks that musl lacks. */
#include <sys/types.h>
#include <stdio.h>
#include <wchar.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>
#include <fcntl.h>
typedef off_t off64_t;
typedef off_t loff_t;
#define fopen64 fopen
#define freopen64 freopen
#define tmpfile64 tmpfile
#define fseeko64 fseeko
#define ftello64 ftello
#define fgetpos64 fgetpos
#define fsetpos64 fsetpos
#define mmap64 mmap
#define open64 open
#define openat64 openat
#define creat64 creat
#define lseek64 lseek
#define pread64 pread
#define pwrite64 pwrite
#define readdir64 readdir
#define readdir64_r readdir_r
#define scandir64 scandir
#define scandirat64 scandirat
#define fstat64 fstat
#define stat64 stat
#define lstat64 lstat
#define fstatat64 fstatat
#define ftruncate64 ftruncate
#define truncate64 truncate
#define statfs64 statfs
#define fstatfs64 fstatfs
#define statvfs64 statvfs
#define fstatvfs64 fstatvfs
#define dirent64 dirent
static inline wchar_t *wmempcpy(wchar_t *d, const wchar_t *s, size_t n){ return wmemcpy(d,s,n)+n; }

#include <stdarg.h>
#include <stdlib.h>
/* glibc malloc extensions musl lacks */
static inline void *pvalloc(size_t n){ return valloc(n); }
struct mallinfo { int arena,ordblks,smblks,hblks,hblkhd,usmblks,fsmblks,uordblks,fordblks,keepcost; };
static inline struct mallinfo mallinfo(void){ struct mallinfo m; __builtin_memset(&m,0,sizeof m); return m; }
/* glibc _FORTIFY_SOURCE checked printf variants musl lacks — forward, skip the size check */
static inline int __snprintf_chk(char *s,size_t n,int f,size_t sl,const char *fmt,...){va_list a;int r;va_start(a,fmt);r=vsnprintf(s,n,fmt,a);va_end(a);return r;}
static inline int __vsnprintf_chk(char *s,size_t n,int f,size_t sl,const char *fmt,va_list a){return vsnprintf(s,n,fmt,a);}
static inline int __sprintf_chk(char *s,int f,size_t sl,const char *fmt,...){va_list a;int r;va_start(a,fmt);r=vsnprintf(s,sl?sl:0x7fffffff,fmt,a);va_end(a);return r;}

/* glibc <sys/cdefs.h> decoration macros absent on musl */
#ifndef __THROW
#define __THROW
#endif
#ifndef __THROWNL
#define __THROWNL
#endif
#ifndef __NTH
#define __NTH(fct) fct
#endif
#ifndef __nonnull
#define __nonnull(params)
#endif
#ifndef __wur
#define __wur
#endif
#ifndef __attribute_malloc__
#define __attribute_malloc__
#endif
#ifndef __attribute_pure__
#define __attribute_pure__
#endif
#ifndef __attribute_const__
#define __attribute_const__
#endif
#ifndef __attribute_warn_unused_result__
#define __attribute_warn_unused_result__
#endif
#ifndef __flexarr
#define __flexarr []
#endif

static inline int __vsprintf_chk(char *s,int f,size_t sl,const char *fmt,va_list a){return vsnprintf(s,sl?sl:0x7fffffff,fmt,a);}

#endif
