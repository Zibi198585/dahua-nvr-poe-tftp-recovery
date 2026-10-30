# Odzyskanie kamery Dahua po przerwanej aktualizacji (TFTP przez rejestrator)

Raport z naprawy wykonanej 30.10.2026 oraz instrukcja do powtórzenia.
Dane identyfikujące urządzenia (numery seryjne, adresy MAC) zostały usunięte.
Wynik: kamera uruchomiona na oficjalnym firmware V3.140.0000000.81.R, rejestrator sam dodał ją na kanale 1.

---

## 1. Sprzęt

| Element | Dane |
|---|---|
| Kamera | DH-IPC-HFW3849T1-AS-PV, obiektyw 2,8 mm, **wersja sprzętowa S5** (tabliczka: `2.8mm/S5`) |
| P/N kamery | 1.0.01.04.42415-9001 |
| MAC kamery | D4:43:0E:xx:xx:xx (zanonimizowany) |
| S/N kamery | (ukryty, w Dahua to także identyfikator P2P) |
| Rejestrator | DHI-NVR4208-8P-EI, firmware V4.005.0000001.7.R, adres 192.168.1.108 |
| Sieć PoE rejestratora | 10.1.1.0/24, brama 10.1.1.1, tryb przełącznika **Trasa** |
| Komputer | MacBook (macOS), adapter **USB 10/100/1000 LAN** (w systemie `en7`), internet przez Wi-Fi (`en0`) |

Firmware (oficjalny, ze strony produktu Dahua, zakładka Download, Firmware):
`DH_IPC-HX3XXX-256-Taurus_MultiLang_PN_Stream3_V3.140.0000000.81.R.260508.zip`
https://materialfile.dahuasecurity.com/uploads/cpq/79691/firmware/DH_IPC-HX3XXX-256-Taurus_MultiLang_PN_Stream3_V3.140.0000000.81.R.260508.zip

> Wersja sprzętowa jest kluczowa. Dla S5 pasuje tylko firmware Taurus (V3.140). Plik dla S3 (Volt V2.840) nie pasuje.
> Lista `hwid` w tym firmware zawiera `IPC-HFW3849T1-AS-PV-S5`.

---

## 2. Objawy

- Po wpięciu do portu PoE rejestratora zapalały się białe diody, po chwili gasły.
- Rejestrator nie widział kamery, wyszukiwanie urządzeń było puste.
- Reset przyciskiem RESET nie pomagał.
- Z sieci było widać, że kamera uruchamia Linuksa i odpowiada na ping, ale:
  - wszystkie porty TCP (80, 443, 554, 37777, 3800, 23) odrzucały połączenia,
  - jedynym otwartym portem był **8088**, który przyjmował połączenie i milczał,
  - usługa wykrywania Dahua (UDP 37810) nie działała.

Wniosek: po przerwanej aktualizacji uszkodzony był **główny system** (aplikacja Dahua), a bootloader i mini-system ratunkowy działały.

---

## 3. Jak działa odzyskiwanie w tej kamerze

Ustalone z nagrań ruchu sieciowego i logu konsoli kamery:

1. Przy każdym starcie kamera uruchamia **mini-system ratunkowy** (partycje `kernel-aol` i `rootfs-aol`), a w nim program **uptool**.
2. uptool ustawia sobie adres **192.168.1.251/24**, pyta ARP o bramę **192.168.1.1** i pinguje **192.168.254.254**.
3. Następnie pobiera przez TFTP z 192.168.254.254 plik **`upgrade_info_7db780a713a4.txt`**.
4. Jeśli plik ma poprawny nagłówek (`CRC:` i `MagicString:`), uptool wykonuje kolejne linie, np. `tftp kernel.img; flwrite`.
5. Każdy obraz jest sprawdzany podpisem RSA i sumą kontrolną przed zapisem (`upTool_commonSwRsaVerify run successfully!`, `flwrite ok!`).
6. **Nieudane pobranie niczego nie zapisuje** (`do flwrite, tftp Buf is NULL`). Pierwszy błąd przerywa całą listę, a kamera prosi o `failed.txt`.
7. Po udanym wgraniu kamera prosi o `success.txt` i czeka w mini-systemie na restart zasilania.
8. Log konsoli wysyła przez UDP na `192.168.254.254:5002`.

Jeśli serwera TFTP nie ma, kamera po kilkunastu sekundach uruchamia normalny system.

---

## 4. Dlaczego zwykła metoda TFTP nie działała

**Rejestrator podszywa się pod obce adresy (proxy ARP).**
W trybie Trasa rejestrator odpowiada na zapytania ARP o adresy 192.168.x.x, których nie posiada (sprawdzone: odpowiadał za 192.168.1.50 i 192.168.254.10 swoim adresem MAC).
Gdy kamera pytała o bramę 192.168.1.1, odpowiadał też rejestrator. Kamera wysyłała żądanie pliku do niego, a ono przepadało.

Rozwiązanie: Mac wysyła **tylko na port kamery** (unicast na jej MAC) odpowiedzi ARP „192.168.1.1 to MAC Maca”, co 20 ms. Robi to skrypt `tools/arp_guard.py`. Rejestrator tych ramek nie dostaje, więc nic w nim nie zmieniamy.

---

## 5. Pułapki macOS, które trzeba było obejść

| Problem | Objaw | Rozwiązanie |
|---|---|---|
| Adapter USB LAN był usługą sieciową nr 1 | Po wpięciu do rejestratora Mac tracił internet (domyślna trasa szła przez 10.1.1.1) | `sudo networksetup -ordernetworkservices "Wi-Fi" "USB 10/100/1000 LAN" "Thunderbolt Bridge"` |
| macOS nie wysyła UDP większych niż 9216 B (`net.inet.udp.maxdgram`) | Kamera prosi o blok 16268 B, serwer nie mógł wysłać pierwszego bloku danych, pobieranie stawało na 0% | Serwer odpowiada blokiem **1468 B** (bez fragmentacji IP) |
| Domyślny czas ponowienia 5 s | Każdy zgubiony pakiet zatrzymywał transfer na 5 s, kilkadziesiąt KB/s | Ponowienie po **0,4 s**, do 40 prób, ok. 300–450 KB/s |
| Logowanie hasłem w terminalu | `sudo` prosi o **hasło do Maca**, nie do rejestratora; podczas pisania nic się nie wyświetla | Wpisać hasło konta macOS i Enter |

Zapora macOS była wyłączona, więc nie blokowała portu 69.

---

## 6. Pliki w repozytorium

| Plik | Do czego |
|---|---|
| `start_flash.sh` | Główny skrypt: adresy na adapterze, plik komend, podsłuch, strażnik ARP, serwer TFTP |
| `commands_flash.txt` | Pełna lista z pliku Install (mini-system + główny system, bez bootloadera) |
| `commands_main.txt` | Tylko główny system (dtb, kernel, romfs, pd, web, firmware) |
| `tools/tftp_server.py` | Serwer TFTP (tylko odczyt), blok 1468, ponowienie 0,4 s, log postępu, nasłuch konsoli kamery na UDP 5002, po znaczniku końca przestaje podawać `upgrade_info` |
| `tools/arp_guard.py` | Strażnik ARP (wymaga sudo), unicast tylko do MAC kamery |
| `tools/make_upgrade_info.py` | Buduje `upgrade_info_7db780a713a4.txt`: `CRC:` + `MagicString:c016dcd6-cdeb-45df-9fd0-e821bf0e1e62` + komendy |
| `stop.sh` | Zdejmuje dodatkowe adresy z adaptera |
| `tools/nvr_query.py` | Odpytuje API rejestratora (lista kamer), hasło podaje się w terminalu |
| `tools/dahua_discover.py` | Wysyła zapytanie wykrywania Dahua (UDP 37810) i pokazuje model, wersję i adres |
| `tftproot/` | Rozpakowane obrazy partycji z firmware + `Install`, `hwid`, `.FLASHING_DONE_STOP_TFTP_NOW` |
| `download/fw.zip` | Oryginalne archiwum Dahua (pobierz sam, nie jest dołączone) |
| `logs/` | Logi serwera (`tftp-*`), konsoli kamery (`console-*`), ruchu (`tcpdump-*`), strażnika (`arpguard-*`) |

`tftproot/`, `download/` i `logs/` tworzą się lokalnie i nie są w repozytorium. Firmware Dahua nie jest dołączony ze względu na licencję.

---

## 7. Instrukcja krok po kroku

### 7.1 Przygotowanie firmware (raz)

Plik `.bin` od Dahua to archiwum ZIP z pierwszymi bajtami `DH` zamiast `PK`.

```bash
mkdir -p download tftproot && cd download   # tu umieść fw.zip pobrany ze strony Dahua
unzip -o fw.zip 'DH_IPC-HX3XXX-256-Taurus_*.bin'
python3 -I -c "
import zipfile
d=bytearray(open('DH_IPC-HX3XXX-256-Taurus_MultiLang_PN_Stream3_V3.140.0000000.81.R.260508.bin','rb').read())
d[:2]=b'PK'; open('fw_as_zip.zip','wb').write(d)
zipfile.ZipFile('fw_as_zip.zip').extractall('../tftproot')"
grep 3849 ../tftproot/hwid
```

Ostatnie polecenie musi pokazać `IPC-HFW3849T1-AS-PV-S5`. Jeśli nie, to zły firmware.

W `tftproot` musi być plik `.FLASHING_DONE_STOP_TFTP_NOW` (dowolna treść). **Nie** może być plików `success.txt` ani `failed.txt`, bo wtedy nie widać, jak kamera zakończyła.

### 7.2 Podłączenie

1. Adapter USB-Ethernet do Maca.
2. Kabel z adaptera do **wolnego portu PoE rejestratora** (adapter nie potrzebuje PoE, rejestrator robi tu za przełącznik).
3. Kamera w swoim porcie PoE rejestratora (zasilanie z rejestratora).
4. Sprawdzić nazwę adaptera:

```bash
networksetup -listallhardwareports
```

U nas: `USB 10/100/1000 LAN` = `en7`. Mac dostaje od rejestratora adres 10.1.1.x, to normalne.

5. Jednorazowo ustawić Wi-Fi jako pierwszą usługę, żeby nie stracić internetu:

```bash
sudo networksetup -ordernetworkservices "Wi-Fi" "USB 10/100/1000 LAN" "Thunderbolt Bridge"
```

### 7.3 Uruchomienie serwera

```bash
sudo ./start_flash.sh en7 commands_flash.txt AA:BB:CC:DD:EE:FF   # MAC kamery z tabliczki
```

Skrypt:
- zatrzymuje poprzedni serwer, strażnika i podsłuch,
- dodaje na `en7` adresy **192.168.1.1/24** (udaje bramę) i **192.168.254.254/16** (serwer TFTP),
- buduje `tftproot/upgrade_info_7db780a713a4.txt` z podanego pliku komend,
- uruchamia podsłuch (`tcpdump`) ruchu kamery,
- uruchamia strażnika ARP na 40 minut,
- uruchamia serwer TFTP i nasłuch konsoli.

### 7.4 Zimny restart kamery

Gdy pojawi się linia `TERAZ odlacz kabel kamery...`:
- wyjąć kabel kamery z portu PoE, odczekać 5 s, włożyć z powrotem,
- **nie ruszać kamery ani kabli do końca wgrywania.**

Samo wyłączenie i włączenie portu sieciowego na Macu **nie** restartuje kamery. Musi zniknąć zasilanie PoE.

### 7.5 Przebieg (co powinno być w logu serwera)

```
[tftp] 192.168.1.251 pobiera 'upgrade_info_7db780a713a4.txt' ... blksize 1468
[tftp] 192.168.1.251 pobiera 'kernel-aol.img' ...
[tftp] 'kernel-aol.img' 9% ... 99%
[tftp] 'kernel-aol.img' WYSLANY w calosci
... kolejne obrazy ...
[tftp] *** KAMERA ZGLOSILA KONIEC WGRYWANIA ***
[tftp] 192.168.1.251 prosi o 'success.txt' -> BRAK PLIKU
```

`success.txt -> BRAK PLIKU` oznacza **sukces** (kamera tylko zgłasza wynik). `failed.txt` oznacza błąd. Szczegóły są wtedy w `logs/console-*.log`.

Orientacyjne czasy przy łączu 10 Mbit:

| Obraz | Rozmiar | Czas |
|---|---|---|
| kernel-aol, kernel | 4,2 MB | ok. 15 s |
| rootfs-aol | 13 MB | ok. 1 min |
| romfs | 30 MB | ok. 1,5 min |
| web | 15 MB | ok. 45 s |
| firmware | 94 MB | ok. 4,5 min |
| zapis każdego obrazu w pamięci kamery | – | kilka do kilkudziesięciu sekund |

### 7.6 Po wgraniu

1. Kamera **nie restartuje się sama**. Zostaje w mini-systemie pod 192.168.1.251. Trzeba zrobić jeszcze jeden zimny restart (wyjąć i włożyć kabel).
2. Przy tym starcie kamera znów prosi o `upgrade_info`, ale serwer celowo odpowiada „brak pliku” (`celowo BRAK`), więc kamera nie wgrywa firmware drugi raz, tylko uruchamia nowy system.
3. Po ok. 30 s kamera rozgłasza się protokołem Dahua (UDP 37810) i ONVIF (UDP 3702), dostaje od rejestratora adres w sieci PoE (u nas **10.1.1.65**) i rejestrator sam dodaje ją do kanału.
4. Sprzątanie:
   - w terminalu z serwerem nacisnąć **Ctrl+C** (zatrzymuje serwer, strażnika i podsłuch),
   - odłączyć adapter od Maca (znikają dodatkowe adresy) albo `sudo ./stop.sh en7`.
5. W panelu rejestratora: Urządzenie zdalne. Kamera powinna być na liście „Dodane urządzenie” ze stanem zielonym.

---

## 8. Co dokładnie zrobiliśmy 30.10.2026 (przebieg)

| Godz. | Zdarzenie |
|---|---|
| 11:35–11:56 | Próby klasycznego TFTP: kamera pytała o bramę z 192.168.1.251, ale nie prosiła o plik. Pełny skan portów: tylko TCP 8088. |
| ok. 11:58 | Test proxy ARP: rejestrator odpowiada za cudze adresy 192.168.x.x. Przyczyna znaleziona. |
| 12:06 | Pierwsza próba ze strażnikiem ARP: kamera pobrała `upgrade_info` i zaczęła `kernel-aol`, ale stanęła na 0%. W konsoli `recv Tftp Pack fail`, bo macOS nie wysłał bloku 16268 B. Nic nie zapisane. |
| 12:09–12:12 | Serwer z blokiem 1468 B: wgrane i zweryfikowane `kernel-aol` oraz `rootfs-aol` (`flwrite ok!`). Pozostałe przerwane celowo, żeby przyspieszyć serwer. |
| 12:13–12:22 | Serwer z ponowieniem 0,4 s i listą `commands_main.txt`: wgrane `dhdtb-bak`, `dhdtb`, `kernel`, `romfs`, `pd`, `web`, `firmware`. Każdy obraz z poprawnym podpisem RSA. 12:22:28 znacznik końca, 12:22:29 `success.txt`. |
| 12:31 | Zimny restart. Serwer odmówił `upgrade_info`. Kamera uruchomiła nowy system. |
| 12:32 | Kamera pod 10.1.1.65: porty 80, 443, 554, 37777 otwarte, WWW zwraca 200, wersja 3.140.0000000.81.R, S/N zgodny z tabliczką. |
| 13:35 | W panelu rejestratora kamera na kanale 1, Port1, stan online. |

Uwaga: kamera po nieudanej próbie sama się restartuje i ponawia odzyskiwanie z tym plikiem `upgrade_info`, który aktualnie podaje serwer. Dlatego można podmienić listę komend między próbami bez dotykania kamery.

---

## 9. Rozwiązywanie problemów

| Objaw w logu | Przyczyna | Co zrobić |
|---|---|---|
| Brak `who-has 192.168.1.1 tell 192.168.1.251` w `tcpdump-*` | Kamera nie startuje odzyskiwania albo nie ma linku | Sprawdzić kabel i zimny restart. Bez tego zapytania metoda nie zadziała, zostaje UART lub serwis. |
| Jest zapytanie ARP, ale brak `pobiera 'upgrade_info...'` | Rejestrator przejmuje bramę (proxy ARP) | Sprawdzić, czy działa strażnik (`logs/arpguard-*`). |
| `pobiera 'kernel-aol.img'`, potem od razu `failed.txt` | Serwer nie wysyła danych (za duży blok) | Sprawdzić, czy serwer podaje `blksize 1468`. |
| Długie przerwy w postępie | Gubione pakiety przy 10 Mbit | Normalne. Serwer ponawia po 0,4 s. Ewentualnie lepszy kabel do adaptera. |
| `failed.txt` po konkretnym obrazie | Błąd pobrania lub podpisu | Zobaczyć `logs/console-*.log`. Uruchomić ponownie. Nieudany obraz nie jest zapisywany. |
| `success.txt`, a kamera dalej pod .251 | To normalne | Zimny restart kamery. |
| Mac traci internet | Adapter ma wyższy priorytet niż Wi-Fi | Polecenie `networksetup -ordernetworkservices` z punktu 7.2. |

---

## 10. Zasady bezpieczeństwa

- **Nigdy nie wgrywać bootloadera** (`dhboot.bin.img`, `dhboot-min.bin.img`). To on uruchamia odzyskiwanie. Jego uszkodzenie oznacza naprawę tylko przez UART.
- Wgrywać **tylko oficjalny firmware dla właściwej wersji sprzętowej** (tu S5).
- Najbezpieczniej najpierw wgrać główny system (`commands_main.txt`), a mini-system (`kernel-aol`, `rootfs-aol`) tylko wtedy, gdy jest potrzebny. Mini-system obsługuje odzyskiwanie.
- Nie odłączać zasilania kamery w trakcie zapisu (między `WYSLANY w calosci` a pobraniem następnego pliku).

---

## 11. Źródła

- IPCamTalk, „Dahua IPC EASY unbricking / recovery over TFTP” (format `upgrade_info`, adres 192.168.1.251, reset przy starcie): https://ipcamtalk.com/threads/dahua-ipc-easy-unbricking-recovery-over-tftp.17189/page-28
- joegarb/dahua-tftp-recovery (opis sekwencji 192.168.1.251, brama 192.168.1.1, serwer 192.168.254.254): https://github.com/joegarb/dahua-tftp-recovery
- IPCamTalk, „Bricked IPC-HDW3849H-AS-PV-S3” (ta sama rodzina, mini-system kernel_min/romfs_min): https://ipcamtalk.com/threads/bricked-ipc-hdw3849h-as-pv-s3.85175/
- Strona produktu Dahua z firmware: https://www.dahuasecurity.com/products/network-products/network-cameras/WizSense-Series/3-Series/TiOC/IPC-HFW3849T1-AS-PV=S5
