#!/usr/bin/env python3
# The Mali KitKat blob queries NATIVE_WINDOW_CONSUMER_USAGE_BITS during eglCreateWindowSurface,
# but libhybris only answers it under #if ANDROID_VERSION_MAJOR>=6 -> on our 4.4 build it falls to
# the default (BAD_VALUE) and the driver aborts. Move the case OUT of the >=6 guard (the enum IS
# defined in our headers). Fix: relocate the closing #endif to before the CONSUMER_USAGE_BITS case.
p = "/home/user/libhybris-musl/hybris/egl/platforms/common/nativewindowbase.cpp"
s = open(p).read()
old = ("\t\tcase NATIVE_WINDOW_CONSUMER_USAGE_BITS:\n"
       "\t\t\t*value = self->getUsage();\n"
       "\t\t\treturn NO_ERROR;\n"
       "#endif\n")
new = ("#endif\n"
       "\t\tcase NATIVE_WINDOW_CONSUMER_USAGE_BITS:\n"
       "\t\t\t*value = self->getUsage();\n"
       "\t\t\treturn NO_ERROR;\n")
if new in s:
    print("already patched")
elif old in s:
    s = s.replace(old, new, 1)
    open(p, "w").write(s)
    print("patched: CONSUMER_USAGE_BITS now handled on all Android versions")
else:
    print("MARKER NOT FOUND — inspect manually")
