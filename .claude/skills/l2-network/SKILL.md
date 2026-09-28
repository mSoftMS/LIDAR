---
name: l2-network
description: Konfiguracja sieci hosta pod lidar Unitree L2. Sprawdzenie, dodanie albo usunięcie drugiego adresu 192.168.1.2 na karcie Wi-Fi. Użyj, gdy lidar nie odpowiada na ping, po restarcie komputera albo gdy użytkownik chce posprzątać konfigurację sieci.
---

# Sieć pod lidar L2

Lidar (`192.168.1.62`) stoi w switchu tej samej sieci co laptop i nadaje na sztywno na
`192.168.1.2:6201`. Host dostaje ten adres jako **drugi adres na karcie Wi-Fi**, obok DHCP.
Internet działa dalej.

## Sprawdzenie (tylko odczyt)

```powershell
Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength,PrefixOrigin
ping -n 2 192.168.1.62
```

## Panel

Panel `l2gui.py` ma w sekcji „Sieć hosta” przyciski **Dodaj adres** i **Usuń adres**
(sprawdzone). Uruchamiają te same komendy co niżej, przez UAC. Gdy panel jest otwarty,
poproś użytkownika o użycie przycisku.

## Dodanie adresu

Wymaga uprawnień administratora. Zapytaj użytkownika o zgodę, potem uruchom z okienkiem UAC:

```powershell
$cmd = 'netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=enabled; netsh interface ipv4 add address "Wi-Fi" 192.168.1.2 255.255.255.0'
Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command',$cmd
```

Potem powtórz sprawdzenie. Upewnij się też, że internet działa:
`Test-NetConnection 8.8.8.8 -InformationLevel Quiet`.

## Usunięcie adresu

Również przez UAC i po zgodzie użytkownika:

```powershell
$cmd = 'netsh interface ipv4 delete address "Wi-Fi" 192.168.1.2; netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=disabled'
Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command',$cmd
```

## Uwagi

- WSL2 działa tu w trybie `networkingMode=Mirrored`. Adres dodany wewnątrz Ubuntu nie
  zadziała, więc konfiguruj go po stronie Windows. Dodany w Windows adres jest widoczny także w WSL.
- Nie skanuj sieci w poszukiwaniu lidara. Jeśli nie ma go pod `.62`, sprawdź jeszcze
  `192.168.123.110`, czyli adres z innego przykładu SDK.
- Zapora Windows może blokować przychodzące UDP 6201 dla nowego interpretera Pythona.
