---
name: l2-capture
description: Capture a point cloud from the Unitree L2 lidar to a PLY file, render PNG projections for a quick check, or start the live 3D view. Use when the user wants to see what the lidar sees, save a scan, or check geometry after a parser change.
---

# L2 point cloud

## Save to PLY and preview as PNG

Port 6201 must be free, so the panel must be closed (check with the `l2-status` skill).

```bash
venv/Scripts/python listen.py 5          # 5 s -> cloud.ply (+ statistics)
venv/Scripts/python render.py cloud.ply cloud.png
```

Look at `cloud.png` with the Read tool and check that the geometry makes sense: straight walls,
a flat ceiling, nothing below the lidar, because the L2 only sees the upward-facing hemisphere.
Do not consider a change in `l2.py` or `live.py` working without this check.

5 s gives about 300 thousand points. `*.ply` and `*.png` are in `.gitignore`.
PLY files open in CloudCompare or MeshLab.

`listen.py` works over UDP only. In UART mode, use the panel's 3D view.

## Live view

- If the panel is running, use the **3D view** button. The panel relays the stream to `127.0.0.1:6202`.
  This works for both Ethernet and UART connections.
- Without the panel:
  ```powershell
  Start-Process venv\Scripts\pythonw.exe -ArgumentList "live.py","1.0" -WorkingDirectory .
  ```
  The first argument is the window length in seconds, the second, optional, is the port (default 6201).
  Note: `live.py` sends no command itself. If the stream went to another port, run
  `l2ctl.py version` first.

After starting, watch the process for at least 30 s. The real interpreter is a child process
of the venv launcher, and its window is titled `Unitree L2 live`. Open3D needs contiguous
`float64` arrays, otherwise it raises `MemoryError: bad allocation`.
