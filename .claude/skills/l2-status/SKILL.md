---
name: l2-status
description: Check whether the Unitree L2 lidar answers and streams. Shows version, work mode, packet rate, lost packets, temperatures and voltages. Use when the user asks whether the lidar works ("czy lidar działa"), about its state or temperature, or to diagnose missing data.
---

# L2 lidar status

All steps are read-only. Run them from the project directory.

1. Connectivity:
   ```bash
   ping -n 2 192.168.1.62
   ```
   If there is no reply, check the `192.168.1.2` address on the host (`l2-network` skill).
   Only then look for the cause on the lidar side. In UART mode ping always fails (step 4).

2. Check whether port 6201 is held by the panel:
   ```powershell
   Get-NetUDPEndpoint -LocalPort 6201 -ErrorAction SilentlyContinue
   ```
   If it is taken, the lidar is most likely served by an open `l2gui.py` panel. Do not close it.
   Ask the user to read the panel, or take a screenshot of the window whose title
   starts with `Unitree L2` (PIL `ImageGrab` + `FindWindowW`) and read the fields.

3. If the port is free:
   ```bash
   venv/Scripts/python l2ctl.py version
   venv/Scripts/python l2ctl.py mode
   venv/Scripts/python listen.py 5
   ```
   `listen.py` sends a version query from port 6201 on startup. That recovers the stream
   if a command from another port redirected it earlier.

4. If the lidar is in UART mode (bit 3 = 1), the network is silent. Check it over COM4:
   ```bash
   venv/Scripts/python l2ctl.py --serial COM4 mode
   venv/Scripts/python l2ctl.py --serial COM4 version
   ```
   Before the Start command, `version` over UART returns ACK `WAIT_ERROR` with no data. That is not a fault.
   `listen.py` works over UDP only. To measure the UART stream, read COM4 through
   `l2ctl.SerialSock` and `l2.FrameSplitter` without sending commands. If COM4 cannot be opened,
   the panel holds the port.

## Interpretation

- About 215 point packets/s (300 points each) and about 250 IMU packets/s if the IMU is enabled.
- `listen.py` shows 0 B while ping works: the lidar may be in standby. With mode bit 4 set
  it waits for the Start command after a restart. The other possibility is the stream going to another port.
- `sys_rot_period` and `com_rot_period` are in µs. Typically about 4640 µs (215 Hz, vertical rotation)
  and about 230 000 µs (4.4 Hz, horizontal rotation).
- After the Start command the IMU sends immediately, points only after about 13 s (motor spin-up).
- Over UART (4 Mbps) the stream with IMU uses about 1.96 Mbit/s. 0.05 % lost packets
  and single bad CRCs were measured.
- Temperatures: APD 42–62 °C, IMU about 75 °C with the IMU enabled. The SDK gives no limits,
  so do not call them "normal" without a caveat. With the IMU disabled the IMU temperature
  has a constant, stale value.
- Packet loss over Wi-Fi reaches about 5 %.
- Window dirt index: 4.000 was observed over UART. The SDK gives no unit or threshold,
  so do not judge it without a caveat.
