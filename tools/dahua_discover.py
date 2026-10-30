#!/usr/bin/env python3
"""Wykrywanie urzadzen Dahua (DHIP, UDP 37810). Bez logowania.
Uzycie: python3 dahua_discover.py <adres_lub_broadcast> [lokalny_adres]
np.     python3 dahua_discover.py 192.168.1.255"""
import socket, struct, json, sys
dst = sys.argv[1] if len(sys.argv) > 1 else "255.255.255.255"
src = sys.argv[2] if len(sys.argv) > 2 else ""
body = json.dumps({"method": "DHDiscover.search", "params": {"mac": "", "uni": 1}}).encode()
hdr = b"\x20\x00\x00\x00DHIP" + b"\x00" * 8 + struct.pack("<I", len(body)) + b"\x00" * 4 + struct.pack("<I", len(body)) + b"\x00" * 4
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.bind((src, 0)); s.settimeout(4)
s.sendto(hdr + body, (dst, 37810))
seen = set()
try:
    while True:
        d, a = s.recvfrom(8192)
        if a[0] in seen: continue
        seen.add(a[0])
        try:
            di = json.loads(d[32:].decode(errors="replace").rstrip("\x00"))["params"]["deviceInfo"]
        except Exception:
            print(a[0], "(nieczytelna odpowiedz)"); continue
        ip = di.get("IPv4Address", {}).get("IPAddress")
        print(f"{a[0]}: {di.get('DeviceType')}  wersja {di.get('Version')}  IP {ip}  port {di.get('Port')}")
except socket.timeout:
    if not seen: print("brak odpowiedzi")
