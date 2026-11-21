# -*- coding: utf-8 -*-
"""NASHAMA - Input Devices Toolkit (Windows)"""
import os, sys, time, json, colorsys, threading, subprocess, queue
from collections import deque
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from pynput import keyboard as kb, mouse as ms
import pygame

BG, PN, PN2, TX, DM, OK, BAD = "#0d1117", "#161b22", "#21262d", "#e6edf3", "#8b949e", "#3fb950", "#f85149"
CHATTER = 0.04
NOWIN = 0x08000000 if os.name == "nt" else 0
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Nashama")
CFG = os.path.join(CFG_DIR, "config.json")
DEF = {"accent": "#f5b301", "kb_color": "#f5b301", "kb_press": "#ffffff", "ms_color": "#f5b301",
       "effect": "Static", "alpha": 1.0, "topmost": False, "padmap": {}, "padturbo": {}, "turbo_cps": 15}
PRESETS = {"Gold": "#f5b301", "Cyan": "#22d3ee", "Magenta": "#e040fb", "Lime": "#7cfc00", "Red": "#ff3b3b", "White": "#ffffff"}


def load_cfg():
    try:
        return {**DEF, **json.load(open(CFG, encoding="utf-8"))}
    except Exception:
        return dict(DEF)


def save_cfg(c):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        json.dump(c, open(CFG, "w", encoding="utf-8"))
    except Exception:
        pass


def alive(w):
    try:
        return w is not None and w.winfo_exists()
    except Exception:
        return False


def blend(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(pa[i] * t + pb[i] * (1 - t)) for i in range(3))


def hsv(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1, 0.9, 1)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                           creationflags=NOWIN, timeout=25)
        return r.stdout.strip()
    except Exception:
        return ""


def list_devices():
    out = ps("Get-PnpDevice -PresentOnly | Where-Object {$_.Class -in 'Keyboard','Mouse','HIDClass','XboxComposite'}"
             " | Select-Object FriendlyName,Class,InstanceId,Status | ConvertTo-Json")
    try:
        d = json.loads(out)
        return d if isinstance(d, list) else [d]
    except Exception:
        return []


def is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


kbc, msc = kb.Controller(), ms.Controller()


def parse_target(s):
    s = (s or "").strip().lower().replace(" click", "")
    if s in ("", "(none)", "none"):
        return None
    btn = {"left": ms.Button.left, "right": ms.Button.right, "middle": ms.Button.middle}
    if s in btn:
        return btn[s]
    if len(s) == 1:
        return s
    return getattr(kb.Key, s, None)


def press(t, down):
    if t is None:
        return
    try:
        if isinstance(t, ms.Button):
            (msc.press if down else msc.release)(t)
        else:
            (kbc.press if down else kbc.release)(t)
    except Exception:
        pass


class Macro:
    def __init__(self):
        self.on, self.target, self.cps = False, "f5", 10.0

    def start(self):
        if not self.on:
            self.on = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.on = False

    def _run(self):
        while self.on:
            t0 = time.perf_counter()
            t = parse_target(self.target)
            if t is not None:
                if isinstance(t, ms.Button):
                    msc.click(t)
                else:
                    kbc.press(t); kbc.release(t)
            time.sleep(max(0.0, 1 / max(self.cps, 0.1) - (time.perf_counter() - t0)))


def kname(k):
    n = k.char.upper() if isinstance(k, kb.KeyCode) and k.char else str(k).replace("Key.", "").upper()
    for b in ("SHIFT", "CTRL", "ALT"):
        if n == b or n.startswith(b + "_"):
            return b
    return n


def kid(n):
    return "k" + n.encode("utf-8").hex()


ROWS = [
    [("ESC", "Esc", 1), (None, "", 1)] + [("F%d" % i, "F%d" % i, 1) for i in range(1, 13)],
    [(c, c, 1) for c in "`1234567890-="] + [("BACKSPACE", "Bksp", 2)],
    [("TAB", "Tab", 1.5)] + [(c.upper(), c.upper(), 1) for c in "qwertyuiop[]"] + [("\\", "\\", 1.5)],
    [("CAPS_LOCK", "Caps", 1.8)] + [(c.upper(), c.upper(), 1) for c in "asdfghjkl;'"] + [("ENTER", "Enter", 2.2)],
    [("SHIFT", "Shift", 2.3)] + [(c.upper(), c.upper(), 1) for c in "zxcvbnm,./"] + [("SHIFT", "Shift", 2.7), (None, "", 0.5), ("UP", "^", 1)],
    [("CTRL", "Ctrl", 1.5), ("CMD", "Win", 1.25), ("ALT", "Alt", 1.25), ("SPACE", "", 6.25), ("ALT", "Alt", 1.25),
     ("CMD", "Win", 1.25), ("CTRL", "Ctrl", 1.5), (None, "", 0.25), ("LEFT", "<", 1), ("DOWN", "v", 1), ("RIGHT", ">", 1)],
]


class KeyboardView(tk.Canvas):
    def __init__(self, parent, app, U=36):
        super().__init__(parent, width=int(18.6 * U), height=int(6.5 * U), bg=BG, highlightthickness=0)
        self.app, self.keys, self.W = app, {}, 18.6 * U
        y = 0.1
        for r, row in enumerate(ROWS):
            x = 0.1
            for name, label, w in row:
                if name:
                    x0, y0 = x * U, y * U
                    rid = self.create_rectangle(x0, y0, x0 + w * U - 4, y0 + U - 4, fill=PN, outline=DM, width=2)
                    tid = self.create_text(x0 + (w * U - 4) / 2, y0 + (U - 4) / 2, text=label, fill=DM, font=("Segoe UI", 9, "bold"))
                    self.keys.setdefault(name, []).append((rid, tid, x0 / self.W))
                x += w
            y += 1.35 if r == 0 else 1
        self.update_colors()

    def col(self, xr, t):
        c, eff = self.app.cfg, self.app.cfg["effect"]
        if eff == "Rainbow":
            return hsv(xr + t * 0.25)
        if eff == "Breathing":
            return blend(c["kb_color"], PN, 0.35 + 0.65 * (0.5 + 0.5 * __import__("math").sin(t * 2.2)))
        return c["kb_color"]

    def update_colors(self):
        t, pc = time.time(), self.app.cfg["kb_press"]
        for name, items in self.keys.items():
            down = name in self.app.kdown
            for rid, tid, xr in items:
                c = self.col(xr, t)
                self.itemconfig(rid, fill=pc if down else PN, outline=pc if down else c)
                self.itemconfig(tid, fill="#000000" if down else c)


class MouseView(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, width=170, height=230, bg=BG, highlightthickness=0)
        self.app = app
        self.body = self.create_oval(10, 5, 160, 225, fill=PN, outline=DM, width=3)
        self.L = self.create_polygon(30, 60, 45, 30, 82, 18, 82, 95, 30, 95, fill=PN, outline=DM, width=2)
        self.R = self.create_polygon(140, 60, 125, 30, 88, 18, 88, 95, 140, 95, fill=PN, outline=DM, width=2)
        self.M = self.create_rectangle(78, 40, 92, 75, fill=PN, outline=DM, width=2)
        self.update_colors()

    def update_colors(self):
        c, pc, d = self.app.cfg["ms_color"], self.app.cfg["kb_press"], self.app.mdown
        wheel = time.time() - self.app.wheel_t < 0.15
        self.itemconfig(self.body, outline=c)
        for item, name, on in ((self.L, "left", "left" in d), (self.R, "right", "right" in d), (self.M, "middle", "middle" in d or wheel)):
            self.itemconfig(item, fill=pc if on else PN, outline=c)


class PadView(tk.Canvas):
    XB = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5, "BACK": 6, "START": 7, "L3": 8, "R3": 9}
    PS = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 9, "RB": 10, "BACK": 4, "START": 6, "L3": 7, "R3": 8}

    def __init__(self, parent, app):
        super().__init__(parent, width=400, height=260, bg=BG, highlightthickness=0)
        self.app, self.it = app, {}
        c = app.cfg["ms_color"]
        for box in ((30, 120, 130, 250), (270, 120, 370, 250), (50, 50, 350, 210)):
            self.create_oval(*box, fill=PN, outline=c, width=2)
        self.create_oval(53, 53, 347, 207, fill=PN, outline=PN)
        part = lambda n, box, col, kind="r": self.it.__setitem__(n, (
            (self.create_oval if kind == "o" else self.create_rectangle)(*box, fill=PN, outline=col, width=2), col))
        for n, box in (("LT", (70, 14, 140, 36)), ("RT", (260, 14, 330, 36)), ("LB", (60, 40, 150, 56)), ("RB", (250, 40, 340, 56)),
                       ("UP", (152, 136, 168, 152)), ("DOWN", (152, 168, 168, 184)), ("LEFT", (136, 152, 152, 168)), ("RIGHT", (168, 152, 184, 168))):
            part(n, box, c)
        part("L3", (86, 76, 138, 128), c, "o"); part("R3", (226, 138, 278, 190), c, "o")
        part("BACK", (172, 92, 192, 104), c, "o"); part("START", (208, 92, 228, 104), c, "o")
        for n, (x, y), col in (("Y", (300, 78), "#e3b341"), ("A", (300, 122), "#3fb950"), ("X", (278, 100), "#58a6ff"), ("B", (322, 100), "#f85149")):
            part(n, (x - 11, y - 11, x + 11, y + 11), col, "o")
            self.create_text(x, y, text=n, fill=col, font=("Segoe UI", 9, "bold"))
        for n, tx, ty in (("LT", 105, 25), ("RT", 295, 25), ("LB", 105, 48), ("RB", 295, 48)):
            self.create_text(tx, ty, text=n, fill=DM, font=("Segoe UI", 8))
        self.ld = self.create_oval(103, 93, 121, 111, fill=c, outline="")
        self.rd = self.create_oval(243, 155, 261, 173, fill=c, outline="")

    def lit(self, name, on):
        if name in self.it:
            i, col = self.it[name]
            self.itemconfig(i, fill=col if on else PN)

    def sticks(self, lx, ly, rx, ry):
        self.coords(self.ld, 103 + lx * 14, 93 + ly * 14, 121 + lx * 14, 111 + ly * 14)
        self.coords(self.rd, 243 + rx * 14, 155 + ry * 14, 261 + rx * 14, 173 + ry * 14)


ACTIONS = (["(none)"] + list("abcdefghijklmnopqrstuvwxyz0123456789") + ["space", "enter", "shift", "ctrl", "alt", "tab", "esc", "up", "down", "left", "right"]
           + ["f%d" % i for i in range(1, 13)] + ["left click", "right click", "middle click"])
PADROWS = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "BACK", "START", "L3", "R3", "UP", "DOWN", "LEFT", "RIGHT"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.title("NASHAMA"); self.geometry("720x690"); self.configure(bg=BG); self.minsize(700, 660)
        self.q = queue.Queue(); self.dev_names = ([], []); self.pads = {}; self.wins = {}
        self.kstat, self.mstat, self.pstat = {}, {}, {}
        self.kdown, self.klast_up, self.mlast = {}, {}, {}
        self.mdown, self.wheel_t, self.moves, self.maxhz, self.hz, self.sp = set(), 0, [], 0, 0, 0
        self.clicks, self.keyhits = deque(), deque()
        self.mac, self.hotkey, self.padmacros, self.trig, self.hatprev = Macro(), "f6", {}, {}, set()
        self.m_t, self.m_c, self.m_h = tk.StringVar(value="f5"), tk.StringVar(value="10"), tk.StringVar(value="f6")
        self.kt = self.mt = self.pv = self.klab = self.mlab = self.dmsg = self.dt = self.mstate = self.pt = None
        self.prow = {}
        self.sty(); self.build()
        self.attributes("-topmost", self.cfg["topmost"]); self.attributes("-alpha", self.cfg["alpha"])
        pygame.init(); pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i); self.pads[j.get_instance_id()] = j
        kb.Listener(on_press=lambda k: self.q.put(("kd", kname(k), time.perf_counter())),
                    on_release=lambda k: self.q.put(("ku", kname(k), time.perf_counter())), daemon=True).start()
        ms.Listener(on_move=lambda x, y: self.moves.append((time.perf_counter(), x, y)),
                    on_click=lambda x, y, b, p: self.q.put(("mc", str(b).replace("Button.", ""), time.perf_counter(), p)),
                    on_scroll=lambda x, y, dx, dy: self.q.put(("wh",)), daemon=True).start()
        self.refresh_devices()
        self.after(30, self.loop); self.after(16, self.pad_loop); self.after(250, self.mouse_calc)
        self.after(50, self.anim); self.after(200, self.tick_info); self.after(3000, self.auto_refresh)

    def sty(self):
        a = self.cfg["accent"]; s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TX, fieldbackground=PN, font=("Segoe UI", 10))
        s.configure("Treeview", background=PN, fieldbackground=PN, foreground=TX, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=PN2, foreground=a, font=("Segoe UI", 10, "bold"))
        s.configure("TButton", background=a, foreground="#000", padding=8, font=("Segoe UI", 10, "bold"))
        s.map("TButton", background=[("active", blend(a, "#ffffff", 0.75))])
        s.configure("TFrame", background=BG); s.configure("TLabel", background=BG)
        s.configure("TCheckbutton", background=BG, foreground=TX)

    def tree(self, parent, cols, widths, h=9):
        t = ttk.Treeview(parent, columns=cols, show="headings", height=h)
        for c, w in zip(cols, widths):
            t.heading(c, text=c); t.column(c, width=w, anchor="center")
        t.tag_configure("bad", foreground=BAD); t.tag_configure("ok", foreground=OK)
        return t

    def lbl(self, parent, text, **k):
        return tk.Label(parent, text=text, bg=BG, fg=k.pop("fg", TX), **k)

    # ---------- home ----------
    def build(self):
        a = self.cfg["accent"]
        hd = tk.Frame(self, bg=BG); hd.pack(fill="x", padx=14, pady=(12, 2))
        lg = tk.Canvas(hd, width=52, height=52, bg=BG, highlightthickness=0); lg.pack(side="left")
        self.logo = lg.create_polygon(26, 2, 48, 9, 48, 28, 26, 50, 4, 28, 4, 9, fill=a)
        lg.create_text(26, 27, text="N", font=("Segoe UI", 20, "bold"), fill="#000")
        tf = tk.Frame(hd, bg=BG); tf.pack(side="left", padx=10)
        self.title_l = tk.Label(tf, text="NASHAMA", bg=BG, fg=a, font=("Segoe UI", 24, "bold")); self.title_l.pack(anchor="w")
        self.lbl(tf, "Input Devices Toolkit", fg=DM).pack(anchor="w")
        self.lbl(hd, "Admin" if is_admin() else "Not admin (device control needs Admin)", fg=OK if is_admin() else DM).pack(side="right")
        bar = tk.Frame(self, bg=BG); bar.pack(pady=8)
        for txt, fn in (("Keyboard Lab", self.w_kb), ("Mouse Lab", self.w_ms), ("Gamepad", self.w_pad),
                        ("Macros", self.w_mac), ("Devices", self.w_dev), ("Style", self.w_style)):
            ttk.Button(bar, text=txt, command=fn).pack(side="left", padx=4)
        self.kv = KeyboardView(self, self); self.kv.pack(padx=14, pady=6)
        bt = tk.Frame(self, bg=BG); bt.pack(fill="x", padx=14, pady=6)
        self.mv = MouseView(bt, self); self.mv.pack(side="left")
        self.info = tk.Label(bt, text="", bg=BG, fg=TX, justify="left", anchor="nw", font=("Consolas", 11), wraplength=480)
        self.info.pack(side="left", fill="both", expand=True, padx=16)

    def apply_theme(self):
        a = self.cfg["accent"]
        self.title_l.config(fg=a); self.sty()
        self.attributes("-topmost", self.cfg["topmost"]); self.attributes("-alpha", self.cfg["alpha"])
        save_cfg(self.cfg)

    def open_win(self, key, title, size, builder):
        w = self.wins.get(key)
        if alive(w):
            w.deiconify(); w.lift(); w.focus_force(); return
        w = tk.Toplevel(self); w.title(title); w.geometry(size); w.configure(bg=BG); self.wins[key] = w
        builder(w)

    # ---------- keyboard / mouse labs ----------
    def w_kb(self): self.open_win("kb", "NASHAMA - Keyboard Lab", "640x440", self.b_kb)

    def b_kb(self, w):
        self.klab = self.lbl(w, "Press any key...", fg=self.cfg["accent"], font=("Segoe UI", 20, "bold")); self.klab.pack(pady=8)
        self.kt = self.tree(w, ("Key", "Presses", "Avg hold ms", "Bounces", "Status"), (120, 100, 130, 100, 130), 12)
        self.kt.pack(fill="both", expand=True, padx=8, pady=6)
        ttk.Button(w, text="Reset stats", command=lambda: (self.kstat.clear(), self.kt.delete(*self.kt.get_children()))).pack(pady=6)
        for n in self.kstat: self.draw_k(n)

    def w_ms(self): self.open_win("ms", "NASHAMA - Mouse Lab", "560x400", self.b_ms)

    def b_ms(self, w):
        self.mlab = self.lbl(w, "Move the mouse...", fg=self.cfg["accent"], font=("Segoe UI", 15, "bold")); self.mlab.pack(pady=8)
        self.mt = self.tree(w, ("Button", "Clicks", "Bounces", "Status"), (130, 110, 110, 130), 8)
        self.mt.pack(fill="both", expand=True, padx=8, pady=6)
        ttk.Button(w, text="Reset stats", command=self.reset_mouse).pack(pady=6)
        for n in self.mstat: self.draw_m(n)

    def verdict(self, n, ch, avg=None):
        if ch >= 1 or (avg is not None and n >= 5 and avg < 15):
            return "Weak", "bad"
        return "OK", "ok"

    def draw_k(self, n):
        if not alive(self.kt): return
        s = self.kstat[n]; avg = sum(s["d"]) / len(s["d"]) if s["d"] else 0
        v, tag = self.verdict(s["n"], s["ch"], avg if s["d"] else None)
        vals = (n, s["n"], "%.0f" % avg, s["ch"], v); i = kid(n)
        if self.kt.exists(i): self.kt.item(i, values=vals, tags=(tag,))
        else: self.kt.insert("", "end", iid=i, values=vals, tags=(tag,))

    def draw_m(self, b):
        if not alive(self.mt): return
        s = self.mstat[b]; v, tag = self.verdict(s["n"], s["ch"]); vals = (b, s["n"], s["ch"], v)
        if self.mt.exists(kid(b)): self.mt.item(kid(b), values=vals, tags=(tag,))
        else: self.mt.insert("", "end", iid=kid(b), values=vals, tags=(tag,))

    def reset_mouse(self):
        self.mstat.clear(); self.mlast.clear(); self.maxhz = 0
        if alive(self.mt): self.mt.delete(*self.mt.get_children())

    # ---------- gamepad ----------
    def pad_layout(self):
        j = next(iter(self.pads.values()), None)
        n = (j.get_name() if j else "").lower()
        return PadView.PS if any(x in n for x in ("dualsense", "dualshock", "wireless controller", "playstation", "ps4", "ps5")) else PadView.XB

    def w_pad(self): self.open_win("pad", "NASHAMA - Gamepad", "960x600", self.b_pad)

    def b_pad(self, w):
        L = tk.Frame(w, bg=BG); L.pack(side="left", padx=10, pady=10)
        self.plab = self.lbl(L, "", fg=self.cfg["accent"], font=("Segoe UI", 13, "bold")); self.plab.pack(pady=4)
        self.pv = PadView(L, self); self.pv.pack()
        self.lbl(L, "Highlight assumes Xbox / PlayStation layout.\nMapping below works with any pad.", fg=DM).pack(pady=6)
        f = tk.Frame(L, bg=BG); f.pack(pady=4)
        self.lbl(f, "Turbo clicks/sec").pack(side="left")
        self.tcps = tk.StringVar(value=str(self.cfg["turbo_cps"]))
        ttk.Entry(f, textvariable=self.tcps, width=6).pack(side="left", padx=6)
        R = tk.Frame(w, bg=BG); R.pack(side="left", fill="both", expand=True, padx=6, pady=10)
        for c, t in enumerate(("Button", "Action", "Turbo", "Presses", "Status")):
            tk.Label(R, text=t, bg=PN2, fg=self.cfg["accent"], font=("Segoe UI", 10, "bold")).grid(row=0, column=c, sticky="ew", padx=1, pady=1)
        self.prow = {}
        for r, n in enumerate(PADROWS, 1):
            self.lbl(R, n).grid(row=r, column=0, pady=2)
            v = tk.StringVar(value=self.cfg["padmap"].get(n, "(none)"))
            v.trace_add("write", lambda *a, n=n, v=v: (self.cfg["padmap"].__setitem__(n, v.get()), save_cfg(self.cfg)))
            ttk.Combobox(R, textvariable=v, values=ACTIONS, width=12).grid(row=r, column=1, padx=4)
            tv = tk.BooleanVar(value=self.cfg["padturbo"].get(n, False))
            tv.trace_add("write", lambda *a, n=n, tv=tv: (self.cfg["padturbo"].__setitem__(n, tv.get()), save_cfg(self.cfg)))
            ttk.Checkbutton(R, variable=tv).grid(row=r, column=2)
            c1, c2 = self.lbl(R, "0"), self.lbl(R, "-", fg=DM)
            c1.grid(row=r, column=3); c2.grid(row=r, column=4, padx=8)
            self.prow[n] = (c1, c2)
        self.on_pad_change()
        for n in self.pstat: self.draw_pad_row(n)

    def on_pad_change(self):
        if alive(getattr(self, "plab", None)):
            j = next(iter(self.pads.values()), None)
            self.plab.config(text=("Controller: " + j.get_name()) if j else "Connect a controller...")

    def draw_pad_row(self, n):
        if n in self.prow and alive(self.prow[n][0]):
            s = self.pstat[n]; v, tag = self.verdict(s["n"], s["ch"])
            self.prow[n][0].config(text=str(s["n"])); self.prow[n][1].config(text=v, fg=OK if tag == "ok" else BAD)

    def pad_event(self, name, down):
        ts = time.perf_counter()
        st = self.pstat.setdefault(name, {"n": 0, "ch": 0, "up": 0})
        if down:
            st["n"] += 1
            if ts - st["up"] < CHATTER: st["ch"] += 1
        else:
            st["up"] = ts
        if alive(self.pv): self.pv.lit(name, down)
        self.draw_pad_row(name)
        tgt = self.cfg["padmap"].get(name); t = parse_target(tgt)
        if t is None: return
        if self.cfg["padturbo"].get(name):
            m = self.padmacros.setdefault(name, Macro()); m.target = tgt
            try: m.cps = float(self.cfg["turbo_cps"])
            except ValueError: m.cps = 15
            m.start() if down else m.stop()
        else:
            press(t, down)

    def pad_loop(self):
        lay = self.pad_layout(); rev = {v: k for k, v in lay.items()}
        for e in pygame.event.get():
            if e.type == pygame.JOYDEVICEADDED:
                j = pygame.joystick.Joystick(e.device_index); self.pads[j.get_instance_id()] = j; self.on_pad_change()
            elif e.type == pygame.JOYDEVICEREMOVED:
                self.pads.pop(e.instance_id, None); self.on_pad_change()
            elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                self.pad_event(rev.get(e.button, "BTN%d" % e.button), e.type == pygame.JOYBUTTONDOWN)
            elif e.type == pygame.JOYHATMOTION:
                x, y = e.value
                now = {n for n, c in (("LEFT", x < 0), ("RIGHT", x > 0), ("UP", y > 0), ("DOWN", y < 0)) if c}
                for n in now - self.hatprev: self.pad_event(n, True)
                for n in self.hatprev - now: self.pad_event(n, False)
                self.hatprev = now
        j = next(iter(self.pads.values()), None)
        if j:
            try:
                if j.get_numaxes() >= 6:
                    for n, ax in (("LT", 4), ("RT", 5)):
                        on = j.get_axis(ax) > 0.2
                        if on != self.trig.get(n, False): self.trig[n] = on; self.pad_event(n, on)
                if alive(self.pv): self.pv.sticks(j.get_axis(0), j.get_axis(1), j.get_axis(2), j.get_axis(3))
            except Exception:
                pass
        try: self.cfg["turbo_cps"] = float(self.tcps.get())
        except Exception: pass
        self.after(16, self.pad_loop)

    # ---------- macros ----------
    def w_mac(self): self.open_win("mac", "NASHAMA - Macros", "520x300", self.b_mac)

    def b_mac(self, w):
        c = tk.LabelFrame(w, text="Keyboard / mouse macro", bg=BG, fg=self.cfg["accent"], font=("Segoe UI", 11, "bold"), padx=10, pady=8)
        c.pack(fill="x", padx=12, pady=12)
        for i, (l, v) in enumerate((("Key to repeat (f5 / a / left click)", self.m_t), ("Presses per second", self.m_c), ("Start/stop hotkey", self.m_h))):
            self.lbl(c, l).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            ttk.Entry(c, textvariable=v, width=14).grid(row=i, column=1, pady=4)
        self.mstate = self.lbl(c, "Stopped", fg=BAD, font=("Segoe UI", 12, "bold")); self.mstate.grid(row=3, column=0, columnspan=2, pady=4)
        ttk.Button(c, text="Apply / Start-Stop", command=self.mac_toggle).grid(row=4, column=0, columnspan=2, pady=4)
        self.lbl(w, "Gamepad button macros: Gamepad window > Action + Turbo.\nSome online games block macros (anti-cheat). Use at your own risk.", fg=DM).pack(pady=8)

    def mac_toggle(self):
        self.mac.target = self.m_t.get()
        try: self.mac.cps = float(self.m_c.get())
        except ValueError: self.mac.cps = 10
        self.mac.stop() if self.mac.on else self.mac.start()
        if alive(self.mstate):
            self.mstate.config(text="Running" if self.mac.on else "Stopped", fg=OK if self.mac.on else BAD)

    # ---------- devices ----------
    def w_dev(self): self.open_win("dev", "NASHAMA - Devices", "720x420", self.b_dev)

    def b_dev(self, w):
        self.dt = self.tree(w, ("Type", "Name", "Status"), (150, 460, 80), 11); self.dt.pack(fill="both", expand=True, padx=8, pady=8)
        b = ttk.Frame(w); b.pack(pady=4)
        for t, fn in (("Refresh", self.refresh_devices), ("Disable", lambda: self.dev_act("dis")), ("Enable", lambda: self.dev_act("en")), ("Reset", lambda: self.dev_act("rst"))):
            ttk.Button(b, text=t, command=fn).pack(side="left", padx=5)
        self.dmsg = self.lbl(w, "", fg=DM); self.dmsg.pack()
        self.show_devs(getattr(self, "devs", []))

    def refresh_devices(self):
        threading.Thread(target=lambda: self.q.put(("devs", list_devices())), daemon=True).start()

    def auto_refresh(self):
        self.refresh_devices(); self.after(3000, self.auto_refresh)

    def show_devs(self, d):
        self.devs = d
        k = [x["FriendlyName"] for x in d if x.get("Class") == "Keyboard" and x.get("FriendlyName")]
        m = [x["FriendlyName"] for x in d if x.get("Class") == "Mouse" and x.get("FriendlyName")]
        self.dev_names = (k, m)
        if alive(self.dt):
            sel = self.dt.selection(); self.dt.delete(*self.dt.get_children())
            names = {"Keyboard": "Keyboard", "Mouse": "Mouse", "HIDClass": "HID / Gamepad", "XboxComposite": "Xbox Controller"}
            for x in d:
                self.dt.insert("", "end", iid=x["InstanceId"], values=(names.get(x["Class"], x["Class"]), x["FriendlyName"], x["Status"]))
            for s in sel:
                if self.dt.exists(s): self.dt.selection_set(s)

    def dev_act(self, a):
        sel = self.dt.selection() if alive(self.dt) else ()
        if not sel: return messagebox.showinfo("NASHAMA", "Select a device first")
        iid = sel[0].replace("'", "''")
        cmd = {"dis": "Disable-PnpDevice -InstanceId '%s' -Confirm:$false" % iid, "en": "Enable-PnpDevice -InstanceId '%s' -Confirm:$false" % iid,
               "rst": "Disable-PnpDevice -InstanceId '%s' -Confirm:$false; Start-Sleep 1; Enable-PnpDevice -InstanceId '%s' -Confirm:$false" % (iid, iid)}[a]
        def w():
            ps(cmd); self.q.put(("msg", "Command sent (needs Admin)")); self.refresh_devices()
        threading.Thread(target=w, daemon=True).start()

    # ---------- style ----------
    def w_style(self): self.open_win("style", "NASHAMA - Style", "520x470", self.b_style)

    def pick(self, key):
        c = colorchooser.askcolor(color=self.cfg[key], parent=self.wins.get("style"))[1]
        if c: self.cfg[key] = c; self.apply_theme()

    def b_style(self, w):
        self.lbl(w, "Colors", fg=self.cfg["accent"], font=("Segoe UI", 14, "bold")).pack(pady=(14, 4))
        for t, k in (("Keyboard color", "kb_color"), ("Pressed key color", "kb_press"), ("Mouse + gamepad color", "ms_color"), ("App accent color", "accent")):
            ttk.Button(w, text=t, command=lambda k=k: self.pick(k)).pack(pady=3)
        self.lbl(w, "Quick presets (keyboard + mouse)").pack(pady=(12, 4))
        pf = tk.Frame(w, bg=BG); pf.pack()
        for n, c in PRESETS.items():
            tk.Button(pf, text=n, bg=c, fg="#000", relief="flat", padx=8,
                      command=lambda c=c: (self.cfg.update(kb_color=c, ms_color=c), self.apply_theme())).pack(side="left", padx=3)
        self.lbl(w, "Keyboard effect").pack(pady=(14, 4))
        ev = tk.StringVar(value=self.cfg["effect"])
        cb = ttk.Combobox(w, textvariable=ev, values=["Static", "Rainbow", "Breathing"], state="readonly", width=16); cb.pack()
        cb.bind("<<ComboboxSelected>>", lambda e: (self.cfg.update(effect=ev.get()), save_cfg(self.cfg)))
        self.lbl(w, "Window opacity").pack(pady=(14, 0))
        sc = ttk.Scale(w, from_=0.4, to=1.0, value=self.cfg["alpha"], length=220,
                       command=lambda v: (self.cfg.update(alpha=float(v)), self.attributes("-alpha", float(v)), save_cfg(self.cfg)))
        sc.pack()
        tv = tk.BooleanVar(value=self.cfg["topmost"])
        ttk.Checkbutton(w, text="Always on top", variable=tv, command=lambda: (self.cfg.update(topmost=tv.get()), self.apply_theme())).pack(pady=10)
        ttk.Button(w, text="Reset all stats", command=self.reset_all).pack(pady=4)

    def reset_all(self):
        self.kstat.clear(); self.pstat.clear(); self.reset_mouse()
        if alive(self.kt): self.kt.delete(*self.kt.get_children())
        for n in list(self.prow): 
            if alive(self.prow[n][0]): self.prow[n][0].config(text="0"); self.prow[n][1].config(text="-", fg=DM)

    # ---------- loops ----------
    def loop(self):
        try:
            while True:
                e = self.q.get_nowait(); t = e[0]
                if t == "devs": self.show_devs(e[1])
                elif t == "msg":
                    if alive(self.dmsg): self.dmsg.config(text=e[1])
                elif t == "wh": self.wheel_t = time.time()
                elif t == "kd":
                    n, ts = e[1], e[2]
                    if n not in self.kdown:
                        self.kdown[n] = ts; self.keyhits.append(ts)
                        st = self.kstat.setdefault(n, {"n": 0, "d": [], "ch": 0}); st["n"] += 1
                        if ts - self.klast_up.get(n, -1) < CHATTER: st["ch"] += 1
                        if alive(self.klab): self.klab.config(text="Key: " + n)
                        self.draw_k(n)
                        if n == self.m_h.get().strip().upper(): self.mac_toggle()
                elif t == "ku":
                    n, ts = e[1], e[2]
                    if n in self.kdown:
                        self.kstat[n]["d"].append((ts - self.kdown.pop(n)) * 1000); self.klast_up[n] = ts; self.draw_k(n)
                elif t == "mc":
                    b, ts, p = e[1], e[2], e[3]
                    if p:
                        self.mdown.add(b); self.clicks.append(ts)
                        s = self.mstat.setdefault(b, {"n": 0, "ch": 0}); s["n"] += 1
                        if ts - self.mlast.get(b, -1) < CHATTER: s["ch"] += 1
                        self.mlast[b] = ts; self.draw_m(b)
                    else:
                        self.mdown.discard(b)
        except queue.Empty:
            pass
        self.after(30, self.loop)

    def mouse_calc(self):
        now = time.perf_counter(); self.moves = [m for m in self.moves if now - m[0] < 1.0]
        if len(self.moves) > 5:
            dt = max(self.moves[-1][0] - self.moves[0][0], 0.001)
            self.hz = len(self.moves) / dt; self.maxhz = max(self.maxhz, self.hz)
            d = sum(((self.moves[i][1] - self.moves[i - 1][1]) ** 2 + (self.moves[i][2] - self.moves[i - 1][2]) ** 2) ** .5 for i in range(1, len(self.moves)))
            self.sp = d / dt
        else:
            self.hz = self.sp = 0
        if alive(self.mlab):
            self.mlab.config(text="Mouse: " + (" | ".join(self.dev_names[1]) or "unknown"))
        self.after(250, self.mouse_calc)

    def anim(self):
        self.kv.update_colors(); self.mv.update_colors(); self.after(50, self.anim)

    def tick_info(self):
        now = time.perf_counter()
        for dq in (self.clicks, self.keyhits):
            while dq and now - dq[0] > 1: dq.popleft()
        j = next(iter(self.pads.values()), None)
        self.info.config(text="KEYBOARD  %s\nMOUSE     %s\nGAMEPAD   %s\n\nPolling   %.0f Hz  (max %.0f)\nSpeed     %.0f px/s\nClicks/s  %d\nKeys/s    %d" % (
            " | ".join(self.dev_names[0]) or "detecting...", " | ".join(self.dev_names[1]) or "detecting...",
            j.get_name() if j else "not connected", self.hz, self.maxhz, self.sp, len(self.clicks), len(self.keyhits)))
        self.after(200, self.tick_info)


if __name__ == "__main__":
    App().mainloop()
