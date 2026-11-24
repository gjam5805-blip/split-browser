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
import re
import threading
import subprocess
import urllib.parse
import urllib.request
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


def yt_top(q):
    """YouTube pe q dhoondh ke pehle video ka watch URL (bina API key)."""
    req = urllib.request.Request('https://www.youtube.com/results?hl=en&gl=IN&search_query=' + urllib.parse.quote(q),
                                 headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36',
                                          'Accept-Language': 'en-IN,en;q=0.9'})
    for _ in range(2):
        try:
            html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'replace')
        except Exception:
            continue
        m = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html) or re.search(r'"videoId":"([\w-]{11})"', html)
        if m:
            return 'https://www.youtube.com/watch?v=' + m.group(1)
    return 'https://www.youtube.com/results?search_query=' + urllib.parse.quote(q)


def find_claude():
    for p in (os.path.join(os.path.expanduser('~'), '.local', 'bin', 'claude.exe' if IS_WIN else 'claude'),
              '/opt/homebrew/bin/claude', '/usr/local/bin/claude'):
        if os.path.exists(p):
            return p
    return shutil.which('claude')


COMMAND_PROMPT = """Tum "Multi Screen" app ke andar ho. Screen pe kai Chrome windows grid me hain, number 1 se shuru (upar-left = 1, phir right, phir neeche wali line).
Abhi ki screens:
{state}

User ka command (Hindi/Hinglish/English): {cmd}

Isko actions me badlo. SIRF ek JSON array lautao, aur kuch nahi. Har action:
{{"screen": <number ya "all">, "do": "<action>", ...}}
Actions:
- "play": YouTube pe dhoondh ke pehla video chalao. field "q" = search words. (gaana/video/movie/trailer/news chalao, "X lagao" -> play)
- "ytsearch": YouTube results dikhao (jab user "dhoondo/list dikhao" bole, chalane ko nahi). field "q".
- "google": Google search. field "q". (price, info, kuch bhi dhoondhna)
- "open": website kholo. field "url" (pura https:// URL; jaise amazon -> https://www.amazon.in, netflix, hotstar, gmail, whatsapp web).
- "key": us screen pe control. field "key" = pause | play | fullscreen | mute | next | back10 | fwd10 | scroll_down | scroll_up | refresh | goback
- "close": wo screen band karo.
- "grid": kitni screens chahiye. field "count" (2,3,4,6,8,9,10,12). screen field ki zaroorat nahi.
- "volume": system volume. field "level" = up | down | mute.
- "say": samajh na aaye ya screen number na ho toh user se poochho. field "text" (Hinglish, chhota).
Agar screen number nahi bataya aur ek hi kaam hai, toh pehli khali/Google wali screen chuno, warna 1.
Example: "2 pe kesariya chalao, 3 pe amazon pe iphone 16" -> [{{"screen":2,"do":"play","q":"kesariya song"}},{{"screen":3,"do":"open","url":"https://www.amazon.in/s?k=iphone+16"}}]"""


KEY_WORDS = {'pause': 'pause', 'ruko': 'pause', 'roko': 'pause', 'stop': 'pause', 'play': 'play', 'resume': 'play',
             'mute': 'mute', 'unmute': 'mute', 'fullscreen': 'fullscreen', 'full screen': 'fullscreen', 'bada': 'fullscreen',
             'next': 'next', 'agla': 'next', 'agla video': 'next', 'refresh': 'refresh', 'reload': 'refresh',
             'neeche': 'scroll_down', 'scroll down': 'scroll_down', 'upar': 'scroll_up', 'scroll up': 'scroll_up',
             'peeche': 'back10', 'aage': 'fwd10', 'back': 'goback', 'wapas': 'goback'}


def quick_parse(text):
    """Seedhe commands bina Claude ke (tez): "2 pe X chalao", "3 pause", "sab pause", "1 band karo". Baaki -> None."""
    t = ' '.join(text.lower().strip().rstrip('.!').split())
    if re.search(r'\b(aur|and|then|phir)\b|,', t):
        return None
    m = re.match(r'^(?:screen\s*)?(\d{1,2}|sab|sabhi|all|saari|sare)\s*(?:wali|wale|number)?\s*(?:screens?)?\s*(?:pe|par|me|mein|ko|:|-)?\s*(.+)$', t)
    if not m:
        return None
    scr = 'all' if not m.group(1).isdigit() else int(m.group(1))
    rest = re.sub(r'\s*(karo|kar do|kardo|kar|please|plz|do)$', '', m.group(2)).strip()
    if rest in KEY_WORDS:
        return [{'screen': scr, 'do': 'key', 'key': KEY_WORDS[rest]}]
    if rest in ('band', 'close', 'hatao', 'hata'):
        return [{'screen': scr, 'do': 'close'}]
    m2 = re.match(r'^(.+?)\s+(chalao|chala|chalado|lagao|laga|play|bajao|baja|sunao|suna|dikhao|dikha)$', rest)
    if m2 and scr != 'all':
        q = m2.group(1)
        if re.match(r'^(youtube|you tube|yt)$', q):
            return [{'screen': scr, 'do': 'open', 'url': 'https://www.youtube.com/'}]
        return [{'screen': scr, 'do': 'play', 'q': q}]
    return None


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
        u.GetWindowTextW.argtypes = [H, wintypes.LPWSTR, ctypes.c_int]
        u.IsIconic.argtypes = [H]
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

    VK = {'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'space': 0x20, 'pageup': 0x21, 'pagedown': 0x22, 'left': 0x25,
          'right': 0x27, 'f5': 0x74, 'esc': 0x1B, 'volup': 0xAF, 'voldown': 0xAE, 'volmute': 0xAD}
    EXT = {0x21, 0x22, 0x25, 0x27, 0xAD, 0xAE, 0xAF}

    def title(self, h):
        n = self.u.GetWindowTextLengthW(h)
        buf = self.ct.create_unicode_buffer(n + 1)
        self.u.GetWindowTextW(h, buf, n + 1)
        return buf.value

    def _press(self, names):
        codes = [self.VK[k] if k in self.VK else ord(k.upper()) for k in names]
        for c in codes:
            self.u.keybd_event(c, 0, 1 if c in self.EXT else 0, 0)
        for c in reversed(codes):
            self.u.keybd_event(c, 0, (1 if c in self.EXT else 0) | 2, 0)

    def keys(self, h, names):
        """Us window ko aage lao aur keys dabao (jaise YouTube pe k = pause)."""
        u = self.u
        u.ShowWindow(h, 9) if u.IsIconic(h) else None
        u.keybd_event(0x12, 0, 0, 0)                 # Alt dabane se Windows focus badalne deta hai
        u.keybd_event(0x12, 0, 2, 0)
        u.SetForegroundWindow(h)
        time.sleep(0.3)
        self._press(names)

    def volume(self, level):
        key = {'up': 'volup', 'down': 'voldown', 'mute': 'volmute'}.get(level, 'volup')
        for _ in range(1 if key == 'volmute' else 5):
            self._press([key])
            time.sleep(0.03)


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

    def title(self, wid):
        return self.osa('tell application "Google Chrome" to get title of active tab of (first window whose id is %d)' % wid)

    MAC_CODES = {'pageup': 116, 'pagedown': 121, 'left': 123, 'right': 124, 'space': 49, 'esc': 53, 'f5': 96}

    def keys(self, wid, names):
        self.osa('tell application "Google Chrome"\nset index of (first window whose id is %d) to 1\nactivate\nend tell' % wid)
        time.sleep(0.3)
        modmap = {'shift': 'shift down', 'ctrl': 'control down', 'alt': 'option down', 'cmd': 'command down'}
        mods = [modmap[k] for k in names if k in modmap]
        for k in [k for k in names if k not in modmap]:
            if k == 'f5':
                k, mods = 'r', mods + ['command down']
            s = 'key code %d' % self.MAC_CODES[k] if k in self.MAC_CODES else 'keystroke "%s"' % k
            if mods:
                s += ' using {%s}' % ', '.join(mods)
            self.osa('tell application "System Events" to ' + s)

    def volume(self, level):
        if level == 'mute':
            self.osa('set volume output muted (not (output muted of (get volume settings)))')
        else:
            d = 10 if level == 'up' else -10
            self.osa('set volume output volume ((output volume of (get volume settings)) + %d)' % d)


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
        root.resizable(True, True)          # maximize button bhi chalega
        try:
            root.iconphoto(True, tk.PhotoImage(file=os.path.join(HERE, 'icon.png')))
        except Exception:
            pass
        f = tk.Frame(root, bg=BG, padx=16, pady=14)
        f.pack(fill='both', expand=True)
        tk.Label(f, text='Multi Screen', font=('Segoe UI', 17, 'bold'), fg=TEXT, bg=BG).pack(anchor='w')

        # ---- command box: jo bolo, screens pe ho jaye
        cbox = tk.Frame(f, bg=PANEL, padx=10, pady=8)
        cbox.pack(fill='x', pady=(6, 8))
        tk.Label(cbox, text='🎤 Command do (Win+H se bol bhi sakte ho):', fg=MUTED, bg=PANEL, font=('Segoe UI', 10)).pack(anchor='w')
        crow = tk.Frame(cbox, bg=PANEL)
        crow.pack(fill='x', pady=(4, 2))
        self.cmd = tk.Entry(crow, font=('Segoe UI', 12), bg=BG, fg=TEXT, insertbackground=TEXT, relief='flat')
        self.cmd.pack(side='left', fill='x', expand=True, ipady=6)
        self.cmd.bind('<Return>', lambda e: self.run_command())
        tk.Button(crow, text='▶ Karo', command=self.run_command, font=('Segoe UI', 11, 'bold'), relief='flat', bd=0, bg=GREEN,
                  fg='#06210f', activebackground='#2fc483', cursor='hand2').pack(side='left', padx=(6, 0), ipady=4, ipadx=6)
        self.hint = tk.Label(cbox, text='jaise: "2 pe kesariya chalao" · "sab pause" · "3 pe amazon pe iphone 16" · "1 band karo"',
                             fg=MUTED, bg=PANEL, font=('Segoe UI', 9), wraplength=330, justify='left')
        self.hint.pack(anchor='w')
        self.claude = find_claude()

        trow = tk.Frame(f, bg=BG)
        trow.pack(fill='x', pady=(0, 6))
        tk.Label(trow, text='Kitni screens chahiye?', fg=MUTED, bg=BG, font=('Segoe UI', 10)).pack(side='left')
        tk.Button(trow, text='🔢 Number dikhao', command=self.show_numbers, font=('Segoe UI', 9), relief='flat', bd=0, bg=PANEL,
                  fg=TEXT, activebackground=BLUE, cursor='hand2').pack(side='right', ipady=2, ipadx=4)

        grid = tk.Frame(f, bg=BG)
        grid.pack(fill='both', expand=True)          # badi window me number buttons bhi bade
        for c in range(4):
            grid.columnconfigure(c, weight=1)
        for r in range(2):
            grid.rowconfigure(r, weight=1)
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
        # window choti/badi ho toh text bhi uske hisaab se line tode
        f.bind('<Configure>', lambda e: (self.hint.config(wraplength=max(200, e.width - 60)),
                                         self.status.config(wraplength=max(200, e.width - 40))))
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())   # isse chhota nahi hoga
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
        if getattr(self, 'want_numbers', False):
            self.want_numbers = False
            self.show_numbers()
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

    def _set_count(self, n, opts, inner=False):
        was_busy = self.busy
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
            self.mark_to = n if n in self.count_btns else None
            self.want_numbers = True                 # kaunsi screen kaunsa number, 3 sec dikhao
        except Exception as e:
            self.say(f'⚠️ Gadbad: {e}', RED)
        finally:
            self.busy = was_busy if inner else False

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

    # ---------- screen numbers (har screen pe bada number, 3 sec)
    def show_numbers(self, secs=3):
        self.wins = [(h, a) for h, a in self.wins if self.be.alive(h)]
        if not self.wins:
            return self.say('Pehle screens kholo (upar number dabao).', MUTED)
        cells, _, _ = self.layout(len(self.wins), not self.wins[0][1], self.monitor())
        badges = []
        for i, (x, y, w, h) in enumerate(cells):
            t = tk.Toplevel(self.root)
            t.overrideredirect(True)
            t.attributes('-topmost', True)
            try:
                t.attributes('-alpha', 0.9)
            except Exception:
                pass
            tk.Label(t, text=str(i + 1), font=('Segoe UI', 44, 'bold'), fg='white', bg=BLUE, padx=26, pady=4).pack()
            t.update_idletasks()
            t.geometry('+%d+%d' % (x + w // 2 - t.winfo_width() // 2, y + h // 2 - t.winfo_height() // 2))
            badges.append(t)
        self.root.after(int(secs * 1000), lambda: [b.destroy() for b in badges])

    # ---------- commands: Claude samjhega, Multi Screen karega
    def run_command(self):
        text = self.cmd.get().strip()
        if not text or self.busy:
            return
        opts = (self.full.get(), START[self.start.get()], self.mon.get(), self.profile_dir())
        threading.Thread(target=self._run_command, args=(text, opts), daemon=True).start()

    def ask_claude(self, text):
        self.wins = [(h, a) for h, a in self.wins if self.be.alive(h)]
        state = '\n'.join(f'{i + 1}: {self.be.title(h)[:90] or "(khali)"}' for i, (h, a) in enumerate(self.wins)) or '(abhi koi screen khuli nahi)'
        prompt = COMMAND_PROMPT.format(state=state, cmd=text)
        if not self.claude:
            raise RuntimeError('Claude is laptop pe nahi mila')
        r = subprocess.run([self.claude, '-p', '--model', 'haiku', '--tools', '', '--strict-mcp-config', '--disable-slash-commands'],
                           input=prompt.encode('utf-8'), capture_output=True, timeout=90,
                           creationflags=0x08000000 if IS_WIN else 0)
        out = r.stdout.decode('utf-8', 'replace')
        m = re.search(r'\[.*\]', out, re.S)
        if not m:
            err = (r.stderr.decode('utf-8', 'replace') + out).strip()[-200:]
            raise RuntimeError('Claude ka jawab samajh nahi aaya: ' + (err or 'khali'))
        return json.loads(m.group(0))

    def _run_command(self, text, opts):
        self.busy = True
        full, url, mon_idx, profile = opts
        try:
            t0 = time.time()
            actions = quick_parse(text)
            if actions is None:
                self.say(f'🤔 Claude samajh raha hai: "{text}"…', TEXT)
                actions = self.ask_claude(text)
            else:
                self.say(f'⚡ "{text}"…', TEXT)
            done = []
            for a in actions:
                done.append(self.do_action(a, opts))
            done = [d for d in done if d]
            self.say('✅ ' + ' · '.join(done) + f'  ({time.time() - t0:.0f}s)' if done else '🤷 Kuch karne layak nahi mila.', GREEN if done else MUTED)
            self.root.after(0, lambda: self.cmd.delete(0, 'end'))
        except Exception as e:
            self.say(f'⚠️ {e}', RED)
        finally:
            self.busy = False

    KEYS = {'pause': ['k'], 'play': ['k'], 'fullscreen': ['f'], 'mute': ['m'], 'next': ['shift', 'n'], 'back10': ['j'],
            'fwd10': ['l'], 'scroll_down': ['pagedown'], 'scroll_up': ['pageup'], 'refresh': ['f5'],
            'goback': ['alt', 'left'] if IS_WIN else ['cmd', '[']}

    def do_action(self, a, opts):
        full, url, mon_idx, profile = opts
        do = str(a.get('do', '')).lower()
        if do == 'say':
            return '💬 ' + str(a.get('text', ''))
        if do == 'volume':
            self.be.volume(str(a.get('level', 'up')))
            return 'volume ' + str(a.get('level', ''))
        if do == 'grid':
            n = int(a.get('count', 4))
            self._set_count(n, opts, inner=True)
            return f'{n} screens'
        scr = a.get('screen', 1)
        self.wins = [(h, ap) for h, ap in self.wins if self.be.alive(h)]
        targets = list(range(len(self.wins))) if str(scr).lower() == 'all' else [int(scr) - 1]
        need = max(targets) + 1 if targets else 1
        if need > len(self.wins):                                  # screen nahi hai toh grid badha do
            n = next((c for c in COUNTS if c >= need), need)
            self._set_count(n, opts, inner=True)
            self.wins = [(h, ap) for h, ap in self.wins if self.be.alive(h)]
        names = []
        for i in targets:
            if i >= len(self.wins):
                continue
            h, app = self.wins[i]
            if do == 'key':
                k = self.KEYS.get(str(a.get('key', '')).lower())
                if k:
                    self.be.keys(h, k)
                    names.append(f'{i + 1}: {a.get("key")}')
            elif do == 'close':
                self.be.close(h)
                self.wins[i] = (None, app)
                names.append(f'{i + 1} band')
            elif do in ('play', 'ytsearch', 'google', 'open'):
                q = str(a.get('q', ''))
                if do == 'play':
                    target = yt_top(q)
                elif do == 'ytsearch':
                    target = 'https://www.youtube.com/results?search_query=' + urllib.parse.quote(q)
                elif do == 'google':
                    target = 'https://www.google.com/search?q=' + urllib.parse.quote(q)
                else:
                    target = str(a.get('url', ''))
                    if not re.match(r'https?://', target):
                        target = 'https://' + target
                self.replace(i, target, profile, mon_idx)
                names.append(f'{i + 1}: {"▶ " + q if do == "play" else q or target}')
        self.wins = [(h, ap) for h, ap in self.wins if h]
        if do == 'close' and self.wins:                            # bachi hui screens phir se grid me
            cells, _, _ = self.layout(len(self.wins), not self.wins[0][1], self.monitor(mon_idx))
            for k, (h, ap) in enumerate(self.wins):
                self.be.place(h, *cells[k])
            self.want_numbers = True
        return ' · '.join(names)

    def replace(self, i, target, profile, mon_idx=0):
        """Screen i me naya page: wahi jagah pe nayi window, purani band (patli windows me address bar nahi hota)."""
        h_old, app = self.wins[i]
        cells, _, _ = self.layout(len(self.wins), not app, self.monitor(mon_idx))
        h_new = self.be.open(target, app, profile)
        if not h_new:
            raise RuntimeError(f'Screen {i + 1} pe page nahi khula')
        self.be.place(h_new, *cells[i])
        self.be.close(h_old)
        self.wins[i] = (h_new, app)
        time.sleep(0.4)
        self.be.place(h_new, *cells[i])

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
    import socket
    lock = socket.socket()
    try:
        lock.bind(('127.0.0.1', 47391))          # ek hi copy chale
    except OSError:
        if IS_WIN:                                # pehle se khula hai: usi ko aage le aao
            import ctypes
            u = ctypes.WinDLL('user32')
            h = u.FindWindowW('TkTopLevel', 'Multi Screen')
            if h:
                u.ShowWindow(h, 9)
                u.keybd_event(0x12, 0, 0, 0)
                u.keybd_event(0x12, 0, 2, 0)
                u.SetForegroundWindow(h)
        return
    root = tk.Tk()
    App(root)
    root.lift()                                   # khulte hi sabse aage dikhe
    root.attributes('-topmost', True)
    root.after(800, lambda: root.attributes('-topmost', False))
    root.focus_force()
    root.mainloop()


if __name__ == '__main__':
    main()
