import subprocess
import winreg
import sys
import tempfile
import os
import ctypes
import time
import pyperclip
import atexit

sys.dont_write_bytecode = True

process = None
proxy_enabled = False


MITM_SCRIPT = r"""
from mitmproxy import http

def request(flow: http.HTTPFlow):
    url = flow.request.pretty_url

    if "query/summon" in url:
        print("SUMMON_URL:" + url, flush=True)
"""


def minimize_game():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    SW_MINIMIZE = 6

    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    IsWindowVisible = user32.IsWindowVisible
    ShowWindow = user32.ShowWindow
    OpenProcess = kernel32.OpenProcess
    GetModuleBaseNameW = ctypes.windll.psapi.GetModuleBaseNameW

    PROCESS_QUERY = 0x0400
    PROCESS_VM_READ = 0x0010

    def callback(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True

        pid = ctypes.c_ulong()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        h_process = OpenProcess(PROCESS_QUERY | PROCESS_VM_READ, False, pid.value)
        if not h_process:
            return True

        name = ctypes.create_unicode_buffer(260)
        GetModuleBaseNameW(h_process, None, name, 260)

        if name.value.lower() == "reverse1999.exe":
            ShowWindow(hwnd, SW_MINIMIZE)

        return True

    EnumWindows(EnumWindowsProc(callback), 0)


def enable_proxy():
    global proxy_enabled

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE,
    )

    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
    winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "127.0.0.1:8080")

    winreg.CloseKey(key)

    proxy_enabled = True
    print("Proxy enabled: 127.0.0.1:8080\n")


def disable_proxy():
    global proxy_enabled

    if not proxy_enabled:
        return

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_SET_VALUE,
        )

        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)

    except:
        pass

    proxy_enabled = False
    print("Proxy disabled")


def cleanup():
    global process

    if process:
        try:
            process.terminate()
        except:
            pass

    disable_proxy()


atexit.register(cleanup)


def main():
    global process

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
    temp.write(MITM_SCRIPT.encode())
    temp.close()

    enable_proxy()

    print("Starting capture...")
    print("Launch the game and open summon history\n")

    process = subprocess.Popen(
        ["mitmdump", "-q", "-s", temp.name],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    found_url = None

    try:
        for line in process.stdout:

            if line.startswith("SUMMON_URL:"):
                found_url = line.strip().replace("SUMMON_URL:", "")

                try:
                    pyperclip.copy(found_url)
                except:
                    pass

                time.sleep(3)
                break

    except KeyboardInterrupt:
        cleanup()
        sys.exit(0)

    if found_url:

        minimize_game()
        disable_proxy()

        print("\n=== SUMMON LINK FOUND ===")
        print(found_url)
        print("Link copied to clipboard")

        print("\nPress Enter to close...")
        input()

    cleanup()

    try:
        os.remove(temp.name)
    except:
        pass


if __name__ == "__main__":
    main()