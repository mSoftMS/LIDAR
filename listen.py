import socket, time, struct, collections, sys
import l2, l2ctl
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 5
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
try:
    s.bind(("0.0.0.0", l2ctl.DATA_PORT))
except OSError:
    sys.exit(f"UDP {l2ctl.DATA_PORT} is busy (panel or viewer running?) - use the panel instead")
s.settimeout(0.5)
# The lidar streams to the source port of its last command; a read-only
# version query from 6201 points the stream back here.
s.sendto(l2ctl.user_cmd(3), l2ctl.LIDAR)
cnt = collections.Counter(); sizes = {}; badcrc = 0; src = set()
pts = []; last_point = None; last_imu = None; nbytes = 0; t0 = time.time()
while time.time() - t0 < DUR:
    try:
        data, addr = s.recvfrom(65535)
    except socket.timeout:
        continue
    src.add(addr); nbytes += len(data)
    h = l2.split_header(data)
    if not h:
        cnt["garbage"] += 1; continue
    ptype, psize = h
    name = l2.TYPES.get(ptype, str(ptype)); cnt[name] += 1; sizes[name] = (len(data), psize)
    if not l2.crc_ok(data, psize):
        badcrc += 1; continue
    if ptype == 102:
        last_point = l2.parse_point(data); pts += l2.to_xyz(last_point)
    elif ptype == 104:
        last_imu = l2.parse_imu(data)
el = time.time() - t0
print(f"sources: {src}  {nbytes/el/1e6*8:.2f} Mbit/s  bad crc: {badcrc}")
for k, v in cnt.items():
    print(f"  {k:10s} {v/el:8.1f} /s  datagram/packet size {sizes.get(k)}")
if last_point:
    st = last_point["state"]
    print("state:", {k: round(v, 3) for k, v in st.items()})
    print("calib:", {k: round(v, 5) for k, v in last_point["cal"].items()})
    print("line :", {k: round(v, 6) for k, v in last_point["line"].items()})
if last_imu:
    print("imu  :", {k: [round(x, 4) for x in v] if isinstance(v, tuple) else v for k, v in last_imu.items()})
if pts:
    import statistics as S
    d = [(x*x+y*y+z*z) ** .5 for x, y, z, _ in pts]
    print(f"points: {len(pts)}  range m: min {min(d):.2f} median {S.median(d):.2f} max {max(d):.2f}")
    with open("cloud.ply", "w") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(pts)}\nproperty float x\nproperty float y\n"
                "property float z\nproperty uchar intensity\nend_header\n")
        for x, y, z, i in pts:
            f.write(f"{x:.4f} {y:.4f} {z:.4f} {i}\n")
    print("saved cloud.ply")
