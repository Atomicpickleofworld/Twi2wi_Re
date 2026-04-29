import time
import socket
import threading
import subprocess
import sys
import re
from PyQt6.QtCore import QThread, pyqtSignal

class PingWorker(QThread):
    result = pyqtSignal(str, int, float)

    def __init__(self, hosts=None):
        super().__init__()
        self.hosts = list(hosts) if hosts else []
        self.running = True
        self.history = {name: [] for name, _ in self.hosts}
        self.lock = threading.Lock()

    def ping_host(self, host):
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "3000", host],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                output = result.stdout.decode("cp866", errors="ignore")

                match = re.search(r"время[= <](\d+)мс", output)
                if match:
                    return int(match.group(1))

                match = re.search(r"time[= <](\d+)ms", output)
                if match:
                    return int(match.group(1))

                return -1
            else:
                # Linux/macOS
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", host],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                output = result.stdout.decode("utf-8", errors="ignore")
                match = re.search(r"time[= <](\d+(?:\.\d+)?)\s*ms", output)
                if match:
                    return int(float(match.group(1)))
                return -1

        except Exception as e:
            print(f"Ping error for {host}: {e}")
            return -1

    def run(self):
        while self.running:
            if not self.hosts:
                time.sleep(1)
                continue
            for name, host in list(self.hosts):
                if not self.running:
                    break
                ms = self.ping_host(host)
                with self.lock:
                    hist = self.history.setdefault(name, [])
                    hist.append(ms)
                    if len(hist) > 10:
                        hist.pop(0)
                    fails = sum(1 for x in hist if x == -1)
                    loss = (fails / len(hist)) * 100.0 if hist else 0.0
                self.result.emit(name, ms, loss)
                time.sleep(0.5)
            time.sleep(0.5)

    def stop(self):
        self.running = False
        self.wait(2000)

    def add_host(self, name, host):
        with self.lock:
            if name not in self.history:
                self.history[name] = []
            self.hosts.append([name, host])