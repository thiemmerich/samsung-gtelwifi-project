#!/usr/bin/env python3
# Rich GPU validation: the diamond gets a position-based color gradient (tests interpolation and
# R/G channels spatially) that also cycles through hues over time via the phase uniform (tests all
# channels + animation), and it drifts around the screen via the offset uniform (tests transforms).
# One continuous run exercising shading, color, and geometry.
import re
p = "/home/user/libhybris-musl/hybris/tests/test_glesv2.cpp"
s = open(p).read()

# math for sinf/cosf
if "#include <math.h>" not in s:
    s = s.replace("#include <stdio.h>", "#include <stdio.h>\n#include <math.h>", 1)

# fragment colour: spatial gradient + temporal hue cycle (single line -> no backslash issues)
frag = ("gl_FragColor = vec4( "
        "0.5+0.5*sin(phase+(pos.x*0.5+0.5)*6.2831), "
        "0.5+0.5*sin(phase+(pos.y*0.5+0.5)*6.2831+2.094), "
        "0.5+0.5*sin(phase+3.1416), 1.0 );")
s = re.sub(r"gl_FragColor = vec4\([^;]*\);", frag, s, count=1)

# animate phase instead of freezing it
s = s.replace("phase = 0.f;    // and update the local variable",
              "phase += 0.06f; // animate", 1)

# drift the diamond around
s = s.replace(
    "\t\tglUniform4f ( offset_loc  ,  offset_x , offset_y , 0.0 , 0.0 );",
    "\t\toffset_x = 0.35f*sinf(phase*0.5f); offset_y = 0.25f*cosf(phase*0.31f);\n"
    "\t\tglUniform4f ( offset_loc  ,  offset_x , offset_y , 0.0 , 0.0 );", 1)

open(p, "w").write(s)
print("validation show installed: gradient + hue cycle + drift")
