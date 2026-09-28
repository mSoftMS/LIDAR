"""Unitree L2 UDP control client (packet layout from unitree_lidar_protocol.h)."""
import socket, struct, zlib, sys, time
import l2

LIDAR = ("192.168.1.62", 6101)
# The lidar streams to the source port of the last command, so send from the data port.
DATA_PORT = 6201
UART_BAUD = 4000000

def build(ptype, data):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    size = 12 + len(data) + 12
    return l2.MAGIC + struct.pack("<II", ptype, size) + data + struct.pack("<II", crc, 0) + b"\x00\x00" + l2.TAIL

def user_cmd(cmd_type, cmd_value=0):
    return build(100, struct.pack("<II", cmd_type, cmd_value))

def describe(d):
    h = l2.split_header(d)
    if not h: return f"non-frame {len(d)} B"
    t, n = h; name = l2.TYPES.get(t, t)
    if t == 101:
        pt, ct, cv, st = struct.unpack_from("<IIII", d, 12)
        return f"ACK packet_type={pt} cmd_type={ct} cmd_value={cv} status={st} ({ {1:'SUCCESS',2:'CRC_ERROR',3:'HEADER_ERROR',4:'BLOCK_ERROR',5:'WAIT_ERROR'}.get(st, st)})"
    if t == 105:
        hw, sw = d[12:16], d[16:20]
        name_ = d[20:44].split(b"\0")[0].decode(errors="replace")
        date = d[44:52].split(b"\0")[0].decode(errors="replace")   # ASCII YYMMDD
        if len(date) == 6 and date.isdigit():
            date = f"20{date[:2]}-{date[2:4]}-{date[4:]}"
        return f"VERSION {name_}  hw {'.'.join(map(str,hw))}  fw {'.'.join(map(str,sw))}  build {date}"
    return f"{name} {n} B"

def send(pkt, sock, wait=1.0):
    sock.sendto(pkt, LIDAR); t = time.time(); out = []
    while time.time() - t < wait:
        try: d, a = sock.recvfrom(65535)
        except socket.timeout: continue
        h = l2.split_header(d)
        if h and h[0] not in (102, 104): out.append((a, describe(d)))
    return out

class SerialSock:
    """Socket-like wrapper so the same send/recv code works over UART."""

    def __init__(self, port):
        import serial
        self.ser = serial.Serial(port, UART_BAUD, timeout=0.2)
        self.split = l2.FrameSplitter()
        self.pending = []

    def sendto(self, pkt, addr):
        self.ser.write(pkt)

    def recvfrom(self, n):
        while not self.pending:
            data = self.ser.read(self.ser.in_waiting or 1)
            if not data:
                raise socket.timeout
            self.pending += self.split.feed(data)
        return self.pending.pop(0), self.ser.port

MODE_BITS = [(0, "FOV", "standard 180", "wide 192"), (1, "measure", "3D", "2D"),
             (2, "IMU", "enabled", "disabled"), (3, "link", "Ethernet", "serial"),
             (4, "power-on", "auto start", "wait for start cmd")]

def decode_mode(m):
    return ", ".join(f"{n}={b if m >> bit & 1 else a}" for bit, n, a, b in MODE_BITS)

def work_mode_pkt(mode):
    return build(107, struct.pack("<I", mode))

def time_sync_pkt():
    t = time.time()
    return build(106, struct.pack("<II", int(t), int((t % 1) * 1e9)))

USAGE = """usage: l2ctl.py [--serial COMx] <command>
  read-only : version | latency | mode
  runtime   : standby | start | timesync | reset
  persistent: setmode <int> --yes   (stored in lidar; bit 3=1 switches it off Ethernet!)"""

if __name__ == "__main__":
    args = sys.argv[1:]
    port = None
    if "--serial" in args:
        i = args.index("--serial")
        if i + 1 >= len(args): sys.exit(USAGE)
        port = args[i + 1]
        del args[i:i + 2]
    sys.argv[1:] = args
    if len(sys.argv) < 2: sys.exit(USAGE)
    if port:
        try:
            s = SerialSock(port)
        except Exception as e:
            sys.exit(f"cannot open {port}: {e}")
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("0.0.0.0", DATA_PORT))
        except OSError:
            sys.exit(f"UDP {DATA_PORT} is busy (panel or viewer running?) - use the panel instead")
        s.settimeout(0.2)
    c = sys.argv[1]
    pkts = {"version": user_cmd(3), "latency": user_cmd(4), "mode": user_cmd(6),
            "standby": user_cmd(2, 1), "start": user_cmd(2, 0), "reset": user_cmd(1),
}
    if c == "timesync":
        pkt = time_sync_pkt()
    elif c == "setmode":
        mode = int(sys.argv[2], 0)
        print("new mode:", mode, "->", decode_mode(mode))
        if "--yes" not in sys.argv: sys.exit("refusing without --yes (persistent change)")
        pkt = work_mode_pkt(mode)
    elif c in pkts:
        pkt = pkts[c]
    else:
        sys.exit(USAGE)
    replies = send(pkt, s, 1.5)
    for a, r in replies:
        print(r)
    if not replies:
        print(f"no reply from lidar via {port or 'UDP'}")
    if c == "mode" and replies:
        s.sendto(pkt, LIDAR); t = time.time()
        while time.time() - t < 1.5:
            try: d, _ = s.recvfrom(65535)
            except socket.timeout: continue
            h = l2.split_header(d)
            if h and h[0] == 107:
                m = struct.unpack_from("<I", d, 12)[0]; print(f"mode={m} ({m:05b}) -> {decode_mode(m)}"); break
