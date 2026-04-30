"""
# utils/url_parser.py — Парсер прокси-ссылок в sing-box JSON формат.

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

# ── Константы безопасности ─────────────────────────────────────────────────
MAX_BASE64_LEN = 8192
MAX_JSON_PAYLOAD = 1_048_576  # 1 MB
MAX_URL_LENGTH = 2048
MAX_QUERY_LENGTH = 1024

# ── Вспомогательные функции ─────────────────────────────────────────────────

def _b64decode(s: str) -> bytes:
    """Base64 decode с автодополнением паддинга и защитой от переполнения."""
    s = s.strip().replace("-", "+").replace("_", "/")
    if len(s) > MAX_BASE64_LEN:
        raise ValueError(f"Base64 payload слишком большой (> {MAX_BASE64_LEN} символов)")
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.b64decode(s)


def _b64decode_str(s: str) -> str:
    return _b64decode(s).decode("utf-8", errors="replace")


def _parse_qs(query: str) -> dict:
    """Парсинг query string с защитой от переполнения."""
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError("Query string слишком длинный")
    return {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}


def _fragment(url: str) -> str:
    """Возвращает fragment (#...) как имя тега."""
    if "#" in url:
        return urllib.parse.unquote(url.split("#", 1)[1])
    return ""


def _validate_host(host: str) -> bool:
    """Базовая проверка хоста (IP или домен)."""
    if not host:
        return False
    # Простая проверка: нет пробелов, нулевых байтов, переносов строк
    if any(c in host for c in ("\x00", "\n", "\r", "\t", " ")):
        return False
    # Проверка на IP
    try:
        import ipaddress
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        pass
    # Проверка на домен
    host_re = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
    return bool(host_re.match(host))


def _validate_port(port) -> bool:
    """Проверка порта."""
    return isinstance(port, int) and 1 <= port <= 65535


def _singbox_tls(params: dict, host: str) -> dict | None:
    """Формирует блок TLS для sing-box из параметров URL."""
    security = params.get("security", "").lower()
    if security not in ("tls", "reality", "xtls"):
        return None

    tls = {"enabled": True}

    sni = params.get("sni") or params.get("host") or host
    if sni:
        tls["server_name"] = sni[:256]  # ограничение длины SNI

    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")[:5]  # максимум 5 ALPN

    fp = params.get("fp")
    if fp:
        tls["utls"] = {"enabled": True, "fingerprint": fp[:64]}

    insecure = params.get("allowInsecure", params.get("insecure", "0"))
    if insecure in ("1", "true"):
        tls["insecure"] = True

    # Reality
    if security == "reality":
        pbk = params.get("pbk")
        sid = params.get("sid", "")
        if pbk and len(pbk) <= 128:
            tls["reality"] = {
                "enabled": True,
                "public_key": pbk,
                "short_id": sid[:32]
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
            t["path"] = urllib.parse.unquote(path)[:1024]
        host = params.get("host")
        if host:
            t["headers"] = {"Host": host[:256]}
        return t

    if net in ("grpc", "gun"):
        t = {"type": "grpc"}
        svc = params.get("serviceName", params.get("path", ""))
        if svc:
            t["service_name"] = svc[:256]
        return t

    if net == "h2":
        t = {"type": "http"}
        host = params.get("host")
        if host:
            t["host"] = [h.strip()[:256] for h in host.split(",")[:5]]
        path = params.get("path", "/")
        if path:
            t["path"] = path[:1024]
        return t

    if net == "xhttp":
        t = {"type": "http"}
        path = params.get("path", "/")
        if path:
            t["path"] = urllib.parse.unquote(path)[:1024]
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
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 2080
            },
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


# ── Парсеры протоколов ─────────────────────────────────────────────────────

def parse_vmess(url: str) -> dict:
    """vmess://base64json"""
    b64 = url[len("vmess://"):].split("#")[0]
    try:
        raw = _b64decode_str(b64)
        v = json.loads(raw)
    except Exception as e:
        raise ValueError(f"VMess: не удалось декодировать: {e}")

    tag = urllib.parse.unquote(str(v.get("ps", "vmess")))[:128]
    host = str(v.get("add", ""))[:256]
    if not _validate_host(host):
        raise ValueError(f"VMess: невалидный хост: {host}")

    port = int(v.get("port", 443))
    if not _validate_port(port):
        raise ValueError(f"VMess: невалидный порт: {port}")

    uid = str(v.get("id", ""))[:64]
    alter_id = min(int(v.get("aid", 0)), 65535)
    security = str(v.get("scy", v.get("security", "auto")))[:32]
    net = str(v.get("net", "tcp"))[:32]
    tls_flag = str(v.get("tls", ""))[:32]

    outbound = {
        "type": "vmess",
        "server": host,
        "server_port": port,
        "uuid": uid,
        "security": security,
        "alter_id": alter_id,
    }

    fake_params = {
        "type": net,
        "net": net,
        "path": str(v.get("path", "/"))[:1024],
        "host": str(v.get("host", ""))[:256],
        "serviceName": str(v.get("path", ""))[:256],
    }
    transport = _singbox_transport(fake_params)
    if transport:
        outbound["transport"] = transport

    if tls_flag == "tls":
        tls = {"enabled": True}
        sni = str(v.get("sni") or v.get("host") or host)[:256]
        if sni:
            tls["server_name"] = sni
        outbound["tls"] = tls

    return _wrap_singbox(tag, outbound)


def parse_vless(url: str) -> dict:
    """vless://uuid@host:port?params#tag"""
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    uid = str(parsed.username or parsed.netloc.split("@")[0])[:64]
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        host = host.strip("[]")[:256]
        port = int(port_s)
    else:
        host = hostport.strip("[]")[:256]
        port = 443

    if not _validate_host(host):
        raise ValueError(f"VLESS: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"VLESS: невалидный порт: {port}")

    flow = str(params.get("flow", ""))[:32]
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
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    rest = url_clean[len("ss://"):]

    try:
        if "@" in rest:
            userinfo, hostport = rest.rsplit("@", 1)
            try:
                decoded = _b64decode_str(userinfo)
                method, password = decoded.split(":", 1)
            except Exception:
                method, password = urllib.parse.unquote(userinfo).split(":", 1)
        else:
            decoded = _b64decode_str(rest)
            method_pass, hostport = decoded.rsplit("@", 1)
            method, password = method_pass.split(":", 1)

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

    method = str(method)[:32]
    password = str(password)[:256]
    host = str(host)[:256]

    if not _validate_host(host):
        raise ValueError(f"Shadowsocks: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"Shadowsocks: невалидный порт: {port}")

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
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    password = urllib.parse.unquote(str(parsed.username or ""))[:256]
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        host = host.strip("[]")[:256]
        port = int(port_s)
    else:
        host = hostport.strip("[]")[:256]
        port = 443

    if not _validate_host(host):
        raise ValueError(f"Trojan: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"Trojan: невалидный порт: {port}")

    outbound = {
        "type": "trojan",
        "server": host,
        "server_port": port,
        "password": password,
    }

    transport = _singbox_transport(params)
    if transport:
        outbound["transport"] = transport

    tls = _singbox_tls(params, host)
    if not tls:
        tls = {"enabled": True, "server_name": str(params.get("sni") or host)[:256]}
    outbound["tls"] = tls

    return _wrap_singbox(tag or "trojan", outbound)


def parse_hysteria2(url: str) -> dict:
    """hysteria2://password@host:port?params#tag"""
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    password = urllib.parse.unquote(str(parsed.username or ""))[:256]
    hostport = parsed.netloc.split("@")[-1]
    if ":" in hostport:
        host, port_s = hostport.rsplit(":", 1)
        host = host.strip("[]")[:256]
        port = int(port_s)
    else:
        host = hostport.strip("[]")[:256]
        port = 443

    if not _validate_host(host):
        raise ValueError(f"Hysteria2: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"Hysteria2: невалидный порт: {port}")

    tls = {
        "enabled": True,
        "server_name": str(params.get("sni") or host)[:256],
        "insecure": params.get("insecure", "0") in ("1", "true"),
    }
    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")[:5]

    outbound = {
        "type": "hysteria2",
        "server": host,
        "server_port": port,
        "password": password,
        "tls": tls,
    }
    obfs = params.get("obfs")
    if obfs:
        outbound["obfs"] = {
            "type": str(obfs)[:32],
            "password": str(params.get("obfs-password", ""))[:256]
        }

    return _wrap_singbox(tag or "hy2", outbound)


def parse_tuic(url: str) -> dict:
    """tuic://uuid:password@host:port?params#tag"""
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)
    params = _parse_qs(parsed.query)

    userinfo = parsed.netloc.split("@")[0]
    uid, password = userinfo.split(":", 1) if ":" in userinfo else (userinfo, "")
    uid = urllib.parse.unquote(str(uid))[:64]
    password = urllib.parse.unquote(str(password))[:256]

    hostport = parsed.netloc.split("@")[-1]
    host, port_s = hostport.rsplit(":", 1)
    host = host.strip("[]")[:256]
    port = int(port_s)

    if not _validate_host(host):
        raise ValueError(f"TUIC: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"TUIC: невалидный порт: {port}")

    tls = {
        "enabled": True,
        "server_name": str(params.get("sni") or host)[:256],
        "insecure": params.get("allowInsecure", "0") in ("1", "true"),
    }
    alpn = params.get("alpn")
    if alpn:
        tls["alpn"] = alpn.split(",")[:5]

    outbound = {
        "type": "tuic",
        "server": host,
        "server_port": port,
        "uuid": uid,
        "password": password,
        "congestion_control": str(params.get("congestion_control", "bbr"))[:32],
        "tls": tls,
    }
    return _wrap_singbox(tag or "tuic", outbound)


def parse_socks5(url: str) -> dict:
    """socks5://user:pass@host:port#tag"""
    tag = _fragment(url)[:128]
    url_clean = url.split("#")[0]
    parsed = urllib.parse.urlparse(url_clean)

    host = str(parsed.hostname or "")[:256]
    port = parsed.port or 1080
    user = urllib.parse.unquote(str(parsed.username or ""))[:256]
    password = urllib.parse.unquote(str(parsed.password or ""))[:256]

    if not _validate_host(host):
        raise ValueError(f"SOCKS5: невалидный хост: {host}")
    if not _validate_port(port):
        raise ValueError(f"SOCKS5: невалидный порт: {port}")

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


# ── Главная точка входа ─────────────────────────────────────────────────────

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
    """Парсит прокси-ссылку в sing-box JSON конфиг. Безопасная версия."""
    url = url.strip()

    # 1. Проверка на пустоту
    if not url:
        raise ValueError("Ссылка пуста. Вставь ссылку на конфиг (vmess://, vless://, ss:// и т.д.)")

    # 2. Проверка на длину
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"Ссылка слишком длинная (> {MAX_URL_LENGTH} символов). Возможно, это не ссылка на конфиг.")

    # 3. Защита от мусора — проверяем, что это вообще похоже на URL
    if "://" not in url:
        raise ValueError(
            "Это не похоже на ссылку. Нет '://'.\n"
            "Поддерживаемые форматы:\n"
            f"{', '.join(sorted(SUPPORTED_SCHEMES))}"
        )

    # 4. Извлекаем схему
    scheme = url.split("://", 1)[0].lower()

    # 5. Защита от невалидных символов в схеме
    if not re.match(r'^[a-z][a-z0-9]*$', scheme):
        raise ValueError(
            f"«{scheme}» — невалидный протокол.\n"
            f"Поддерживаются: {', '.join(sorted(SUPPORTED_SCHEMES))}"
        )

    # 6. Проверяем схему
    parser = PARSERS.get(scheme)
    if not parser:
        raise ValueError(
            f"Протокол «{scheme}» не поддерживается.\n"
            f"Поддерживаются: {', '.join(sorted(SUPPORTED_SCHEMES))}"
        )

    # 7. Безопасный парсинг с перехватом всех ошибок
    try:
        config = parser(url)
    except ValueError:
        raise  # Пробрасываем наши же ошибки
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка в данных ссылки (невалидный JSON): {e}")
    except Exception as e:
        raise ValueError(
            f"Не удалось обработать ссылку.\n"
            f"Проверь формат: {scheme}://...\n"
            f"Ошибка: {e}"
        )

    # 8. Проверка размера результата
    try:
        config_json = json.dumps(config)
    except Exception as e:
        raise ValueError(f"Ошибка при проверке конфига: {e}")

    if len(config_json) > MAX_JSON_PAYLOAD:
        raise ValueError("Сгенерированный конфиг слишком большой (> 1 MB)")

    return config, scheme


def url_to_singbox_json(url: str) -> str:
    """Возвращает готовый sing-box JSON как строку."""
    config, _ = parse_proxy_url(url)
    return json.dumps(config, ensure_ascii=False, indent=2)