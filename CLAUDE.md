# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Unitree L2 — Windows tools

Talk to the user in Polish. Code, identifiers, comments, UI texts and documentation
(README, skills, this file) are in English.
Protocol and network details are in `README.md`. Read it before changing `l2.py` or `l2ctl.py`.

## Key facts

- The lidar `192.168.1.62:6101` streams UDP to `192.168.1.2:6201`. The host has `192.168.1.2`
  as a second address on the Wi-Fi adapter (the lidar is on a switch in the same network).
  Do not scan the network.
- **The lidar sends its stream to the source port of the last command.** Send every command
  from port 6201. Never send from an ephemeral port, it would redirect the stream into the void.
- Only one process can use port 6201 at a time: the `l2gui.py` panel or `l2ctl.py`/`listen.py`.
  While the panel is open, the CLI reports `UDP 6201 is busy`. Then ask the user to close
  the panel or to use the panel button. Do not kill the panel process without consent.
  The same applies to COM4 when the panel is connected over UART.
- Python: `venv\Scripts\python.exe` in the project directory (in Bash: `venv/Scripts/python`).
- A `workMode` change is persistent. **Bit 3 = 1 takes the lidar off the network**, and the
  only way back is over UART. Such a change requires an explicit instruction from the user.
- Bit 4 = 1: after power-up the lidar waits for the Start command.
- The UART adapter (CH343) shows up as COM4, 4 Mbps. Switching to UART, running the panel
  over UART and going back to Ethernet were tested by the user on 2026-09-28. In Ethernet mode
  the lidar is silent on UART, and in UART mode on the network. The host address buttons in the
  panel were also tested by the user. Over UART `version` returns `WAIT_ERROR` until the Start
  command. UART measurements are in `README.md`.

## Commands

The project has no tests, linter or build step. Verification happens on the real lidar.

```bash
venv/Scripts/python l2ctl.py version|latency|mode        # read-only
venv/Scripts/python l2ctl.py standby|start|timesync|reset # changes state — ask first
venv/Scripts/python l2ctl.py setmode <int> --yes          # persistent — explicit instruction only
venv/Scripts/python l2ctl.py --serial COM4 <command>      # the same over UART
venv/Scripts/python listen.py [seconds]                   # statistics + writes cloud.ply (UDP only)
venv/Scripts/python render.py [cloud.ply] [cloud.png]     # PNG projections to view with Read
start_panel.bat                                           # panel (pythonw, no console)
```

Project skills in `.claude/skills/` cover the usual tasks (`l2-status`, `l2-control`,
`l2-capture`, `l2-network`). `*.ply`, `*.png` and `dist/` are in `.gitignore`.

## Architecture

- `l2.py` — pure parser without I/O: header, CRC, point packet (102), IMU (104),
  XYZ conversion (`to_xyz`, a plain Python loop) and `FrameSplitter`, which reassembles
  frames from a byte stream.
- `l2ctl.py` — builds command frames (`build`, `user_cmd`, `work_mode_pkt`,
  `time_sync_pkt`), `describe` and `decode_mode`. The panel and `listen.py` import it as a library,
  so check all three files when changing signatures.
- `l2gui.py` — `Link` handles frames regardless of transport: it counts stream statistics
  and puts other frames (ACK, version, mode) on a queue that `App._pump` processes in the Tk thread.
  `UdpLink` is the only owner of socket 6201 and sends commands from it.
  `SerialLink` reassembles frames from bytes with `l2.FrameSplitter`. `l2ctl.SerialSock` does the
  same for the CLI. The host address buttons run `netsh` through UAC (`run_elevated`), and the panel
  checks whether the address is present by trying to `bind` to `192.168.1.2`.
- 3D view: the panel starts `live.py` as a subprocess and relays a copy of every frame
  to `127.0.0.1:6202`. `live.py` has its own vectorised (NumPy) copy of the XYZ conversion in `xyz_np`.
  **A geometry change in `l2.to_xyz` needs the same change in `live.xyz_np`.**
- `listen.py` sends a version query from 6201 on startup to bring the stream back to that port.
  `live.py` started on its own on 6201 sends nothing.

## Working rules

- Read-only commands (`version`, `latency`, `mode`) can be sent freely.
  `standby`, `start`, `timesync` and `reset` change the lidar state, so ask the user first.
- Do not claim something works without a test on the real lidar. Check GUI changes with a window screenshot.
- Do not commit or push without an explicit instruction.
- Git remote: `mSoftMS/LIDAR` (private account). Never use the `mstepienDPS` account for this repo.
