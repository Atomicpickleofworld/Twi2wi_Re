import sys
import time
import subprocess
import logging
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from utils.config import SINGBOX_PATH, AMNEZIAWG_PATH


class SingBoxWorker(QThread):
    log_line = pyqtSignal(str)
    status_changed = pyqtSignal(bool)

    def __init__(self, config_path, config_type="singbox"):
        super().__init__()
        self.config_path = config_path
        self.config_type = config_type
        self.process = None
        self.running = True

    def is_awg_config(self, content):
        return "[Interface]" in content and ("Jc" in content or "Jmin" in content or "PrivateKey" in content)

    def run(self):
        try:
            content = Path(self.config_path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.log_line.emit(f"[!] Ошибка чтения конфига: {e}")
            self.status_changed.emit(False)
            return

        is_awg = self.is_awg_config(content)
        if self.config_type.lower() == "amneziawg" or is_awg:
            self.run_amneziawg(content)
        else:
            self.run_singbox()

    def run_amneziawg(self, content):
        if not AMNEZIAWG_PATH.exists():
            self.log_line.emit("[!] amneziawg.exe не найден")
            self.status_changed.emit(False)
            return

        tunnel = "twi2wi_tunnel"
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # 🔧 Фикс краша 0xC0000409

        try:
            conf_dir = Path(self.config_path).parent.parent / "tmp_awg"
            conf_dir.mkdir(exist_ok=True)
            conf_file = conf_dir / f"{tunnel}.conf"
            conf_file.write_text(content, encoding="utf-8")

            self.log_line.emit(f"[>] Установка туннеля...")
            subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", tunnel],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cf, timeout=5)
            time.sleep(1)

            res = subprocess.run([str(AMNEZIAWG_PATH), "/installtunnelservice", str(conf_file)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=cf,
                                 timeout=30)
            if res.stdout: self.log_line.emit(res.stdout.strip())
            if res.stderr: self.log_line.emit(f"[!] {res.stderr.strip()}")

            if res.returncode != 0:
                self.log_line.emit(f"[!] Ошибка установки: {res.returncode}")
                self.status_changed.emit(False)
                return

            self.log_line.emit("[+] Туннель установлен, запуск сервиса...")
            subprocess.run(["sc", "start", tunnel], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=cf, timeout=10)
            self.status_changed.emit(True)
        except Exception as e:
            self.log_line.emit(f"[!] Ошибка AWG: {e}")
            self.status_changed.emit(False)

    def run_singbox(self):
        if not SINGBOX_PATH.exists():
            self.log_line.emit("[!] sing-box.exe не найден")
            self.status_changed.emit(False)
            return
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self.log_line.emit(f"[>] Запуск sing-box...")
            self.process = subprocess.Popen(
                [str(SINGBOX_PATH), "run", "-c", self.config_path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=cf
            )
            self.status_changed.emit(True)
            logging.info(f"PID SingBox: {self.process.pid}")
            for line in iter(self.process.stdout.readline, ''):
                if not line: break
                ln = line.strip()
                if ln: self.log_line.emit(ln)
            ret = self.process.wait()
            self.log_line.emit(f"[i] sing-box завершился: {ret}")
            self.status_changed.emit(False)
        except Exception as e:
            self.log_line.emit(f"[!] Ошибка sing-box: {e}")
            self.status_changed.emit(False)

    def stop(self):
        self.running = False
        # Быстрая остановка sing-box
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)  # Ждём максимум 2 сек
            except:
                try: self.process.kill()
                except: pass
            self.process = None

        # Мгновенная остановка AWG (без сна и повторов)
        if AMNEZIAWG_PATH.exists() and sys.platform == "win32":
            cf = subprocess.CREATE_NO_WINDOW
            tunnel = "twi2wi_tunnel"
            try:
                subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", tunnel],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=cf, timeout=2)
                self.log_line.emit("[i] AWG туннель остановлен")
            except Exception as e:
                self.log_line.emit(f"[!] Ошибка остановки: {e}")