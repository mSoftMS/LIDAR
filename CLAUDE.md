# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Unitree L2 — narzędzia na Windows

Komunikacja z użytkownikiem i dokumentacja po polsku. Kod, identyfikatory i komentarze w kodzie po angielsku.
Szczegóły protokołu i sieci są w `README.md`. Przeczytaj go przed zmianą w `l2.py` lub `l2ctl.py`.

## Najważniejsze fakty

- Lidar `192.168.1.62:6101` nadaje UDP na `192.168.1.2:6201`. Host ma `192.168.1.2`
  jako drugi adres na karcie Wi-Fi (lidar jest w switchu tej samej sieci).
  Nie skanuj sieci.
- **Lidar kieruje strumień na port źródłowy ostatniej komendy.** Każdą komendę wysyłaj
  z portu 6201. Nigdy nie wysyłaj z portu tymczasowego, bo przestawi to strumień w próżnię.
- Portu 6201 naraz może używać tylko jeden proces: panel `l2gui.py` albo `l2ctl.py`/`listen.py`.
  Gdy panel jest otwarty, CLI zgłosi `UDP 6201 is busy`. Wtedy poproś użytkownika
  o zamknięcie panelu albo o użycie przycisku w panelu. Nie zabijaj procesu panelu bez zgody.
- Python: `venv\Scripts\python.exe` w katalogu projektu (w Bash: `venv/Scripts/python`).
- Zmiana `workMode` jest trwała. **Bit 3 = 1 odcina lidar od sieci**, a powrót jest
  możliwy tylko przez UART. Taka zmiana wymaga wyraźnego polecenia użytkownika.
- Bit 4 = 1: po włączeniu zasilania lidar czeka na komendę Start.
- Adapter UART (CH343) zgłasza się jako COM4, 4 Mbps. Przełączenie na UART, pracę panelu
  po UART i powrót na Ethernet sprawdził użytkownik 2026-09-28. W trybie Ethernet lidar milczy
  na UART, a w trybie UART na sieci. Przyciski adresu hosta w panelu też sprawdził użytkownik.

## Polecenia

Projekt nie ma testów, lintera ani kroku budowania. Weryfikacja odbywa się na prawdziwym lidarze.

```bash
venv/Scripts/python l2ctl.py version|latency|mode        # tylko odczyt
venv/Scripts/python l2ctl.py standby|start|timesync|reset # zmienia stan — zapytaj
venv/Scripts/python l2ctl.py setmode <int> --yes          # trwałe — tylko na wyraźne polecenie
venv/Scripts/python l2ctl.py --serial COM4 <komenda>      # to samo przez UART
venv/Scripts/python listen.py [sekundy]                   # statystyki + zapis cloud.ply
venv/Scripts/python render.py [cloud.ply] [cloud.png]     # rzuty PNG do obejrzenia przez Read
start_panel.bat                                           # panel (pythonw, bez konsoli)
```

Do typowych zadań są skille projektu w `.claude/skills/` (`l2-status`, `l2-control`,
`l2-capture`, `l2-network`). `*.ply` i `*.png` są w `.gitignore`.

## Architektura

- `l2.py` — czysty parser bez I/O: nagłówek, CRC, pakiet punktów (102), IMU (104)
  i przeliczenie na XYZ (`to_xyz`, pętla w czystym Pythonie).
- `l2ctl.py` — budowanie ramek komend (`build`, `user_cmd`, `work_mode_pkt`,
  `time_sync_pkt`), `describe` i `decode_mode`. Panel i `listen.py` importują go jako bibliotekę,
  więc przy zmianie sygnatur sprawdź wszystkie trzy pliki.
- `l2gui.py` — `Link` obsługuje ramki niezależnie od transportu: liczy statystyki strumienia,
  a pozostałe ramki (ACK, wersja, tryb) wrzuca do kolejki, którą `App._pump` obsługuje w wątku Tk.
  `UdpLink` jest jedynym właścicielem gniazda 6201 i wysyła komendy z niego.
  `SerialLink` składa ramki z bajtów przez `l2.FrameSplitter`. `l2ctl.SerialSock` robi to samo
  dla CLI. Przyciski adresu hosta uruchamiają `netsh` przez UAC (`run_elevated`), a obecność
  adresu panel sprawdza próbą `bind` na `192.168.1.2`.
- Podgląd 3D: panel uruchamia `live.py` jako podproces i przekazuje kopię każdego datagramu
  na `127.0.0.1:6202`. `live.py` ma własną, wektorową (NumPy) kopię przeliczenia XYZ w `xyz_np`.
  **Zmiana geometrii w `l2.to_xyz` wymaga tej samej zmiany w `live.xyz_np`.**
- `listen.py` na starcie wysyła z 6201 zapytanie o wersję, żeby przywrócić strumień na ten port.
  `live.py` uruchomiony samodzielnie na 6201 niczego nie wysyła.

## Zasady pracy

- Komendy tylko do odczytu (`version`, `latency`, `mode`) można wysyłać swobodnie.
  Komendy `standby`, `start`, `timesync` i `reset` zmieniają stan lidara, więc przed nimi zapytaj użytkownika.
- Nie deklaruj działania bez testu na prawdziwym lidarze. Zmianę GUI sprawdź zrzutem okna.
- Nie rób commitów ani pushy bez wyraźnego polecenia.
