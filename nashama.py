# -*- coding: utf-8 -*-
"""النشاما - Nashama: Input Devices Toolkit (Windows)"""
import os, sys, time, json, threading, subprocess, queue
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import keyboard as kb, mouse as ms
import pygame

BG, PN, AC, TX, DM, OK, BAD = "#0d1117", "#161b22", "#f5b301", "#e6edf3", "#8b949e", "#3fb950", "#f85149"
CHATTER = 0.04          # ضغطتين أسرع من 40ms = زر ضعيف/مضروب
NOWIN = 0x08000000 if os.name == "nt" else 0
KIND = {"Keyboard": "كيبورد", "Mouse": "ماوس", "HIDClass": "جهاز HID / يد", "XboxComposite": "يد Xbox"}


def ps(cmd):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                           text=True, creationflags=NOWIN, timeout=25)
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
    s = s.strip().lower()
    btn = {"left": ms.Button.left, "right": ms.Button.right, "middle": ms.Button.middle}
    if s in btn:
        return btn[s]
    if len(s) == 1:
        return s
    return getattr(kb.Key, s, None)


class Macro:
    """يكرر ضغطة (زر كيبورد أو كليك ماوس) بعدد ضغطات في الثانية"""
    def __init__(self):
        self.on, self.target, self.cps = False, "f5", 10.0

    def tap(self):
        t = parse_target(self.target)
        if t is None:
            return
        if isinstance(t, ms.Button):
            msc.click(t)
        else:
            kbc.press(t); kbc.release(t)

    def start(self):
        if not self.on:
            self.on = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.on = False

    def _run(self):
        while self.on:
            t0 = time.perf_counter()
            self.tap()
            time.sleep(max(0.0, 1 / max(self.cps, 0.1) - (time.perf_counter() - t0)))


def kname(k):
    return (k.char or str(k)).upper() if isinstance(k, kb.KeyCode) and k.char else str(k).replace("Key.", "").upper()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("النشاما | Nashama"); self.geometry("1020x700"); self.configure(bg=BG)
        self.q = queue.Queue(); self.devs = []; self.pads = {}
        self.kstat, self.mstat, self.pstat = {}, {}, {}
        self.kdown, self.klast_up, self.mlast = {}, {}, {}
        self.moves, self.maxhz, self.pos = [], 0, None
        self.mac, self.padmac = Macro(), Macro()
        self.hotkey, self.learn_pad, self.pad_trigger = "f6", False, None
        self.kb_enabled = True
        self.style()
        self.build()
        pygame.init(); pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i); self.pads[j.get_instance_id()] = j
        self.pad_ui()
        kb.Listener(on_press=self.kp, on_release=self.kr, daemon=True).start()
        ms.Listener(on_move=self.mm, on_click=self.mc, daemon=True).start()
        self.refresh_devices()
        self.after(30, self.loop); self.after(16, self.pad_loop); self.after(250, self.mouse_calc)
        self.after(2000, self.auto_refresh)

    # ---------- UI ----------
    def style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TX, fieldbackground=PN, font=("Segoe UI", 10))
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PN, foreground=DM, padding=(18, 9), font=("Segoe UI", 11, "bold"))
        s.map("TNotebook.Tab", background=[("selected", AC)], foreground=[("selected", "#000")])
        s.configure("Treeview", background=PN, fieldbackground=PN, foreground=TX, rowheight=26, borderwidth=0)
        s.configure("Treeview.Heading", background="#21262d", foreground=AC, font=("Segoe UI", 10, "bold"))
        s.configure("TButton", background=AC, foreground="#000", padding=8, font=("Segoe UI", 10, "bold"))
        s.map("TButton", background=[("active", "#ffd33d")])
        s.configure("TFrame", background=BG); s.configure("TLabel", background=BG)
        s.configure("TCheckbutton", background=BG, foreground=TX)
        s.configure("Horizontal.TProgressbar", background=AC, troughcolor=PN)

    def tree(self, parent, cols, widths):
        t = ttk.Treeview(parent, columns=cols, show="headings", height=9)
        for c, w in zip(cols, widths):
            t.heading(c, text=c); t.column(c, width=w, anchor="center")
        t.tag_configure("bad", foreground=BAD); t.tag_configure("ok", foreground=OK); t.tag_configure("down", background="#3d2f00")
        return t

    def build(self):
        head = tk.Canvas(self, height=84, bg=BG, highlightthickness=0); head.pack(fill="x")
        head.create_polygon(40, 10, 80, 22, 80, 52, 60, 76, 40, 70, 20, 52, 20, 22, fill=AC, outline="")
        head.create_text(50, 42, text="ن", font=("Segoe UI", 30, "bold"), fill="#000")
        head.create_text(105, 30, text="النشاما", font=("Segoe UI", 24, "bold"), fill=AC, anchor="w")
        head.create_text(105, 60, text="NASHAMA  •  Input Devices Toolkit", font=("Segoe UI", 10), fill=DM, anchor="w")
        self.badge = head.create_text(1000, 42, text="", font=("Segoe UI", 10, "bold"), fill=DM, anchor="e")
        self.head = head
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=8)
        self.tabs = {n: ttk.Frame(nb) for n in ("الأجهزة", "الكيبورد", "الماوس", "اليد", "الماكرو", "الإعدادات")}
        for n, f in self.tabs.items():
            nb.add(f, text=n)
        self.t_dev(); self.t_kb(); self.t_ms(); self.t_pad(); self.t_mac(); self.t_set()
        self.update_badge()

    def update_badge(self):
        self.head.itemconfig(self.badge, text=("● مدير" if is_admin() else "○ مو مدير (التعطيل يحتاج Admin)"),
                             fill=OK if is_admin() else DM)

    def t_dev(self):
        f = self.tabs["الأجهزة"]
        self.dt = self.tree(f, ("النوع", "الاسم", "الحالة"), (140, 560, 100)); self.dt.pack(fill="both", expand=True, padx=8, pady=8)
        b = ttk.Frame(f); b.pack(pady=6)
        for txt, fn in (("تحديث", self.refresh_devices), ("تعطيل (فصل)", lambda: self.dev_act("dis")),
                        ("تفعيل (توصيل)", lambda: self.dev_act("en")), ("إعادة ضبط", lambda: self.dev_act("rst"))):
            ttk.Button(b, text=txt, command=fn).pack(side="left", padx=5)
        self.dmsg = tk.Label(f, text="", bg=BG, fg=DM); self.dmsg.pack()

    def t_kb(self):
        f = self.tabs["الكيبورد"]
        self.klab = tk.Label(f, text="اضغط أي زر...", bg=BG, fg=AC, font=("Segoe UI", 20, "bold")); self.klab.pack(pady=8)
        self.kinfo = tk.Label(f, text="", bg=BG, fg=DM); self.kinfo.pack()
        self.kt = self.tree(f, ("الزر", "الضغطات", "متوسط الضغط ms", "تكرار خاطئ", "الحالة"), (130, 100, 150, 110, 140))
        self.kt.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(f, text="تصفير الإحصائيات", command=lambda: (self.kstat.clear(), self.kt.delete(*self.kt.get_children()))).pack(pady=4)

    def t_ms(self):
        f = self.tabs["الماوس"]
        self.mlab = tk.Label(f, text="حرّك الماوس...", bg=BG, fg=AC, font=("Segoe UI", 20, "bold")); self.mlab.pack(pady=8)
        self.mhz = tk.Label(f, text="Polling: -- Hz   |   أعلى: -- Hz   |   السرعة: -- px/s", bg=BG, fg=TX, font=("Segoe UI", 13)); self.mhz.pack()
        self.mt = self.tree(f, ("الزر", "الضغطات", "تكرار خاطئ", "الحالة"), (150, 120, 120, 150)); self.mt.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(f, text="تصفير", command=self.reset_mouse).pack(pady=4)

    def t_pad(self):
        f = self.tabs["اليد"]
        self.plab = tk.Label(f, text="وصّل اليد...", bg=BG, fg=AC, font=("Segoe UI", 18, "bold")); self.plab.pack(pady=6)
        self.pt = self.tree(f, ("الزر", "الضغطات", "تكرار خاطئ", "الحالة"), (150, 120, 120, 150)); self.pt.pack(fill="both", expand=True, padx=8)
        self.axf = ttk.Frame(f); self.axf.pack(fill="x", padx=12, pady=6); self.axb = []

    def t_mac(self):
        f = self.tabs["الماكرو"]
        def card(title):
            fr = tk.LabelFrame(f, text=title, bg=BG, fg=AC, font=("Segoe UI", 11, "bold"), padx=10, pady=8); fr.pack(fill="x", padx=12, pady=8); return fr
        c = card("ماكرو الكيبورد / الماوس  (تشغيل وإيقاف بزر)")
        self.m_t, self.m_c, self.m_h = tk.StringVar(value="f5"), tk.StringVar(value="10"), tk.StringVar(value="f6")
        for i, (l, v) in enumerate((("الزر المكرر (مثال: f5 / a / left)", self.m_t), ("كم ضغطة بالثانية", self.m_c), ("زر التشغيل/الإيقاف", self.m_h))):
            tk.Label(c, text=l, bg=BG, fg=TX).grid(row=i, column=1, sticky="e", padx=6, pady=3)
            ttk.Entry(c, textvariable=v, width=14).grid(row=i, column=0, pady=3)
        self.mstate = tk.Label(c, text="متوقف", bg=BG, fg=BAD, font=("Segoe UI", 12, "bold")); self.mstate.grid(row=3, column=0, columnspan=2)
        ttk.Button(c, text="تطبيق / تشغيل-إيقاف", command=self.mac_toggle).grid(row=4, column=0, columnspan=2, pady=4)
        c2 = card("ماكرو اليد  (اضغط زر باليد = يكرر ضغطة بالكيبورد/الماوس)")
        self.p_t, self.p_c = tk.StringVar(value="left"), tk.StringVar(value="15")
        for i, (l, v) in enumerate((("الهدف (left / space / e ...)", self.p_t), ("ضغطة بالثانية", self.p_c))):
            tk.Label(c2, text=l, bg=BG, fg=TX).grid(row=i, column=1, sticky="e", padx=6, pady=3)
            ttk.Entry(c2, textvariable=v, width=14).grid(row=i, column=0, pady=3)
        self.ptr = tk.Label(c2, text="الزر: غير محدد", bg=BG, fg=DM); self.ptr.grid(row=2, column=0, columnspan=2)
        ttk.Button(c2, text="حدّد زر اليد (اضغطه بعد الضغط)", command=self.start_learn).grid(row=3, column=0, columnspan=2, pady=4)
        tk.Label(f, text="تنبيه: بعض الألعاب الأونلاين بحظر الماكرو (Anti-Cheat). استخدمه على مسؤوليتك.", bg=BG, fg=DM).pack(pady=6)

    def t_set(self):
        f = self.tabs["الإعدادات"]
        self.top = tk.BooleanVar()
        ttk.Checkbutton(f, text="خلّي البرنامج فوق كل النوافذ", variable=self.top, command=lambda: self.attributes("-topmost", self.top.get())).pack(anchor="e", padx=20, pady=12)
        ttk.Button(f, text="تصفير كل الإحصائيات", command=self.reset_all).pack(pady=6)
        ttk.Button(f, text="ايقاف كل الماكرو", command=lambda: (self.mac.stop(), self.padmac.stop(), self.mstate.config(text="متوقف", fg=BAD))).pack(pady=6)
        tk.Label(f, text="فصل/توصيل الأجهزة من تبويب «الأجهزة» (يحتاج تشغيل كمسؤول).", bg=BG, fg=DM).pack(pady=14)

    # ---------- devices ----------
    def refresh_devices(self):
        def w():
            d = list_devices(); self.q.put(("devs", d))
        threading.Thread(target=w, daemon=True).start()

    def auto_refresh(self):
        self.refresh_devices(); self.after(3000, self.auto_refresh)

    def show_devs(self, d):
        self.devs = d; self.dt.delete(*self.dt.get_children())
        for x in d:
            self.dt.insert("", "end", iid=x["InstanceId"], values=(KIND.get(x["Class"], x["Class"]), x["FriendlyName"], x["Status"]))
        k = [x["FriendlyName"] for x in d if x["Class"] == "Keyboard"]; m = [x["FriendlyName"] for x in d if x["Class"] == "Mouse"]
        self.kinfo.config(text="الكيبورد: " + (" | ".join(k) or "غير معروف")); self.dev_names = (k, m)

    def dev_act(self, a):
        sel = self.dt.selection()
        if not sel:
            return messagebox.showinfo("النشاما", "اختر جهاز من القائمة")
        iid = sel[0].replace("'", "''")
        cmd = {"dis": f"Disable-PnpDevice -InstanceId '{iid}' -Confirm:$false",
               "en": f"Enable-PnpDevice -InstanceId '{iid}' -Confirm:$false",
               "rst": f"Disable-PnpDevice -InstanceId '{iid}' -Confirm:$false; Start-Sleep 1; Enable-PnpDevice -InstanceId '{iid}' -Confirm:$false"}[a]
        def w():
            ps(cmd); self.q.put(("msg", "تم تنفيذ الأمر (إذا ما اشتغل شغّل البرنامج كمسؤول)")); self.refresh_devices()
        threading.Thread(target=w, daemon=True).start()

    # ---------- input hooks ----------
    def kp(self, k):
        self.q.put(("kd", kname(k), time.perf_counter()))
    def kr(self, k):
        self.q.put(("ku", kname(k), time.perf_counter()))
    def mm(self, x, y):
        self.moves.append((time.perf_counter(), x, y))
    def mc(self, x, y, b, p):
        self.q.put(("mc", str(b).replace("Button.", ""), time.perf_counter(), p))

    def verdict(self, n, ch, avg=None):
        if ch >= 1:
            return "ضعيف ⚠", "bad"
        if avg is not None and n >= 5 and avg < 15:
            return "ضعيف ⚠", "bad"
        return "سليم ✔", "ok"

    def loop(self):
        try:
            while True:
                e = self.q.get_nowait(); t = e[0]
                if t == "devs": self.show_devs(e[1])
                elif t == "msg": self.dmsg.config(text=e[1])
                elif t == "kd":
                    n, ts = e[1], e[2]
                    if n not in self.kdown:
                        s = self.kstat.setdefault(n, {"n": 0, "d": [], "ch": 0}); s["n"] += 1
                        if n in self.klast_up and ts - self.klast_up[n] < CHATTER: s["ch"] += 1
                        self.kdown[n] = ts
                        self.klab.config(text=f"الزر: {n}"); self.draw_k(n)
                    if n == self.hotkey.upper() and not self.mac.on: pass
                    if n == self.m_h.get().strip().upper(): self.mac_toggle(True)
                elif t == "ku":
                    n, ts = e[1], e[2]
                    if n in self.kdown:
                        self.kstat[n]["d"].append((ts - self.kdown.pop(n)) * 1000); self.klast_up[n] = ts; self.draw_k(n)
                elif t == "mc":
                    b, ts, p = e[1], e[2], e[3]
                    if p:
                        s = self.mstat.setdefault(b, {"n": 0, "ch": 0}); s["n"] += 1
                        if b in self.mlast and ts - self.mlast[b] < CHATTER: s["ch"] += 1
                        self.mlast[b] = ts; self.mlab.config(text=f"زر الماوس: {b}"); self.draw_m(b)
        except queue.Empty:
            pass
        self.after(30, self.loop)

    def draw_k(self, n):
        s = self.kstat[n]; avg = sum(s["d"]) / len(s["d"]) if s["d"] else 0
        v, tag = self.verdict(s["n"], s["ch"], avg if s["d"] else None)
        vals = (n, s["n"], f"{avg:.0f}", s["ch"], v)
        if self.kt.exists(n): self.kt.item(n, values=vals, tags=(tag,))
        else: self.kt.insert("", "end", iid=n, values=vals, tags=(tag,))

    def draw_m(self, b):
        s = self.mstat[b]; v, tag = self.verdict(s["n"], s["ch"]); vals = (b, s["n"], s["ch"], v)
        if self.mt.exists(b): self.mt.item(b, values=vals, tags=(tag,))
        else: self.mt.insert("", "end", iid=b, values=vals, tags=(tag,))

    def mouse_calc(self):
        now = time.perf_counter(); self.moves = [m for m in self.moves if now - m[0] < 1.0]
        if len(self.moves) > 5:
            hz = len(self.moves) / max(self.moves[-1][0] - self.moves[0][0], 0.001)
            d = sum(((self.moves[i][1] - self.moves[i-1][1]) ** 2 + (self.moves[i][2] - self.moves[i-1][2]) ** 2) ** .5 for i in range(1, len(self.moves)))
            sp = d / max(self.moves[-1][0] - self.moves[0][0], 0.001); self.maxhz = max(self.maxhz, hz)
            names = getattr(self, "dev_names", ([], []))[1]
            self.mlab.config(text="الماوس: " + (" | ".join(names) or "غير معروف"))
            self.mhz.config(text=f"Polling: {hz:.0f} Hz   |   أعلى: {self.maxhz:.0f} Hz   |   السرعة: {sp:.0f} px/s")
        self.after(250, self.mouse_calc)

    def reset_mouse(self):
        self.mstat.clear(); self.mlast.clear(); self.maxhz = 0; self.mt.delete(*self.mt.get_children())

    def reset_all(self):
        self.kstat.clear(); self.kt.delete(*self.kt.get_children()); self.reset_mouse(); self.pstat.clear(); self.pad_ui()

    # ---------- macro ----------
    def mac_toggle(self, from_hotkey=False):
        self.mac.target = self.m_t.get(); self.hotkey = self.m_h.get().strip().lower()
        try: self.mac.cps = float(self.m_c.get())
        except ValueError: self.mac.cps = 10
        if self.mac.on: self.mac.stop()
        else: self.mac.start()
        self.mstate.config(text="يشتغل ▶" if self.mac.on else "متوقف", fg=OK if self.mac.on else BAD)

    def start_learn(self):
        self.learn_pad = True; self.ptr.config(text="اضغط الزر في اليد الحين...", fg=AC)

    # ---------- gamepad ----------
    def pad_ui(self):
        self.pt.delete(*self.pt.get_children())
        for w in self.axf.winfo_children(): w.destroy()
        self.axb = []
        if not self.pads:
            self.plab.config(text="وصّل اليد (PS5 / Xbox / أي يد)..."); return
        j = next(iter(self.pads.values()))
        self.plab.config(text=f"اليد: {j.get_name()}")
        for i in range(j.get_numbuttons()):
            self.pt.insert("", "end", iid=f"b{i}", values=(f"زر {i}", 0, 0, "سليم ✔"), tags=("ok",))
        for i in range(j.get_numaxes()):
            r = ttk.Frame(self.axf); r.pack(fill="x", pady=1)
            ttk.Label(r, text=f"محور {i}", width=8).pack(side="right")
            pb = ttk.Progressbar(r, maximum=200); pb.pack(fill="x", side="left", expand=True); self.axb.append(pb)

    def pad_loop(self):
        for e in pygame.event.get():
            if e.type == pygame.JOYDEVICEADDED:
                j = pygame.joystick.Joystick(e.device_index); self.pads[j.get_instance_id()] = j; self.pad_ui()
            elif e.type == pygame.JOYDEVICEREMOVED:
                self.pads.pop(e.instance_id, None); self.pad_ui()
            elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                i, down, ts = e.button, e.type == pygame.JOYBUTTONDOWN, time.perf_counter(); iid = f"b{i}"
                if down:
                    s = self.pstat.setdefault(i, {"n": 0, "ch": 0, "up": 0}); s["n"] += 1
                    if ts - s["up"] < CHATTER: s["ch"] += 1
                    if self.learn_pad:
                        self.pad_trigger, self.learn_pad = i, False; self.ptr.config(text=f"الزر المحدد: {i}", fg=OK)
                    elif i == self.pad_trigger:
                        self.padmac.target = self.p_t.get()
                        try: self.padmac.cps = float(self.p_c.get())
                        except ValueError: self.padmac.cps = 15
                        self.padmac.start()
                    if self.pt.exists(iid):
                        v, tag = self.verdict(s["n"], s["ch"]); self.pt.item(iid, values=(f"زر {i}", s["n"], s["ch"], v), tags=("down", tag))
                else:
                    if i in self.pstat: self.pstat[i]["up"] = ts
                    if i == self.pad_trigger: self.padmac.stop()
                    if self.pt.exists(iid):
                        s = self.pstat.get(i); v, tag = self.verdict(s["n"], s["ch"]); self.pt.item(iid, tags=(tag,))
        if self.pads:
            j = next(iter(self.pads.values()))
            for i, pb in enumerate(self.axb):
                try: pb["value"] = (j.get_axis(i) + 1) * 100
                except Exception: pass
        self.after(16, self.pad_loop)


if __name__ == "__main__":
    App().mainloop()
