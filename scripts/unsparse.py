#!/usr/bin/env python3
"""
Convert an Android sparse image back to a raw filesystem image (the inverse of
`scripts/mksparse.py`; a stand-in for `simg2img` when it isn't installed).

Handles the standard AOSP sparse format (28-byte file header / 12-byte chunk
header) with RAW / FILL / DONT_CARE / CRC32 chunks. Samsung's downloader dialect
(32/16 headers, RAW+DONT_CARE only) is also read fine — the header sizes are taken
from the file header, not assumed.

Usage:  unsparse.py <sparse_in> <raw_out>
"""
import struct, sys

sp, out = sys.argv[1], sys.argv[2]
MAGIC = 0xed26ff3a
RAW, FILL, DONT_CARE, CRC32 = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4

with open(sp, "rb") as f, open(out, "wb") as o:
    hdr = f.read(28)
    (magic, vmaj, vmin, fhs, chs, blk, total_blks,
     total_chunks, _csum) = struct.unpack("<IHHHHIIII", hdr)
    assert magic == MAGIC, f"not a sparse image (magic {magic:#x})"
    f.seek(fhs)                                  # skip any extra file-header bytes
    written = 0
    for _ in range(total_chunks):
        ctype, _res, csz, tot = struct.unpack("<HHII", f.read(12))
        f.seek(chs - 12, 1)                      # skip extra chunk-header bytes
        n = csz * blk                            # output bytes this chunk expands to
        if ctype == RAW:
            o.write(f.read(n))
        elif ctype == FILL:
            fill = f.read(4)
            o.write(fill * (n // 4))
        elif ctype == DONT_CARE:
            o.write(b"\0" * n)                   # materialize as zeros
        elif ctype == CRC32:
            f.read(4)                            # checksum only, no output
            n = 0
        else:
            raise SystemExit(f"unknown chunk type {ctype:#x}")
        written += n
    print(f"wrote {out}: {written} bytes ({written // blk} blocks of {blk})")
