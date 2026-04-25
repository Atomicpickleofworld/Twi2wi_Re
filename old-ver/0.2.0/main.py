import sys
import os
import json
import subprocess
import tempfile
import threading
import time
import socket
import platform
import uuid
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
    QInputDialog, QMessageBox, QFrame, QStackedWidget, QTextEdit,
    QScrollArea, QLineEdit, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
import logging

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
BASE_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent

DATA_DIR = Path(os.getenv("APPDATA")) / "Twi2wi"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONF_DIR = DATA_DIR / "conf"
CONF_DIR.mkdir(exist_ok=True)

CONFIGS_FILE = DATA_DIR / "configs.json"

SINGBOX_PATH = BASE_DIR / "sing-box.exe"
AMNEZIAWG_PATH = BASE_DIR / "amneziawg.exe"

ACTIVE_CONFIG_JSON = CONF_DIR / "active_config.json"
ACTIVE_CONFIG_CONF = CONF_DIR / "active_config.conf"

logging.basicConfig(
    filename=str(BASE_DIR / "vpn_debug.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

STYLE = """
QMainWindow, QWidget {
background-color: #F8F6F2;
color: #2C2430;
font-family: 'Segoe UI', 'Consolas', sans-serif;
}
#sidebar {
background-color: #EDE5F5;
border-right: 1px solid #D8C8E8;
min-width: 220px;
max-width: 220px;
}
#logo_label {
color: #7A5C9A;
font-size: 20px;
font-weight: bold;
letter-spacing: 3px;
padding: 20px 16px 8px 16px;
}
QPushButton:focus {
outline: none;
}
#version_label {
color: #9B8AAE;
font-size: 10px;
padding: 0 16px 20px 16px;
letter-spacing: 1px;
}
#nav_btn {
background: transparent;
border: none;
color: #6B5A7E;
font-size: 12px;
letter-spacing: 1px;
text-align: left;
padding: 12px 20px;
border-left: 2px solid transparent;
}
#nav_btn:hover {
color: #FF9E43;
background: rgba(255, 158, 67, 0.08);
border-left: 2px solid #FF9E43;
}
#nav_btn[active="true"] {
color: #FF9E43;
background: rgba(255, 158, 67, 0.12);
border-left: 2px solid #FF9E43;
}
#status_dot_connected {
background: #4CAF50;
border-radius: 5px;
min-width: 10px; max-width: 10px;
min-height: 10px; max-height: 10px;
}
#status_dot_disconnected {
background: #C62828;
border-radius: 5px;
min-width: 10px; max-width: 10px;
min-height: 10px; max-height: 10px;
}
#connect_btn {
background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FF9E43, stop:1 #F28C33);
border: none;
border-radius: 8px;
color: #FFFFFF;
font-size: 13px;
font-weight: bold;
letter-spacing: 2px;
padding: 10px 14px;
margin: 8px 16px;
}
#status_dot_waiting {
background: #FFC107;
border-radius: 5px;
min-width: 10px; max-width: 10px;
min-height: 10px; max-height: 10px;
}
#connect_btn:hover {
background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFB74D, stop:1 #FF9E43);
}
#disconnect_btn {
background: transparent;
border: 1px solid #C62828;
border-radius: 8px;
color: #C62828;
font-size: 13px;
font-weight: bold;
letter-spacing: 2px;
padding: 14px;
margin: 8px 16px;
}
#disconnect_btn:hover { background: rgba(198, 40, 40, 0.1); }
/* ФИКС ФОНА СПИСКОВ */
QListWidget#config_list {
background: transparent;
border: none;
outline: none;
}
QListWidget#config_list::item {
background: transparent;
border-radius: 8px;
margin-bottom: 4px;
padding: 4px;
}
QListWidget#config_list::item:hover { background: rgba(122, 92, 154, 0.08); }
QListWidget#config_list::item:selected {
background: #E6D8FF;
color: black;
}
#card {
background: #FDFCF9;
border: 1px solid #E8DFF0;
border-radius: 12px;
padding: 12px;
}
#card_title { color: #7A5C9A; font-size: 11px; letter-spacing: 2px; }
#card_host { color: #9B8AAE; font-size: 10px; }
#card_value_good { color: #2E7D32; font-size: 20px; font-weight: bold; }
#card_value_mid   { color: #F57C00; font-size: 20px; font-weight: bold; }
#card_value_bad   { color: #C62828; font-size: 20px; font-weight: bold; }
#card_value_none  { color: #2C2430; font-size: 20px; font-weight: bold; }
#section_title { background-color: rgba(255, 255, 255, 0); color: #7A5C9A; font-size: 11px; letter-spacing: 3px; padding: 0 0 8px 0; }
#add_btn {
background: transparent;
border: 1px dashed #C8B8D8;
border-radius: 8px;
color: #7A5C9A;
font-size: 12px;
padding: 10px;
letter-spacing: 1px;
}
#add_btn:hover { border-color: #FF9E43; color: #FF9E43; background: rgba(255, 158, 67, 0.05); }
#log_view, #sys_view {
background: #FFFFFF;
border: 1px solid #E8DFF0;
border-radius: 8px;
color: #4A3B52;
font-family: 'Consolas', monospace;
font-size: 11px;
padding: 12px;
}
QLineEdit {
background: #FFFFFF;
border: 1px solid #D8C8E8;
border-radius: 6px;
padding: 8px;
color: #2C2430;
}
QLineEdit:focus { border-color: #FF9E43; }
QScrollBar:vertical { background: #F8F6F2; width: 6px; border-radius: 3px; }
QScrollBar::handle:vertical { background: #D8C8E8; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollArea { background: transparent; border: none; }
"""

class PingWorker(QThread):
    result = pyqtSignal(str, int, float)
    def __init__(self, hosts):
        super().__init__()
        self.hosts = list(hosts)
        self.running = True
        self.history = {name: [] for name, _ in hosts}
        self.lock = threading.Lock()
    def ping_host(self, host):
        try:
            start = time.time()
            sock = socket.create_connection((host, 80), timeout=3)
            sock.close()
            return int((time.time() - start) * 1000)
        except:
            return -1
    def run(self):
        while self.running:
            for name, host in list(self.hosts):
                if not self.running: break
                ms = self.ping_host(host)
                with self.lock:
                    hist = self.history.setdefault(name, [])
                    hist.append(ms)
                    if len(hist) > 10: hist.pop(0)
                fails = sum(1 for x in hist if x == -1)
                loss = (fails / len(hist)) * 100.0 if hist else 0.0
                self.result.emit(name, ms, loss)
                time.sleep(0.5)
            time.sleep(0.5)
    def stop(self):
        self.running = False
    def add_host(self, name, host):
        with self.lock:
            if name not in self.history: self.history[name] = []
            self.hosts.append([name, host])

class SingBoxWorker(QThread):
    log_line = pyqtSignal(str)
    status_changed = pyqtSignal(bool)
    def __init__(self, config_path, config_type="singbox"):
        super().__init__()
        self.config_path = config_path
        self.config_type = config_type
        self.process = None
        self.connected_config = None
        self.running = True
        logging.info(f"Запуск __init__. Тип: {self.config_type}, путь: {self.config_path}")
    def is_awg_config(self, content):
        return "[Interface]" in content and ("Jc" in content or "Jmin" in content or "PrivateKey" in content)
    def run(self):
        logging.info(f"Запуск run. Тип: {self.config_type}, путь: {self.config_path}")
        try:
            content = Path(self.config_path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self.log_line.emit(f"[!] Ошибка чтения конфига: {e}")
            self.status_changed.emit(False)
            return
        is_awg = self.is_awg_config(content)
        if self.config_type.lower() == "amneziawg" or is_awg:
            self.run_amneziawg(content)
        elif self.config_type.lower() == "singbox":
            self.run_singbox()
        else:
            self.log_line.emit("[!] Неизвестный тип, пробуем sing-box")
            self.run_singbox()
    def run_amneziawg(self, content):
        if not AMNEZIAWG_PATH.exists():
            self.log_line.emit("[!] amneziawg.exe не найден")
            self.status_changed.emit(False)
            return
        tunnel = "twi2wi_tunnel"
        conf_dir = Path(tempfile.gettempdir()) / "twi2wi"
        conf_dir.mkdir(exist_ok=True)
        conf_file = conf_dir / f"{tunnel}.conf"
        try:
            conf_file.write_text(content, encoding="utf-8")
        except Exception as e:
            self.log_line.emit(f"[!] Ошибка записи конфига: {e}")
            self.status_changed.emit(False)
            return
        try:
            self.log_line.emit(f"[>] Установка туннеля: {conf_file}")
            subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", tunnel], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            result = subprocess.run([str(AMNEZIAWG_PATH), "/installtunnelservice", str(conf_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.stdout: self.log_line.emit(result.stdout)
            if result.stderr: self.log_line.emit(result.stderr)
            if result.returncode != 0:
                self.log_line.emit(f"[!] Код ошибки: {result.returncode}")
                self.status_changed.emit(False)
                return
            self.log_line.emit("[+] Туннель установлен")
            subprocess.run(["sc", "start", tunnel])
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
        try:
            self.log_line.emit(f"[>] Запуск sing-box: {self.config_path}")
            self.process = subprocess.Popen([str(SINGBOX_PATH), "run", "-c", self.config_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
        print("STOP CALLED")
        self.running = False
        if self.process:
            try: self.process.terminate()
            except: pass
            self.process = None
        if AMNEZIAWG_PATH.exists():
            try:
                subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", "twi2wi_tunnel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, timeout=5)
                self.log_line.emit("[i] AWG туннель остановлен")
            except Exception as e:
                self.log_line.emit(f"[!] Ошибка остановки туннеля: {e}")
            for _ in range(2):
                subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", "twi2wi_tunnel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0, timeout=5)
                time.sleep(0.1)

class ConfigCard(QWidget):
    def __init__(self, cfg, parent=None, compact=False):
        super().__init__(parent)
        self.cfg = cfg
        self.compact = compact
        self.setObjectName("card")
        self.setStyleSheet("background: transparent; border: none;")
        name = QLabel(cfg.get("name", "Без имени"))
        name.setObjectName("card_title")
        typ = QLabel(cfg.get("type", "").upper())
        typ.setObjectName("card_host")
        btn = QPushButton("⋮")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet("border:none; background:transparent; font-size:16px; color: #7A5C9A;")
        btn.setToolTip("Меню")
        btn.clicked.connect(self.show_menu)
        left = QVBoxLayout()
        left.addWidget(name)
        if not compact: left.addWidget(typ)
        left.setSpacing(2)
        left.setContentsMargins(8, 6, 8, 6)
        h = QHBoxLayout(self)
        h.addLayout(left)
        h.addStretch()
        h.addWidget(btn)
        h.setContentsMargins(0, 0, 0, 0)
    def show_menu(self):
        menu = QMenu(self)
        rename = menu.addAction("✏️ Переименовать")
        delete = menu.addAction("🗑️ Удалить")
        act = menu.exec(self.mapToGlobal(self.rect().bottomRight()))
        top = self.window()
        if act == rename and hasattr(top, "rename_config_by_obj"): top.rename_config_by_obj(self.cfg)
        elif act == delete and hasattr(top, "delete_config_by_obj"): top.delete_config_by_obj(self.cfg)

class VPNManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.configs = []
        self.selected_config = None
        self.singbox_worker = None
        self.ping_worker = None
        self.is_connected = False
        self.ping_cards = {}
        self.ping_hosts = {}
        self.active_config_path = None
        self.is_connecting = False
        self.load_configs()
        self.init_ui()
        self.start_ping_monitor()
    def closeEvent(self, event):
        print("Закрытие приложения...")
        try:
            subprocess.run([str(AMNEZIAWG_PATH), "/uninstalltunnelservice", "twi2wi_tunnel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        except: pass
        try:
            if hasattr(self, "worker") and self.worker:
                print("STOP CALLED")
                self.worker.stop()
                self.worker.quit()
                self.worker.wait(3000)
        except Exception as e:
            print("Ошибка при остановке:", e)
        event.accept()
    def load_configs(self):
        CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIGS_FILE.exists():
            try: self.configs = json.loads(CONFIGS_FILE.read_text())
            except: self.configs = []
    def save_configs(self):
        CONFIGS_FILE.write_text(json.dumps(self.configs, ensure_ascii=False, indent=2))
    def init_ui(self):
        self.setWindowTitle("Twi2wi_Re")
        self.setMinimumSize(950, 620)
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        logo = QLabel("◈ Twi2wi_Re")
        logo.setObjectName("logo_label")
        sl.addWidget(logo)
        ver = QLabel("v0.2.0 — Re Edition")
        ver.setObjectName("version_label")
        sl.addWidget(ver)
        status_frame = QFrame()
        sf = QHBoxLayout(status_frame)
        sf.setContentsMargins(16, 8, 16, 8)
        sf.setSpacing(8)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(0, 0)
        self.status_dot.hide()
        self.status_text = QLabel("ОТКЛЮЧЁН")
        self.status_text.setStyleSheet("color: #C62828; font-size: 11px; letter-spacing: 1px;")
        sf.addWidget(self.status_text)
        sf.addStretch()
        sl.addWidget(status_frame)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#D8C8E8; max-height:1px;")
        sl.addWidget(sep)
        sl.addSpacing(8)
        self.nav_btns = []
        for n, p in [("◎  ПОДКЛЮЧЕНИЕ", 0), ("  КОНФИГИ", 1), ("◈  ПИНГ", 2), ("≡  СИСТЕМА", 3)]:
            b = QPushButton(n)
            b.setObjectName("nav_btn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, p=p: self.switch_page(p))
            sl.addWidget(b)
            self.nav_btns.append(b)
        sl.addStretch()
        self.connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ")
        self.connect_btn.setObjectName("connect_btn")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self.toggle_connection)
        sl.addSpacing(16)
        main.addWidget(sidebar)
        self.pages = QStackedWidget()
        main.addWidget(self.pages)
        self.pages.addWidget(self.build_connect_page())
        self.pages.addWidget(self.build_configs_page())
        self.pages.addWidget(self.build_ping_page())
        self.pages.addWidget(self.build_sys_page())
        self.switch_page(0)
    def switch_page(self, idx):
        self.pages.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)
    def build_connect_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(12)
        top_row = QFrame()
        tr = QHBoxLayout(top_row)
        tr.setContentsMargins(0, 0, 0, 0)
        self.top_connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ")
        self.top_connect_btn.setObjectName("connect_btn")
        self.top_connect_btn.clicked.connect(self.toggle_connection)
        tr.addStretch()
        tr.addWidget(self.top_connect_btn)
        l.addWidget(top_row)
        t = QLabel("АКТИВНОЕ ПОДКЛЮЧЕНИЕ")
        t.setObjectName("section_title")
        l.addWidget(t)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        self.big_status = QLabel("● ОТКЛЮЧЁН")
        self.big_status.setStyleSheet("color: #C62828; font-size: 28px; font-weight: bold; background: transparent; padding: 0px; ")
        self.active_label = QLabel("Конфиг не выбран")
        self.active_label.setStyleSheet("color: #7A5C9A; font-size: 12px; background: transparent; padding: 0px;")
        cl.addWidget(self.big_status)
        cl.addWidget(self.active_label)
        l.addWidget(card)
        t2 = QLabel("ВЫБРАТЬ КОНФИГ")
        t2.setObjectName("section_title")
        l.addWidget(t2)
        self.quick_list = QListWidget()
        self.quick_list.setObjectName("config_list")
        self.quick_list.itemClicked.connect(self.on_quick_select)
        l.addWidget(self.quick_list, 1)
        self.refresh_quick_list()
        return w
    def open_config_menu(self, pos):
        item = self.quick_list.itemAt(pos)
        if not item: return
        idx = self.quick_list.row(item)
        if idx < 0 or idx >= len(self.configs): return
        menu = QMenu()
        rename_action = menu.addAction("✏ Переименовать")
        delete_action = menu.addAction("🗑 Удалить")
        action = menu.exec(self.quick_list.mapToGlobal(pos))
        if action == rename_action: self.rename_config(idx)
        elif action == delete_action: self.delete_config(idx)
    def rename_config(self, idx):
        old_name = self.configs[idx]["name"]
        text, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=old_name)
        if ok and text:
            self.configs[idx]["name"] = text
            if self.selected_config == self.configs[idx]: self.selected_config = self.configs[idx]
            self.save_configs()
            self.refresh_quick_list()
            self.quick_list.setCurrentRow(idx)
    def delete_config(self, idx=None):
        try:
            if idx is None:
                idx = self.config_list.currentRow()
            item = self.quick_list.currentItem() if idx is None else self.quick_list.item(idx)
            if not item and idx is not None: return
            config_path = self.configs[idx].get("path", "")
            if config_path and Path(config_path).exists():
                try: Path(config_path).unlink()
                except: pass
            self.configs.pop(idx)
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
        except Exception as e:
            print("CRASH HERE:", e)
    def build_configs_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(12)
        t = QLabel("МЕНЕДЖЕР КОНФИГОВ")
        t.setObjectName("section_title")
        l.addWidget(t)
        r = QHBoxLayout()
        for ttxt, f in [("+ ФАЙЛ", self.add_config_file), ("+ ССЫЛКА", self.add_config_url), ("+ ТЕКСТ", self.add_config_text), (" УДАЛИТЬ", self.delete_config)]:
            b = QPushButton(ttxt)
            b.setObjectName("add_btn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(f)
            r.addWidget(b)
        l.addLayout(r)
        self.config_list = QListWidget()
        self.config_list.setObjectName("config_list")
        self.config_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.config_list.itemClicked.connect(self.on_config_select)
        l.addWidget(self.config_list, 1)
        self.refresh_config_list()
        t2 = QLabel("ПРЕДПРОСМОТР")
        t2.setObjectName("section_title")
        l.addWidget(t2)
        self.preview = QTextEdit()
        self.preview.setObjectName("log_view")
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(150)
        self.preview.setPlaceholderText("Выбери конфиг...")
        l.addWidget(self.preview)
        return w
    def build_ping_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(16)
        t = QLabel("МОНИТОРИНГ ПИНГА")
        t.setObjectName("section_title")
        l.addWidget(t)
        input_frame = QFrame()
        input_frame.setObjectName("card")
        input_frame.setStyleSheet("border: 1px solid #FF9E43;")
        ifr = QHBoxLayout(input_frame)
        ifr.setContentsMargins(10, 6, 10, 6)
        ifr.setSpacing(10)
        self.ping_input = QLineEdit()
        self.ping_input.setPlaceholderText("host:port или домен (напр. 8.8.8.8 или google.com)")
        self.ping_input.returnPressed.connect(self.add_ping_from_input)
        self.ping_add_btn = QPushButton("+ ДОБАВИТЬ")
        self.ping_add_btn.setObjectName("add_btn")
        self.ping_add_btn.clicked.connect(self.add_ping_from_input)
        ifr.addWidget(self.ping_input)
        ifr.addWidget(self.ping_add_btn)
        l.addWidget(input_frame)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ping_container = QWidget()
        self.ping_layout = QGridLayout(self.ping_container)
        self.ping_layout.setSpacing(12)
        self.ping_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.ping_container)
        l.addWidget(scroll, 1)
        self.row_idx = 0
        defaults = [("GOOGLE DNS", "8.8.8.8"), ("CLOUDFLARE", "1.1.1.1"), ("YANDEX DNS", "77.88.8.8"), ("STRINOVA JP", "101.32.143.247")]
        for n, h in defaults: self._add_ping_card(n, h)
        return w
    def _add_ping_card(self, name, host):
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setSpacing(4)
        lbl_n = QLabel(name)
        lbl_n.setObjectName("card_title")
        lbl_h = QLabel(host)
        lbl_h.setObjectName("card_host")
        lbl_v = QLabel("...")
        lbl_v.setObjectName("card_value_none")
        lbl_l = QLabel("Потери: —")
        lbl_l.setStyleSheet("color: #7A5C9A; font-size: 11px;")
        cl.addWidget(lbl_n)
        cl.addWidget(lbl_h)
        cl.addWidget(lbl_v)
        cl.addWidget(lbl_l)
        col = self.row_idx % 2
        row = self.row_idx // 2
        self.ping_layout.addWidget(card, row, col)
        self.row_idx += 1
        self.ping_cards[name] = (lbl_v, lbl_l)
        self.ping_hosts[name] = host
    def add_ping_from_input(self):
        txt = self.ping_input.text().strip()
        if not txt: return
        host = txt.split(":")[0]
        name = host.upper() if "." not in host else host.split(".")[0].upper()
        if name not in self.ping_cards:
            self._add_ping_card(name, host)
            if self.ping_worker: self.ping_worker.add_host(name, host)
        self.ping_input.clear()
    def build_sys_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(16)
        t = QLabel("СИСТЕМА И ЛОГИ")
        t.setObjectName("section_title")
        l.addWidget(t)
        self.sys_view = QTextEdit()
        self.sys_view.setObjectName("sys_view")
        self.sys_view.setReadOnly(True)
        self.sys_view.setText(self.get_system_info())
        l.addWidget(self.sys_view, 1)
        t2 = QLabel("ЖУРНАЛ РАБОТЫ")
        t2.setObjectName("section_title")
        l.addWidget(t2)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        self.log_view.append("[i] Логи появятся после подключения...")
        l.addWidget(self.log_view, 1)
        r = QHBoxLayout()
        r.addStretch()
        clr = QPushButton("ОЧИСТИТЬ ЛОГ")
        clr.setObjectName("add_btn")
        clr.clicked.connect(lambda: self.log_view.clear())
        r.addWidget(clr)
        l.addLayout(r)
        return w
    def get_system_info(self):
        info = []
        info.append("🖥️ ВЕРСИИ И ПЛАТФОРМА")
        info.append(f"Python: {platform.python_version()}")
        info.append(f"OS: {platform.system()} {platform.release()}")
        info.append(f"Arch: {platform.machine()}")
        try: info.append(f"PyQt6: {__import__('PyQt6.QtCore').QtCore.PYQT_VERSION_STR}")
        except: info.append("PyQt6: N/A")
        info.append("")
        info.append("📦 ПРОТОКОЛЫ / УТИЛИТЫ")
        info.append(f"sing-box: {'✓ найден' if SINGBOX_PATH.exists() else '✗ отсутствует'}")
        info.append(f"AmneziaWG: {'✓ найден' if AMNEZIAWG_PATH.exists() else '✗ отсутствует'}")
        try:
            v = subprocess.check_output([str(SINGBOX_PATH), "version"], text=True).splitlines()[0]
            info.append(f"  → {v}")
        except: pass
        try:
            v = subprocess.check_output([str(AMNEZIAWG_PATH), "--version"], text=True).splitlines()[0]
            info.append(f"  → {v}")
        except: pass
        info.append("")
        info.append("🌐 СЕТЕВОЙ АДАПТЕР")
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)][::-1])
            info.append(f"Host: {hostname} | IPv4: {ip} | MAC: {mac}")
            info.append("Статус: Активен")
        except Exception as e: info.append(f"Ошибка получения данных: {e}")
        info.append("")
        info.append("⚙️ АППАРАТНОЕ ОБЕСПЕЧЕНИЕ")
        info.append(f"CPU: {platform.processor() or 'N/A'}")
        try:
            if sys.platform == "win32":
                ram = subprocess.check_output("wmic computersystem get totalphysicalmemory", shell=True, text=True).split()[1]
                info.append(f"RAM: {int(ram) / (1024 ** 3):.1f} GB")
                gpu = subprocess.check_output("wmic path win32_videocontroller get name", shell=True, text=True).strip().split('\n')[-1].strip()
                info.append(f"GPU: {gpu}")
            else: info.append("RAM: N/A (Linux/macOS)")
        except: info.append("RAM: N/A")
        return "\n".join(info)
    def refresh_quick_list(self):
        self.quick_list.clear()
        if not self.configs:
            self.quick_list.addItem("Нет конфигов")
            return
        for c in self.configs: self.quick_list.addItem(c.get("name", "Без имени"))
    def refresh_config_list(self):
        self.config_list.clear()
        for c in self.configs:
            item = QListWidgetItem()
            card = ConfigCard(c, parent=self.config_list, compact=False)
            item.setSizeHint(card.sizeHint())
            self.config_list.addItem(item)
            self.config_list.setItemWidget(item, card)
    def on_config_select(self, item):
        idx = self.config_list.currentRow()
        if 0 <= idx < len(self.configs):
            self.selected_config = self.configs[idx]
            self.preview.setPlainText(self.selected_config.get("content", "")[:2000] + ("..." if len(self.selected_config.get("content", "")) > 2000 else ""))
            self.update_tunnel_info()
    def on_quick_select(self, item):
        idx = self.quick_list.currentRow()
        if idx < 0 or idx >= len(self.configs): return
        self.selected_config = self.configs[idx]
    def add_config_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Открыть конфиг", "", "JSON/Conf (*.json *.conf *.yaml *.yml);;Все файлы (*)")
        if not p: return
        c = Path(p).read_text(encoding="utf-8", errors="replace")
        new_name = Path(p).name
        new_path = CONF_DIR / new_name
        new_path.write_text(c, encoding="utf-8")
        self.configs.append({"name": new_name, "type": self.detect_type(c), "content": c, "path": str(new_path)})
        self.save_configs()
        self.refresh_config_list()
        self.refresh_quick_list()
    def add_config_url(self):
        url, ok = QInputDialog.getText(self, "Добавить по ссылке", "Вставь ссылку (vmess://, vless://, ss://, trojan://, hy2://):")
        if ok and url.strip():
            name, _ = QInputDialog.getText(self, "Название", "Название конфига:")
            safe_name = (name or "link_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(url, encoding="utf-8")
            self.configs.append({"name": name or url[:30], "type": url.split("://")[0], "content": url, "path": str(new_path)})
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
    def add_config_text(self):
        t, ok = QInputDialog.getMultiLineText(self, "Вставить конфиг", "JSON или raw-конфиг:")
        if ok and t.strip():
            name, _ = QInputDialog.getText(self, "Название", "Название:")
            safe_name = (name or "text_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(t, encoding="utf-8")
            self.configs.append({"name": name or "Новый конфиг", "type": self.detect_type(t), "content": t, "path": str(new_path)})
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
    def delete_config_by_obj(self, cfg):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                if QMessageBox.question(self, "Удалить", f"Удалить «{c.get('name')}»?") == QMessageBox.StandardButton.Yes:
                    cfg_path = c.get("path", "")
                    if cfg_path and Path(cfg_path).exists():
                        try: Path(cfg_path).unlink()
                        except: pass
                    self.configs.pop(i)
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                return
    def rename_config_by_obj(self, cfg):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=c.get("name", ""))
                if ok and new_name.strip():
                    self.configs[i]["name"] = new_name.strip()
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                    if self.selected_config == c: self.selected_config = self.configs[i]
                    self.active_label.setText(f"Конфиг: {new_name}")
                return
    def detect_type(self, content):
        c = content.lower()
        for p in ["vless", "vmess", "trojan", "shadowsocks", "amneziawg", "wireguard", "hysteria", "tuic", "socks"]:
            if p in c: return p
        return "singbox"
    def toggle_connection(self):
        if self.is_connected: self.disconnect_vpn()
        else: self.connect_vpn()
    def connect_vpn(self):
        if not self.selected_config:
            QMessageBox.warning(self, "Нет конфига", "Сначала выбери конфиг!")
            return
        c = self.selected_config.get("content", "")
        config_type = self.selected_config.get('type', 'singbox')
        self.big_status.setText("● ОЖИДАНИЕ...")
        self.big_status.setStyleSheet("color: #FFC107; font-size: 28px; font-weight: bold; background: transparent; padding: 0px;")
        self.status_dot.setObjectName("status_dot_waiting")
        self.status_text.setText("ОЖИДАНИЕ...")
        self.status_text.setStyleSheet("color: #FFC107; font-size: 11px; letter-spacing: 1px; background: transparent;")
        if config_type.lower() in ['amneziawg', 'wireguard']: self.active_config_path = ACTIVE_CONFIG_CONF
        else: self.active_config_path = ACTIVE_CONFIG_JSON
        try:
            self.active_config_path.write_text(c, encoding="utf-8")
            logging.info(f"Конфиг сохранен в: {self.active_config_path}")
        except Exception as e:
            logging.error(f"Ошибка сохранения конфига: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить конфиг:\n{e}")
            return
        self.append_log(f"[i] Активный конфиг: {self.active_config_path.name}")
        self.append_log(f"[i] Тип конфига: {config_type}")
        self.singbox_worker = SingBoxWorker(str(self.active_config_path), config_type)
        self.singbox_worker.log_line.connect(self.append_log)
        self.singbox_worker.status_changed.connect(self.on_status_changed)
        self.singbox_worker.start()
    def disconnect_vpn(self):
        if self.singbox_worker:
            self.singbox_worker.stop()
            self.singbox_worker = None
        for f in [ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF]:
            try:
                if f.exists(): f.unlink()
            except: pass
        self.on_status_changed(False)
    def on_status_changed(self, connected):
        self.is_connected = connected
        if connected:
            self.connected_config = self.selected_config
            st, clr = "ПОДКЛЮЧЁН", "#4CAF50"
            self.status_dot.setObjectName("status_dot_connected")
        else:
            self.connected_config = None
            st, clr = "ОТКЛЮЧЁН", "#C62828"
            self.status_dot.setObjectName("status_dot_disconnected")
        self.connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.top_connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.big_status.setText("● " + st)
        self.big_status.setStyleSheet(f"color: {clr}; font-size: 28px; font-weight: bold; background: transparent; padding: 0px; ")
        self.status_text.setText(st)
        self.status_text.setStyleSheet(f"color: {clr}; font-size: 11px; letter-spacing: 1px; background: transparent;")
        if self.connected_config: self.active_label.setText(f"Конфиг: {self.connected_config['name']}")
        else: self.active_label.setText("Конфиг не выбран")
        self.update_tunnel_info()
    def update_tunnel_info(self): pass
    def append_log(self, line):
        try:
            low = line.lower()
            if "command" in low and "amneziawg" in low and "returned non-zero" in low: return
            self.log_view.append(line)
        except: pass
        low = line.lower()
        if "local ip" in low or "assigned local" in low or "local address" in low: self.append_system_message(f"Найден локальный IP: {line}")
        if "handshake" in low: self.append_system_message(f"Handshake: {line}")
        if "permission" in low or "access denied" in low or "требуются права" in low: self.append_system_message("[!] Требуются права администратора для этой операции")
    def append_system_message(self, msg):
        try: self.sys_view.append(msg)
        except: pass
    def start_ping_monitor(self):
        hosts = list(self.ping_hosts.items())
        hosts = [[n, h] for n, h in hosts]
        self.ping_worker = PingWorker(hosts)
        self.ping_worker.result.connect(self.on_ping_result)
        self.ping_worker.start()
    def on_ping_result(self, name, ms, loss):
        if name not in self.ping_cards: self._add_ping_card(name, self.ping_hosts.get(name, name))
        lbl_v, lbl_l = self.ping_cards[name]
        if ms >= 0: lbl_v.setText(f"{ms} ms")
        else: lbl_v.setText("timeout")
        lbl_l.setText(f"Потери: {loss:.0f}%")
        if ms == -1: lbl_v.setStyleSheet("color: #000000;")
        elif ms < 100: lbl_v.setStyleSheet("color: #2E7D32;")
        elif ms <= 200: lbl_v.setStyleSheet("color: #F57C00;")
        else: lbl_v.setStyleSheet("color: #C62828;")
    def extract_ip(self, text):
        import re
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", text)
        return m.group(1) if m else None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VPNManager()
    win.show()
    sys.exit(app.exec())
