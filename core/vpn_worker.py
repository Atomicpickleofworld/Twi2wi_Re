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
        self._used_awg = False  # 🔧 Флаг: использовался ли AWG в этой сессии

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
        if self.config_type.lower() in ("amneziawg", "wireguard") or is_awg:
            self._used_awg = True
            self.run_amneziawg(content)
        else:
            self._used_awg = False
            self.run_singbox()

    def run_amneziawg(self, content):
        if not AMNEZIAWG_PATH.exists():
            self.log_line.emit("[!] amneziawg.exe не найден")
            self.status_changed.emit(False)
            return

        tunnel = "twi2wi_tunnel"
        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            conf_dir = Path(self.config_path).parent.parent / "tmp_awg"
            conf_dir.mkdir(exist_ok=True)
            conf_file = conf_dir / f"{tunnel}.conf"
            conf_file.write_text(content, encoding="utf-8")

            self.log_line.emit("[>] Установка туннеля...")
            subprocess.run(
                [str(AMNEZIAWG_PATH), "/uninstalltunnelservice", tunnel],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=cf, timeout=5
            )
            time.sleep(1)

            res = subprocess.run(
                [str(AMNEZIAWG_PATH), "/installtunnelservice", str(conf_file)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=cf, timeout=30
            )
            if res.stdout: self.log_line.emit(res.stdout.strip())
            if res.stderr: self.log_line.emit(f"[!] {res.stderr.strip()}")

            if res.returncode != 0:
                self.log_line.emit(f"[!] Ошибка установки AWG: код {res.returncode}")
                self.status_changed.emit(False)
                return

            self.log_line.emit("[+] Туннель установлен, запуск сервиса...")
            subprocess.run(
                ["sc", "start", tunnel],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=cf, timeout=10
            )
            self.status_changed.emit(True)

        except Exception as e:
            self.log_line.emit(f"[!] Ошибка AWG: {e}")
            self.status_changed.emit(False)

    def run_singbox(self):
        if not SINGBOX_PATH.exists():
            self.log_line.emit("[!] sing-box.exe не найден")
            self.status_changed.emit(False)
            return

        if not Path(self.config_path).exists():
            self.log_line.emit(f"[!] Конфиг не найден: {self.config_path}")
            self.status_changed.emit(False)
            return

        # 🔧 Валидация JSON
        try:
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.log_line.emit(f"[i] Версия конфига: {config.get('log', {}).get('level', 'N/A')}")
                self.log_line.emit(f"[i] Inbounds: {len(config.get('inbounds', []))}")
                self.log_line.emit(f"[i] Outbounds: {len(config.get('outbounds', []))}")
        except Exception as e:
            self.log_line.emit(f"[!] Конфиг не является валидным JSON: {e}")
            self.status_changed.emit(False)
            return

        cf = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self.log_line.emit(f"[>] Запуск sing-box: {Path(self.config_path).name}")
            self.log_line.emit(f"[>] Полный путь: {self.config_path}")

            # 🔧 Проверяем версию sing-box
            try:
                version_out = subprocess.check_output(
                    [str(SINGBOX_PATH), "version"],
                    text=True,
                    creationflags=cf
                ).strip().split('\n')[0]
                self.log_line.emit(f"[i] {version_out}")
            except:
                pass

            self.process = subprocess.Popen(
                [str(SINGBOX_PATH), "run", "-c", self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=cf,
                bufsize=1
            )

            # 🔧 Ждём инициализацию
            init_ok = False
            start_time = time.time()
            while time.time() - start_time < 5.0:  # Увеличил до 5 сек
                if not self.running:
                    self.process.terminate()
                    return
                line = self.process.stdout.readline()
                if not line:
                    break
                ln = line.strip()
                if ln:
                    self.log_line.emit(ln)
                    # 🔧 Детектим успешный старт
                    if any(ok in ln.lower() for ok in [
                        "started", "listening", "mixed-in",
                        "router: updated", "tun", "interface"
                    ]):
                        init_ok = True
                    # 🔧 Детектим ошибки
                    if any(err in ln.lower() for err in [
                        "fatal", "parse error", "failed to",
                        "invalid config", "decode config", "error"
                    ]):
                        self.log_line.emit("[!] sing-box сообщил об ошибке")
                        init_ok = False
                        break

            if init_ok:
                self.status_changed.emit(True)
                logging.info(f"PID SingBox: {self.process.pid}")
                self.log_line.emit("[+] Подключение установлено")
            else:
                self.log_line.emit("[!] Не удалось инициализировать sing-box")
                self.process.terminate()
                self.status_changed.emit(False)
                return

            # Основной цикл
            for line in iter(self.process.stdout.readline, ''):
                if not self.running:
                    break
                ln = line.strip()
                if ln:
                    self.log_line.emit(ln)

            ret = self.process.wait()
            if ret != 0:
                self.log_line.emit(f"[!] sing-box завершился с кодом {ret}")
            self.status_changed.emit(False)

        except Exception as e:
            self.log_line.emit(f"[!] Ошибка запуска sing-box: {e}")
            import traceback
            self.log_line.emit(f"[!] Traceback: {traceback.format_exc()}")
            self.status_changed.emit(False)

    def stop(self):
        self.running = False

        # Остановка sing-box
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        # 🔧 Остановка AWG только если он реально использовался в этой сессии
        if self._used_awg and AMNEZIAWG_PATH.exists() and sys.platform == "win32":
            cf = subprocess.CREATE_NO_WINDOW
            tunnel = "twi2wi_tunnel"
            try:
                subprocess.run(
                    [str(AMNEZIAWG_PATH), "/uninstalltunnelservice", tunnel],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=cf, timeout=3
                )
                self.log_line.emit("[i] AWG туннель остановлен")
            except Exception as e:
                self.log_line.emit(f"[!] Ошибка остановки AWG: {e}")
            self._used_awg = False