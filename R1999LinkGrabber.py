import asyncio
import ctypes
import socket
import sys
import winreg
from ctypes import wintypes

from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

sys.dont_write_bytecode = True

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
URL_MARKER = "query/summon"
GAME_EXE = "reverse1999.exe"
GRACE_SECONDS = 3

INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
wininet = ctypes.WinDLL("wininet", use_last_error=True)


class SystemProxy:
    _MISSING = object()
    _VALUES = ("ProxyEnable", "ProxyServer")

    def __init__(self):
        self._saved = None

    @staticmethod
    def _notify():
        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        wininet.InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
        wininet.InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)

    def enable(self, server):
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        ) as key:
            saved = {}
            for name in self._VALUES:
                try:
                    saved[name] = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    saved[name] = self._MISSING
            self._saved = saved

            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
        self._notify()

    def restore(self):
        saved, self._saved = self._saved, None
        if saved is None:
            return False
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE,
            ) as key:
                for name, value in saved.items():
                    if value is self._MISSING:
                        try:
                            winreg.DeleteValue(key, name)
                        except FileNotFoundError:
                            pass
                    else:
                        winreg.SetValueEx(key, name, 0, value[1], value[0])
            self._notify()
        except OSError as e:
            print(f"Failed to restore proxy settings: {e}")
            return False
        return True


proxy = SystemProxy()


CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT = 2, 5, 6


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
def _console_handler(event):
    if event in (CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT):
        proxy.restore()
        return True
    return False


def copy_to_clipboard(text):
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)

    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, size)
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def minimize_game():
    SW_MINIMIZE = 6
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]

    names = {}

    def exe_name(pid):
        if pid not in names:
            name = ""
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                try:
                    buf = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(buf))
                    if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                        name = buf.value.rsplit("\\", 1)[-1].lower()
                finally:
                    kernel32.CloseHandle(handle)
            names[pid] = name
        return names[pid]

    @EnumWindowsProc
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if exe_name(pid.value) == GAME_EXE:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
        return True

    user32.EnumWindows(callback, 0)


class SummonGrabber:
    def __init__(self, master):
        self.master = master
        self.url = None

    def request(self, flow: http.HTTPFlow):
        if self.url is None and URL_MARKER in flow.request.pretty_url:
            self.url = flow.request.pretty_url
            asyncio.get_running_loop().call_later(GRACE_SECONDS, self.master.shutdown)


def port_in_use(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


async def capture():
    opts = Options(listen_host=PROXY_HOST, listen_port=PROXY_PORT)
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    grabber = SummonGrabber(master)
    master.addons.add(grabber)
    await master.run()
    return grabber.url


def wait_for_enter():
    try:
        input("\nPress Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass


def main():
    kernel32.SetConsoleCtrlHandler(_console_handler, True)

    if port_in_use(PROXY_HOST, PROXY_PORT):
        print(f"Port {PROXY_PORT} is already in use. Close the program using it and try again.")
        wait_for_enter()
        return 1

    url = None
    try:
        proxy.enable(f"{PROXY_HOST}:{PROXY_PORT}")
        print(f"Proxy enabled: {PROXY_HOST}:{PROXY_PORT}\n")
        print("Starting capture...")
        print("Launch the game and open summon history")
        print("(press Ctrl+C to cancel)\n")
        url = asyncio.run(capture())
    except KeyboardInterrupt:
        pass
    finally:
        if proxy.restore():
            print("Proxy disabled")

    if not url:
        return 1

    minimize_game()

    print("\n=== SUMMON LINK FOUND ===")
    print(url)
    if copy_to_clipboard(url):
        print("Link copied to clipboard")
    else:
        print("Could not copy the link, please copy it manually")

    wait_for_enter()
    return 0


if __name__ == "__main__":
    sys.exit(main())
