---
name: l2-control
description: Sterowanie lidarem Unitree L2. Start, standby, synchronizacja czasu, reset i zmiana trwałego trybu pracy (workMode, bity FOV/2D/IMU/UART/autostart). Użyj, gdy użytkownik chce zatrzymać lub uruchomić lidar, włączyć lub wyłączyć IMU albo zmienić tryb.
---

# Sterowanie lidarem L2

Narzędzie: `venv/Scripts/python l2ctl.py <komenda>`. Wysyła z portu 6201, bo lidar kieruje
strumień na port źródłowy ostatniej komendy. Gdy panel `l2gui.py` jest otwarty, CLI odmówi
(`UDP 6201 is busy`). Wtedy poproś użytkownika o użycie przycisku w panelu.

| Komenda | Skutek | Zgoda |
|---|---|---|
| `version`, `latency`, `mode` | tylko odczyt | nie trzeba |
| `standby` / `start` | zatrzymuje lub wznawia obrót | zapytaj |
| `timesync` | ustawia zegar lidara na czas hosta | zapytaj |
| `reset` | restart lidara | zapytaj |
| `setmode <n> --yes` | **trwały** zapis trybu | wyraźne polecenie |

## Tryb pracy

Bity: 0 = szeroki FOV 192°, 1 = pomiar 2D, 2 = IMU **wyłączone**, 3 = **UART zamiast Ethernetu**,
4 = czekanie na Start po włączeniu zasilania.

Procedura zmiany trybu:
1. Odczytaj obecny tryb (`mode`) i pokaż użytkownikowi nowy tryb rozpisany na bity.
   `setmode <n>` bez `--yes` tylko go wypisuje i nic nie wysyła.
2. **Jeśli nowy tryb ma bit 3 = 1**, ostrzeż wyraźnie: po restarcie lidar przestanie odpowiadać
   po sieci, a powrót będzie możliwy tylko przez UART (COM4, 4 Mbps). Obsługi UART nie
   napisano ani nie przetestowano.
3. Po zgodzie wyślij `setmode <n> --yes` i potwierdź zmianę ponownym `mode`.
4. Zmiana może wymagać wyłączenia i włączenia zasilania. Poproś o to użytkownika.
   Przy bicie 4 = 1 po restarcie trzeba wysłać `start`.

## Weryfikacja

Po `standby` i `start` sprawdź skillem `l2-status`, czy strumień zatrzymał się i wrócił.
Dopóki tego nie sprawdzisz na lidarze, nie pisz, że komenda działa. Do tej pory
na lidarze sprawdzono tylko `version`, `latency`, `mode` i zapis trybu z panelu.
