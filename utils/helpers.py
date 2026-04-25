import sys
import platform
import socket
import uuid
import subprocess
from .config import SINGBOX_PATH, AMNEZIAWG_PATH

def detect_type(content):
    c = content.lower()
    for p in ["vless", "vmess", "trojan", "shadowsocks", "amneziawg", "wireguard", "hysteria", "tuic", "socks"]:
        if p in c: return p
    return "singbox"

def get_system_info():
    info = []
    info.append("🖥️ ВЕРСИИ И ПЛАТФОРМА")
    info.append(f"Python: {platform.python_version()}")
    info.append(f"OS: {platform.system()} {platform.release()}")
    info.append(f"Arch: {platform.machine()}")
    try: info.append(f"PyQt6: {__import__('PyQt6.QtCore').QtCore.PYQT_VERSION_STR}")
    except: info.append("PyQt6: N/A")
    info.append("")
    info.append("📦 ПРОТОКОЛЫ / УТИЛИТЫ")
    info.append(f"sing-box: {'✓ найден' if SINGBOX_PATH.exists() else '✗ отсутствует'}")
    info.append(f"AmneziaWG: {'✓ найден' if AMNEZIAWG_PATH.exists() else '✗ отсутствует'}")
    try:
        v = subprocess.check_output([str(SINGBOX_PATH), "version"], text=True).splitlines()[0]
        info.append(f"  → {v}")
    except: pass
    try:
        v = subprocess.check_output([str(AMNEZIAWG_PATH), "--version"], text=True).splitlines()[0]
        info.append(f"  → {v}")
    except: pass
    info.append("")
    info.append("🌐 СЕТЕВОЙ АДАПТЕР")
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> el) & 0xff) for el in range(0, 2 * 6, 2)][::-1])
        info.append(f"Host: {hostname} | IPv4: {ip} | MAC: {mac}")
    except Exception as e: info.append(f"Ошибка: {e}")
    info.append("")
    info.append("⚙️ АППАРАТНОЕ ОБЕСПЕЧЕНИЕ")
    info.append(f"CPU: {platform.processor() or 'N/A'}")
    try:
        if sys.platform == "win32":
            ram = subprocess.check_output("wmic computersystem get totalphysicalmemory", shell=True, text=True).split()[1]
            info.append(f"RAM: {int(ram) / (1024 ** 3):.1f} GB")
    except: info.append("RAM: N/A")
    return "\n".join(info)