# core/validator.py
import re
import ipaddress
import json
from pathlib import Path
from typing import Any, Dict
from utils.i18n import tr


# ── Ошибки ──────────────────────────────────────────────────────────────────
class ValidationError(Exception): pass


class UnsafeSchemeError(ValidationError): pass


class MalformedDataError(ValidationError): pass


class InvalidConfigStructureError(ValidationError): pass


class UnsafePathError(ValidationError): pass


# ── Константы ───────────────────────────────────────────────────────────────
MAX_URL_LENGTH = 2048
MAX_BASE64_LENGTH = 8192
ALLOWED_SCHEMES = {
    "vmess", "vless", "ss", "shadowsocks", "trojan",
    "hysteria2", "hy2", "tuic", "socks5", "socks", "http", "https"
}
SAFE_HOST_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


# ── Валидация URL ───────────────────────────────────────────────────────────
def validate_url(url: str) -> str:
    url = url.strip()
    if not url:
        raise MalformedDataError(tr._("sec_val_empty_url"))
    if len(url) > MAX_URL_LENGTH:
        raise MalformedDataError(tr._("sec_val_url_too_long", max=MAX_URL_LENGTH))
    if any(c in url for c in ("\x00", "\n", "\r", "\t")):
        raise MalformedDataError(tr._("sec_val_invalid_chars"))

    scheme = url.split("://", 1)[0].lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeSchemeError(tr._("sec_val_unsupported_scheme", scheme=scheme))
    return url


# ── Санитизация имени файла ─────────────────────────────────────────────────
def sanitize_filename(raw_name: str, ext: str = ".json") -> str:
    safe = re.sub(r'[\\/:*?"<>|]', '_', raw_name)
    safe = re.sub(r'\.{2,}', '_', safe)
    safe = safe.strip().strip('_ .')
    if not safe:
        safe = "proxy_config"
    return f"{safe[:60]}{ext}""


# ── Валидация sing-box конфига ──────────────────────────────────────────────
def validate_singbox_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict):
        raise InvalidConfigStructureError(tr._("sec_cfg_not_json"))

    if "outbounds" not in config or not isinstance(config.get("outbounds"), list):
        raise InvalidConfigStructureError(tr._("sec_cfg_missing_outbounds"))
    if not config["outbounds"]:
        raise InvalidConfigStructureError(tr._("sec_cfg_empty_outbounds"))

    allowed_types = {
        "direct", "block", "dns", "socks", "http", "shadowsocks", "vmess",
        "vless", "trojan", "wireguard", "hysteria", "hysteria2", "tuic", "ssh", "tor", "mixed"
    }

    for i, ob in enumerate(config["outbounds"]):
        if not isinstance(ob, dict):
            raise InvalidConfigStructureError(tr._("sec_cfg_invalid_outbound", index=i))

        ob_type = ob.get("type", "direct")
        if ob_type not in allowed_types:
            raise InvalidConfigStructureError(tr._("sec_cfg_unsupported_type", type=ob_type))

        if "server" in ob and not is_host_safe(str(ob["server"])):
            raise InvalidConfigStructureError(tr._("sec_cfg_invalid_host", host=ob["server"]))
        if "server_port" in ob:
            port = ob["server_port"]
            if not (isinstance(port, int) and 1 <= port <= 65535):
                raise InvalidConfigStructureError(tr._("sec_cfg_invalid_port", port=port))

    if "dns" in config and "fakeip" in config["dns"]:
        raise InvalidConfigStructureError(tr._("sec_cfg_fakeip_forbidden"))

    return config


def is_host_safe(host: str) -> bool:
    if not host: return False
    if SAFE_HOST_RE.match(host): return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


# ── Защита путей ────────────────────────────────────────────────────────────
def ensure_path_safe(target: Path, root: Path) -> Path:
    target = target.resolve()
    root = root.resolve()
    if not str(target).startswith(str(root) + str(target._flavour.sep)):
        raise UnsafePathError(tr._("sec_path_outside_root", root=root))
    if target.is_symlink():
        raise UnsafePathError(tr._("sec_path_symlink_forbidden"))
    return target