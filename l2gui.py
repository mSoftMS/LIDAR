"""Small Tk control panel for the Unitree L2 lidar over UDP or UART."""
import os, queue, socket, struct, subprocess, sys, threading, time
import tkinter as tk
from tkinter import messagebox, ttk
import l2, l2ctl

DATA_PORT = 6201          # lidar streams here
RELAY_PORT = 6202         # copy of the stream for the 3D viewer
HOST_IP = "192.168.1.2"   # the lidar sends to this address
IFACE = "Wi-Fi"           # host interface that carries HOST_IP as a second address
DEFAULT_COM = "COM4"
HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(HERE, "venv", "Scripts", "python.exe")


class Link:
    """Common frame handling; subclasses own the transport.

    Non-stream frames (ACK, version, mode) go to the events queue.
    """

    def __init__(self, events):
        self.events = events
        self.relay = False
        self.out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.alive = True
        self.lock = threading.Lock()
        self.n_point = self.n_imu = self.n_bad = self.lost = 0
        self.last_seq = None
        self.last_rx = 0.0
        self.state = self.line = self.imu = None

    def start(self):
        threading.Thread(target=self._rx, daemon=True).start()

    def snapshot(self):
        """Return counters for the last interval and reset them."""
        with self.lock:
            s = dict(n_point=self.n_point, n_imu=self.n_imu, n_bad=self.n_bad, lost=self.lost,
                     last_rx=self.last_rx, state=self.state, line=self.line, imu=self.imu)
            self.n_point = self.n_imu = self.n_bad = self.lost = 0
        return s

    def _handle(self, d):
        if self.relay:
            self.out.sendto(d, ("127.0.0.1", RELAY_PORT))
        h = l2.split_header(d)
        if not h:
            return
        if not l2.crc_ok(d, h[1]):
            with self.lock:
                self.n_bad += 1
            return
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


class UdpLink(Link):
    """The lidar streams to the source address of the last command it received, so
    commands must leave from the same socket that receives the data.
    """
    name = f"Ethernet UDP {DATA_PORT}"

    def __init__(self, events):
        super().__init__(events)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
        self.sock.bind(("0.0.0.0", DATA_PORT))
        self.start()

    def _rx(self):
        while self.alive:
            try:
                d, _ = self.sock.recvfrom(65535)
            except OSError:
                if not self.alive:
                    break
                continue    # e.g. ICMP port unreachable reported on Windows
            self._handle(d)

    def send(self, pkt):
        self.sock.sendto(pkt, l2ctl.LIDAR)

    def close(self):
        self.alive = False
        self.sock.close()


class SerialLink(Link):
    def __init__(self, events, port):
        super().__init__(events)
        import serial
        self.ser = serial.Serial(port, l2ctl.UART_BAUD, timeout=0.1)
        self.name = f"UART {port} @ {l2ctl.UART_BAUD // 1000000} Mbps"
        self.split = l2.FrameSplitter()
        self.start()

    def _rx(self):
        while self.alive:
            try:
                data = self.ser.read(self.ser.in_waiting or 1)
            except Exception:
                break
            for d in self.split.feed(data):
                self._handle(d)

    def send(self, pkt):
        self.ser.write(pkt)

    def close(self):
        self.alive = False
        self.ser.close()


def com_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return sorted(p.device for p in list_ports.comports())


def host_ip_present():
    """HOST_IP is assigned locally iff a socket can bind to it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((HOST_IP, 0))
        return True
    except OSError:
        return False
    finally:
        s.close()


def run_elevated(cmd):
    """Run a PowerShell command through UAC; returns True when it ran (not cancelled)."""
    outer = ("try { Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden "
             f"-ArgumentList '-NoProfile','-Command','{cmd}'; exit 0 }} catch {{ exit 1 }}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", outer],
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode == 0


class App:
    def __init__(self, root):
        self.root = root
        root.title("Unitree L2 — panel")
        self.events = queue.Queue()
        self.notes = queue.Queue()      # log lines from worker threads
        self.link = None
        self.viewer = None
        self.mode = None
        self.fields = {}
        self.net_busy = False
        self._build()
        self.do_connect()
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
        self.where = ttk.Label(top, text="")
        self.where.pack(side="right")

        cn = ttk.LabelFrame(self.root, text="Połączenie z lidarem")
        cn.pack(fill="x", **pad)
        self.transport = tk.StringVar(value="udp")
        ttk.Radiobutton(cn, text=f"Ethernet ({l2ctl.LIDAR[0]}, UDP {DATA_PORT})",
                        variable=self.transport, value="udp").grid(row=0, column=0, sticky="w", padx=6)
        ttk.Radiobutton(cn, text=f"UART ({l2ctl.UART_BAUD // 1000000} Mbps):",
                        variable=self.transport, value="uart").grid(row=0, column=1, sticky="w", padx=(18, 2))
        ports = com_ports()
        self.com = ttk.Combobox(cn, width=8, values=ports, postcommand=self._refresh_ports)
        self.com.set(DEFAULT_COM if DEFAULT_COM in ports or not ports else ports[0])
        self.com.grid(row=0, column=2, sticky="w")
        ttk.Button(cn, text="Połącz", command=self.do_connect).grid(row=0, column=3, sticky="e", padx=6, pady=4)
        cn.columnconfigure(3, weight=1)

        net = ttk.LabelFrame(self.root, text=f"Sieć hosta (adres {HOST_IP} na karcie {IFACE})")
        net.pack(fill="x", **pad)
        self.net_lbl = ttk.Label(net, text="—")
        self.net_lbl.grid(row=0, column=0, sticky="w", padx=6)
        self.btn_add = ttk.Button(net, text="Dodaj adres", command=self.do_ip_add, state="disabled")
        self.btn_add.grid(row=0, column=1, sticky="e", padx=4, pady=4)
        self.btn_del = ttk.Button(net, text="Usuń adres", command=self.do_ip_del, state="disabled")
        self.btn_del.grid(row=0, column=2, sticky="e", padx=6, pady=4)
        net.columnconfigure(0, weight=1)

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

    def _refresh_ports(self):
        self.com.configure(values=com_ports())

    def say(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S ") + msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def tx(self, pkt, label):
        if not self.link:
            self.say(f"{label}: brak połączenia")
            return False
        try:
            self.link.send(pkt)
        except Exception as e:
            self.say(f"{label}: błąd wysyłania: {e}")
            return False
        self.say("TX " + label)
        return True

    # ---------- connection ----------
    def do_connect(self):
        relay = bool(self.link and self.link.relay)
        if self.link:
            self.link.close()
            self.link = None
        self.mode = None    # values read over the previous link are stale now
        for v in self.fields.values():
            v.configure(text="—")
        try:
            if self.transport.get() == "uart":
                self.link = SerialLink(self.events, self.com.get().strip())
            else:
                self.link = UdpLink(self.events)
        except ImportError:
            self.say("Brak modułu pyserial: venv\\Scripts\\pip install pyserial")
        except Exception as e:
            what = self.com.get() if self.transport.get() == "uart" else f"portu UDP {DATA_PORT}"
            self.say(f"Nie mogę otworzyć {what}: {e}")
            if self.transport.get() == "udp":
                self.say("Zamknij inny program odbierający dane z lidara (l2ctl.py, listen.py, live.py).")
        if not self.link:
            self.where.configure(text="rozłączony")
            return
        self.link.relay = relay
        self.where.configure(text=self.link.name)
        self.say("Połączono: " + self.link.name)
        self.do_refresh()

    # ---------- host network ----------
    def _net_update(self):
        present = host_ip_present()
        self.net_lbl.configure(text=f"{HOST_IP} jest na tym komputerze" if present
                               else f"brak adresu {HOST_IP} — lidar nie ma dokąd nadawać")
        busy = "disabled" if self.net_busy else None
        self.btn_add.configure(state=busy or ("disabled" if present else "normal"))
        self.btn_del.configure(state=busy or ("normal" if present else "disabled"))

    def _net_run(self, what, cmd):
        self.net_busy = True
        self._net_update()
        self.say(f"{what}: potwierdź w okienku UAC…")

        def work():
            ok = run_elevated(cmd)
            self.notes.put(f"{what}: " + ("wykonano" if ok else "anulowano lub błąd"))
            self.net_busy = False
        threading.Thread(target=work, daemon=True).start()

    def do_ip_add(self):
        self._net_run(f"Dodanie adresu {HOST_IP}",
                      f'netsh interface ipv4 set interface \\"{IFACE}\\" dhcpstaticipcoexistence=enabled; '
                      f'netsh interface ipv4 add address \\"{IFACE}\\" {HOST_IP} 255.255.255.0')

    def do_ip_del(self):
        if self.transport.get() == "udp" and not messagebox.askyesno(
                "Usunięcie adresu", f"Usunąć {HOST_IP} z karty {IFACE}?\n\n"
                "Panel przestanie odbierać dane z lidara po sieci."):
            return
        self._net_run(f"Usunięcie adresu {HOST_IP}",
                      f'netsh interface ipv4 delete address \\"{IFACE}\\" {HOST_IP}; '
                      f'netsh interface ipv4 set interface \\"{IFACE}\\" dhcpstaticipcoexistence=disabled')

    # ---------- actions ----------
    def do_start(self):
        self.tx(l2ctl.user_cmd(2, 0), "start")

    def do_standby(self):
        self.tx(l2ctl.user_cmd(2, 1), "standby")

    def do_timesync(self):
        self.tx(l2ctl.time_sync_pkt(), "timesync")

    def do_refresh(self):
        if self.tx(l2ctl.user_cmd(3), "version"):
            self.tx(l2ctl.user_cmd(6), "mode")

    def do_reset(self):
        if messagebox.askyesno("Reset", "Zrestartować lidar?"):
            self.tx(l2ctl.user_cmd(1), "reset")

    def do_viewer(self):
        if self.viewer and self.viewer.poll() is None:
            self.say("Podgląd 3D już działa")
            return
        if not self.link:
            self.say("Podgląd 3D: brak połączenia")
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
        to_uart = mode >> 3 & 1
        if to_uart and self.transport.get() == "udp":
            msg += ("\n\nUWAGA: bit 3 przełącza lidar na UART. Po restarcie przestanie odpowiadać "
                    "po sieci. Wtedy wybierz w panelu „UART” i kliknij „Połącz”. "
                    "Powrót do Ethernetu jest możliwy tylko przez port szeregowy.")
        elif not to_uart and self.transport.get() == "uart":
            msg += ("\n\nLidar wróci na Ethernet. Po restarcie wybierz w panelu „Ethernet” "
                    "i kliknij „Połącz”.")
        if messagebox.askyesno("Zmiana trybu pracy", msg, icon="warning"):
            if self.tx(l2ctl.work_mode_pkt(mode), f"setmode {mode}"):
                self.root.after(800, lambda: self.tx(l2ctl.user_cmd(6), "mode"))

    # ---------- incoming ----------
    def _pump(self):
        while not self.notes.empty():
            self.say(self.notes.get())
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
        self._net_update()
        if not self.link:
            self.dot.itemconfigure(self.dot_id, fill="#e74c3c")
            self.conn.configure(text="Brak połączenia")
            self.root.after(1000, self._tick)
            return
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
        if self.link:
            self.link.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
