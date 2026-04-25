import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
                             QFileDialog, QInputDialog, QMessageBox, QFrame, QStackedWidget,
                             QTextEdit, QScrollArea, QLineEdit, QSizePolicy, QMenu)
from PyQt6.QtCore import Qt, QTimer
from ui.styles import STYLE
from ui.widgets import ConfigCard
from core.ping_worker import PingWorker
from core.vpn_worker import SingBoxWorker
from utils.config import DATA_DIR, CONF_DIR, CONFIGS_FILE, ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF
from utils.helpers import detect_type, get_system_info
import logging


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

        self.connect_timeout_timer = QTimer(self)
        self.connect_timeout_timer.setSingleShot(True)
        self.connect_timeout_timer.timeout.connect(self._handle_connect_timeout)

        self.load_configs()
        self.init_ui()
        self.start_ping_monitor()

    def closeEvent(self, event):
        print("Закрытие приложения...")
        self.connect_timeout_timer.stop()
        try:
            if hasattr(self, "singbox_worker") and self.singbox_worker and self.singbox_worker.isRunning():
                self.singbox_worker.stop()
                self.singbox_worker.quit()
                if not self.singbox_worker.wait(3000): self.singbox_worker.terminate()
        except Exception as e:
            print("Ошибка остановки:", e)
        if hasattr(self, "ping_worker") and self.ping_worker:
            self.ping_worker.stop()
            self.ping_worker.wait(1000)
        event.accept()

    def load_configs(self):
        CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIGS_FILE.exists():
            try:
                self.configs = json.loads(CONFIGS_FILE.read_text())
            except:
                self.configs = []
        for c in self.configs: c.setdefault("favorite", False)

    def save_configs(self):
        CONFIGS_FILE.write_text(json.dumps(self.configs, ensure_ascii=False, indent=2))

    def init_ui(self):
        self.setWindowTitle("Twi2wi Re v1.3.0")
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

        logo = QLabel("◈ Twi2wi_Re");
        logo.setObjectName("logo_label");
        sl.addWidget(logo)
        ver = QLabel("v1.3.0 Re");
        ver.setObjectName("version_label");
        sl.addWidget(ver)

        status_frame = QFrame()
        sf = QHBoxLayout(status_frame)
        sf.setContentsMargins(16, 8, 16, 8)
        self.status_dot = QLabel();
        self.status_dot.setFixedSize(0, 0);
        self.status_dot.hide()
        self.status_text = QLabel("ОТКЛЮЧЁН");
        self.status_text.setStyleSheet("color: #C62828; font-size: 11px;")
        sf.addWidget(self.status_text);
        sf.addStretch()
        sl.addWidget(status_frame)

        sep = QFrame();
        sep.setFrameShape(QFrame.Shape.HLine);
        sep.setStyleSheet("background:#D8C8E8; max-height:1px;");
        sl.addWidget(sep)
        sl.addSpacing(8)

        self.nav_btns = []
        for n, p in [("◎  ПОДКЛЮЧЕНИЕ", 0), ("  КОНФИГИ", 1), ("◈  ПИНГ", 2), ("≡  СИСТЕМА", 3)]:
            b = QPushButton(n);
            b.setObjectName("nav_btn");
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, p=p: self.switch_page(p))
            sl.addWidget(b);
            self.nav_btns.append(b)
        sl.addStretch()

        self.connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ");
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
            b.style().unpolish(b);
            b.style().polish(b)

    def build_connect_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(12)

        top_row = QFrame()
        tr = QHBoxLayout(top_row);
        tr.setContentsMargins(0, 0, 0, 0)
        self.top_connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ");
        self.top_connect_btn.setObjectName("connect_btn")
        self.top_connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.top_connect_btn.clicked.connect(self.toggle_connection)
        tr.addStretch();
        tr.addWidget(self.top_connect_btn)
        l.addWidget(top_row)

        t = QLabel("АКТИВНОЕ ПОДКЛЮЧЕНИЕ");
        t.setObjectName("section_title");
        l.addWidget(t)
        card = QFrame();
        card.setObjectName("card");
        cl = QVBoxLayout(card)
        self.big_status = QLabel("● ОТКЛЮЧЁН");
        self.big_status.setStyleSheet(
            "color: #C62828; font-size: 28px; font-weight: bold; background: transparent; padding: 0px; ")
        self.active_label = QLabel("Конфиг не выбран");
        self.active_label.setStyleSheet("color: #7A5C9A; font-size: 12px; background: transparent; padding: 0px;")
        cl.addWidget(self.big_status);
        cl.addWidget(self.active_label)
        l.addWidget(card)

        # 🔹 СПЛИТ: ЛЕВАЯ (списки) + ПРАВАЯ (инфо)
        split_frame = QFrame()
        split_layout = QHBoxLayout(split_frame)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(16)

        # Левая колонка
        left_col = QVBoxLayout()
        self.fav_title = QLabel("⭐ ИЗБРАННОЕ");
        self.fav_title.setObjectName("fav_section");
        left_col.addWidget(self.fav_title)

        self.fav_list = QListWidget()
        self.fav_list.setObjectName("config_list")
        self.fav_list.itemClicked.connect(self.on_quick_select)
        self.fav_list.setMaximumHeight(110)
        self.fav_list.hide()

        # 🔧 Плавная прокрутка
        self.fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.fav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.fav_list.setStyleSheet("""
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
            QListWidget#config_list::item:hover {
                background: rgba(122, 92, 154, 0.08);
            }
            QListWidget#config_list::item:selected {
                background: #E6D8FF;
                color: black;
            }
            QScrollBar:vertical {
                background: #F8F6F2;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #D8C8E8;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #C8B8D8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        left_col.addWidget(self.fav_list)

        t2 = QLabel("ВСЕ КОНФИГУРАЦИИ");
        t2.setObjectName("section_title");
        left_col.addWidget(t2)
        self.quick_list = QListWidget();
        self.quick_list.setObjectName("config_list");
        self.quick_list.itemClicked.connect(self.on_quick_select)
        left_col.addWidget(self.quick_list, 1)

        # Правая колонка
        self.info_panel = QWidget()
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(0, 0, 0, 0);
        info_layout.setSpacing(10)
        self.info_title = QLabel("ИНФОРМАЦИЯ О КОНФИГЕ");
        self.info_title.setObjectName("section_title");
        info_layout.addWidget(self.info_title)
        self.info_name = QLabel("Имя: —");
        self.info_name.setObjectName("card_title");
        info_layout.addWidget(self.info_name)
        self.info_type = QLabel("Тип: —");
        self.info_type.setObjectName("card_host");
        info_layout.addWidget(self.info_type)
        self.info_preview = QTextEdit();
        self.info_preview.setObjectName("log_view");
        self.info_preview.setReadOnly(True)
        self.info_preview.setPlaceholderText("Выбери конфиг из списка слева...")
        info_layout.addWidget(self.info_preview, 1)

        split_layout.addLayout(left_col, 1)
        split_layout.addWidget(self.info_panel, 1)
        l.addWidget(split_frame, 1)
        self.refresh_quick_list()
        return w

    def build_configs_page(self):
        w = QWidget();
        l = QVBoxLayout(w);
        l.setContentsMargins(32, 32, 32, 32);
        l.setSpacing(12)
        t = QLabel("МЕНЕДЖЕР КОНФИГОВ");
        t.setObjectName("section_title");
        l.addWidget(t)
        r = QHBoxLayout()
        for ttxt, f in [("+ ФАЙЛ", self.add_config_file), ("+ ССЫЛКА", self.add_config_url),
                        ("+ ТЕКСТ", self.add_config_text), (" УДАЛИТЬ", self.delete_config)]:
            b = QPushButton(ttxt);
            b.setObjectName("add_btn");
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(f);
            r.addWidget(b)
        l.addLayout(r)
        self.config_list = QListWidget();
        self.config_list.setObjectName("config_list")
        self.config_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.config_list.itemClicked.connect(self.on_config_select)
        l.addWidget(self.config_list, 1)
        self.refresh_config_list()
        t2 = QLabel("ПРЕДПРОСМОТР");
        t2.setObjectName("section_title");
        l.addWidget(t2)
        self.preview = QTextEdit();
        self.preview.setObjectName("log_view");
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(150);
        self.preview.setPlaceholderText("Выбери конфиг...")
        l.addWidget(self.preview)
        return w

    def build_ping_page(self):
        w = QWidget();
        l = QVBoxLayout(w);
        l.setContentsMargins(32, 32, 32, 32);
        l.setSpacing(16)
        t = QLabel("МОНИТОРИНГ ПИНГА");
        t.setObjectName("section_title");
        l.addWidget(t)
        input_frame = QFrame();
        input_frame.setObjectName("card");
        input_frame.setStyleSheet("border: 1px solid #FF9E43;")
        ifr = QHBoxLayout(input_frame);
        ifr.setContentsMargins(10, 6, 10, 6);
        ifr.setSpacing(10)
        self.ping_input = QLineEdit();
        self.ping_input.setPlaceholderText("host:port или домен")
        self.ping_input.returnPressed.connect(self.add_ping_from_input)
        self.ping_add_btn = QPushButton("+ ДОБАВИТЬ");
        self.ping_add_btn.setObjectName("add_btn")
        self.ping_add_btn.clicked.connect(self.add_ping_from_input)
        ifr.addWidget(self.ping_input);
        ifr.addWidget(self.ping_add_btn)
        l.addWidget(input_frame)
        scroll = QScrollArea();
        scroll.setWidgetResizable(True);
        scroll.setStyleSheet("border:none; background:transparent;")
        self.ping_container = QWidget();
        self.ping_layout = QGridLayout(self.ping_container)
        self.ping_layout.setSpacing(12);
        self.ping_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.ping_container)
        l.addWidget(scroll, 1)
        self.row_idx = 0
        for n, h in [("GOOGLE DNS", "8.8.8.8"), ("CLOUDFLARE", "1.1.1.1"), ("YANDEX DNS", "77.88.8.8"),
                     ("STRINOVA JP", "101.32.143.247")]:
            self._add_ping_card(n, h)
        return w

    def _add_ping_card(self, name, host):
        if name in self.ping_cards: return
        card = QFrame();
        card.setObjectName("card");
        cl = QVBoxLayout(card);
        cl.setSpacing(4)
        lbl_n = QLabel(name);
        lbl_n.setObjectName("card_title")
        lbl_h = QLabel(host);
        lbl_h.setObjectName("card_host")
        lbl_v = QLabel("...");
        lbl_v.setObjectName("card_value_none")
        lbl_l = QLabel("Потери: —");
        lbl_l.setStyleSheet("color: #7A5C9A; font-size: 11px;")
        cl.addWidget(lbl_n);
        cl.addWidget(lbl_h);
        cl.addWidget(lbl_v);
        cl.addWidget(lbl_l)
        col = self.row_idx % 2;
        row = self.row_idx // 2
        self.ping_layout.addWidget(card, row, col)
        self.row_idx += 1
        self.ping_cards[name] = (lbl_v, lbl_l)
        self.ping_hosts[name] = host

    def add_ping_from_input(self):
        txt = self.ping_input.text().strip()
        if not txt: return
        host = txt.split(":")[0];
        name = host.upper() if "." not in host else host.split(".")[0].upper()
        if name not in self.ping_cards:
            self._add_ping_card(name, host)
            if self.ping_worker: self.ping_worker.add_host(name, host)
        self.ping_input.clear()

    def build_sys_page(self):
        w = QWidget();
        l = QVBoxLayout(w);
        l.setContentsMargins(32, 32, 32, 32);
        l.setSpacing(16)
        t = QLabel("СИСТЕМА И ЛОГИ");
        t.setObjectName("section_title");
        l.addWidget(t)
        self.sys_view = QTextEdit();
        self.sys_view.setObjectName("sys_view");
        self.sys_view.setReadOnly(True)
        self.sys_view.setText(get_system_info())
        l.addWidget(self.sys_view, 1)
        t2 = QLabel("ЖУРНАЛ РАБОТЫ");
        t2.setObjectName("section_title");
        l.addWidget(t2)
        self.log_view = QTextEdit();
        self.log_view.setObjectName("log_view");
        self.log_view.setReadOnly(True)
        self.log_view.append("[i] Логи появятся после подключения...")
        l.addWidget(self.log_view, 1)
        r = QHBoxLayout();
        r.addStretch()
        clr = QPushButton("ОЧИСТИТЬ ЛОГ");
        clr.setObjectName("add_btn");
        clr.clicked.connect(lambda: self.log_view.clear())
        r.addWidget(clr);
        l.addLayout(r)
        return w

    def refresh_quick_list(self):
        self.fav_list.clear()
        self.quick_list.clear()

        favs = [c for c in self.configs if c.get("favorite")]
        others = [c for c in self.configs if not c.get("favorite")]

        if favs:
            self.fav_list.show(); self.fav_title.show()
        else:
            self.fav_list.hide(); self.fav_title.hide()

        if not self.configs: self.quick_list.addItem("Нет конфигов"); return
        for c in favs: self._add_card_to_list(self.fav_list, c)
        for c in others: self._add_card_to_list(self.quick_list, c)

    def _add_card_to_list(self, lst, cfg):
        item = QListWidgetItem()
        card = ConfigCard(cfg, parent=lst)
        item.setSizeHint(card.sizeHint())
        lst.addItem(item)
        lst.setItemWidget(item, card)

    def refresh_config_list(self):
        self.config_list.clear()
        for c in self.configs:
            item = QListWidgetItem()
            card = ConfigCard(c, parent=self.config_list)
            item.setSizeHint(card.sizeHint())
            self.config_list.addItem(item)
            self.config_list.setItemWidget(item, card)

    def on_config_select(self, item):
        idx = self.config_list.currentRow()
        if 0 <= idx < len(self.configs):
            self.selected_config = self.configs[idx]
            self.preview.setPlainText(self.selected_config.get("content", "")[:2000] + (
                "..." if len(self.selected_config.get("content", "")) > 2000 else ""))
            self._update_right_panel()

    def on_quick_select(self, item):
        idx = self.quick_list.currentRow()
        if 0 <= idx < len(self.configs):
            self.selected_config = self.configs[idx]
            self._update_right_panel()

    def _update_right_panel(self):
        if not self.selected_config: return
        self.info_name.setText(f"Имя: {self.selected_config.get('name', '—')}")
        self.info_type.setText(f"Тип: {self.selected_config.get('type', 'singbox').upper()}")
        self.info_preview.setPlainText(self.selected_config.get("content", ""))
        self.active_label.setText(f"Конфиг: {self.selected_config['name']}")

    def add_config_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Открыть конфиг", "",
                                           "JSON/Conf (*.json *.conf *.yaml *.yml);;Все файлы (*)")
        if not p: return
        c = Path(p).read_text(encoding="utf-8", errors="replace")
        new_name = Path(p).name;
        new_path = CONF_DIR / new_name
        new_path.write_text(c, encoding="utf-8")
        self.configs.append({"name": new_name, "type": detect_type(c), "content": c, "path": str(new_path)})
        self.save_configs();
        self.refresh_config_list();
        self.refresh_quick_list()

    def add_config_url(self):
        url, ok = QInputDialog.getText(self, "Добавить по ссылке",
                                       "Вставь ссылку (vmess://, vless://, ss://, trojan://, hy2://):")
        if ok and url.strip():
            name, _ = QInputDialog.getText(self, "Название", "Название конфига:")
            safe_name = (name or "link_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name;
            new_path.write_text(url, encoding="utf-8")
            self.configs.append(
                {"name": name or url[:30], "type": url.split("://")[0], "content": url, "path": str(new_path)})
            self.save_configs();
            self.refresh_config_list();
            self.refresh_quick_list()

    def add_config_text(self):
        t, ok = QInputDialog.getMultiLineText(self, "Вставить конфиг", "JSON или raw-конфиг:")
        if ok and t.strip():
            name, _ = QInputDialog.getText(self, "Название", "Название:")
            safe_name = (name or "text_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name;
            new_path.write_text(t, encoding="utf-8")
            self.configs.append(
                {"name": name or "Новый конфиг", "type": detect_type(t), "content": t, "path": str(new_path)})
            self.save_configs();
            self.refresh_config_list();
            self.refresh_quick_list()

    def delete_config(self):
        idx = self.config_list.currentRow()
        if idx < 0 or idx >= len(self.configs):
            QMessageBox.warning(self, "Внимание", "Сначала выбери конфиг из списка!")
            return
        cfg = self.configs[idx]
        if QMessageBox.question(self, "Удалить", f"Удалить «{cfg.get('name')}»?") == QMessageBox.StandardButton.Yes:
            cfg_path = cfg.get("path", "")
            if cfg_path and Path(cfg_path).exists():
                try:
                    Path(cfg_path).unlink()
                except:
                    pass
            self.configs.pop(idx)
            self.save_configs();
            self.refresh_config_list();
            self.refresh_quick_list()
            if self.selected_config == cfg: self.selected_config = None

    def delete_config_by_obj(self, cfg):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                if QMessageBox.question(self, "Удалить",
                                        f"Удалить «{c.get('name')}»?") == QMessageBox.StandardButton.Yes:
                    cfg_path = c.get("path", "")
                    if cfg_path and Path(cfg_path).exists():
                        try:
                            Path(cfg_path).unlink()
                        except:
                            pass
                    self.configs.pop(i)
                    self.save_configs();
                    self.refresh_config_list();
                    self.refresh_quick_list()
                    return

    def rename_config_by_obj(self, cfg):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=c.get("name", ""))
                if ok and new_name.strip():
                    self.configs[i]["name"] = new_name.strip()
                    self.save_configs();
                    self.refresh_config_list();
                    self.refresh_quick_list()
                    if self.selected_config == c: self.selected_config = self.configs[i]
                    self.active_label.setText(f"Конфиг: {new_name}")
                    return

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_vpn()
        else:
            self.connect_vpn()

    def connect_vpn(self):
        self.connect_timeout_timer.stop()
        if not self.selected_config:
            QMessageBox.warning(self, "Нет конфига", "Сначала выбери конфиг!")
            return

        cfg = self.selected_config
        c = cfg.get("content", "")
        config_type = cfg.get('type', 'singbox')

        self.big_status.setText("● ОЖИДАНИЕ...")
        self.big_status.setStyleSheet(
            "color: #FFC107; font-size: 28px; font-weight: bold; background: transparent; padding: 0px;")
        self.status_dot.setObjectName("status_dot_waiting");
        self.status_text.setText("ОЖИДАНИЕ...")
        self.status_text.setStyleSheet("color: #FFC107; font-size: 11px; letter-spacing: 1px; background: transparent;")

        if config_type.lower() in ['amneziawg', 'wireguard']:
            self.active_config_path = ACTIVE_CONFIG_CONF
        else:
            self.active_config_path = ACTIVE_CONFIG_JSON

        try:
            self.active_config_path.write_text(c, encoding="utf-8")
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить конфиг:\n{e}")
            self.on_status_changed(False);
            return

        self.append_log(f"[i] Активный конфиг: {self.active_config_path.name}")
        self.append_log(f"[i] Тип: {config_type}")

        self.singbox_worker = SingBoxWorker(str(self.active_config_path), config_type)
        self.singbox_worker.log_line.connect(self.append_log)
        self.singbox_worker.status_changed.connect(self.on_status_changed)
        self.singbox_worker.start()
        self.connect_timeout_timer.start(10000)

    def _handle_connect_timeout(self):
        if not self.is_connected:
            self.append_log("[!] Таймаут подключения.")
            self.disconnect_vpn()
            QMessageBox.warning(self, "Таймаут", "Подключение не удалось в течение 10 сек.")

    def disconnect_vpn(self):
        self.connect_timeout_timer.stop()
        if self.singbox_worker:
            self.singbox_worker.stop()
            self.singbox_worker = None
        for f in [ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF]:
            try:
                if f.exists(): f.unlink()
            except:
                pass
        self.on_status_changed(False)

    def on_status_changed(self, connected):
        self.connect_timeout_timer.stop()
        self.is_connected = connected
        if connected:
            st, clr = "ПОДКЛЮЧЁН", "#4CAF50"
            self.status_dot.setObjectName("status_dot_connected")
        else:
            st, clr = "ОТКЛЮЧЁН", "#C62828"
            self.status_dot.setObjectName("status_dot_disconnected")

        self.connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.top_connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.big_status.setText("● " + st)
        self.big_status.setStyleSheet(
            f"color: {clr}; font-size: 28px; font-weight: bold; background: transparent; padding: 0px; ")
        self.status_text.setText(st)
        self.status_text.setStyleSheet(f"color: {clr}; font-size: 11px; letter-spacing: 1px; background: transparent;")

        if self.selected_config:
            self.active_label.setText(f"Конфиг: {self.selected_config['name']}")
        else:
            self.active_label.setText("Конфиг не выбран")

    def append_log(self, line):
        try:
            low = line.lower()
            if "command" in low and "amneziawg" in low and "returned non-zero" in low: return
            self.log_view.append(line)
        except:
            pass
        low = line.lower()
        if "local ip" in low or "assigned local" in low: self.append_system_message(f"Найден локальный IP: {line}")
        if "handshake" in low: self.append_system_message(f"Handshake: {line}")

    def append_system_message(self, msg):
        try:
            self.sys_view.append(msg)
        except:
            pass

    def start_ping_monitor(self):
        hosts = list(self.ping_hosts.items())
        self.ping_worker = PingWorker(hosts)
        self.ping_worker.result.connect(self.on_ping_result)
        self.ping_worker.start()

    def on_ping_result(self, name, ms, loss):
        if name not in self.ping_cards: return
        lbl_v, lbl_l = self.ping_cards[name]
        if ms >= 0:
            lbl_v.setText(f"{ms} ms")
        else:
            lbl_v.setText("timeout")
        lbl_l.setText(f"Потери: {loss:.0f}%")
        if ms == -1:
            lbl_v.setStyleSheet("color: #000000;")
        elif ms < 100:
            lbl_v.setStyleSheet("color: #2E7D32;")
        elif ms <= 200:
            lbl_v.setStyleSheet("color: #F57C00;")
        else:
            lbl_v.setStyleSheet("color: #C62828;")