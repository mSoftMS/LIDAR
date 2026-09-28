---
name: l2-status
description: Sprawdź, czy lidar Unitree L2 odpowiada i nadaje. Pokazuje wersję, tryb pracy, częstotliwość pakietów, zgubione pakiety, temperatury i napięcia. Użyj, gdy użytkownik pyta „czy lidar działa”, o jego stan, temperaturę albo diagnozę braku danych.
---

# Status lidara L2

Wszystkie kroki są tylko do odczytu. Uruchamiaj je z katalogu projektu.

1. Łączność:
   ```bash
   ping -n 2 192.168.1.62
   ```
   Jeśli nie ma odpowiedzi, sprawdź adres `192.168.1.2` na hoście (skill `l2-network`).
   Dopiero potem szukaj przyczyny po stronie lidara.

2. Sprawdź, czy port 6201 nie jest zajęty przez panel:
   ```powershell
   Get-NetUDPEndpoint -LocalPort 6201 -ErrorAction SilentlyContinue
   ```
   Jeśli jest zajęty, lidar najpewniej obsługuje otwarty panel `l2gui.py`. Nie zamykaj go.
   Poproś użytkownika o odczyt z panelu albo zrób zrzut okna o tytule
   zaczynającym się od `Unitree L2` (PIL `ImageGrab` + `FindWindowW`) i odczytaj pola.

3. Jeśli port jest wolny:
   ```bash
   venv/Scripts/python l2ctl.py version
   venv/Scripts/python l2ctl.py mode
   venv/Scripts/python listen.py 5
   ```
   `listen.py` na starcie wysyła zapytanie o wersję z portu 6201. W ten sposób odzyskuje strumień,
   jeśli wcześniej przestawiła go komenda z innego portu.

## Interpretacja

- Około 215 pakietów punktów/s (300 punktów w każdym) i około 250 pakietów IMU/s, jeśli IMU jest włączone.
- `listen.py` pokazuje 0 B, a ping działa: lidar może być w trybie standby. Przy bicie 4 trybu
  czeka po restarcie na komendę Start. Druga możliwość to strumień wysyłany na inny port.
- `sys_rot_period` i `com_rot_period` są w µs. Typowo około 4640 µs (215 Hz, obrót pionowy)
  i około 230 000 µs (4,4 Hz, obrót poziomy).
- Temperatury: APD 48–62 °C, IMU około 75 °C przy włączonym IMU. SDK nie podaje limitów,
  więc nie oceniaj ich jako „w normie” bez zastrzeżenia. Przy wyłączonym IMU temperatura IMU
  ma stałą, nieaktualną wartość.
- Straty pakietów przez Wi-Fi dochodzą do około 5 %.
