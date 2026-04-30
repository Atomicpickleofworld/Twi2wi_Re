import time
import subprocess
import sys
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal

HISTORY_SIZE = 10          # сколько последних результатов храним
CYCLE_INTERVAL = 1.0       # секунда между полными циклами пинга
PING_TIMEOUT = 5           # таймаут subprocess
MAX_WORKERS = 10           # максимум одновременных пингов

class PingWorker(QThread):
    """
    Фоновый воркер для параллельного ICMP-пинга с историей.
    Сигнал result содержит: name, ms, loss, stats
    stats = {"min": int, "avg": float, "max": int} (по последним HISTORY_SIZE измерениям)
    """
    result = pyqtSignal(str, int, float, dict)   # name, ms, loss%, stats

    def __init__(self, hosts=None):
        super().__init__()
        self.hosts: list[list] = list(hosts) if hosts else []   # [[name, host], ...]
        self.running = True
        self.history: dict[str, list[int]] = {}
        self.lock = threading.Lock()
        # Инициализация истории для переданных хостов
        for name, _ in self.hosts:
            self.history[name] = []
        self._executor = None

    def run(self):
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        while self.running:
            if not self.hosts:
                time.sleep(1)
                continue

            # Копия списка хостов, чтобы избежать изменения во время итерации
            current_hosts = list(self.hosts)
            futures = {}
            for name, host in current_hosts:
                future = self._executor.submit(self._ping_host, host)
                futures[future] = (name, host)

            # Собираем результаты по мере готовности, с таймаутом
            for future in as_completed(futures, timeout=PING_TIMEOUT):
                name, host = futures[future]
                try:
                    ms = future.result()
                except Exception:
                    ms = -1

                with self.lock:
                    hist = self.history.setdefault(name, [])
                    hist.append(ms)
                    if len(hist) > HISTORY_SIZE:
                        hist.pop(0)
                    # Считаем потери
                    fails = sum(1 for x in hist if x == -1)
                    loss = (fails / len(hist)) * 100.0
                    # Статистика по успешным
                    valid = [x for x in hist if x >= 0]
                    if valid:
                        stats = {
                            "min": min(valid),
                            "avg": round(sum(valid) / len(valid), 1),
                            "max": max(valid),
                        }
                    else:
                        stats = {"min": -1, "avg": -1.0, "max": -1}

                # Эмитим результат только если изменились данные или новая попытка (чтобы не спамить UI)
                # Простейшая оптимизация: шлём всегда, UI сам решит обновляться, это легче.
                self.result.emit(name, ms, loss, stats)

            # Если нужно, эмитим отдельно хосты, которые не ответили за таймаут
            # (они уже учтены через ms=-1)

            # Небольшая пауза между циклами
            time.sleep(CYCLE_INTERVAL)

    def stop(self):
        self.running = False
        if self._executor:
            self._executor.shutdown(wait=False)
        self.wait(2000)

    def add_host(self, name, host):
        with self.lock:
            if name not in self.history:
                self.history[name] = []
            self.hosts.append([name, host])

    def remove_host(self, name):
        with self.lock:
            self.hosts = [h for h in self.hosts if h[0] != name]
            if name in self.history:
                del self.history[name]

    @staticmethod
    def _ping_host(host):
        """Пингует хост, возвращает ms или -1 при ошибке."""
        try:
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "3000", host],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    creationflags=creationflags,
                )
                output = result.stdout.decode("cp866", errors="ignore")
                # Русская локаль
                match = re.search(r"время[= <](\d+)мс", output)
                if match:
                    return int(match.group(1))
                # Английская локаль
                match = re.search(r"time[= <](\d+)ms", output)
                if match:
                    return int(match.group(1))
                return -1
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", host],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                )
                output = result.stdout.decode("utf-8", errors="ignore")
                match = re.search(r"time[= <](\d+(?:\.\d+)?)\s*ms", output)
                if match:
                    return int(float(match.group(1)))
                return -1
        except Exception:
            return -1