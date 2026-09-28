---
name: l2-control
description: Control the Unitree L2 lidar. Start, standby, time sync, reset and changing the persistent work mode (workMode bits FOV/2D/IMU/UART/autostart). Use when the user wants to stop or start the lidar, enable or disable the IMU, or change the mode.
---

# L2 lidar control

Tool: `venv/Scripts/python l2ctl.py [--serial COM4] <command>`. Over Ethernet it sends from
port 6201, because the lidar directs its stream to the source port of the last command. While the
panel `l2gui.py` is open, the CLI refuses (`UDP 6201 is busy`, or COM4 cannot be opened).
Then ask the user to use the button in the panel.

| Command | Effect | Consent |
|---|---|---|
| `version`, `latency`, `mode` | read-only | not needed |
| `standby` / `start` | stops or resumes rotation | ask |
| `timesync` | sets the lidar clock to host time | ask |
| `reset` | restarts the lidar | ask |
| `setmode <n> --yes` | **persistent** mode write | explicit instruction |

## Work mode

Bits: 0 = wide FOV 192°, 1 = 2D measurement, 2 = IMU **disabled**, 3 = **UART instead of Ethernet**,
4 = wait for Start after power-up.

Mode change procedure:
1. Read the current mode (`mode`) and show the user the new mode broken down into bits.
   `setmode <n>` without `--yes` only prints it and sends nothing.
2. **If the new mode has bit 3 = 1**, warn clearly: after a restart the lidar stops answering
   on the network, and the only way back is over UART (COM4, 4 Mbps). The panel ("UART" option)
   and `l2ctl.py --serial COM4 ...` support UART. Switching and going back from the panel were
   tested on the lidar. In Ethernet mode the lidar does not answer over UART, so the link cannot
   be tested before switching.
3. After consent send `setmode <n> --yes` and confirm the change with another `mode`.
   Going back from UART to Ethernet: `l2ctl.py --serial COM4 setmode <n with bit 3 = 0> --yes`.
4. The change may require a power cycle. Ask the user to do it.
   With bit 4 = 1 you have to send `start` after a restart. Points arrive about 13 s after Start,
   the IMU immediately. In UART mode the lidar only reports its version after Start (`WAIT_ERROR` before).

## Verification

After `standby` and `start`, check with the `l2-status` skill that the stream stopped and came back.
Until you have checked it on the lidar, do not say a command works. So far the following were
tested on the lidar: `version`, `latency`, `mode`, writing the mode from the panel, switching
to UART and back to Ethernet from the panel, and `start`, `version`, `latency` and `mode`
via `l2ctl.py --serial COM4`.
