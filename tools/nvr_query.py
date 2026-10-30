#!/usr/bin/env python3
"""Odpytuje NVR Dahua przez HTTP API (digest). Haslo pyta w terminalu, nigdzie go nie zapisuje.
Uzycie: python3 -I nvr_query.py 192.168.1.108 admin
"""
import sys, getpass, urllib.request, urllib.error

host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.108"
user = sys.argv[2] if len(sys.argv) > 2 else "admin"
pw = getpass.getpass(f"Haslo NVR dla {user}@{host}: ")

base = f"http://{host}"
mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
mgr.add_password(None, base, user, pw)
opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))

def get(path, label):
    print(f"\n===== {label}\n--- GET {path}")
    try:
        with opener.open(base + path, timeout=15) as r:
            body = r.read().decode(errors="replace").strip()
            print(body if body else "(pusta odpowiedz)")
    except urllib.error.HTTPError as e:
        try: body = e.read().decode(errors="replace")[:300]
        except Exception: body = ""
        print(f"HTTP {e.code}: {body}")
    except Exception as e:
        print(f"blad: {e}")

get("/cgi-bin/magicBox.cgi?action=getSystemInfo", "Info o NVR")
get("/cgi-bin/LogicDeviceManager.cgi?action=getCameraAll", "Wszystkie skonfigurowane kamery")
get("/cgi-bin/LogicDeviceManager.cgi?action=getCameraState&uniqueChannels[0]=-1", "Stan kamer")
get("/cgi-bin/configManager.cgi?action=getConfig&name=Switch", "Konfiguracja switcha PoE")
get("/cgi-bin/configManager.cgi?action=getConfig&name=PoE", "Konfiguracja PoE")
# kandydaci na status portow PoE (nazwa rozni sie miedzy firmware; bledy sa nieszkodliwe)
for p in ["/cgi-bin/netApp.cgi?action=getPoEStatus",
          "/cgi-bin/netApp.cgi?action=getPoEPower",
          "/cgi-bin/PoE.cgi?action=getPoEInfo",
          "/cgi-bin/PoE.cgi?action=getPowerStatus",
          "/cgi-bin/devVideoInput.cgi?action=getPoEStatus",
          "/cgi-bin/LogicDeviceManager.cgi?action=getPoEStatus"]:
    get(p, "Status portow PoE (proba)")
get("/cgi-bin/configManager.cgi?action=getConfig&name=RemoteDevice", "Konfiguracja zdalnych urzadzen (kanaly)")
print("\n===== KONIEC")
