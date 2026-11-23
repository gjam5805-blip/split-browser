#!/usr/bin/env python3
"""
Multi Screen - ek click me kai ASLI Chrome windows, screen pe grid me set.
Windows + Mac. Sirf Python (tkinter) chahiye.

Har screen asli Chrome hai, toh YouTube (recommendations, login, video), Netflix, sab chalta hai.
"Poora Chrome" = tabs + address bar wali normal window (patli nahi ho sakti, isliye kam column).
"Patli windows" = Chrome app window (address bar nahi), 10-12 screens bhi aa jati hain.
"""
import os
import sys
import json
import math
import time
import shutil
import threading
import subprocess
try:
    import tkinter as tk
except Exception:          # kuch Mac pe tkinter nahi hota: tab terminal wala menu chalega
    tk = None

IS_WIN = os.name == 'nt'
IS_MAC = sys.platform == 'darwin'
HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, 'settings.json')
COUNTS = [2, 3, 4, 6, 8, 9, 10, 12]
LAYOUT = {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 5: (3, 2), 6: (3, 2), 7: (4, 2), 8: (4, 2),
          9: (3, 3), 10: (5, 2), 11: (4, 3), 12: (4, 3)}
START = {'Google': 'https://www.google.com/', 'YouTube': 'https://www.youtube.com/'}
NORMAL_MIN_DIP = 505      # Chrome ki normal window isse patli nahi hoti (measured: 754px @150%)


def chrome_profiles():
    """[(folder, naam)] Chrome ke profiles, aur last used folder."""
    if IS_WIN:
        p = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Local State')
    else:
        p = os.path.expanduser('~/Library/Application Support/Google/Chrome/Local State')
    try:
        with open(p, encoding='utf-8') as f:
            prof = json.load(f).get('profile', {})
    except Exception:
        return [('Default', 'Default')], 'Default'
    items = [(k, (v.get('name') or k).strip()) for k, v in prof.get('info_cache', {}).items()]
    names = [n for _, n in items]
    items = [(k, n if names.count(n) == 1 else f'{n} ({k})') for k, n in items]   # do "Work" ho toh folder bhi dikhao
    items.sort(key=lambda x: x[1].lower())
    return items or [('Default', 'Default')], prof.get('last_used', 'Default')


def load_settings():
    try:
        with open(SETTINGS, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d):
    try:
        with open(SETTINGS, 'w', encoding='utf-8') as f:
            json.dump(d, f)
    except Exception:
        pass


# ------------------------------------------------------------------ Windows
class WinBackend:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct, self.wt = ctypes, wintypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # asli pixels me kaam
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        u = self.u = ctypes.WinDLL('user32', use_last_error=True)
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.dwm = ctypes.WinDLL('dwmapi')
        H = wintypes.HWND

        class RECT(ctypes.Structure):
            _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long), ('r', ctypes.c_long), ('b', ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', RECT), ('rcWork', RECT), ('dwFlags', wintypes.DWORD)]
        self.RECT, self.MONITORINFO = RECT, MONITORINFO
        self.ENUMWIN = ctypes.WINFUNCTYPE(wintypes.BOOL, H, wintypes.LPARAM)
        self.ENUMMON = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), wintypes.LPARAM)
        u.EnumWindows.argtypes = [self.ENUMWIN, wintypes.LPARAM]
        u.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, self.ENUMMON, wintypes.LPARAM]
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        u.IsWindow.argtypes = [H]
        u.IsWindowVisible.argtypes = [H]
        u.GetClassNameW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowTextLengthW.argtypes = [H]
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
        u.SetWindowPos.argtypes = [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u.ShowWindow.argtypes = [H, ctypes.c_int]
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(RECT)]
        u.PostMessageW.argtypes = [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.SetForegroundWindow.argtypes = [H]
        self.k.OpenProcess.restype = wintypes.HANDLE
        self.k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.chrome = self.find_chrome()

    @staticmethod
    def find_chrome():
        for base in (os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                     os.environ.get('LOCALAPPDATA', '')):
            p = os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')
            if base and os.path.exists(p):
                return p
        return shutil.which('chrome')

    def monitors(self):
        ct, out = self.ct, []

        def cb(hmon, hdc, rc, lp):
            mi = self.MONITORINFO()
            mi.cbSize = ct.sizeof(self.MONITORINFO)
            self.u.GetMonitorInfoW(hmon, ct.byref(mi))
            dpi_x, dpi_y = self.wt.UINT(96), self.wt.UINT(96)
            try:
                ct.windll.shcore.GetDpiForMonitor(ct.c_void_p(hmon), 0, ct.byref(dpi_x), ct.byref(dpi_y))
            except Exception:
                pass
            w = mi.rcWork
            out.append({'work': (w.l, w.t, w.r, w.b), 'primary': bool(mi.dwFlags & 1), 'scale': dpi_x.value / 96.0})
            return True
        self.u.EnumDisplayMonitors(None, None, self.ENUMMON(cb), 0)
        out.sort(key=lambda m: (not m['primary'], m['work'][0]))
        return out or [{'work': (0, 0, 1920, 1040), 'primary': True, 'scale': 1.0}]

    def _exe(self, h):
        ct, wt = self.ct, self.wt
        pid = wt.DWORD()
        self.u.GetWindowThreadProcessId(h, ct.byref(pid))
        hp = self.k.OpenProcess(0x1000, False, pid.value)
        if not hp:
            return ''
        buf = ct.create_unicode_buffer(520)
        n = wt.DWORD(520)
        ok = self.k.QueryFullProcessImageNameW(hp, 0, buf, ct.byref(n))
        self.k.CloseHandle(hp)
        return buf.value.lower() if ok else ''

    def chrome_windows(self):
        out = set()

        def cb(h, lp):
            if self.u.IsWindowVisible(h) and self.u.GetWindowTextLengthW(h) > 0:
                buf = self.ct.create_unicode_buffer(64)
                self.u.GetClassNameW(h, buf, 64)
                if buf.value == 'Chrome_WidgetWin_1' and self._exe(h).endswith('chrome.exe'):
                    out.add(h)
            return True
        self.u.EnumWindows(self.ENUMWIN(cb), 0)
        return out

    def open(self, url, app, profile=None):
        before = self.chrome_windows()
        args = [self.chrome] + (['--profile-directory=' + profile] if profile else [])
        args += ['--app=' + url] if app else ['--new-window', url]
        subprocess.Popen(args, creationflags=0x08000000)
        for _ in range(100):                       # ~10 sec tak nayi window dhoondo
            time.sleep(0.1)
            new = self.chrome_windows() - before
            if new:
                return sorted(new)[0]
        return None

    def place(self, h, x, y, w, hh):
        u, ct = self.u, self.ct
        u.ShowWindow(h, 9)                          # maximize ho toh normal karo
        flags = 0x0004 | 0x0010                     # NOZORDER | NOACTIVATE
        u.SetWindowPos(h, None, x, y, w, hh, flags)
        # Windows 10/11 me window ke chaaron taraf invisible border hota hai; use hata ke exact fit
        r, e = self.RECT(), self.RECT()
        u.GetWindowRect(h, ct.byref(r))
        if self.dwm.DwmGetWindowAttribute(h, 9, ct.byref(e), ct.sizeof(e)) == 0:
            bl, bt, br, bb = e.l - r.l, e.t - r.t, r.r - e.r, r.b - e.b
            u.SetWindowPos(h, None, x - bl, y - bt, w + bl + br, hh + bt + bb, flags)

    def alive(self, h):
        return bool(self.u.IsWindow(h)) and bool(self.u.IsWindowVisible(h))

    def close(self, h):
        self.u.PostMessageW(h, 0x0010, 0, 0)        # WM_CLOSE

    def focus(self, h):
        self.u.SetForegroundWindow(h)


# ------------------------------------------------------------------ Mac
class MacBackend:
    def __init__(self):
        self.chrome = '/Applications/Google Chrome.app' if os.path.exists('/Applications/Google Chrome.app') else None

    @staticmethod
    def osa(script):
        r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()

    def monitors(self):
        b = self.osa('tell application "Finder" to get bounds of window of desktop')
        try:
            l, t, r, bt = [int(x) for x in b.split(',')]
        except Exception:
            l, t, r, bt = 0, 0, 1440, 900
        return [{'work': (l, t + 33, r, bt), 'primary': True, 'scale': 1.0}]   # upar menu bar

    def ids(self):
        out = self.osa('tell application "Google Chrome" to get id of every window')
        return [int(x) for x in out.replace(' ', '').split(',') if x.strip().isdigit()]

    def open(self, url, app, profile=None):
        before = set(self.ids())
        args = ['open', '-na', 'Google Chrome', '--args'] + (['--profile-directory=' + profile] if profile else [])
        args += ['--app=' + url] if app else ['--new-window', url]
        subprocess.run(args)
        for _ in range(100):
            time.sleep(0.1)
            new = set(self.ids()) - before
            if new:
                return sorted(new)[0]
        return None

    def place(self, wid, x, y, w, h):
        self.osa('tell application "Google Chrome" to set bounds of (first window whose id is %d) to {%d, %d, %d, %d}' % (wid, x, y, x + w, y + h))

    def alive(self, wid):
        return wid in self.ids()

    def close(self, wid):
        self.osa('tell application "Google Chrome" to close (first window whose id is %d)' % wid)

    def focus(self, wid):
        self.osa('tell application "Google Chrome" to activate')


# ------------------------------------------------------------------ App (control panel)
BG, PANEL, TEXT, MUTED, BLUE, RED, GREEN = '#0f1115', '#171a21', '#eef1f6', '#9aa3b2', '#4dabff', '#ff4d6d', '#3ddc97'


class App:
    def __init__(self, root):
        self.root = root
        self.be = WinBackend() if IS_WIN else MacBackend()
        self.s = load_settings()
        self.wins = []            # [(handle, is_app)]
        self.busy = False
        self.msgs = []
        self.mark_to = False
        root.title('Multi Screen')
        root.configure(bg=BG)
        root.resizable(False, False)
        try:
            root.iconphoto(True, tk.PhotoImage(file=os.path.join(HERE, 'icon.png')))
        except Exception:
            pass
        f = tk.Frame(root, bg=BG, padx=16, pady=14)
        f.pack(fill='both')
        tk.Label(f, text='Multi Screen', font=('Segoe UI', 17, 'bold'), fg=TEXT, bg=BG).pack(anchor='w')
        tk.Label(f, text='Har screen asli Chrome. Kitni screens chahiye?', fg=MUTED, bg=BG, font=('Segoe UI', 10)).pack(anchor='w', pady=(0, 8))

        grid = tk.Frame(f, bg=BG)
        grid.pack(fill='x')
        self.count_btns = {}
        for i, n in enumerate(COUNTS):
            b = tk.Button(grid, text=str(n), width=4, font=('Segoe UI', 14, 'bold'), relief='flat', bd=0, cursor='hand2',
                          bg=PANEL, fg=TEXT, activebackground=BLUE, activeforeground='white', command=lambda n=n: self.set_count(n))
            b.grid(row=i // 4, column=i % 4, padx=4, pady=4, ipady=6, sticky='nsew')
            self.count_btns[n] = b

        self.full = tk.BooleanVar(value=self.s.get('full', True))
        self.start = tk.StringVar(value=self.s.get('start', 'Google'))
        self.mon = tk.IntVar(value=self.s.get('monitor', 0))
        box = tk.Frame(f, bg=PANEL, padx=10, pady=8)
        box.pack(fill='x', pady=(10, 4))
        tk.Label(box, text='Window kaisi ho:', fg=MUTED, bg=PANEL, font=('Segoe UI', 10)).pack(anchor='w')
        for val, txt in ((True, 'Poora Chrome (tabs + address bar)'), (False, 'Patli windows (zyada screens, address bar nahi)')):
            tk.Radiobutton(box, text=txt, variable=self.full, value=val, fg=TEXT, bg=PANEL, selectcolor=BG, activebackground=PANEL,
                           activeforeground=TEXT, font=('Segoe UI', 10), command=self.remember).pack(anchor='w')
        self.profiles, last = chrome_profiles()
        dirs = [d for d, _ in self.profiles]
        default = self.s.get('profile')
        if default not in dirs:
            default = next((d for d, n in self.profiles if 'shivam' in n.lower()), last if last in dirs else dirs[0])
        self.profile = tk.StringVar(value=dict(self.profiles)[default])
        prow = tk.Frame(box, bg=PANEL)
        prow.pack(anchor='w', pady=(6, 0))
        tk.Label(prow, text='Chrome profile:', fg=MUTED, bg=PANEL, font=('Segoe UI', 10)).pack(side='left')
        om = tk.OptionMenu(prow, self.profile, *[n for _, n in self.profiles], command=lambda _=None: self.remember())
        om.config(bg=BG, fg=TEXT, activebackground=BLUE, activeforeground='white', relief='flat', highlightthickness=0, font=('Segoe UI', 10))
        om['menu'].config(bg=PANEL, fg=TEXT, activebackground=BLUE, font=('Segoe UI', 10))
        om.pack(side='left', padx=6)
        row = tk.Frame(box, bg=PANEL)
        row.pack(anchor='w', pady=(6, 0))
        tk.Label(row, text='Har screen me khule:', fg=MUTED, bg=PANEL, font=('Segoe UI', 10)).pack(side='left')
        for k in START:
            tk.Radiobutton(row, text=k, variable=self.start, value=k, fg=TEXT, bg=PANEL, selectcolor=BG, activebackground=PANEL,
                           activeforeground=TEXT, font=('Segoe UI', 10), command=self.remember).pack(side='left', padx=4)
        mons = self.be.monitors()
        if len(mons) > 1:
            row2 = tk.Frame(box, bg=PANEL)
            row2.pack(anchor='w', pady=(6, 0))
            tk.Label(row2, text='Kis screen pe:', fg=MUTED, bg=PANEL, font=('Segoe UI', 10)).pack(side='left')
            for i, m in enumerate(mons):
                tk.Radiobutton(row2, text='Laptop' if m['primary'] else 'Projector %d' % i, variable=self.mon, value=i, fg=TEXT, bg=PANEL,
                               selectcolor=BG, activebackground=PANEL, activeforeground=TEXT, font=('Segoe UI', 10),
                               command=self.remember).pack(side='left', padx=4)

        acts = tk.Frame(f, bg=BG)
        acts.pack(fill='x', pady=(8, 0))
        tk.Button(acts, text='↻ Phir se set karo', command=self.retile_async, font=('Segoe UI', 11, 'bold'), relief='flat', bd=0,
                  bg=BLUE, fg='white', activebackground='#3a92e0', cursor='hand2').pack(side='left', expand=True, fill='x', padx=(0, 4), ipady=6)
        tk.Button(acts, text='✕ Sab band karo', command=self.close_all, font=('Segoe UI', 11, 'bold'), relief='flat', bd=0,
                  bg=RED, fg='white', activebackground='#e0435f', cursor='hand2').pack(side='left', expand=True, fill='x', padx=(4, 0), ipady=6)
        self.status = tk.Label(f, text='Number dabao, utni Chrome windows khul ke grid me lag jayengi.', fg=MUTED, bg=BG,
                               font=('Segoe UI', 9), wraplength=330, justify='left')
        self.status.pack(anchor='w', pady=(10, 0))
        if not self.be.chrome:
            self.say('⚠️ Google Chrome nahi mila. Pehle Chrome install karo.', RED)
        self._poll()

    # ---------- helpers
    def profile_dir(self):
        name = self.profile.get()
        return next((d for d, n in self.profiles if n == name), None)

    def remember(self):
        self.s.update(full=self.full.get(), start=self.start.get(), monitor=self.mon.get(), profile=self.profile_dir())
        save_settings(self.s)

    def say(self, text, color=MUTED):
        self.msgs.append((text, color))          # background thread se seedha Tk ko mat chhuo

    def _poll(self):
        while self.msgs:
            text, color = self.msgs.pop(0)
            self.status.config(text=text, fg=color)
        if self.mark_to is not False:
            n, self.mark_to = self.mark_to, False
            self.mark(n)
        self.root.after(120, self._poll)

    def monitor(self, idx=None):
        mons = self.be.monitors()
        i = self.mon.get() if idx is None else idx
        return mons[i] if i < len(mons) else mons[0]

    def layout(self, n, full, mon):
        l, t, r, b = mon['work']
        W, H = r - l, b - t
        if full:
            min_w = int(NORMAL_MIN_DIP * mon['scale'])
            cols = max(1, min(n, W // min_w))
            cols = min(cols, LAYOUT.get(n, (n, 1))[0]) if n in LAYOUT else cols
            rows = math.ceil(n / cols)
        else:
            cols, rows = LAYOUT.get(n) or (math.ceil(math.sqrt(n)), math.ceil(n / math.ceil(math.sqrt(n))))
        cells = []
        for i in range(n):
            c, rw = i % cols, i // cols
            x0 = l + round(c * W / cols)
            x1 = l + round((c + 1) * W / cols)
            y0 = t + round(rw * H / rows)
            y1 = t + round((rw + 1) * H / rows)
            cells.append((x0, y0, x1 - x0, y1 - y0))
        return cells, cols, rows

    def mark(self, n):
        for k, b in self.count_btns.items():
            b.config(bg=BLUE if k == n else PANEL)

    # ---------- actions
    def set_count(self, n):
        if self.busy:
            return
        self.mark(n)
        opts = (self.full.get(), START[self.start.get()], self.mon.get(), self.profile_dir())   # Tk values main thread me hi padho
        threading.Thread(target=self._set_count, args=(n, opts), daemon=True).start()

    def _set_count(self, n, opts):
        self.busy = True
        try:
            full, url, mon_idx, profile = opts
            mon = self.monitor(mon_idx)
            self.wins = [(h, a) for h, a in self.wins if self.be.alive(h)]
            want_app = not full
            # galat type wali windows (patli <-> poori) band karke nayi kholo
            for h, a in [w for w in self.wins if w[1] != want_app]:
                self.be.close(h)
            self.wins = [w for w in self.wins if w[1] == want_app]
            while len(self.wins) > n:                # zyada hain toh aakhri wali band
                h, a = self.wins.pop()
                self.be.close(h)
            cells, cols, rows = self.layout(n, full, mon)
            for i, (h, a) in enumerate(self.wins):
                self.be.place(h, *cells[i])
            while len(self.wins) < n:
                i = len(self.wins)
                self.say(f'Chrome window {i + 1}/{n} khol raha hoon…', TEXT)
                h = self.be.open(url, want_app, profile)
                if not h:
                    self.say('⚠️ Chrome window nahi khuli. Chrome chalu hai? Dobara try karo.', RED)
                    return
                self.wins.append((h, want_app))
                self.be.place(h, *cells[i])
            # Chrome kabhi kabhi khulte waqt khud size badal deta hai, isliye ek baar aur
            time.sleep(0.6)
            for i, (h, a) in enumerate(self.wins):
                self.be.place(h, *cells[i])
            msg = f'✅ {n} Chrome windows {cols}×{rows} grid me.'
            if full and cols < (LAYOUT.get(n) or (cols,))[0]:
                msg += ' Poori Chrome window isse patli nahi hoti; zyada column chahiye toh "Patli windows" chuno.'
            self.say(msg, GREEN)
        except Exception as e:
            self.say(f'⚠️ Gadbad: {e}', RED)
        finally:
            self.busy = False

    def retile_async(self):
        if not self.busy:
            threading.Thread(target=self._retile, args=(self.mon.get(),), daemon=True).start()

    def _retile(self, mon_idx):
        self.busy = True
        try:
            self.wins = [(h, a) for h, a in self.wins if self.be.alive(h)]
            if not self.wins:
                return self.say('Koi Multi Screen window khuli nahi hai. Upar number dabao.', MUTED)
            n = len(self.wins)
            cells, cols, rows = self.layout(n, not self.wins[0][1], self.monitor(mon_idx))
            for i, (h, a) in enumerate(self.wins):
                self.be.place(h, *cells[i])
            self.mark_to = n if n in self.count_btns else None
            self.say(f'✅ {n} windows phir se {cols}×{rows} me set.', GREEN)
        finally:
            self.busy = False

    def close_all(self):
        for h, a in self.wins:
            try:
                if self.be.alive(h):
                    self.be.close(h)
            except Exception:
                pass
        self.wins = []
        self.mark(None)
        self.say('Sab Multi Screen windows band kar di.', MUTED)


def terminal_menu():
    """tkinter na ho toh simple number wala menu."""
    be = WinBackend() if IS_WIN else MacBackend()
    s = load_settings()
    profs, last = chrome_profiles()
    prof = s.get('profile') or next((d for d, n in profs if 'shivam' in n.lower()), last)
    wins = []
    print('\nMulti Screen (terminal)  —  Chrome profile:', dict(profs).get(prof, prof))
    while True:
        c = input('\nKitni screens? (2/3/4/6/8/9/10/12, p = patli windows ke saath, x = sab band, q = bahar): ').strip().lower()
        if c == 'q':
            break
        if c == 'x':
            for h, a in wins:
                be.close(h)
            wins = []
            continue
        app = c.startswith('p')
        try:
            n = int(c.lstrip('p'))
        except ValueError:
            continue
        for h, a in wins:
            be.close(h)
        wins = []
        mon = be.monitors()[0]
        l, t, r, b = mon['work']
        W, H = r - l, b - t
        cols, rows = LAYOUT.get(n, (n, 1)) if app else (max(1, min(n, W // int(NORMAL_MIN_DIP * mon['scale']))), 0)
        rows = rows or math.ceil(n / cols)
        for i in range(n):
            h = be.open(START['YouTube'] if s.get('start') == 'YouTube' else START['Google'], app, prof)
            if h:
                c_, r_ = i % cols, i // cols
                be.place(h, l + c_ * W // cols, t + r_ * H // rows, W // cols, H // rows)
                wins.append((h, app))
        print(f'✅ {len(wins)} windows {cols}×{rows}')


def main():
    if tk is None:
        return terminal_menu()
    if len(sys.argv) > 1 and sys.argv[1] == 'test':          # bina UI ke: python multiscreen.py test 4 [app]
        root = tk.Tk()
        root.withdraw()
        a = App(root)
        full = not (len(sys.argv) > 3 and sys.argv[3] == 'app')
        a._set_count(int(sys.argv[2]) if len(sys.argv) > 2 else 4, (full, START['Google'], 0))
        print(a.msgs[-1][0] if a.msgs else '')
        print('windows:', len(a.wins))
        if len(sys.argv) > 4 and sys.argv[4] == 'close':
            time.sleep(float(sys.argv[5]) if len(sys.argv) > 5 else 3)
            a.close_all()
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
