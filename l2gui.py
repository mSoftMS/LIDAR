"""Small Tk control panel for the Unitree L2 lidar over UDP."""
import os, queue, socket, struct, subprocess, sys, threading, time
import tkinter as tk
from tkinter import messagebox, ttk
import l2, l2ctl

DATA_PORT = 6201          # lidar streams here
RELAY_PORT = 6202         # copy of the stream for the 3D viewer
HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(HERE, "venv", "Scripts", "python.exe")


class Link:
    """Owns the UDP socket; pushes non-stream frames into a queue.

    The lidar streams to the source address of the last command it received, so
    commands must leave from the same socket that receives the data.
    """

    def __init__(self, events):
        self.events = events
        self.relay = False
        self.data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
        self.data.bind(("0.0.0.0", DATA_PORT))
        self.out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.lock = threading.Lock()
        self.n_point = self.n_imu = self.n_bad = self.lost = 0
        self.last_seq = None
        self.last_rx = 0.0
        self.state = self.line = self.imu = None
        threading.Thread(target=self._rx_data, daemon=True).start()

    def snapshot(self):
        """Return counters for the last interval and reset them."""
        with self.lock:
            s = dict(n_point=self.n_point, n_imu=self.n_imu, n_bad=self.n_bad, lost=self.lost,
                     last_rx=self.last_rx, state=self.state, line=self.line, imu=self.imu)
            self.n_point = self.n_imu = self.n_bad = self.lost = 0
        return s

    def _rx_data(self):
        while True:
            d, _ = self.data.recvfrom(65535)
            if self.relay:
                self.out.sendto(d, ("127.0.0.1", RELAY_PORT))
            h = l2.split_header(d)
            if not h:
                continue
            if not l2.crc_ok(d, h[1]):
                with self.lock:
                    self.n_bad += 1
                continue
            with self.lock:
                self.last_rx = time.time()
                if h[0] == 102:
                    p = l2.parse_point(d)
                    if self.last_seq is not None and p["seq"] > self.last_seq + 1:
                        self.lost += p["seq"] - self.last_seq - 1
                    self.last_seq = p["seq"]
                    self.n_point += 1
                    self.state, self.line = p["state"], p["line"]
                elif h[0] == 104:
                    self.n_imu += 1
                    self.imu = l2.parse_imu(d)
                else:
                    self.events.put(d)

    def send(self, pkt):
        self.data.sendto(pkt, l2ctl.LIDAR)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Unitree L2 — panel")
        self.events = queue.Queue()
        self.link = Link(self.events)
        self.viewer = None
        self.mode = None
        self.fields = {}
        self._build()
        self.do_refresh()
        self.root.after(200, self._pump)
        self.root.after(1000, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # ---------- layout ----------
    def _build(self):
        pad = dict(padx=8, pady=4)
        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        self.dot = tk.Canvas(top, width=18, height=18, highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(3, 3, 16, 16, fill="grey")
        self.conn = ttk.Label(top, text="Łączenie…", font=("Segoe UI", 11, "bold"))
        self.conn.pack(side="left", padx=6)
        ttk.Label(top, text=f"lidar {l2ctl.LIDAR[0]}:{l2ctl.LIDAR[1]}").pack(side="right")

        st = ttk.LabelFrame(self.root, text="Status")
        st.pack(fill="x", **pad)
        rows = [("device", "Urządzenie"), ("rate", "Pakiety punktów"), ("points", "Punkty / s"),
                ("lost", "Zgubione pakiety"), ("rot", "Obrót (poziomy / pionowy)"),
                ("temp", "Temperatura APD / IMU"), ("volt", "Napięcie APD / lasera"),
                ("dirty", "Zabrudzenie osłony"), ("imu", "IMU"), ("mode", "Tryb pracy")]
        for r, (key, label) in enumerate(rows):
            ttk.Label(st, text=label + ":").grid(row=r, column=0, sticky="w", padx=6, pady=1)
            v = ttk.Label(st, text="—")
            v.grid(row=r, column=1, sticky="w", padx=6, pady=1)
            self.fields[key] = v

        bt = ttk.LabelFrame(self.root, text="Sterowanie")
        bt.pack(fill="x", **pad)
        buttons = [("▶ Start", self.do_start), ("⏸ Standby", self.do_standby),
                   ("⏱ Synchronizuj czas", self.do_timesync), ("⟳ Odśwież info", self.do_refresh),
                   ("⚠ Reset lidara", self.do_reset), ("Podgląd 3D", self.do_viewer)]
        for i, (txt, fn) in enumerate(buttons):
            ttk.Button(bt, text=txt, command=fn).grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
        for c in range(3):
            bt.columnconfigure(c, weight=1)

        md = ttk.LabelFrame(self.root, text="Tryb pracy (zapis trwały w lidarze)")
        md.pack(fill="x", **pad)
        self.bits = []
        for bit, name, off, on in l2ctl.MODE_BITS:
            var = tk.IntVar()
            ttk.Checkbutton(md, text=f"bit {bit} {name}: {on}   (odznaczone: {off})",
                            variable=var).pack(anchor="w", padx=6)
            self.bits.append((bit, var))
        ttk.Button(md, text="Zapisz tryb…", command=self.do_setmode).pack(anchor="e", padx=6, pady=4)

        lg = ttk.LabelFrame(self.root, text="Dziennik")
        lg.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(lg, height=8, width=90, font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True)

    def say(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S ") + msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---------- actions ----------
    def do_start(self):
        self.link.send(l2ctl.user_cmd(2, 0))
        self.say("TX start")

    def do_standby(self):
        self.link.send(l2ctl.user_cmd(2, 1))
        self.say("TX standby")

    def do_timesync(self):
        self.link.send(l2ctl.time_sync_pkt())
        self.say("TX timesync")

    def do_refresh(self):
        self.link.send(l2ctl.user_cmd(3))
        self.link.send(l2ctl.user_cmd(6))
        self.say("TX version + mode")

    def do_reset(self):
        if messagebox.askyesno("Reset", "Zrestartować lidar?"):
            self.link.send(l2ctl.user_cmd(1))
            self.say("TX reset")

    def do_viewer(self):
        if self.viewer and self.viewer.poll() is None:
            self.say("Podgląd 3D już działa")
            return
        self.link.relay = True
        py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
        self.viewer = subprocess.Popen([py, os.path.join(HERE, "live.py"), "1.0", str(RELAY_PORT)], cwd=HERE)
        self.say("Uruchomiono podgląd 3D")

    def do_setmode(self):
        mode = sum(var.get() << bit for bit, var in self.bits)
        if mode == self.mode:
            messagebox.showinfo("Tryb pracy", "Tryb się nie zmienia.")
            return
        msg = (f"Zapisać w lidarze tryb {mode} ({mode:05b})?\n\n{l2ctl.decode_mode(mode)}\n\n"
               "Zmiana jest trwała. Może wymagać wyłączenia i włączenia zasilania lidara.")
        if mode >> 3 & 1:
            msg += ("\n\nUWAGA: bit 3 przełącza lidar na UART. Po restarcie przestanie odpowiadać "
                    "po sieci i ten panel straci z nim kontakt. Powrót tylko przez port szeregowy.")
        if messagebox.askyesno("Zmiana trybu pracy", msg, icon="warning"):
            self.link.send(l2ctl.work_mode_pkt(mode))
            self.say(f"TX setmode {mode}")
            self.root.after(800, lambda: self.link.send(l2ctl.user_cmd(6)))

    # ---------- incoming ----------
    def _pump(self):
        while not self.events.empty():
            d = self.events.get()
            h = l2.split_header(d)
            if not h:
                continue
            if h[0] == 107:
                self.mode = struct.unpack_from("<I", d, 12)[0]
                self.fields["mode"].configure(
                    text=f"{self.mode} ({self.mode:05b}) — {l2ctl.decode_mode(self.mode)}")
                for bit, var in self.bits:
                    var.set(self.mode >> bit & 1)
                self.say(f"RX mode {self.mode}")
            elif h[0] == 105:
                self.fields["device"].configure(text=l2ctl.describe(d).replace("VERSION ", ""))
                self.say("RX version")
            else:
                self.say("RX " + l2ctl.describe(d))
        self.root.after(200, self._pump)

    def _tick(self):
        s = self.link.snapshot()
        age = time.time() - s["last_rx"] if s["last_rx"] else None
        if age is not None and age < 2:
            self.dot.itemconfigure(self.dot_id, fill="#2ecc40")
            self.conn.configure(text="Dane płyną")
        elif age is not None:
            self.dot.itemconfigure(self.dot_id, fill="#ffb000")
            self.conn.configure(text=f"Brak danych od {age:.0f} s (standby?)")
        else:
            self.dot.itemconfigure(self.dot_id, fill="#e74c3c")
            self.conn.configure(text="Brak danych z lidara")
        f = self.fields
        f["rate"].configure(text=f"{s['n_point']} /s" + (f"   (błędne CRC: {s['n_bad']})" if s["n_bad"] else ""))
        pts = s["n_point"] * (s["line"]["point_num"] if s["line"] else 0)
        f["points"].configure(text=f"{pts:,}".replace(",", " "))
        tot = s["n_point"] + s["lost"]
        f["lost"].configure(text=f"{s['lost']}  ({100 * s['lost'] / tot:.2f} %)" if tot else "—")
        st = s["state"]
        if st:
            if st["com_rot_period"] and st["sys_rot_period"]:
                f["rot"].configure(text=f"{1e6 / st['com_rot_period']:.2f} Hz / {1e6 / st['sys_rot_period']:.1f} Hz")
            else:
                f["rot"].configure(text="zatrzymany")
            f["temp"].configure(text=f"{st['apd_temp']:.1f} °C / {st['imu_temp']:.1f} °C")
            f["volt"].configure(text=f"{st['apd_voltage']:.1f} V / {st['laser_voltage']:.1f} V")
            f["dirty"].configure(text=f"{st['dirty_index']:.3f}")
        if s["imu"]:
            g, a = s["imu"]["gyro"], s["imu"]["acc"]
            f["imu"].configure(text=f"{s['n_imu']} /s  gyro [{g[0]:+.3f} {g[1]:+.3f} {g[2]:+.3f}] rad/s  "
                               f"acc [{a[0]:+.2f} {a[1]:+.2f} {a[2]:+.2f}] m/s²")
        elif self.mode is not None and self.mode >> 2 & 1:
            f["imu"].configure(text="wyłączone w trybie pracy")
        self.root.after(1000, self._tick)

    def _close(self):
        if self.viewer and self.viewer.poll() is None:
            self.viewer.terminate()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        App(root)
    except OSError as e:
        messagebox.showerror("Unitree L2", f"Nie mogę otworzyć portu UDP {DATA_PORT}.\n"
                             f"Zamknij inny program odbierający dane z lidara.\n\n{e}")
        sys.exit(1)
    root.mainloop()
