# Unitree L2 — narzędzia na Windows

Proste narzędzia w Pythonie do lidaru Unitree 4D L2 podłączonego po Ethernecie (UDP).
Działają bez oficjalnego SDK, które jest dostępne tylko jako biblioteka dla Linuksa.
Format ramek i przeliczenie odległości na punkty XYZ przeniesiono z nagłówków
[unilidar_sdk2](https://github.com/unitreerobotics/unilidar_sdk2)
(`unitree_lidar_protocol.h`, `unitree_lidar_utilities.h`).

## Pliki

| Plik | Co robi |
|---|---|
| `l2gui.py` | panel ze statusem i przyciskami sterowania (Tkinter); połączenie przez Ethernet albo UART, przyciski dodania i usunięcia adresu `192.168.1.2` |
| `live.py` | podgląd chmury punktów na żywo (Open3D) |
| `l2ctl.py` | sterowanie z wiersza poleceń; `--serial COM4` wysyła przez UART |
| `listen.py` | kilkusekundowy nasłuch: statystyki ramek, stan lidara, zapis `cloud.ply` |
| `render.py` | rzuty chmury z pliku PLY do PNG (widok z góry i dwa z boku) |
| `l2.py` | parser protokołu (nagłówek, CRC, punkty, IMU) |

## Instalacja

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

Uruchomienie panelu: `start_panel.bat`. Podgląd 3D włącza się przyciskiem w panelu.

## Sieć

Domyślne adresy fabryczne:

- lidar: `192.168.1.62`, UDP 6101;
- host: `192.168.1.2`, UDP 6201. Lidar nadaje na ten adres.

Komputer musi mieć adres `192.168.1.2/24`. Jeśli lidar jest w tej samej sieci
co karta Wi-Fi, można dodać ten adres jako drugi, bez utraty DHCP i internetu
(PowerShell jako administrator):

```powershell
netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=enabled
netsh interface ipv4 add address "Wi-Fi" 192.168.1.2 255.255.255.0
```

W panelu robią to przyciski **Dodaj adres** i **Usuń adres** w sekcji „Sieć hosta”
(potwierdzenie w okienku UAC). Nazwa karty jest w stałej `IFACE` w `l2gui.py`.

Wycofanie:

```powershell
netsh interface ipv4 delete address "Wi-Fi" 192.168.1.2
netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=disabled
```

Przez Wi-Fi część pakietów UDP ginie (zmierzono do ok. 5 % przy włączonym IMU).
Do pracy wymagającej ciągłości danych lepszy jest kabel.

## Ustalenia o protokole (niezgodne z dokumentacją SDK lub w niej pominięte)

- **Lidar wysyła strumień na adres i port, z którego przyszła ostatnia komenda.**
  Komenda wysłana z przypadkowego portu przekierowuje strumień na ten port.
  Dlatego panel i `l2ctl.py` wysyłają komendy z portu danych 6201.
  Oba programy nie mogą działać jednocześnie. Gdy panel jest otwarty,
  `l2ctl.py` odmówi działania.
- CRC32 w stopce ramki obejmuje **tylko pole danych**, bez 12-bajtowego nagłówka.
- Pakiet punktów (typ 102) ma 1044 B, a nie 1036 B, jak podaje komentarz w nagłówku SDK.
  Pakiet IMU (typ 104) ma 80 B, a nie 156 B. Układ pól się zgadza (`DataInfo` i 10 liczb float).
- W pakiecie wersji data kompilacji jest zapisana w ASCII jako `YYMMDD`.
- README SDK podaje dwie różne pary adresów. Właściwa dla nowego egzemplarza to
  `192.168.1.62` → `192.168.1.2`. Para `192.168.123.110/120` występuje tylko
  w przykładzie `set_to_serial_mode.cpp`.
- Przy wyłączonym IMU pole temperatury IMU nadal ma wartość. Zaobserwowano stałe
  25,6 °C, a po włączeniu IMU 74,5 °C. Stała wartość jest więc najpewniej nieaktualna.

## Tryb pracy (`workMode`)

Tryb pracy jest zapisywany trwale w lidarze. Znaczenie bitów:

| Bit | 0 | 1 |
|---|---|---|
| 0 | FOV standardowy 180° | FOV szeroki 192° |
| 1 | pomiar 3D | pomiar 2D |
| 2 | IMU włączone | IMU wyłączone |
| 3 | Ethernet | UART |
| 4 | start po włączeniu zasilania | czeka na komendę Start |

**Bit 3 = 1 odcina lidar od sieci.** Po restarcie odpowiada wyłącznie przez UART
(4 Mbps, 8N1). Wrócić do Ethernetu można tylko przez port szeregowy. W panelu:
wybierz „UART” i kliknij „Połącz”, potem odznacz bit 3 i kliknij „Zapisz tryb…”.
Po restarcie lidara przełącz panel z powrotem na „Ethernet”.

## Sprawdzony egzemplarz

- `YS-L2`, hw `2.2.1.1`, fw `2.8.11.1`, build 2025-07-15.
- Tryb zastany przy pierwszym podłączeniu: `5` (szeroki FOV, IMU wyłączone).
  Nie był to tryb fabryczny.
- Przełączenie na UART, praca panelu po UART i powrót na Ethernet działają.
  Po UART lidar używa tego samego formatu ramek co po UDP.
- W trybie Ethernet lidar nie odpowiada na komendy wysłane po UART i nic po nim nie nadaje.
- Przyciski **Dodaj adres** i **Usuń adres** w panelu działają.

## Ograniczenia

- Tryb 2D (typ pakietu 103) nie jest dekodowany.
- Akcelerometr w osi pionowej pokazuje ok. 10,35 m/s², czyli ok. 5 % więcej niż grawitacja.
  Przyczyna nie jest zbadana.
- SDK nie podaje limitów temperatury APD i IMU ani jednostki wskaźnika zabrudzenia osłony.
