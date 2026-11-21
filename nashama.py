# -*- coding: utf-8 -*-
"""NASHAMA - Input Devices Toolkit (Windows)"""
import os, sys, time, json, colorsys, threading, subprocess, queue
from collections import deque
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from tkinter import font as tkfont
from pynput import keyboard as kb, mouse as ms
import pygame

BG, PN, PN2, TX, DM, OK, BAD = "#0d1117", "#161b22", "#21262d", "#e6edf3", "#8b949e", "#3fb950", "#f85149"
CHATTER = 0.04
NOWIN = 0x08000000 if os.name == "nt" else 0
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Nashama")
CFG = os.path.join(CFG_DIR, "config.json")
import faulthandler, traceback
try:
    os.makedirs(CFG_DIR, exist_ok=True)
    LOG = open(os.path.join(CFG_DIR, "crash.log"), "a", buffering=1, encoding="utf-8")
    faulthandler.enable(file=LOG)
except Exception:
    LOG = open(os.devnull, "w")


def _hook(t, v, tb):
    traceback.print_exception(t, v, tb, file=LOG)


sys.excepthook = _hook
threading.excepthook = lambda a: _hook(a.exc_type, a.exc_value, a.exc_traceback)
DEF = {"accent": "#f5b301", "kb_color": "#f5b301", "kb_press": "#ffffff", "ms_color": "#f5b301",
       "effect": "Static", "alpha": 1.0, "topmost": False, "padmap": {}, "padturbo": {}, "turbo_cps": 15, "pad_color": "White", "padmode": {}, "padcps": {}}
ACC = {"c": "#f5b301"}
PRESETS = {"ذهبي": "#f5b301", "سماوي": "#22d3ee", "وردي": "#e040fb", "أخضر": "#7cfc00", "أحمر": "#ff3b3b", "أبيض": "#ffffff"}
EFF = {"ثابت": "Static", "قوس قزح": "Rainbow", "تنفس": "Breathing"}


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
    r, g, b = colorsys.hsv_to_rgb(round((h % 1) * 48) / 48, 0.9, 1)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                           creationflags=NOWIN, timeout=15)
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
    s = (s or "").strip().lower()
    s = {"كليك يسار": "left", "كليك يمين": "right", "كليك وسط": "middle"}.get(s, s).replace(" click", "")
    if s in ("", "(none)", "none", "بدون"):
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


MAX_CPS = 20000
SPECIAL = {"space": 0x20, "enter": 0x0D, "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "tab": 0x09, "esc": 0x1B,
           "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, **{"f%d" % i: 0x6F + i for i in range(1, 13)}}
if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _MI(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _KI(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("mi", _MI), ("ki", _KI)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def fast_spec(t):
    """Turn a target into raw SendInput data (mouse flags or key scancode)"""
    if os.name != "nt" or t is None:
        return None
    if isinstance(t, ms.Button):
        f = {ms.Button.left: (0x2, 0x4), ms.Button.right: (0x8, 0x10), ms.Button.middle: (0x20, 0x40)}.get(t)
        return ("m",) + f if f else None
    name = t if isinstance(t, str) else getattr(t, "name", "")
    rvk = {v: k for k, v in VK.items()}
    vk = rvk.get(name.upper()) or SPECIAL.get(name)
    if not vk:
        return None
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    return ("k", scan, 1 if name in ("up", "down", "left", "right") else 0)


def make_pair(spec):
    a, b = INPUT(), INPUT()
    if spec[0] == "m":
        a.type = b.type = 0
        a.u.mi.dwFlags, b.u.mi.dwFlags = spec[1], spec[2]
    else:
        a.type = b.type = 1
        a.u.ki.wScan = b.u.ki.wScan = spec[1]
        a.u.ki.dwFlags = 0x8 | spec[2]
        b.u.ki.dwFlags = 0x8 | spec[2] | 0x2
    return [a, b]


def tname(s):
    t = parse_target(s)
    if t is None:
        return None
    if isinstance(t, ms.Button):
        return t.name
    return (t if isinstance(t, str) else t.name).upper()


class Macro:
    """Repeats a key / mouse click. Above 50/s it sends batches with SendInput (up to MAX_CPS per second)"""
    def __init__(self):
        self.on, self.target, self.cps, self.gen = False, "f5", 10.0, 0

    def start(self):
        if not self.on:
            self.on = True; self.gen += 1
            threading.Thread(target=self._run, args=(self.gen,), daemon=True).start()

    def stop(self):
        self.on = False

    def _alive(self, g):
        return self.on and g == self.gen

    def _cps(self):
        return max(0.1, min(self.cps, MAX_CPS))

    def _run(self, g):
        try:
            t = parse_target(self.target)
            if t is None:
                self.on = False; return
            spec = fast_spec(t)
            if spec and self._cps() > 50:
                self._fast(spec, g)
            else:
                self._slow(t, g)
        except Exception:
            traceback.print_exc(file=LOG); self.on = False

    def _slow(self, t, g):
        while self._alive(g):
            t0 = time.perf_counter()
            if isinstance(t, ms.Button):
                msc.click(t)
            else:
                kbc.press(t); kbc.release(t)
            time.sleep(max(0.0, 1 / self._cps() - (time.perf_counter() - t0)))

    def _fast(self, spec, g):
        w = ctypes.windll
        w.winmm.timeBeginPeriod(1)
        try:
            pair, sz = make_pair(spec), ctypes.sizeof(INPUT)
            acc, last = 0.0, time.perf_counter()
            while self._alive(g):
                now = time.perf_counter(); acc += self._cps() * (now - last); last = now
                k = int(acc); acc -= k; k = min(k, 2000)
                if k:
                    arr = (INPUT * (2 * k))(*(pair * k))
                    w.user32.SendInput(2 * k, arr, sz)
                time.sleep(0.001)
        finally:
            w.winmm.timeEndPeriod(1)


VK = {**{0x41 + i: chr(65 + i) for i in range(26)}, **{0x30 + i: str(i) for i in range(10)},
      0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`", 0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'"}


def kname(k):
    if isinstance(k, kb.KeyCode):
        vk = getattr(k, "vk", None)
        if vk in VK:
            return VK[vk]
        n = k.char.upper() if k.char else "VK%s" % vk
    else:
        n = str(k).replace("Key.", "").upper()
    for b in ("SHIFT", "CTRL", "ALT"):
        if n == b or n.startswith(b + "_"):
            return b
    return n


def kid(n):
    return "k" + n.encode("utf-8").hex()


def rrect(c, x0, y0, x1, y1, r=8, **kw):
    p = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(p, smooth=True, **kw)


class RBtn(tk.Canvas):
    """Rounded flat button with hover effect"""
    def __init__(self, parent, text="", command=None, bg=BG, h=36, fs=10, **kw):
        f = tkfont.Font(family="Segoe UI", size=fs, weight="bold")
        w = f.measure(text) + 34
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, cursor="hand2")
        self.cmd, self.w, self.h = command, w, h
        self.shape = rrect(self, 1, 1, w - 1, h - 1, 12, fill=ACC["c"], outline="")
        self.create_text(w / 2, h / 2, text=text, fill="#000000", font=f)
        self.bind("<Enter>", lambda e: self.itemconfig(self.shape, fill=blend(ACC["c"], "#ffffff", 0.72)))
        self.bind("<Leave>", lambda e: self.itemconfig(self.shape, fill=ACC["c"]))
        self.bind("<ButtonPress-1>", lambda e: self.itemconfig(self.shape, fill=blend(ACC["c"], "#000000", 0.8)))
        self.bind("<ButtonRelease-1>", self._rel)

    def _rel(self, e):
        self.itemconfig(self.shape, fill=ACC["c"])
        if 0 <= e.x <= self.w and 0 <= e.y <= self.h and self.cmd:
            self.cmd()


class Tile(tk.Frame):
    def __init__(self, parent, cap):
        super().__init__(parent, bg=PN, highlightbackground=PN2, highlightthickness=1)
        self.v = tk.Label(self, text="--", bg=PN, fg=ACC["c"], font=("Segoe UI", 20, "bold")); self.v.pack(pady=(8, 0))
        tk.Label(self, text=cap, bg=PN, fg=DM, font=("Segoe UI", 8, "bold")).pack(pady=(0, 8))

    def set(self, t):
        self.v.config(text=t)


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
        W, H = 18.4 * U, 6.75 * U
        super().__init__(parent, width=int(W), height=int(H), bg=BG, highlightthickness=0)
        self.app, self.keys, self.W, self.last = app, {}, W, {}
        rrect(self, 1, 1, W - 1, H - 1, 16, fill="#090c10", outline=PN2, width=2)
        y = 0.3
        for r, row in enumerate(ROWS):
            x = 0.3
            for name, label, w in row:
                if name:
                    x0, y0 = x * U, y * U
                    x1, y1 = x0 + w * U - 5, y0 + U - 5
                    rid = rrect(self, x0, y0, x1, y1, 7, fill=PN, outline=DM, width=2)
                    tid = self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, fill=DM, font=("Segoe UI", 9, "bold"))
                    self.keys.setdefault(name, []).append((rid, tid, x0 / W))
                x += w
            y += 1.3 if r == 0 else 1
        self.update_colors()

    def col(self, xr, t):
        c, eff = self.app.cfg, self.app.cfg["effect"]
        if eff == "Rainbow":
            return hsv(xr + t * 0.25)
        if eff == "Breathing":
            return blend(c["kb_color"], PN, 0.35 + 0.65 * (0.5 + 0.5 * __import__("math").sin(t * 2.2)))
        return c["kb_color"]

    def update_colors(self):
        t, pc, now = time.time(), self.app.cfg["kb_press"], time.perf_counter()
        for name, items in self.keys.items():
            down = name in self.app.kdown or now - self.app.klast_up.get(name, -9) < 0.12
            for rid, tid, xr in items:
                c = self.col(xr, t)
                st = (down, c, pc)
                if self.last.get(rid) == st:
                    continue
                self.last[rid] = st
                self.itemconfig(rid, fill=pc if down else PN, outline=pc if down else c)
                self.itemconfig(tid, fill="#000000" if down else c)


class MouseView(tk.Canvas):
    def __init__(self, parent, app):
        super().__init__(parent, width=170, height=240, bg=PN, highlightthickness=0)
        self.app = app
        dark = "#0d1117"
        self.body = self.create_polygon(85, 4, 125, 12, 152, 52, 162, 120, 156, 192, 130, 228, 85, 236, 40, 228, 14, 192, 8, 120, 18, 52, 45, 12,
                                        smooth=True, fill=dark, outline=DM, width=3)
        self.L = self.create_polygon(30, 66, 46, 28, 82, 12, 82, 106, 22, 106, smooth=True, fill=dark, outline=DM, width=2)
        self.R = self.create_polygon(140, 66, 124, 28, 88, 12, 88, 106, 148, 106, smooth=True, fill=dark, outline=DM, width=2)
        self.M = rrect(self, 77, 34, 93, 76, 7, fill=dark, outline=DM, width=2)
        self.X1 = rrect(self, 9, 120, 21, 150, 4, fill=dark, outline=DM, width=2)
        self.X2 = rrect(self, 9, 156, 21, 186, 4, fill=dark, outline=DM, width=2)
        self.glow = self.create_oval(68, 150, 102, 184, fill=dark, outline=DM, width=2)
        self.create_text(85, 98, text="", fill=DM)
        self.update_colors()

    def update_colors(self):
        c, pc, d = self.app.cfg["ms_color"], self.app.cfg["kb_press"], self.app.mdown
        wheel = time.time() - self.app.wheel_t < 0.15
        st = (c, pc, tuple(sorted(d)), wheel)
        if st == getattr(self, "_st", None):
            return
        self._st = st
        self.itemconfig(self.body, outline=c)
        for item, on in ((self.L, "left" in d), (self.R, "right" in d), (self.M, "middle" in d or wheel),
                         (self.X1, "x1" in d), (self.X2, "x2" in d)):
            self.itemconfig(item, fill=pc if on else "#0d1117", outline=c)
        self.itemconfig(self.glow, fill=c, outline=c)


class PadView(tk.Canvas):
    XB = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5, "BACK": 6, "START": 7, "L3": 8, "R3": 9}
    PS = {"A": 0, "B": 1, "X": 2, "Y": 3, "LB": 9, "RB": 10, "BACK": 4, "START": 6, "L3": 7, "R3": 8}

    def __init__(self, parent, app):
        super().__init__(parent, width=400, height=270, bg=BG, highlightthickness=0)
        self.app, self.kind, self.it = app, "XB", {}
        self.draw()

    def set_kind(self, k):
        if k != self.kind:
            self.kind = k; self.draw()

    def draw(self):
        self.delete("all"); self.it = {}
        a = self.app.cfg
        black = a.get("pad_color") == "Black"
        body, edge, btn = ("#2a2f37", "#454b55", "#101317") if black else ("#f2f3f5", "#9aa1ab", "#3a3f47")
        ps, sw = self.kind == "PS", self.kind == "SW"
        pts = ([90, 62, 150, 50, 250, 50, 310, 62, 350, 100, 372, 190, 352, 236, 318, 240, 290, 205, 255, 185, 145, 185, 110, 205, 82, 240, 48, 236, 28, 190, 50, 100] if ps else
               [80, 60, 150, 48, 250, 48, 320, 60, 360, 110, 378, 190, 356, 236, 322, 242, 292, 204, 256, 182, 144, 182, 108, 204, 78, 242, 44, 236, 22, 190, 40, 110])
        self.create_polygon(*pts, smooth=True, fill=body, outline=edge, width=3)
        L3, R3, DP, FC, BK, ST = (((140, 168), (260, 168), (92, 102), (308, 102), (150, 92), (250, 92)) if ps else
                                  ((112, 104), (254, 166), (160, 160), (300, 102), (180, 100), (220, 100)))
        self.lc, self.rc = L3, R3

        def part(n, box, kind="r", fill=btn, lit=None):
            i = (self.create_oval if kind == "o" else self.create_rectangle)(*box, fill=fill, outline=edge, width=2)
            self.it[n] = (i, lit or a["ms_color"], fill)

        if ps:
            self.create_rectangle(165, 70, 235, 112, fill=body, outline=edge, width=2)
            self.create_oval(192, 142, 208, 158, fill=btn, outline=edge)
        for n, box in (("LT", (70, 16, 140, 40)), ("RT", (260, 16, 330, 40)), ("LB", (60, 44, 150, 60)), ("RB", (250, 44, 340, 60))):
            part(n, box, fill=body)
        for n, tx, ty in (("LT", 105, 28), ("RT", 295, 28), ("LB", 105, 52), ("RB", 295, 52)):
            self.create_text(tx, ty, text=n, fill=edge, font=("Segoe UI", 8, "bold"))
        cx, cy = DP
        self.create_rectangle(cx - 8, cy - 8, cx + 8, cy + 8, fill=btn, outline=btn)
        for n, box in (("UP", (cx - 8, cy - 24, cx + 8, cy - 8)), ("DOWN", (cx - 8, cy + 8, cx + 8, cy + 24)),
                       ("LEFT", (cx - 24, cy - 8, cx - 8, cy + 8)), ("RIGHT", (cx + 8, cy - 8, cx + 24, cy + 8))):
            part(n, box)
        for n, (x, y) in (("L3", L3), ("R3", R3)):
            part(n, (x - 26, y - 26, x + 26, y + 26), "o")
        part("BACK", (BK[0] - 10, BK[1] - 6, BK[0] + 10, BK[1] + 6), "o"); part("START", (ST[0] - 10, ST[1] - 6, ST[0] + 10, ST[1] + 6), "o")
        fx, fy = FC
        faces = ((("Y", (fx, fy - 22), "#e3b341"), ("A", (fx, fy + 22), "#3fb950"), ("X", (fx - 22, fy), "#58a6ff"), ("B", (fx + 22, fy), "#f85149")) if not ps else
                 (("Y", (fx, fy - 22), "#4ade80"), ("A", (fx, fy + 22), "#6ea8ff"), ("X", (fx - 22, fy), "#ff8ad8"), ("B", (fx + 22, fy), "#ff6b6b")))
        sym = {"Y": "\u25b3", "A": "\u2715", "X": "\u25a1", "B": "\u25cb"}
        swl = {"Y": "X", "A": "B", "X": "Y", "B": "A"}
        for n, (x, y), col in faces:
            part(n, (x - 12, y - 12, x + 12, y + 12), "o", lit=a["ms_color"] if sw else col)
            self.create_text(x, y, text=sym[n] if ps else (swl[n] if sw else n), fill="#c9d1d9" if sw else col, font=("Segoe UI Symbol", 11, "bold"))
        d = "#8b949e"
        self.ld = self.create_oval(0, 0, 0, 0, fill=d, outline=""); self.rd = self.create_oval(0, 0, 0, 0, fill=d, outline="")
        self.sticks(0, 0, 0, 0)

    def lit(self, name, on):
        if name in self.it:
            i, col, idle = self.it[name]
            self.itemconfig(i, fill=col if on else idle)

    def sticks(self, lx, ly, rx, ry):
        (lx0, ly0), (rx0, ry0) = self.lc, self.rc
        self.coords(self.ld, lx0 - 9 + lx * 14, ly0 - 9 + ly * 14, lx0 + 9 + lx * 14, ly0 + 9 + ly * 14)
        self.coords(self.rd, rx0 - 9 + rx * 14, ry0 - 9 + ry * 14, rx0 + 9 + rx * 14, ry0 + 9 + ry * 14)


ACTIONS = (["بدون"] + list("abcdefghijklmnopqrstuvwxyz0123456789") + ["space", "enter", "shift", "ctrl", "alt", "tab", "esc", "up", "down", "left", "right"]
           + ["f%d" % i for i in range(1, 13)] + ["كليك يسار", "كليك يمين", "كليك وسط"])
MODES = ["عادي", "تيربو (طول ما أضغط)", "تشغيل/إيقاف (ضغطة وحدة)"]
PADROWS = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "BACK", "START", "L3", "R3", "UP", "DOWN", "LEFT", "RIGHT"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.title("النشاما"); self.geometry("720x720"); self.configure(bg=BG); self.minsize(700, 700)
        self.q = queue.Queue(maxsize=3000); self.dev_names = ([], []); self.pads = {}; self.wins = {}
        self.kstat, self.mstat, self.pstat = {}, {}, {}
        self.kdown, self.klast_up, self.mlast = {}, {}, {}
        self.mdown, self.wheel_t, self.moves, self.maxhz, self.hz, self.sp = set(), 0, [], 0, 0, 0
        self.clicks, self.keyhits = deque(), deque()
        self.mac, self.hotkey, self.padmacros, self.trig, self.hatprev = Macro(), "f6", {}, {}, set()
        self.m_t, self.m_c, self.m_h = tk.StringVar(value="f5"), tk.StringVar(value="10"), tk.StringVar(value="f6")
        self.kt = self.mt = self.pv = self.klab = self.mlab = self.dmsg = self.dt = self.mstate = self.pt = None
        self.prow, self.pvars, self.rlab, self.learn_row, self.learn_t, self.nrow = {}, {}, {}, None, 0, 1
        self.sty(); self.build()
        self.attributes("-topmost", self.cfg["topmost"]); self.attributes("-alpha", self.cfg["alpha"])
        pygame.display.init(); pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i); self.pads[j.get_instance_id()] = j
        kb.Listener(on_press=lambda k: self._kq("kd", k),
                    on_release=lambda k: self._kq("ku", k), daemon=True).start()
        ms.Listener(on_move=lambda x, y: self.moves.append((time.perf_counter(), x, y)),
                    on_click=lambda x, y, b, p: self._mq(b, p),
                    on_scroll=lambda x, y, dx, dy: self.q.put(("wh",)), daemon=True).start()
        self.refresh_devices()
        self.after(30, self.loop); self.after(16, self.pad_loop); self.after(250, self.mouse_calc)
        self.after(50, self.anim); self.after(200, self.tick_info); self.after(10000, self.auto_refresh)

    def sty(self):
        a = self.cfg["accent"]; ACC["c"] = a; s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TX, fieldbackground=PN, font=("Segoe UI", 10))
        s.configure("Treeview", background=PN, fieldbackground=PN, foreground=TX, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background=PN2, foreground=a, font=("Segoe UI", 10, "bold"))
        s.configure("TButton", background=a, foreground="#000", padding=8, font=("Segoe UI", 10, "bold"))
        s.map("TButton", background=[("active", blend(a, "#ffffff", 0.75))])
        s.configure("TFrame", background=BG); s.configure("TLabel", background=BG)
        s.configure("TCheckbutton", background=BG, foreground=TX)
        s.configure("TEntry", fieldbackground=PN, foreground=TX, insertcolor=TX)
        s.configure("TCombobox", fieldbackground=PN, foreground=TX, background=PN2, arrowcolor=a, insertcolor=TX)
        s.map("TCombobox", fieldbackground=[("readonly", PN)], foreground=[("readonly", TX)],
              selectbackground=[("readonly", PN)], selectforeground=[("readonly", TX)])
        self.option_add("*TCombobox*Listbox.background", PN); self.option_add("*TCombobox*Listbox.foreground", TX)
        self.option_add("*TCombobox*Listbox.selectBackground", a); self.option_add("*TCombobox*Listbox.selectForeground", "#000000")
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
        hd = tk.Frame(self, bg=BG); hd.pack(fill="x", padx=16, pady=(14, 2))
        lg = tk.Canvas(hd, width=52, height=52, bg=BG, highlightthickness=0); lg.pack(side="left")
        self.logo = lg.create_polygon(26, 2, 48, 9, 48, 28, 26, 50, 4, 28, 4, 9, fill=a)
        lg.create_text(26, 27, text="N", font=("Segoe UI", 20, "bold"), fill="#000")
        tf = tk.Frame(hd, bg=BG); tf.pack(side="left", padx=10)
        self.title_l = tk.Label(tf, text="النشاما", bg=BG, fg=a, font=("Segoe UI", 24, "bold")); self.title_l.pack(anchor="w")
        self.lbl(tf, "فحص وتحكم بالكيبورد والماوس واليد", fg=DM).pack(anchor="w")
        self.lbl(hd, "مدير" if is_admin() else "مو مدير (التحكم بالأجهزة يحتاج صلاحية المدير)", fg=OK if is_admin() else DM,
                 font=("Segoe UI", 9, "bold")).pack(side="right")
        bar = tk.Frame(self, bg=BG); bar.pack(pady=12)
        for txt, fn in (("فحص الكيبورد", self.w_kb), ("فحص الماوس", self.w_ms), ("اليد", self.w_pad),
                        ("الماكرو", self.w_mac), ("الأجهزة", self.w_dev), ("المظهر", self.w_style)):
            RBtn(bar, text=txt, command=fn).pack(side="left", padx=4)
        card = tk.Frame(self, bg=PN2); card.pack(padx=16, pady=6)
        self.kv = KeyboardView(card, self); self.kv.pack(padx=1, pady=1)
        bt = tk.Frame(self, bg=BG); bt.pack(fill="x", padx=16, pady=10)
        mc = tk.Frame(bt, bg=PN2); mc.pack(side="left")
        self.mv = MouseView(mc, self); self.mv.pack(padx=1, pady=1)
        rt = tk.Frame(bt, bg=BG); rt.pack(side="left", fill="both", expand=True, padx=16)
        g = tk.Frame(rt, bg=BG); g.pack(fill="x")
        self.tiles = {}
        for i, (k, cap) in enumerate((("hz", "معدل الاستجابة"), ("sp", "سرعة الماوس"), ("cps", "كليك بالثانية"), ("kps", "ضغطة بالثانية"))):
            t = Tile(g, cap); t.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4); self.tiles[k] = t
        g.columnconfigure((0, 1), weight=1)
        self.info = tk.Label(rt, text="", bg=BG, fg=DM, justify="left", anchor="nw", font=("Segoe UI", 10), wraplength=400)
        self.info.pack(fill="x", pady=10)

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
    def w_kb(self): self.open_win("kb", "النشاما - فحص الكيبورد", "640x440", self.b_kb)

    def b_kb(self, w):
        self.klab = self.lbl(w, "اضغط أي زر...", fg=self.cfg["accent"], font=("Segoe UI", 20, "bold")); self.klab.pack(pady=8)
        self.kt = self.tree(w, ("الزر", "الضغطات", "متوسط الضغط ms", "تكرار خاطئ", "الحالة"), (120, 100, 130, 100, 130), 12)
        self.kt.pack(fill="both", expand=True, padx=8, pady=6)
        RBtn(w, text="تصفير الإحصائيات", command=lambda: (self.kstat.clear(), self.kt.delete(*self.kt.get_children()))).pack(pady=6)
        for n in self.kstat: self.draw_k(n)

    def w_ms(self): self.open_win("ms", "النشاما - فحص الماوس", "560x400", self.b_ms)

    def b_ms(self, w):
        self.mlab = self.lbl(w, "حرّك الماوس...", fg=self.cfg["accent"], font=("Segoe UI", 15, "bold")); self.mlab.pack(pady=8)
        self.mt = self.tree(w, ("الزر", "الضغطات", "تكرار خاطئ", "الحالة"), (130, 110, 110, 130), 8)
        self.mt.pack(fill="both", expand=True, padx=8, pady=6)
        RBtn(w, text="تصفير الإحصائيات", command=self.reset_mouse).pack(pady=6)
        for n in self.mstat: self.draw_m(n)

    def verdict(self, n, ch, avg=None):
        if ch >= 1 or (avg is not None and n >= 5 and avg < 15):
            return "ضعيف ⚠", "bad"
        return "سليم ✔", "ok"

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
    def pad_kind(self):
        j = next(iter(self.pads.values()), None)
        n = (j.get_name() if j else "").lower()
        if any(x in n for x in ("pro controller", "nintendo", "switch", "joy-con")):
            return "SW"
        return "PS" if any(x in n for x in ("dualsense", "dualshock", "wireless controller", "playstation", "ps4", "ps5")) else "XB"

    def pad_layout(self):
        return PadView.PS if self.pad_kind() == "PS" else PadView.XB

    def toggle_pad_color(self):
        self.cfg["pad_color"] = "White" if self.cfg.get("pad_color") == "Black" else "Black"
        save_cfg(self.cfg)
        if alive(self.pv): self.pv.draw()

    def w_pad(self): self.open_win("pad", "النشاما - اليد", "1180x800", self.b_pad)

    def b_pad(self, w):
        L = tk.Frame(w, bg=BG); L.pack(side="left", padx=10, pady=10)
        self.plab = self.lbl(L, "", fg=self.cfg["accent"], font=("Segoe UI", 13, "bold")); self.plab.pack(pady=4)
        self.pv = PadView(L, self); self.pv.pack()
        RBtn(L, text="تغيير لون اليد: أبيض / أسود", command=self.toggle_pad_color).pack(pady=4)
        self.lbl(L, "الرسم: إكس بوكس / بلايستيشن / سويتش.\nجدول الأزرار يشتغل مع أي يد.", fg=DM).pack(pady=6)
        self.lbl(L, "عادي = ضغطة عادية\nتيربو = يكرر طول ما أنت ضاغط الزر\nتشغيل/إيقاف = ضغطة وحدة تشغّل وضغطة ثانية توقف", fg=DM, justify="left").pack(pady=4)
        RBtn(L, text="إيقاف كل الماكرو", command=self.stop_all).pack(pady=6)
        R = tk.Frame(w, bg=BG); R.pack(side="left", fill="both", expand=True, padx=6, pady=10)
        self.rowsf, self.nrow = R, 1
        self.prow, self.pvars, self.rlab = {}, {}, {}
        for c, t in enumerate(("الزر", "الإجراء", "النمط", "السرعة / ث", "الضغطات", "الحالة")):
            tk.Label(R, text=t, bg=PN2, fg=self.cfg["accent"], font=("Segoe UI", 10, "bold")).grid(row=0, column=c, sticky="ew", padx=1, pady=1)
        self.speedmsg = self.lbl(R, "", fg=BAD); self.speedmsg.grid(row=999, column=0, columnspan=6, pady=6)
        for n in PADROWS:
            self.add_row(n)
        j = next(iter(self.pads.values()), None)
        if j:
            used = set(self.pad_layout().values())
            for i in range(j.get_numbuttons()):
                if i not in used:
                    self.add_row("BTN%d" % i)
        self.on_pad_change()
        for n in self.pstat: self.draw_pad_row(n)

    def on_pad_change(self):
        if alive(getattr(self, "plab", None)):
            j = next(iter(self.pads.values()), None)
            kind = {"PS": "بلايستيشن", "SW": "نينتندو سويتش", "XB": "إكس بوكس / عامة"}[self.pad_kind()]
            self.plab.config(text=("%s  [%s]" % (j.get_name(), kind)) if j else "وصّل اليد...")

    def draw_pad_row(self, n):
        if n in self.prow and alive(self.prow[n][0]):
            s = self.pstat[n]; v, tag = self.verdict(s["n"], s["ch"])
            m = self.padmacros.get(n)
            self.prow[n][0].config(text=str(s["n"]))
            if m and m.on: self.prow[n][1].config(text="يشتغل ▶", fg=self.cfg["accent"])
            else: self.prow[n][1].config(text=v, fg=OK if tag == "ok" else BAD)

    def pad_event(self, name, down):
        if name not in self.prow and alive(getattr(self, "rowsf", None)):
            self.add_row(name)
        lb = self.rlab.get(name)
        if alive(lb): lb.config(fg=self.cfg["accent"] if down else TX)
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
        mode = self.cfg["padmode"].get(name, MODES[0])
        if mode == MODES[0]:
            press(t, down); return
        m = self.padmacros.setdefault(name, Macro()); m.target = tgt
        try: m.cps = float(self.cfg["padcps"].get(name, 15))
        except ValueError: m.cps = 15
        if mode == MODES[1]:
            m.start() if down else m.stop()
        elif down:
            m.stop() if m.on else m.start()
        self.draw_pad_row(name)

    def pad_loop(self):
        try: self._pad_body()
        except Exception: traceback.print_exc(file=LOG)
        self.after(16, self.pad_loop)

    def _pad_body(self):
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

    # ---------- macros ----------
    def w_mac(self): self.open_win("mac", "النشاما - الماكرو", "520x300", self.b_mac)

    def b_mac(self, w):
        c = tk.LabelFrame(w, text="ماكرو الكيبورد / الماوس", bg=BG, fg=self.cfg["accent"], font=("Segoe UI", 11, "bold"), padx=10, pady=8)
        c.pack(fill="x", padx=12, pady=12)
        for i, (l, v) in enumerate((("الزر المكرر (f5 / a / كليك يسار)", self.m_t), ("ضغطة بالثانية", self.m_c), ("زر التشغيل / الإيقاف", self.m_h))):
            self.lbl(c, l).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            ttk.Entry(c, textvariable=v, width=14).grid(row=i, column=1, pady=4)
        self.mstate = self.lbl(c, "متوقف", fg=BAD, font=("Segoe UI", 12, "bold")); self.mstate.grid(row=3, column=0, columnspan=2, pady=4)
        RBtn(c, text="تطبيق / تشغيل-إيقاف", command=self.mac_toggle).grid(row=4, column=0, columnspan=2, pady=4)
        self.lbl(w, "ماكرو أزرار اليد: من نافذة اليد اختر الإجراء وفعّل تيربو.\nبعض الألعاب الأونلاين تمنع الماكرو (Anti-Cheat). استخدمه على مسؤوليتك.", fg=DM).pack(pady=8)
        RBtn(w, text="إيقاف كل الماكرو", command=self.stop_all).pack(pady=6)

    def mac_toggle(self):
        self.mac.target = self.m_t.get()
        try: self.mac.cps = float(self.m_c.get())
        except ValueError: self.mac.cps = 10
        self.mac.stop() if self.mac.on else self.mac.start()
        if alive(self.mstate):
            self.mstate.config(text="يشتغل" if self.mac.on else "متوقف", fg=OK if self.mac.on else BAD)

    # ---------- devices ----------
    def w_dev(self): self.open_win("dev", "النشاما - الأجهزة", "720x420", self.b_dev)

    def b_dev(self, w):
        self.dt = self.tree(w, ("النوع", "الاسم", "الحالة"), (150, 460, 80), 11); self.dt.pack(fill="both", expand=True, padx=8, pady=8)
        b = ttk.Frame(w); b.pack(pady=4)
        for t, fn in (("تحديث", self.refresh_devices), ("تعطيل", lambda: self.dev_act("dis")), ("تفعيل", lambda: self.dev_act("en")), ("إعادة ضبط", lambda: self.dev_act("rst"))):
            RBtn(b, text=t, command=fn).pack(side="left", padx=5)
        self.dmsg = self.lbl(w, "", fg=DM); self.dmsg.pack()
        self.show_devs(getattr(self, "devs", []))

    def refresh_devices(self):
        if getattr(self, "_devbusy", False):
            return
        self._devbusy = True

        def w():
            try: self.q.put(("devs", list_devices()))
            finally: self._devbusy = False
        threading.Thread(target=w, daemon=True).start()

    def auto_refresh(self):
        self.refresh_devices(); self.after(10000, self.auto_refresh)

    def show_devs(self, d):
        self.devs = d
        k = list(dict.fromkeys(x["FriendlyName"] for x in d if x.get("Class") == "Keyboard" and x.get("FriendlyName")))
        m = list(dict.fromkeys(x["FriendlyName"] for x in d if x.get("Class") == "Mouse" and x.get("FriendlyName")))
        self.dev_names = (k, m)
        if alive(self.dt):
            sel = self.dt.selection(); self.dt.delete(*self.dt.get_children())
            names = {"Keyboard": "كيبورد", "Mouse": "ماوس", "HIDClass": "جهاز HID / يد", "XboxComposite": "يد Xbox"}
            for x in d:
                self.dt.insert("", "end", iid=x["InstanceId"], values=(names.get(x["Class"], x["Class"]), x["FriendlyName"], x["Status"]))
            for s in sel:
                if self.dt.exists(s): self.dt.selection_set(s)

    def dev_act(self, a):
        sel = self.dt.selection() if alive(self.dt) else ()
        if not sel: return messagebox.showinfo("النشاما", "اختر جهاز من القائمة أولاً")
        iid = sel[0].replace("'", "''")
        cmd = {"dis": "Disable-PnpDevice -InstanceId '%s' -Confirm:$false" % iid, "en": "Enable-PnpDevice -InstanceId '%s' -Confirm:$false" % iid,
               "rst": "Disable-PnpDevice -InstanceId '%s' -Confirm:$false; Start-Sleep 1; Enable-PnpDevice -InstanceId '%s' -Confirm:$false" % (iid, iid)}[a]
        def w():
            ps(cmd); self.q.put(("msg", "تم إرسال الأمر (يحتاج صلاحية المدير)")); self.refresh_devices()
        threading.Thread(target=w, daemon=True).start()

    # ---------- style ----------
    def w_style(self): self.open_win("style", "النشاما - المظهر", "520x470", self.b_style)

    def pick(self, key):
        c = colorchooser.askcolor(color=self.cfg[key], parent=self.wins.get("style"))[1]
        if c: self.cfg[key] = c; self.apply_theme()

    def b_style(self, w):
        self.lbl(w, "الألوان", fg=self.cfg["accent"], font=("Segoe UI", 14, "bold")).pack(pady=(14, 4))
        for t, k in (("لون الكيبورد", "kb_color"), ("لون الزر المضغوط", "kb_press"), ("لون الماوس واليد", "ms_color"), ("لون البرنامج", "accent")):
            RBtn(w, text=t, command=lambda k=k: self.pick(k)).pack(pady=3)
        self.lbl(w, "ألوان جاهزة (كيبورد + ماوس)").pack(pady=(12, 4))
        pf = tk.Frame(w, bg=BG); pf.pack()
        for n, c in PRESETS.items():
            tk.Button(pf, text=n, bg=c, fg="#000", relief="flat", padx=8,
                      command=lambda c=c: (self.cfg.update(kb_color=c, ms_color=c), self.apply_theme())).pack(side="left", padx=3)
        self.lbl(w, "تأثير الكيبورد").pack(pady=(14, 4))
        ev = tk.StringVar(value={v: k for k, v in EFF.items()}.get(self.cfg["effect"], "ثابت"))
        cb = ttk.Combobox(w, textvariable=ev, values=list(EFF), state="readonly", width=16); cb.pack()
        cb.bind("<<ComboboxSelected>>", lambda e: (self.cfg.update(effect=EFF.get(ev.get(), "Static")), save_cfg(self.cfg)))
        self.lbl(w, "شفافية النافذة").pack(pady=(14, 0))
        sc = ttk.Scale(w, from_=0.4, to=1.0, value=self.cfg["alpha"], length=220,
                       command=lambda v: (self.cfg.update(alpha=float(v)), self.attributes("-alpha", float(v)), save_cfg(self.cfg)))
        sc.pack()
        tv = tk.BooleanVar(value=self.cfg["topmost"])
        ttk.Checkbutton(w, text="خلّي البرنامج فوق كل النوافذ", variable=tv, command=lambda: (self.cfg.update(topmost=tv.get()), self.apply_theme())).pack(pady=10)
        RBtn(w, text="تصفير كل الإحصائيات", command=self.reset_all).pack(pady=4)

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
                    if self.learn_row: self.finish_learn(n, ts)
                    if n not in self.kdown:
                        self.kdown[n] = ts; self.keyhits.append(ts)
                        st = self.kstat.setdefault(n, {"n": 0, "d": [], "ch": 0}); st["n"] += 1
                        if ts - self.klast_up.get(n, -1) < CHATTER: st["ch"] += 1
                        if alive(self.klab): self.klab.config(text="الزر: " + n)
                        self.draw_k(n)
                        if n == self.m_h.get().strip().upper(): self.mac_toggle()
                elif t == "ku":
                    n, ts = e[1], e[2]
                    if n in self.kdown:
                        self.kstat[n]["d"].append((ts - self.kdown.pop(n)) * 1000); self.klast_up[n] = ts; self.draw_k(n)
                elif t == "mc":
                    b, ts, p = e[1], e[2], e[3]
                    if p:
                        if self.learn_row: self.finish_learn(b, ts, True)
                        self.mdown.add(b); self.clicks.append(ts)
                        s = self.mstat.setdefault(b, {"n": 0, "ch": 0}); s["n"] += 1
                        if ts - self.mlast.get(b, -1) < CHATTER: s["ch"] += 1
                        self.mlast[b] = ts; self.draw_m(b)
                    else:
                        self.mdown.discard(b)
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc(file=LOG)
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
            self.mlab.config(text="الماوس: " + (" | ".join(self.dev_names[1]) or "غير معروف"))
        self.after(250, self.mouse_calc)

    def anim(self):
        try:
            self.kv.update_colors(); self.mv.update_colors()
            if alive(self.pv): self.pv.set_kind(self.pad_kind())
        except Exception:
            traceback.print_exc(file=LOG)
        self.after(50, self.anim)

    def blocked(self, n):
        for m in [self.mac, *self.padmacros.values()]:
            if m.on and tname(m.target) == n:
                return True
        return False

    def _kq(self, kind, k):
        n = kname(k)
        if kind == "kd" and self.blocked(n):
            return
        try: self.q.put_nowait((kind, n, time.perf_counter()))
        except queue.Full: pass

    def _mq(self, b, p):
        n = str(b).replace("Button.", "")
        if p and self.blocked(n):
            return
        try: self.q.put_nowait(("mc", n, time.perf_counter(), p))
        except queue.Full: pass

    def stop_all(self):
        self.mac.stop()
        for m in self.padmacros.values(): m.stop()
        if alive(self.mstate): self.mstate.config(text="متوقف", fg=BAD)
        for n in list(self.prow):
            if n in self.pstat: self.draw_pad_row(n)

    def add_row(self, n):
        R, r = self.rowsf, self.nrow; self.nrow += 1
        lb = self.lbl(R, n); lb.grid(row=r, column=0, pady=1, padx=4)
        v = tk.StringVar(value=self.cfg["padmap"].get(n, "بدون")); self.pvars[n] = v
        v.trace_add("write", lambda *a, n=n, v=v: (self.cfg["padmap"].__setitem__(n, v.get()), save_cfg(self.cfg)))
        af = tk.Frame(R, bg=BG); af.grid(row=r, column=1, padx=3)
        ttk.Combobox(af, textvariable=v, values=ACTIONS, width=11).pack(side="left")
        RBtn(af, text="تسجيل", command=lambda n=n: self.start_learn(n), h=26, fs=9).pack(side="left", padx=3)
        mv = tk.StringVar(value=self.cfg["padmode"].get(n, MODES[0]))
        mv.trace_add("write", lambda *a, n=n, mv=mv: (self.cfg["padmode"].__setitem__(n, mv.get()), save_cfg(self.cfg)))
        ttk.Combobox(R, textvariable=mv, values=MODES, state="readonly", width=24).grid(row=r, column=2, padx=3)
        sv = tk.StringVar(value=str(self.cfg["padcps"].get(n, 15)))
        sv.trace_add("write", lambda *a, n=n, sv=sv: self.set_cps(n, sv.get()))
        ttk.Entry(R, textvariable=sv, width=9).grid(row=r, column=3, padx=3)
        c1, c2 = self.lbl(R, "0"), self.lbl(R, "-", fg=DM)
        c1.grid(row=r, column=4); c2.grid(row=r, column=5, padx=8)
        self.prow[n] = (c1, c2); self.rlab[n] = lb
        if n in self.pstat: self.draw_pad_row(n)

    def start_learn(self, n):
        self.learn_row, self.learn_t = n, time.perf_counter()
        if alive(getattr(self, "speedmsg", None)):
            self.speedmsg.config(text="اضغط الحين الزر أو الكليك اللي تبيه (Esc للإلغاء)", fg=self.cfg["accent"])

    def finish_learn(self, name, ts, mouse=False):
        if not self.learn_row or ts < self.learn_t + 0.25:
            return
        n, self.learn_row = self.learn_row, None
        if not mouse and name == "ESC":
            msg = "تم الإلغاء"
        else:
            tgt = {"left": "كليك يسار", "right": "كليك يمين", "middle": "كليك وسط"}.get(name) if mouse else name.lower()
            if tgt is None or parse_target(tgt) is None:
                msg = "هذا الزر مو مدعوم، جرّب زر ثاني"
            else:
                if n in self.pvars: self.pvars[n].set(tgt)
                msg = "تم: زر اليد %s ← %s" % (n, tgt)
        if alive(getattr(self, "speedmsg", None)):
            self.speedmsg.config(text=msg, fg=OK)

    def set_cps(self, n, s):
        self.cfg["padcps"][n] = s; save_cfg(self.cfg)
        try: over = float(s) > MAX_CPS
        except ValueError: over = False
        if alive(getattr(self, "speedmsg", None)):
            self.speedmsg.config(text=("السرعة فوق الحد، بتتحدد على %d ضغطة/ث" % MAX_CPS) if over else "", fg=BAD)

    def report_callback_exception(self, exc, val, tb):
        traceback.print_exception(exc, val, tb, file=LOG)

    def tick_info(self):
        now = time.perf_counter()
        for dq in (self.clicks, self.keyhits):
            while dq and now - dq[0] > 1: dq.popleft()
        j = next(iter(self.pads.values()), None)
        self.tiles["hz"].set("%.0f Hz" % self.hz); self.tiles["sp"].set("%.0f px/s" % self.sp)
        self.tiles["cps"].set(str(len(self.clicks))); self.tiles["kps"].set(str(len(self.keyhits)))
        self.info.config(text="الكيبورد:  %s\nالماوس:  %s\nاليد:  %s\nأعلى معدل استجابة:  %.0f Hz" % (
            " | ".join(self.dev_names[0]) or "جاري البحث...", " | ".join(self.dev_names[1]) or "جاري البحث...",
            j.get_name() if j else "غير متصلة", self.maxhz))
        self.after(200, self.tick_info)

if __name__ == "__main__":
    App().mainloop()
