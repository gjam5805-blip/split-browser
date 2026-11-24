"""
Multi Screen hotkey: Ctrl+Alt+M dabao -> Multi Screen khul jaye (khula ho toh aage aa jaye).
Windows login pe chupchaap chalta hai (Startup folder). Koi window nahi.
"""
import os
import sys
import ctypes
import subprocess
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, 'multiscreen.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32 = ctypes.WinDLL('user32', use_last_error=True)
k32.CreateMutexW.restype = wintypes.HANDLE

# ek hi copy
k32.CreateMutexW(None, False, 'MultiScreenHotkeyListener')
if ctypes.get_last_error() == 183:          # ERROR_ALREADY_EXISTS
    sys.exit(0)

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
VK_M, WM_HOTKEY = 0x4D, 0x0312
if not u32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_M):
    sys.exit(1)                              # koi aur app pehle se Ctrl+Alt+M le chuka hai

msg = wintypes.MSG()
while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
    if msg.message == WM_HOTKEY:
        # app khud dekh leta hai: pehle se khula ho toh wahi aage aata hai
        subprocess.Popen([PYW, APP], cwd=HERE)
