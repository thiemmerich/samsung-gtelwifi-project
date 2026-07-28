#!/usr/bin/env python3
"""
Write a Samsung-Odin-compatible sparse image (for odin4) from a raw filesystem image.

WHY THIS EXISTS: odin4 REJECTS the default output of `img2simg` on this device with
"Fail request receive -1". Samsung's downloader only accepts sparse images that:
  - use RAW + DONT_CARE chunks ONLY (no FILL chunks),
  - use 32-byte file header / 16-byte chunk header (img2simg uses 28/12),
  - declare the FULL target-partition size (pad the tail with one DONT_CARE chunk).

Usage:  mksparse.py <raw_in> <sparse_out> [total_blks]
  total_blks defaults to 384000  (SM-T560 SYSTEM partition = 384000 * 4096 = 1,572,864,000 B).
"""
import struct, os, sys

raw, out = sys.argv[1], sys.argv[2]
TOTAL = int(sys.argv[3]) if len(sys.argv) > 3 else 384000
BLK = 4096
FHS, CHS = 32, 16          # Samsung header sizes (NOT the AOSP 28/12)
RAW, DONT_CARE = 0xCAC1, 0xCAC3
CHUNK_BLKS = 16384         # 64 MiB RAW chunks

size = os.path.getsize(raw)
data_blks = (size + BLK - 1) // BLK
assert data_blks <= TOTAL, f"image is {data_blks} blocks > partition {TOTAL} blocks"
nraw = (data_blks + CHUNK_BLKS - 1) // CHUNK_BLKS
pad = TOTAL - data_blks
nchunks = nraw + (1 if pad else 0)

with open(raw, "rb") as f, open(out, "wb") as o:
    o.write(struct.pack("<IHHHHIIII", 0xed26ff3a, 1, 0, FHS, CHS, BLK, TOTAL, nchunks, 0) + b"\0" * (FHS - 28))
    left = data_blks
    while left:
        k = min(CHUNK_BLKS, left)
        o.write(struct.pack("<HHII", RAW, 0, k, CHS + k * BLK) + b"\0" * (CHS - 12))
        b = f.read(k * BLK)
        o.write(b + b"\0" * (k * BLK - len(b)))   # zero-pad a short final read
        left -= k
    if pad:
        o.write(struct.pack("<HHII", DONT_CARE, 0, pad, CHS) + b"\0" * (CHS - 12))

print(f"wrote {out}: {nraw} RAW chunk(s) + {'1 DONT_CARE' if pad else 'no'} pad, total_blks={TOTAL}")
