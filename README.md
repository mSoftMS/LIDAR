# Unitree L2 — Windows tools

Version 1.0.

Simple Python tools for the Unitree 4D L2 lidar connected over Ethernet (UDP) or UART.
They work without the official SDK, which is only available as a Linux library.
The frame format and the range-to-XYZ conversion were ported from the
[unilidar_sdk2](https://github.com/unitreerobotics/unilidar_sdk2) headers
(`unitree_lidar_protocol.h`, `unitree_lidar_utilities.h`).

## Files

| File | Purpose |
|---|---|
| `l2gui.py` | control panel with status and buttons (Tkinter); connects over Ethernet or UART, buttons to add and remove the `192.168.1.2` host address |
| `live.py` | live point cloud view (Open3D) |
| `l2ctl.py` | command-line control; `--serial COM4` sends over UART |
| `listen.py` | listens for a few seconds: frame statistics, lidar state, writes `cloud.ply` |
| `render.py` | renders a PLY cloud to PNG (top view and two side views) |
| `l2.py` | protocol parser (header, CRC, points, IMU, frame reassembly from a byte stream) |

## Installation

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

Start the panel with `start_panel.bat`. The 3D view is started with a button in the panel.

## Network

Factory default addresses:

- lidar: `192.168.1.62`, UDP 6101;
- host: `192.168.1.2`, UDP 6201. The lidar sends to this address.

The computer must have the address `192.168.1.2/24`. If the lidar is on the same network
as the Wi-Fi adapter, the address can be added as a second one, keeping DHCP and internet access
(PowerShell as administrator):

```powershell
netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=enabled
netsh interface ipv4 add address "Wi-Fi" 192.168.1.2 255.255.255.0
```

In the panel, the **Add address** and **Remove address** buttons in the "Host network" section
do this (confirmed in a UAC prompt). The adapter name is the `IFACE` constant in `l2gui.py`.

To undo:

```powershell
netsh interface ipv4 delete address "Wi-Fi" 192.168.1.2
netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=disabled
```

Over Wi-Fi some UDP packets are lost (up to about 5 % measured with the IMU enabled).
Use a cable or UART when data continuity matters.

## Protocol findings (differing from the SDK documentation or missing from it)

- **The lidar sends its stream to the address and port the last command came from.**
  A command sent from a random port redirects the stream to that port.
  That is why the panel and `l2ctl.py` send commands from the data port 6201.
  The two programs cannot run at the same time. While the panel is open,
  `l2ctl.py` refuses to run.
- The CRC32 in the frame footer covers **only the data section**, not the 12-byte header.
- A point packet (type 102) is 1044 B, not 1036 B as the SDK header comment says.
  An IMU packet (type 104) is 80 B, not 156 B. The field layout matches (`DataInfo` and 10 floats).
- In the version packet the build date is stored as ASCII `YYMMDD`.
- The SDK README gives two different address pairs. The right one for a new unit is
  `192.168.1.62` → `192.168.1.2`. The `192.168.123.110/120` pair only appears
  in the `set_to_serial_mode.cpp` example.
- With the IMU disabled the IMU temperature field still has a value. A constant 25.6 °C
  was observed, and 74.5 °C after enabling the IMU. The constant value is most likely stale.

## Work mode (`workMode`)

The work mode is stored permanently in the lidar. Bit meanings:

| Bit | 0 | 1 |
|---|---|---|
| 0 | standard FOV 180° | wide FOV 192° |
| 1 | 3D measurement | 2D measurement |
| 2 | IMU enabled | IMU disabled |
| 3 | Ethernet | UART |
| 4 | starts on power-up | waits for the Start command |

**Bit 3 = 1 takes the lidar off the network.** After a restart it only answers over UART
(4 Mbps, 8N1). Going back to Ethernet is only possible over the serial port. In the panel:
select "UART" and click "Connect", then uncheck bit 3 and click "Save mode…".
After the lidar restarts, switch the panel back to "Ethernet".

## Tested unit

- `YS-L2`, hw `2.2.1.1`, fw `2.8.11.1`, build 2025-07-15.
- Mode found on first connection: `5` (wide FOV, IMU disabled).
  This was not the factory mode.
- Switching to UART, running the panel over UART and going back to Ethernet all work.
  Over UART the lidar uses the same frame format as over UDP.
- In Ethernet mode the lidar does not answer commands sent over UART and sends nothing on it.
- The **Add address** and **Remove address** buttons in the panel work.

## UART operation (measured 2026-09-28)

- The point and IMU stream uses 1.96 of 4 Mbit/s. Packet rates are the same as over Ethernet:
  about 216 point packets/s and about 249 IMU packets/s.
- Over 10 s: 1 bad CRC and 1 lost packet (0.05 %). Over Wi-Fi up to about 5 % is lost.
- Before the Start command, a version query returns ACK `WAIT_ERROR` with no data. After Start
  the version arrives normally. Over Ethernet the version also arrives before Start.
  `mode` and `latency` work before Start.
- After Start the IMU sends immediately, points only after about 13 s (motor spin-up).
- `listen.py` works over UDP only. Over UART, use the panel or `l2ctl.py --serial`.

## Limitations

- 2D mode (packet type 103) is not decoded.
- The accelerometer shows about 10.35 m/s² on the vertical axis, about 5 % more than gravity.
  The cause has not been investigated.
- The SDK gives no limits for APD and IMU temperature and no unit for the window dirt index.
  Over UART the dirt index read 4.000. It is not known whether that is high.
