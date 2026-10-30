#!/usr/bin/env python3
"""Zamienia plik z komendami U-Boot na upgrade_info_7db780a713a4.txt (format Dahua: CRC + MagicString + komendy)."""
import sys, zlib, os
src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else "tftproot"
data = open(src, "rb").read().replace(b"\r\n", b"\n")
if not data.endswith(b"\n"): data += b"\n"
magic = b"MagicString:c016dcd6-cdeb-45df-9fd0-e821bf0e1e62\n"
crc = zlib.crc32(data, zlib.crc32(magic))
out = b"CRC:" + str(crc).encode() + b"\n" + magic + data
open(os.path.join(dst, "upgrade_info_7db780a713a4.txt"), "wb").write(out)
print(f"zapisano {dst}/upgrade_info_7db780a713a4.txt z komend z {src}:")
print(data.decode())
