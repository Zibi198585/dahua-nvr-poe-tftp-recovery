# dahua-nvr-poe-tftp-recovery

Recover a Dahua IP camera that no longer boots after an interrupted firmware update, by reflashing
the official firmware over TFTP **while the camera stays plugged into the PoE port of a Dahua NVR**.
Tested on macOS.

Full step-by-step guide (Polish): [docs/ODZYSKANIE_KAMERY_DAHUA.md](docs/ODZYSKANIE_KAMERY_DAHUA.md)

## Tested

| Camera | Hardware | Firmware flashed | NVR | Result |
|---|---|---|---|---|
| DH-IPC-HFW3849T1-AS-PV | S5 (Taurus, HX3XXX-256) | V3.140.0000000.81.R.260508 | DHI-NVR4208-8P-EI, V4.005 | Recovered |

## Symptoms this fixes

- After a failed or interrupted update the white LEDs come on, then go off, and the NVR never finds the camera.
- The camera answers ping, but every service port (80, 443, 554, 37777) refuses connections. Only TCP 8088 accepts and stays silent.
- Dahua discovery (UDP 37810) does not answer.

## How the camera recovers itself

On every boot the camera's recovery mini-system (`uptool`, partitions `kernel-aol` / `rootfs-aol`):

1. takes `192.168.1.251/24`, ARPs for gateway `192.168.1.1`, pings `192.168.254.254`,
2. fetches `upgrade_info_7db780a713a4.txt` over TFTP from `192.168.254.254`,
3. runs its lines (`tftp <image>; flwrite`), verifying every image's RSA signature before writing,
4. logs to UDP `192.168.254.254:5002`, asks for `success.txt` when done (or `failed.txt`), then waits for a power cycle.

A failed download writes nothing, and the bootloader is never touched, so you can retry safely.

## Why the usual TFTP method fails behind a Dahua NVR

With the PoE switch in **Route** mode the NVR answers ARP for 192.168.x.x addresses it does not own (proxy ARP).
The camera's ARP for `192.168.1.1` is answered by the NVR too, so its TFTP request goes to the NVR and is lost.

`tools/arp_guard.py` fixes this: it sends unicast ARP replies, only to the camera's MAC, saying
`192.168.1.1 is-at <this Mac>`. The NVR never sees them and its configuration is not changed.

## macOS gotchas handled here

- `net.inet.udp.maxdgram` is 9216 bytes. The camera asks for 16268-byte blocks, so the server answers with 1468.
- Lost blocks are resent after 0.4 s instead of 5 s (about 300-450 KB/s on a 10 Mbit PoE link).
- Put Wi-Fi first in the network service order, or plugging the adapter into the NVR takes your default route.

## Quick start

```bash
# 1. download the official firmware for your exact hardware version, unpack it (see docs, step 7.1)
#    into ./tftproot  (the .bin is a zip whose first two bytes are DH instead of PK)
# 2. USB Ethernet adapter -> free PoE port of the NVR; camera stays in its own PoE port
networksetup -listallhardwareports
sudo networksetup -ordernetworkservices "Wi-Fi" "USB 10/100/1000 LAN" "Thunderbolt Bridge"
# 3. start (interface, command list, camera MAC from its label)
sudo ./start_flash.sh en7 commands_main.txt AA:BB:CC:DD:EE:FF
# 4. unplug the camera cable for 5 s, plug it back, and leave it alone until the log says
#    "KAMERA ZGLOSILA KONIEC WGRYWANIA" and the camera asks for success.txt
# 5. power-cycle the camera once more; it boots the new firmware and the NVR picks it up
```

`commands_main.txt` flashes the main system only (dtb, kernel, romfs, pd, web, firmware).
`commands_flash.txt` also flashes the recovery mini-system. Neither ever flashes the bootloader.

## Safety

- Use only the official firmware for your exact hardware revision (check `hwid` in the unpacked firmware).
- Never flash `dhboot.bin.img` or `dhboot-min.bin.img`.
- Firmware is not included in this repository (Dahua license).

## Credits

- IPCamTalk thread "Dahua IPC EASY unbricking / recovery over TFTP" (upgrade_info format)
- [joegarb/dahua-tftp-recovery](https://github.com/joegarb/dahua-tftp-recovery) (the 192.168.1.251 sequence)
