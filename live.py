"""Live Open3D viewer for Unitree L2 UDP stream (keeps a rolling window of points)."""
import socket, threading, collections, time, sys
import numpy as np, open3d as o3d, matplotlib.cm as cm
import l2

WINDOW_S = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
# 6201 receives straight from the lidar; the GUI relays a copy to 127.0.0.1:6202
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 6201
PKT_PER_S = 215
chunks = collections.deque(maxlen=int(WINDOW_S * PKT_PER_S))
lock = threading.Lock()

def xyz_np(p):
    c, l = p["cal"], p["line"]
    r = np.asarray(p["ranges"], np.float32); it = np.frombuffer(p["intensities"], np.uint8)
    k = np.arange(len(r), dtype=np.float32)
    alpha = l["angle_min"] + c["alpha_bias"] + k * l["angle_inc"]
    theta = l["h_start"] + c["theta_bias"] + k * l["h_step"]
    rf = c["range_scale"] * (r + c["range_bias"])
    m = (r >= 1) & (rf >= l["range_min"]) & (rf <= l["range_max"])
    rf, alpha, theta, it = rf[m], alpha[m], theta[m], it[m]
    sb, cb, sx, cx = np.sin(c["beta"]), np.cos(c["beta"]), np.sin(c["xi"]), np.cos(c["xi"])
    sa = np.sin(alpha)
    A = (-cb * sx + sb * cx * sa) * rf + c["b_axis"]
    B = np.cos(alpha) * cx * rf
    C = (sb * sx + cb * cx * sa) * rf
    ct, st = np.cos(theta), np.sin(theta)
    return np.column_stack([ct * A - st * B, st * A + ct * B, C + c["a_axis"]]), it

def rx():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20); s.bind(("0.0.0.0", PORT))
    while True:
        d, _ = s.recvfrom(65535)
        h = l2.split_header(d)
        if h and h[0] == 102 and l2.crc_ok(d, h[1]):
            pts = xyz_np(l2.parse_point(d))
            with lock: chunks.append(pts)

threading.Thread(target=rx, daemon=True).start()
vis = o3d.visualization.Visualizer(); vis.create_window("Unitree L2 live", 1280, 800)
pcd = o3d.geometry.PointCloud(); first = True
vis.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(0.3))
opt = vis.get_render_option(); opt.point_size = 2; opt.background_color = np.array([0.05, 0.05, 0.08])
while True:
    with lock: cs = list(chunks)
    if cs:
        xyz = np.concatenate([c[0] for c in cs]); d = np.linalg.norm(xyz, axis=1)
        # Open3D needs contiguous float64 arrays, otherwise it may fail with "bad allocation"
        pcd.points = o3d.utility.Vector3dVector(np.ascontiguousarray(xyz, np.float64))
        pcd.colors = o3d.utility.Vector3dVector(np.ascontiguousarray(cm.turbo(np.clip(d / 5, 0, 1))[:, :3], np.float64))
        if first: vis.add_geometry(pcd); first = False
        else: vis.update_geometry(pcd)
    if not vis.poll_events(): break
    vis.update_renderer(); time.sleep(0.03)
vis.destroy_window()
