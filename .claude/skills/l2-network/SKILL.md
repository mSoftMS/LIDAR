---
name: l2-network
description: Host network setup for the Unitree L2 lidar. Check, add or remove the second address 192.168.1.2 on the Wi-Fi adapter. Use when the lidar does not answer ping, after a computer restart, or when the user wants to clean up the network configuration.
---

# Network for the L2 lidar

The lidar (`192.168.1.62`) is on a switch in the same network as the laptop and always sends to
`192.168.1.2:6201`. The host gets this address as a **second address on the Wi-Fi adapter**, next
to DHCP. Internet access keeps working.

## Check (read-only)

```powershell
Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength,PrefixOrigin
ping -n 2 192.168.1.62
```

## Panel

The panel `l2gui.py` has **Add address** and **Remove address** buttons in the "Host network"
section (tested). They run the same commands as below, through UAC. While the panel is open,
ask the user to use the button.

## Adding the address

Requires administrator rights. Ask the user for consent, then run it with a UAC prompt:

```powershell
$cmd = 'netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=enabled; netsh interface ipv4 add address "Wi-Fi" 192.168.1.2 255.255.255.0'
Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command',$cmd
```

Then repeat the check. Also make sure the internet still works:
`Test-NetConnection 8.8.8.8 -InformationLevel Quiet`.

## Removing the address

Also through UAC and after the user's consent:

```powershell
$cmd = 'netsh interface ipv4 delete address "Wi-Fi" 192.168.1.2; netsh interface ipv4 set interface "Wi-Fi" dhcpstaticipcoexistence=disabled'
Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command',$cmd
```

## Notes

- WSL2 runs here with `networkingMode=Mirrored`. An address added inside Ubuntu will not
  work, so configure it on the Windows side. An address added in Windows is also visible in WSL.
- Do not scan the network for the lidar. If it is not at `.62`, also try
  `192.168.123.110`, the address from another SDK example.
- Windows Firewall may block incoming UDP 6201 for a new Python interpreter.
- In UART mode (work mode bit 3 = 1) the lidar is not on the network at all, so ping fails.
