#!/bin/bash
# Wgrywanie firmware przez TFTP z obejsciem proxy ARP rejestratora.
# Uzycie: sudo ./start_flash.sh <interfejs> <plik_komend> <MAC_kamery>
#   np.  sudo ./start_flash.sh en7 commands_flash.txt AA:BB:CC:DD:EE:FF
set -e
cd "$(dirname "$0")"
IF="${1:?podaj interfejs, np. en7}"
CMDFILE="${2:?podaj plik komend, np. commands_flash.txt}"
CAM="${3:?podaj MAC kamery z tabliczki, np. AA:BB:CC:DD:EE:FF}"
CAM=$(echo "$CAM" | tr "A-F" "a-f")
[ "$(id -u)" = 0 ] || { echo "uruchom przez sudo"; exit 1; }
echo "== zatrzymuje poprzedni serwer/podsluch (jesli dziala)"
pkill -f 'tools/tftp_server.py' 2>/dev/null || true
pkill -f 'tools/arp_guard.py' 2>/dev/null || true
pkill -f "tcpdump -i $IF" 2>/dev/null || true
sleep 1
ifconfig "$IF" inet 192.168.1.1 netmask 255.255.255.0 alias 2>/dev/null || true
ifconfig "$IF" inet 192.168.254.254 netmask 255.255.0.0 alias 2>/dev/null || true
ifconfig "$IF" | grep 'inet '
[ -d tftproot ] || { echo "brak katalogu tftproot z obrazami firmware (patrz docs)"; exit 1; }
[ -e tftproot/.FLASHING_DONE_STOP_TFTP_NOW ] || echo done > tftproot/.FLASHING_DONE_STOP_TFTP_NOW
python3 -I tools/make_upgrade_info.py "$CMDFILE" tftproot
mkdir -p logs; STAMP=$(date +%Y%m%d-%H%M%S)
tcpdump -i "$IF" -l -n -e -tttt "ether host $CAM or arp or udp port 69 or udp port 5002" > "logs/tcpdump-$STAMP.txt" 2>&1 &
TD=$!
python3 -I tools/arp_guard.py "$IF" "$CAM" 2400 20 > "logs/arpguard-$STAMP.txt" 2>&1 &
AG=$!
trap 'kill $TD $AG 2>/dev/null' EXIT INT TERM
echo "== podsluch: logs/tcpdump-$STAMP.txt, straznik ARP: logs/arpguard-$STAMP.txt (40 min)"
echo "== TERAZ odlacz kabel kamery, odczekaj 5 s, podlacz z powrotem. Potem NIE ruszaj kamery."
python3 -I tools/tftp_server.py tftproot
