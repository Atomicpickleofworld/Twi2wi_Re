# plugins/system_monitor/main.py (упрощённая версия без psutil)
"""
System Monitor Plugin (упрощённый) — только RAM, без CPU
"""
import time
import threading

_running = True


def get_ram_usage():
    """Возвращает процент использованной RAM (Windows/Linux/macOS)"""
    import platform
    import subprocess
    import re

    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.check_output(
                "wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value",
                shell=True, text=True
            )
            total = re.search(r"TotalVisibleMemorySize=(\d+)", output)
            free = re.search(r"FreePhysicalMemory=(\d+)", output)
            if total and free:
                total_mb = int(total.group(1)) / 1024
                free_mb = int(free.group(1)) / 1024
                used_mb = total_mb - free_mb
                return round((used_mb / total_mb) * 100, 1)
        elif system in ("Linux", "Darwin"):  # Darwin = macOS
            output = subprocess.check_output(["free" if system == "Linux" else "vm_stat"], text=True)
            # Упрощённо: возвращаем заглушку
            return "?"
    except:
        pass
    return "?"


def monitor_loop(ctx):
    global _running
    while _running:
        ram = get_ram_usage()
        if ram != "?" and ram > 85:
            ctx.notify(f"⚠️ Высокое использование RAM: {ram}%")
        time.sleep(5)


def on_connect(ctx, payload):
    if not hasattr(on_connect, "_thread"):
        on_connect._thread = threading.Thread(target=monitor_loop, args=(ctx,), daemon=True)
        on_connect._thread.start()
    ctx.log("System Monitor запущен")


def on_disconnect(ctx, payload):
    global _running
    _running = False
    ctx.log("System Monitor остановлен")