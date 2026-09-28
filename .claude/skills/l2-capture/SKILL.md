---
name: l2-capture
description: Zbierz chmurę punktów z lidaru Unitree L2 do pliku PLY, zrób rzuty PNG do szybkiej oceny albo uruchom podgląd 3D na żywo. Użyj, gdy użytkownik chce zobaczyć, co widzi lidar, zapisać skan albo sprawdzić geometrię po zmianie w parserze.
---

# Chmura punktów L2

## Zapis do PLY i podgląd PNG

Port 6201 musi być wolny, czyli panel zamknięty (sprawdź skillem `l2-status`).

```bash
venv/Scripts/python listen.py 5          # 5 s -> cloud.ply (+ statystyki)
venv/Scripts/python render.py cloud.ply cloud.png
```

Obejrzyj `cloud.png` narzędziem Read i sprawdź sensowność geometrii: proste ściany,
płaski sufit, pusto pod lidarem, bo L2 widzi tylko półsferę skierowaną w górę.
Bez takiego sprawdzenia nie uznawaj zmiany w `l2.py` lub `live.py` za działającą.

5 s daje około 300 tys. punktów. Pliki `*.ply` i `*.png` są w `.gitignore`.
Pliki PLY otwiera CloudCompare albo MeshLab.

## Podgląd na żywo

- Jeśli panel działa, użyj przycisku **Podgląd 3D**. Panel przekazuje strumień na `127.0.0.1:6202`.
- Bez panelu:
  ```powershell
  Start-Process venv\Scripts\pythonw.exe -ArgumentList "live.py","1.0" -WorkingDirectory .
  ```
  Pierwszy argument to długość okna w sekundach, drugi, opcjonalny, to port (domyślnie 6201).
  Uwaga: `live.py` samo nie wysyła komendy. Jeśli strumień poszedł na inny port, najpierw uruchom
  `l2ctl.py version`.

Po starcie sprawdzaj proces co najmniej przez 30 s. Właściwy interpreter jest procesem potomnym
launchera z venv, a jego okno nosi tytuł `Unitree L2 live`. Open3D wymaga ciągłych tablic
`float64`, inaczej zgłasza `MemoryError: bad allocation`.
