#!/usr/bin/env python3
"""Wysyla do kamery (unicast, tylko jej MAC) odpowiedzi ARP: "192.168.1.1 to MAC Maca".
Cel: wygrac z proxy ARP rejestratora, zeby zadanie TFTP kamery trafilo do Maca.
Uzycie (root): python3 arp_guard.py <iface> <MAC_kamery> [czas_s] [odstep_ms]"""
import os, sys, fcntl, struct, time, subprocess, socket

iface = sys.argv[1]
cam = bytes.fromhex(sys.argv[2].replace(":", ""))
dur = float(sys.argv[3]) if len(sys.argv) > 3 else 900
gap = float(sys.argv[4]) / 1000 if len(sys.argv) > 4 else 0.001

out = subprocess.run(["ifconfig", iface], capture_output=True, text=True).stdout
mymac = bytes.fromhex([l.split()[1] for l in out.splitlines() if l.strip().startswith("ether")][0].replace(":", ""))

fd = None
for i in range(256):
    try:
        fd = os.open(f"/dev/bpf{i}", os.O_RDWR); break
    except OSError:
        continue
if fd is None:
    sys.exit("brak wolnego /dev/bpf")
BIOCSETIF = 0x8020426C       # _IOW('B',108,struct ifreq[32])
BIOCSHDRCMPLT = 0x80044275   # _IOW('B',117,u_int)
fcntl.ioctl(fd, BIOCSETIF, struct.pack("16s16x", iface.encode()))
fcntl.ioctl(fd, BIOCSHDRCMPLT, struct.pack("I", 1))

gw = socket.inet_aton("192.168.1.1")
def reply(target_ip):
    eth = cam + mymac + b"\x08\x06"
    arp = struct.pack("!HHBBH", 1, 0x0800, 6, 4, 2) + mymac + gw + cam + socket.inet_aton(target_ip)
    return (eth + arp).ljust(60, b"\0")
frames = [reply("192.168.1.251"), reply("192.168.1.108")]
print(f"[arp-guard] {iface} {mymac.hex(':')} -> kamera {cam.hex(':')}: 192.168.1.1 is-at Mac, co {gap*1000:.1f} ms przez {dur:.0f} s", flush=True)
end = time.time() + dur; n = 0
try:
    while time.time() < end:
        for f in frames:
            os.write(fd, f)
        n += 1
        time.sleep(gap)
except KeyboardInterrupt:
    pass
print(f"[arp-guard] koniec, wyslano {n*2} ramek", flush=True)
