#!/usr/bin/env python3
# Clean any glReadPixels debug injection and set test_glesv2 to a flat solid color
# (both fragment shader and glClearColor) so the whole panel is one uniform color.
# Usage: set_test_color.py R G B      (floats 0..1)
import re, sys
R, G, B = sys.argv[1], sys.argv[2], sys.argv[3]
p = "/home/user/libhybris-musl/hybris/tests/test_glesv2.cpp"
s = open(p).read()

# strip any prior readpix debug blocks (either variant), matching a whole line
s = "\n".join(l for l in s.splitlines()
              if "GLES-READPIX" not in l and "glReadPixels(400,640" not in l)
if not s.endswith("\n"):
    s += "\n"

# solid fragment + matching clear color
s = re.sub(r"gl_FragColor = vec4\([^;]*\);",
           "gl_FragColor = vec4( %s, %s, %s, 1.0 );" % (R, G, B), s, count=1)
s = re.sub(r"glClearColor \([^;]*\);",
           "glClearColor ( %s, %s, %s, 1.);" % (R, G, B), s, count=1)
open(p, "w").write(s)
print("test set to solid (%s,%s,%s), readpix debug removed" % (R, G, B))
