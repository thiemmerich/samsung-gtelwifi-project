#!/usr/bin/env python3
# Read the dominant 16-bit pixel from a center block of /dev/fb0 (reliable only when the
# whole screen is a flat color). Decode under several format interpretations so we can see
# which one turns the *stored* value back into the color we asked GL to render.
import collections, sys
W, H, stride = 800, 1280, 800 * 2
want = sys.argv[1] if len(sys.argv) > 1 else "?"
d = open("/dev/fb0", "rb").read(stride * H)
c = collections.Counter()
for y in range(H // 2 - 200, H // 2 + 200, 8):
    for x in range(W // 2 - 200, W // 2 + 200, 4):
        o = y * stride + x * 2
        c[d[o] | (d[o + 1] << 8)] += 1
v, n = c.most_common(1)[0]
r5 = (v >> 11) & 0x1f; g6 = (v >> 5) & 0x3f; b5 = v & 0x1f
sw = ((v & 0xff) << 8) | (v >> 8)
sr = (sw >> 11) & 0x1f; sg = (sw >> 5) & 0x3f; sb = sw & 0x1f
# BGR565 read of the stored word
br = v & 0x1f; bg = (v >> 5) & 0x3f; bb = (v >> 11) & 0x1f
print("want=%-6s stored=0x%04X (%d%% of block)" % (want, v, n * 100 // max(1, sum(c.values()))))
print("   as RGB565 : R%2d G%2d B%2d  (~%3d,%3d,%3d)" % (r5, g6, b5, r5*255//31, g6*255//63, b5*255//31))
print("   byteswap  : R%2d G%2d B%2d  (~%3d,%3d,%3d)" % (sr, sg, sb, sr*255//31, sg*255//63, sb*255//31))
print("   as BGR565 : R%2d G%2d B%2d  (~%3d,%3d,%3d)" % (br, bg, bb, br*255//31, bg*255//63, bb*255//31))
