# utils/helpers.py
import sys
import os
import platform
import socket
import uuid
import subprocess
from .config import SINGBOX_PATH, AMNEZIAWG_PATH
from .i18n import tr  # ← ИМПОРТ ПЕРЕВОДЧИКА


def detect_type(content):
    c = content.lower()
    for p in ["vless", "vmess", "trojan", "shadowsocks", "amneziawg", "wireguard", "hysteria", "tuic", "socks"]:
        if p in c: return p
    return "singbox"


def get_system_info():
    info = []
    cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    # Заголовки секций
    info.append(tr("sys_section_platform"))
    info.append(tr("sys_python_label") + f" {platform.python_version()}")
    info.append(tr("sys_os_label") + f" {platform.system()} {platform.release()}")
    info.append(tr("sys_arch_label") + f" {platform.machine()}")
    try:
        info.append(tr("sys_pyqt_label") + f" {__import__('PyQt6.QtCore').QtCore.PYQT_VERSION_STR}")
    except:
        info.append(tr("sys_pyqt_label") + " N/A")

    info.append("")  # пустая строка-разделитель
    info.append(tr("sys_section_utilities"))

    # Статус бинарников
    sing_found = tr("sys_found") if SINGBOX_PATH.exists() else tr("sys_missing")
    awg_found = tr("sys_found") if AMNEZIAWG_PATH.exists() else tr("sys_missing")
    info.append(f"sing-box: {sing_found}")
    info.append(f"AmneziaWG: {awg_found}")

    # Версия sing-box
    try:
        v = subprocess.check_output(
            [str(SINGBOX_PATH), "version"],
            text=True, creationflags=cf, timeout=3
        ).splitlines()[0]
        info.append(f"  → {v}")
    except:
        pass

    # Размер amneziawg.exe
    try:
        if AMNEZIAWG_PATH.exists():
            size_kb = os.path.getsize(str(AMNEZIAWG_PATH)) // 1024
            info.append(f"  → amneziawg.exe ({size_kb} KB)")
    except:
        pass

    info.append("")
    info.append(tr("sys_section_network"))

    # Сетевая информация
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> el) & 0xff) for el in range(0, 2 * 6, 2)][::-1])
        info.append(tr("sys_network_info", host=hostname, ip=ip, mac=mac))
    except Exception as e:
        info.append(tr("sys_error_label") + f" {e}")

    info.append("")
    info.append(tr("sys_section_hardware"))

    # Аппаратное обеспечение
    info.append(tr("sys_cpu_label") + f" {platform.processor() or 'N/A'}")
    try:
        if sys.platform == "win32":
            ram = subprocess.check_output(
                "wmic computersystem get totalphysicalmemory",
                shell=True, text=True, creationflags=cf
            ).split()[1]
            info.append(tr("sys_ram_label") + f" {int(ram) / (1024 ** 3):.1f} GB")
    except:
        info.append(tr("sys_ram_label") + " N/A")

    return "\n".join(info)

def extract_config_info(config: dict) -> dict:
    """
    Извлекает из конфига (JSON sing-box или raw-конфиг AmneziaWG/WireGuard)
    сервер, порт, метод шифрования.
    Возвращает словарь: {host, port, method}
    """
    content = config.get("content", "")
    result = {"host": None, "port": None, "method": None}

    # 1. Пробуем распарсить как AmneziaWG / WireGuard (raw конфиг)
    if "[Interface]" in content:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("Endpoint"):
                # Endpoint = domain:port или ip:port
                endpoint = line.split("=", 1)[1].strip()
                if ":" in endpoint:
                    host, port_str = endpoint.rsplit(":", 1)
                    result["host"] = host
                    try:
                        result["port"] = int(port_str)
                    except:
                        pass
                else:
                    result["host"] = endpoint
            elif line.startswith("Jc") or line.startswith("Jmin") or line.startswith("Jmax"):
                result["method"] = "AmneziaWG"
            elif line.startswith("PrivateKey"):
                if not result["method"]:
                    result["method"] = "WireGuard"
        if result["host"]:
            return result

    # 2. Если не AmneziaWG, пробуем как JSON sing-box
    try:
        import json
        if isinstance(content, str):
            raw = content.strip()
            if raw.startswith(("{", "[")):
                cfg = json.loads(raw)
            else:
                # Возможно, это ссылка, но мы уже должны были распарсить её при добавлении
                return result
        else:
            cfg = content

        outbounds = cfg.get("outbounds", [])
        proxy = None
        for ob in outbounds:
            ob_type = ob.get("type", "")
            if ob_type in ("vmess", "vless", "trojan", "shadowsocks", "socks", "http", "hysteria2", "tuic",
                           "wireguard", "amneziawg"):
                proxy = ob
                result["method"] = ob_type.upper()
                break
        if not proxy:
            return result

        result["host"] = proxy.get("server")
        result["port"] = proxy.get("server_port")

        # Уточняем метод шифрования для некоторых типов
        if proxy.get("type") == "shadowsocks":
            result["method"] = proxy.get("method", "chacha20-ietf-poly1305").upper()
        elif proxy.get("type") == "vmess":
            result["method"] = f"VMess {proxy.get('security', 'auto')}"
        elif proxy.get("type") == "vless":
            result["method"] = "VLESS" + (f" + {proxy.get('flow','')}" if proxy.get('flow') else "")
        elif proxy.get("type") == "amneziawg":
            result["method"] = "AmneziaWG"
    except Exception:
        pass

    return result