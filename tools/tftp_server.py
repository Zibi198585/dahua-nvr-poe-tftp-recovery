#!/usr/bin/env python3
"""Minimalny serwer TFTP (tylko odczyt) + nasluch konsoli bootloadera Dahua.
Uruchamiac przez sudo (port 69). Serwuje katalog podany jako argument.
Konsola: bootloader wysyla log na UDP 5002 adresu 192.168.254.254.
"""
import os, sys, socket, struct, threading, time, datetime

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "tftproot")
LISTEN_IP = os.environ.get("TFTP_IP", "192.168.254.254")
TFTP_PORT = int(os.environ.get("TFTP_PORT", "69"))
LOGDIR = os.path.join(os.path.dirname(ROOT), "logs")
os.makedirs(LOGDIR, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
TFTPLOG = open(os.path.join(LOGDIR, f"tftp-{stamp}.log"), "a", buffering=1)
CONLOG = open(os.path.join(LOGDIR, f"console-{stamp}.log"), "a", buffering=1)

def log(f, msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True); f.write(line + "\n")

def console_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LISTEN_IP, 5002))
    log(CONLOG, f"[konsola] nasluch na {LISTEN_IP}:5002")
    while True:
        d, a = s.recvfrom(65535)
        for ln in d.decode(errors="replace").splitlines():
            log(CONLOG, f"[kamera {a[0]}] {ln}")

def error(sock, addr, code, msg):
    sock.sendto(struct.pack("!HH", 5, code) + msg.encode() + b"\0", addr)

DONE = {"flag": False}
MAX_BLK = int(os.environ.get("TFTP_MAX_BLK", "1468"))  # bez fragmentacji IP; macOS i tak nie wysle >9216 B
def serve(req, addr):
    try:
        _serve(req, addr)
    except Exception as e:
        import traceback
        log(TFTPLOG, f"[tftp] BLAD watku dla {addr[0]}: {e!r}")
        log(TFTPLOG, traceback.format_exc().replace("\n", " | "))

def _serve(req, addr):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, 0))
    sock.settimeout(float(os.environ.get("TFTP_RTO", "0.4")))
    parts = req[2:].split(b"\0")
    fname = parts[0].decode(errors="replace").lstrip("/\\")
    fname = fname.replace("\\", "/").split("/")[-1]   # tylko nazwa pliku
    opts = {}
    rest = [p for p in parts[2:] if p]
    for i in range(0, len(rest) - 1, 2):
        opts[rest[i].decode().lower()] = rest[i + 1].decode()
    if fname == ".FLASHING_DONE_STOP_TFTP_NOW":
        DONE["flag"] = True
        log(TFTPLOG, "[tftp] *** KAMERA ZGLOSILA KONIEC WGRYWANIA *** (upgrade_info nie bedzie juz podawany)")
    if DONE["flag"] and fname.startswith("upgrade_info"):
        log(TFTPLOG, f"[tftp] {addr[0]} prosi o '{fname}' po zakonczeniu -> celowo BRAK (kamera ma startowac normalnie)")
        error(sock, addr, 1, "File not found"); return
    path = os.path.join(ROOT, fname)
    if not os.path.isfile(path):
        log(TFTPLOG, f"[tftp] {addr[0]} prosi o '{fname}' -> BRAK PLIKU")
        error(sock, addr, 1, "File not found"); return
    size = os.path.getsize(path)
    blk = int(opts.get("blksize", 512))
    blk = max(8, min(blk, MAX_BLK))
    log(TFTPLOG, f"[tftp] {addr[0]} pobiera '{fname}' ({size} B, blksize {blk})")
    if opts:
        oack = b"\0\x06"
        if "blksize" in opts: oack += b"blksize\0" + str(blk).encode() + b"\0"
        if "tsize" in opts: oack += b"tsize\0" + str(size).encode() + b"\0"
        if "timeout" in opts: oack += b"timeout\0" + opts["timeout"].encode() + b"\0"
        if not wait_ack(sock, addr, oack, 0): return
    with open(path, "rb") as f:
        n = 0
        while True:
            data = f.read(blk); n += 1
            pkt = struct.pack("!HH", 3, n & 0xFFFF) + data
            if size >= 1_000_000 and n % max(1, (size // blk) // 10) == 0:
                log(TFTPLOG, f"[tftp] '{fname}' {min(100, n*blk*100//size)}%")
            if not wait_ack(sock, addr, pkt, n & 0xFFFF):
                log(TFTPLOG, f"[tftp] '{fname}' PRZERWANE na bloku {n}"); return
            if len(data) < blk: break
    log(TFTPLOG, f"[tftp] '{fname}' WYSLANY w calosci ({n} blokow)")

def wait_ack(sock, addr, pkt, n):
    for _ in range(int(os.environ.get("TFTP_RETRIES", "40"))):
        sock.sendto(pkt, addr)
        try:
            while True:
                d, a = sock.recvfrom(1024)
                if len(d) >= 4 and d[1] == 4 and struct.unpack("!H", d[2:4])[0] == n:
                    return True
                if d[1] == 5:
                    log(TFTPLOG, f"[tftp] klient zglosil blad: {d[4:].decode(errors='replace')}")
                    return False
        except socket.timeout:
            continue
    return False

def main():
    threading.Thread(target=console_listener, daemon=True).start()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LISTEN_IP, TFTP_PORT))
    log(TFTPLOG, f"[tftp] serwer na {LISTEN_IP}:{TFTP_PORT}, katalog {ROOT}")
    log(TFTPLOG, "[tftp] teraz wlacz zasilanie kamery (wepnij kabel). Ctrl+C konczy.")
    while True:
        d, a = s.recvfrom(1024)
        if len(d) >= 2 and d[1] == 1:
            threading.Thread(target=serve, args=(d, a), daemon=True).start()
        elif len(d) >= 2 and d[1] == 2:
            log(TFTPLOG, f"[tftp] {a[0]} chce ZAPISAC plik (WRQ) - odrzucam")
            error(s, a, 2, "read only")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nkoniec")
