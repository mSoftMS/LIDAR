"""Minimal Unitree L2 UDP protocol parser (ported from unilidar_sdk2 headers)."""
import struct, math, zlib

MAGIC = b"\x55\xAA\x05\x0A"
TAIL = b"\x00\xFF"
TYPES = {100: "USER_CMD", 101: "ACK", 102: "POINT", 103: "POINT_2D", 104: "IMU",
         105: "VERSION", 106: "TIMESTAMP", 107: "WORK_MODE", 108: "IP_CFG", 109: "MAC_CFG"}

def split_header(pkt):
    if len(pkt) < 24 or pkt[:4] != MAGIC:
        return None
    ptype, psize = struct.unpack_from("<II", pkt, 4)
    return ptype, psize

def crc_ok(pkt, psize):
    # CRC covers the data section only, not the frame header
    crc = struct.unpack_from("<I", pkt, psize - 12)[0]
    return (zlib.crc32(pkt[12:psize - 12]) & 0xFFFFFFFF) == crc

def parse_point(pkt):
    o = 12
    seq, payload, sec, nsec = struct.unpack_from("<IIII", pkt, o); o += 16
    st = struct.unpack_from("<II7f", pkt, o); o += 36
    state = dict(zip(["sys_rot_period", "com_rot_period", "dirty_index", "lost_up", "lost_down",
                      "apd_temp", "apd_voltage", "laser_voltage", "imu_temp"], st))
    cal = dict(zip(["a_axis", "b_axis", "theta_bias", "alpha_bias", "beta", "xi", "range_bias",
                    "range_scale"], struct.unpack_from("<8f", pkt, o))); o += 32
    li = struct.unpack_from("<8fI", pkt, o); o += 36
    line = dict(zip(["h_start", "h_step", "scan_period", "range_min", "range_max", "angle_min",
                     "angle_inc", "time_inc", "point_num"], li))
    n = line["point_num"]
    ranges = struct.unpack_from("<300H", pkt, o); o += 600
    inten = pkt[o:o + 300]
    return dict(seq=seq, stamp=sec + nsec * 1e-9, state=state, cal=cal, line=line,
                ranges=ranges[:n], intensities=inten[:n])

def to_xyz(p):
    c, l = p["cal"], p["line"]
    sb, cb, sx, cx = math.sin(c["beta"]), math.cos(c["beta"]), math.sin(c["xi"]), math.cos(c["xi"])
    alpha = l["angle_min"] + c["alpha_bias"]
    theta = l["h_start"] + c["theta_bias"]
    out = []
    for r, i in zip(p["ranges"], p["intensities"]):
        if r >= 1:
            rf = c["range_scale"] * (r + c["range_bias"])
            if l["range_min"] <= rf <= l["range_max"]:
                sa, ca, st, ct = math.sin(alpha), math.cos(alpha), math.sin(theta), math.cos(theta)
                A = (-cb * sx + sb * cx * sa) * rf + c["b_axis"]
                B = ca * cx * rf
                C = (sb * sx + cb * cx * sa) * rf
                out.append((ct * A - st * B, st * A + ct * B, C + c["a_axis"], i))
        alpha += l["angle_inc"]; theta += l["h_step"]
    return out

def parse_imu(pkt):
    seq, _, sec, nsec = struct.unpack_from("<IIII", pkt, 12)
    v = struct.unpack_from("<10f", pkt, 28)
    return dict(seq=seq, stamp=sec + nsec * 1e-9, quat=v[0:4], gyro=v[4:7], acc=v[7:10])

class FrameSplitter:
    """Reassembles frames from a byte stream (UART has no datagram boundaries)."""
    MAX_SIZE = 4096

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(MAGIC)
            if i < 0:
                del self.buf[:max(0, len(self.buf) - len(MAGIC) + 1)]
                return out
            del self.buf[:i]
            if len(self.buf) < 12:
                return out
            psize = struct.unpack_from("<I", self.buf, 8)[0]
            if not 24 <= psize <= self.MAX_SIZE:
                del self.buf[:1]    # false magic, resync
                continue
            if len(self.buf) < psize:
                return out
            out.append(bytes(self.buf[:psize]))
            del self.buf[:psize]
