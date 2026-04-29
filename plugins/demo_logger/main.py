# plugins/demo_logger/main.py
#
# Плагин видит ТОЛЬКО:
#   ctx     — объект PluginContext (log, notify)
#   payload — dict с данными события
#
# Плагин НЕ видит: VPNManager, конфиги, файловую систему вне своей папки,
#                  сеть (если нет права network:http), subprocess и т.д.

def on_connect(ctx, payload):
    """Вызывается когда VPN подключился."""
    config_name = payload.get("config", {}).get("name", "неизвестно")
    ctx.log(f"VPN подключился. Конфиг: {config_name}")
    ctx.notify(f"✅ VPN активен — {config_name}")


def on_disconnect(ctx, payload):
    """Вызывается когда VPN отключился."""
    ctx.log("VPN отключился.")
    ctx.notify("🔴 VPN отключён")


def on_log(ctx, payload):
    """Вызывается при каждой строке лога VPN."""
    line = payload.get("line", "")
    # Например: ищем handshake в логах
    if "handshake" in line.lower():
        ctx.log(f"Handshake обнаружен: {line[:80]}")


def on_ping_result(ctx, payload):
    """Вызывается при получении результата пинга."""
    name = payload.get("name", "?")
    ms   = payload.get("ms", -1)
    if ms > 300:
        ctx.log(f"Высокий пинг на {name}: {ms}ms")
