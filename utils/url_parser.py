"""
url_parser.py — Парсер прокси-ссылок в sing-box JSON формат.

Поддерживаемые протоколы:
  vmess://    — VMess (base64 JSON)
  vless://    — VLESS (с XTLS/Reality/WS/gRPC)
  ss://       — Shadowsocks (base64 или SIP002)
  trojan://   — Trojan
  hysteria2:// / hy2:// — Hysteria2
  tuic://     — TUIC v5
  socks5://   — SOCKS5
  http://     — HTTP прокси (в контексте прокси-ссылки)
"""

import base64
import json
import urllib.parse
import uuid
import re


# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def _b64decode(s: str) -> bytes:
    """Base64 decode с автодополнением паддинга."""
    s = s.strip().replace("-", "+").replace("_", "/")
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.b64decode(s)


def _b64decode_str(s: str) -> str:
    return _b64decode(s).decode("utf-8", errors="replace")


def _parse_qs(query: str) -> dict:
    return {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}


def _fragment(url: str) -> str:
    """Возвращает fragment (#...) как имя тега."""
    if "#" in url:
        return urllib.parse.unquote(url.split("#", 1)[1])
    return ""


def _singbox_tls(params: dict, host: str) -> dict | None:
    """Формирует блок TLS для sing-box из параметров URL."""
    security = params.get("security", "").lower()
    if security not in ("tls", "reality", "xtls"):
        return None

    tls = {"enabled": True}

    sni = params.get("sni") or params.get("host") or host
    if sni:
        tls["server_name"] = sni

    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")

    fp = params.get("fp")
    if fp:
        tls["utls"] = {"enabled": True, "fingerprint": fp}

    insecure = params.get("allowInsecure", params.get("insecure", "0"))
    if insecure in ("1", "true"):
        tls["insecure"] = True

    # Reality
    if security == "reality":
        pbk = params.get("pbk")
        sid = params.get("sid", "")
        if pbk:
            tls["reality"] = {
                "enabled": True,
                "public_key": pbk,
                "short_id": sid
            }

    return tls


def _singbox_transport(params: dict) -> dict | None:
    """Формирует блок transport для sing-box."""
    net = params.get("type", params.get("net", "tcp")).lower()
    if net in ("tcp", ""):
        header_type = params.get("headerType", params.get("type", ""))
        if header_type == "http":
            return {"type": "http"}
        return None

    if net == "ws":
        t = {"type": "websocket"}
        path = params.get("path", "/")
        if path:
            t["path"] = urllib.parse.unquote(path)
        host = params.get("host")
        if host:
            t["headers"] = {"Host": host}
        return t

    if net in ("grpc", "gun"):
        t = {"type": "grpc"}
        svc = params.get("serviceName", params.get("path", ""))
        if svc:
            t["service_name"] = svc
        return t

    if net == "h2":
        t = {"type": "http"}
        host = params.get("host")
        if host:
            t["host"] = host.split(",")
        path = params.get("path", "/")
        if path:
            t["path"] = path
        return t

    if net == "xhttp":
        t = {"type": "http"}
        path = params.get("path", "/")
        if path:
            t["path"] = urllib.parse.unquote(path)
        return t

    if net == "quic":
        return {"type": "quic"}

    return None


def _wrap_singbox(tag: str, outbound: dict) -> dict:
    """Оборачивает outbound в полный sing-box конфиг с TUN (1.11.3+)."""
    outbound["tag"] = tag or "proxy"
    return {
        "log": {"level": "info"},
        "inbounds": [
            # 🔹 Локальный прокси (для приложений)
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 2080
            },
            # 🔹 TUN-адаптер (системный VPN) — ГЛАВНОЕ!
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "Twi2wi-VPN",
                "stack": "gvisor",
                "auto_route": True,
                "strict_route": False,
                "sniff": True
            }
        ],
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"}
        ],
        "route": {
            "rules": [
                {
                    "inbound": ["mixed-in", "tun-in"],
                    "action": "sniff"
                }
            ],
            "final": tag or "proxy",
            "auto_detect_interface": True
        }
    }


# ─────────────────────────────────────────────
# Парсеры протоколов
# ─────────────────────────────────────────────

def parse_vmess(url: str) -> dict:
    """vmess://base64json"""
    b64 = url[len("vmess://"):].split("#")[0]
    try:
        raw = _b64decode_str(b64)
        v = json.loads(raw)
    except Exception as e:
        raise ValueError(f"VMess: не удалось декодировать: {e}")

    tag = urllib.parse.unquote(v.get("ps", "vmess"))
    host = v.get("add", "")
    port = int(v.get("port", 443))
    uid = v.get("id", "")
    alter_id = int(v.get("aid", 0))
    security = v.get("scy", v.get("security", "auto"))
    net = v.get("net", "tcp")
    tls_flag = v.get("tls", "")

    outbound = {
        "type": "vmess",
        "server": host,
        "server_port": port,
        "uuid": uid,
        "security": security,
        "alter_id": alter_id,
    }

    # Transport
    fake_params = {
        "type": net,
        "net": net,
        "path": v.get("path", "/"),
        "host": v.get("host", ""),
        "serviceName": v.get("path", ""),
    }
    transport = _singbox_transport(fake_params)
    if transport:
        outbound["transport"] = transport

    # TLS
    if tls_flag == "tls":
        tls = {"enabled": True}
        sni = v.get("sni") or v.get("host") or host
        if sni:
            tls["server_name"] = sni
        outbound["tls"] = tls

    return _wrap_singbox(tag, outbound)


def parse_vless(url: str) -> dict:
    """vless://uuid@host:port?params#tag"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    uid = parsed.username or parsed.netloc.split("@")[0]
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        port = int(port_s)
    else:
        host = hostport
        port = 443

    host = host.strip("[]")  # IPv6

    flow = params.get("flow", "")
    outbound = {
        "type": "vless",
        "server": host,
        "server_port": port,
        "uuid": uid,
    }
    if flow:
        outbound["flow"] = flow

    transport = _singbox_transport(params)
    if transport:
        outbound["transport"] = transport

    tls = _singbox_tls(params, host)
    if tls:
        outbound["tls"] = tls

    return _wrap_singbox(tag, outbound)


def parse_shadowsocks(url: str) -> dict:
    """ss://base64@host:port#tag  или  ss://base64(method:pass)@host:port"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]

    # SIP002: ss://BASE64(method:pass)@host:port
    # Legacy: ss://BASE64(method:pass@host:port)
    rest = url_clean[len("ss://"):]

    try:
        if "@" in rest:
            # SIP002 формат
            userinfo, hostport = rest.rsplit("@", 1)
            try:
                decoded = _b64decode_str(userinfo)
                method, password = decoded.split(":", 1)
            except Exception:
                method, password = urllib.parse.unquote(userinfo).split(":", 1)
        else:
            # Legacy: всё base64
            decoded = _b64decode_str(rest)
            # method:pass@host:port
            method_pass, hostport = decoded.rsplit("@", 1)
            method, password = method_pass.split(":", 1)

        # Убираем query string из hostport
        if "?" in hostport:
            hostport = hostport.split("?")[0]
        if ":" in hostport:
            host, port_s = hostport.rsplit(":", 1)
            port = int(port_s)
        else:
            host = hostport
            port = 8388

    except Exception as e:
        raise ValueError(f"Shadowsocks: не удалось разобрать: {e}")

    outbound = {
        "type": "shadowsocks",
        "server": host,
        "server_port": port,
        "method": method,
        "password": password,
    }
    return _wrap_singbox(tag or "ss", outbound)


def parse_trojan(url: str) -> dict:
    """trojan://password@host:port?params#tag"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    password = urllib.parse.unquote(parsed.username or "")
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        port = int(port_s)
    else:
        host = hostport
        port = 443

    outbound = {
        "type": "trojan",
        "server": host,
        "server_port": port,
        "password": password,
    }

    transport = _singbox_transport(params)
    if transport:
        outbound["transport"] = transport

    # Trojan всегда TLS
    tls = _singbox_tls(params, host)
    if not tls:
        tls = {"enabled": True, "server_name": params.get("sni") or host}
    outbound["tls"] = tls

    return _wrap_singbox(tag or "trojan", outbound)


def parse_hysteria2(url: str) -> dict:
    """hysteria2://password@host:port?params#tag"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    password = urllib.parse.unquote(parsed.username or "")
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        port = int(port_s)
    else:
        host = hostport
        port = 443

    tls = {
        "enabled": True,
        "server_name": params.get("sni") or host,
        "insecure": params.get("insecure", "0") in ("1", "true"),
    }
    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")

    outbound = {
        "type": "hysteria2",
        "server": host,
        "server_port": port,
        "password": password,
        "tls": tls,
    }
    obfs = params.get("obfs")
    if obfs:
        outbound["obfs"] = {"type": obfs, "password": params.get("obfs-password", "")}

    return _wrap_singbox(tag or "hy2", outbound)


def parse_tuic(url: str) -> dict:
    """tuic://uuid:password@host:port?params#tag"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    userinfo = parsed.netloc.split("@")[0]
    uid, password = userinfo.split(":", 1) if ":" in userinfo else (userinfo, "")
    uid = urllib.parse.unquote(uid)
    password = urllib.parse.unquote(password)

    hostport = parsed.netloc.split("@")[-1]
    host, port_s = hostport.rsplit(":", 1)
    port = int(port_s)

    tls = {
        "enabled": True,
        "server_name": params.get("sni") or host,
        "insecure": params.get("allowInsecure", "0") in ("1", "true"),
    }
    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")

    outbound = {
        "type": "tuic",
        "server": host,
        "server_port": port,
        "uuid": uid,
        "password": password,
        "congestion_control": params.get("congestion_control", "bbr"),
        "tls": tls,
    }
    return _wrap_singbox(tag or "tuic", outbound)


def parse_socks5(url: str) -> dict:
    """socks5://user:pass@host:port#tag"""
    tag = _fragment(url)
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)

    host = parsed.hostname or ""
    port = parsed.port or 1080
    user = urllib.parse.unquote(parsed.username or "")
    password = urllib.parse.unquote(parsed.password or "")

    outbound = {
        "type": "socks",
        "server": host,
        "server_port": port,
        "version": "5",
    }
    if user:
        outbound["username"] = user
        outbound["password"] = password

    return _wrap_singbox(tag or "socks5", outbound)


# ─────────────────────────────────────────────
# Главная точка входа
# ─────────────────────────────────────────────

PARSERS = {
    "vmess": parse_vmess,
    "vless": parse_vless,
    "ss": parse_shadowsocks,
    "shadowsocks": parse_shadowsocks,
    "trojan": parse_trojan,
    "hysteria2": parse_hysteria2,
    "hy2": parse_hysteria2,
    "tuic": parse_tuic,
    "socks5": parse_socks5,
    "socks": parse_socks5,
}

SUPPORTED_SCHEMES = list(PARSERS.keys())


def parse_proxy_url(url: str) -> tuple[dict, str]:
    """
    Парсит прокси-ссылку в sing-box JSON конфиг.

    Возвращает (config_dict, protocol_name).
    Бросает ValueError если протокол не поддерживается или ссылка битая.
    """
    url = url.strip()
    scheme = url.split("://")[0].lower()

    parser = PARSERS.get(scheme)
    if not parser:
        raise ValueError(
            f"Протокол «{scheme}» не поддерживается.\n"
            f"Поддерживаются: {', '.join(SUPPORTED_SCHEMES)}"
        )

    config = parser(url)
    return config, scheme


def url_to_singbox_json(url: str) -> str:
    """Возвращает готовый sing-box JSON как строку."""
    config, _ = parse_proxy_url(url)
    return json.dumps(config, ensure_ascii=False, indent=2)