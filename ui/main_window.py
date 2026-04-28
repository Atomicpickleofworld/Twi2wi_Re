import json
import time
from pathlib import Path

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
                             QFileDialog, QInputDialog, QMessageBox, QFrame, QStackedWidget,
                             QTextEdit, QScrollArea, QLineEdit, QSizePolicy, QMenu, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, QEvent
from ui.styles import STYLE
from ui.widgets import ConfigCard
from core.ping_worker import PingWorker
from core.vpn_worker import SingBoxWorker
from utils.config import CONF_DIR, CONFIGS_FILE, ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF
from utils.helpers import detect_type, get_system_info
# from utils.plugin_manager import PluginManager
from utils.url_parser import url_to_singbox_json, SUPPORTED_SCHEMES
import logging
from PyQt6.QtCore import Qt, QTimer
from utils.version import __version__, __app_name__


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

        # self.plugin_manager = PluginManager(app_context=self, base_dir=Path(__file__).resolve().parent.parent)
        # self.plugin_manager.scan_and_load()

    def closeEvent(self, event):
        print("Закрытие приложения...")
        # self.plugin_manager.unload_all()
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
        """Загрузка конфигов с защитой от ошибок"""
        try:
            CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            if CONFIGS_FILE.exists():
                content = CONFIGS_FILE.read_text(encoding="utf-8")
                if content.strip():
                    self.configs = json.loads(content)
                    logging.info(f"Загружено {len(self.configs)} конфигов")
                else:
                    self.configs = []
                    logging.warning("configs.json пустой")
            else:
                self.configs = []
                logging.info("configs.json не найден, создан пустой список")
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигов: {e}")
            self.configs = []

        # 🔧 Гарантируем наличие favorite у всех конфигов
        for c in self.configs:
            c.setdefault("favorite", False)

    def save_configs(self):
        """Сохранение конфигов с логированием"""
        try:
            CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIGS_FILE.write_text(
                json.dumps(self.configs, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logging.info(f"Сохранено {len(self.configs)} конфигов")
        except Exception as e:
            logging.error(f"Ошибка сохранения конфигов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить конфиги:\n{e}")

    def init_ui(self):
        self.setWindowTitle(f"{__app_name__} v{__version__}")
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
        ver = QLabel(f"v{__version__} Re Edition")
        ver.setObjectName("version_label")
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
        for n, p in [("ПОДКЛЮЧЕНИЕ", 0), ("КОНФИГИ", 1), ("ПИНГ", 2), ("СИСТЕМА", 3), ("ПЛАГИНЫ", 4)]:
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
        self.pages.addWidget(self.build_plugins_page())
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

        split_frame = QFrame()
        split_layout = QHBoxLayout(split_frame)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(16)

        left_col = QVBoxLayout()
        self.fav_title = QLabel("⭐ ИЗБРАННОЕ");
        self.fav_title.setObjectName("fav_section");
        left_col.addWidget(self.fav_title)

        self.fav_list = QListWidget()
        self.fav_list.setObjectName("config_list")
        self.fav_list.itemClicked.connect(self.on_quick_select)
        self.fav_list.setMaximumHeight(110)
        self.fav_list.hide()
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


    def build_plugins_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(32, 32, 32, 32)
        l.setSpacing(16)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        self.plugin_search = QLineEdit()
        self.plugin_search.setPlaceholderText("🔍 Поиск плагинов по названию...")
        self.plugin_search.textChanged.connect(self.filter_plugins)
        top_bar.addWidget(self.plugin_search, 1)

        self.plugin_add_btn = QPushButton("+")
        self.plugin_add_btn.setObjectName("add_btn")
        self.plugin_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plugin_add_btn.setToolTip("Добавить плагин")
        self.plugin_add_btn.clicked.connect(self.show_import_menu)
        top_bar.addWidget(self.plugin_add_btn)
        l.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none; background:transparent;")
        self.plugin_container = QWidget()
        self.plugin_layout = QVBoxLayout(self.plugin_container)
        self.plugin_layout.setSpacing(8)
        self.plugin_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.plugin_container)
        l.addWidget(scroll, 1)

        # 🔧 Обновлённая структура данных (добавлены icon и fullDescription)
        self.plugins_data = [
            # {"id": "traffic_mon", "name": "📊 Traffic Monitor", "desc": "Отслеживание трафика в реальном времени",
            #  "ver": "1.2.0", "enabled": True, "icon": "📈",
            #  "fullDescription": "Мониторинг входящего и исходящего трафика с графиками и статистикой за сессию. Поддерживает экспорт отчетов в CSV."},
            # {"id": "auto_reconnect", "name": "🔄 Auto Reconnect", "desc": "Автоматическое переподключение при обрыве",
            #  "ver": "0.9.1", "enabled": False, "icon": "🔁",
            #  "fullDescription": "Следит за стабильностью соединения. При потере пинга или разрыве туннеля автоматически инициирует переподключение к выбранному серверу."},
            # {"id": "geo_ip", "name": "🌍 Geo IP Checker", "desc": "Проверка IP и страны после подключения",
            #  "ver": "1.0.0", "enabled": True, "icon": "🌐",
            #  "fullDescription": "Автоматически определяет ваш внешний IP-адрес и страну после успешного подключения к VPN. Показывает флаг и провайдера."},
            # {"id": "theme_switch", "name": "🎨 Theme Switcher", "desc": "Переключение светлой/тёмной темы",
            #  "ver": "0.5.0", "enabled": False, "icon": "🎭",
            #  "fullDescription": "Позволяет быстро менять интерфейс приложения. Доступны: Светлая, Тёмная и Акцентная темы оформления."}
        ]

        self.render_plugins()  # ← вызываем отрисовку
        return w

    def create_plugin_card(self, plugin):
        """Создаёт карточку плагина с правильными стилями"""
        card = QFrame()
        card.setObjectName("plugin_card")
        card.plugin_ref = plugin
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.installEventFilter(self)

        # Применяем стиль в зависимости от состояния
        if plugin.get("has_error", False):
            card.setProperty("state", "error")
        elif plugin["enabled"]:
            card.setProperty("state", "enabled")
        else:
            card.setProperty("state", "disabled")

        # Основной layout
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Иконка
        icon = QLabel(plugin.get("icon", "🧩"))
        icon.setStyleSheet("font-size: 22px; min-width: 28px;")
        layout.addWidget(icon)

        # Информационный блок
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        name = QLabel(plugin["name"])
        name.setObjectName("card_title")
        desc = QLabel(plugin["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7A5C9A; font-size: 11px;")
        version = QLabel(f"v{plugin['ver']}")
        version.setStyleSheet("color: #9B8AAE; font-size: 10px;")

        info_layout.addWidget(name)
        info_layout.addWidget(desc)
        info_layout.addWidget(version)
        layout.addWidget(info_widget, 1)

        # Статус (ВКЛ/ВЫКЛ/ОШИБКА)
        if plugin.get("has_error", False):
            status_text = "ОШИБКА"
            status_color = "#F57C00"
        elif plugin["enabled"]:
            status_text = "ВКЛ"
            status_color = "#4CAF50"
        else:
            status_text = "ВЫКЛ"
            status_color = "#9b2d30"

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"""
            color: {status_color};
            font-size: 11px;
            font-weight: bold;
            min-width: 45px;
            text-align: center;
        """)
        layout.addWidget(status_label)

        # Кнопка меню
        menu_btn = QPushButton("⋮")
        menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_btn.setFixedSize(28, 28)
        menu_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 18px;
                color: #7A5C9A;
            }
            QPushButton:hover {
                color: #FF9E43;
            }
        """)
        menu_btn.clicked.connect(lambda checked=False, p=plugin: self.show_plugin_menu(p))
        layout.addWidget(menu_btn)

        # Сохраняем ссылки на динамические элементы
        card.status_label = status_label

        return card

    def apply_plugin_style(self, card, state):
        """Принудительно применяет стиль к карточке плагина"""
        card.setProperty("state", state)
        card.style().unpolish(card)
        card.style().polish(card)

        for child in card.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)

    def render_plugins(self, filter_text=""):
        """Перерисовывает список плагинов с учётом фильтра"""
        # Очистка
        while self.plugin_layout.count():
            item = self.plugin_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Фильтрация
        visible = []
        for p in self.plugins_data:
            if not filter_text or filter_text.lower() in p["name"].lower():
                visible.append(p)

        # Создание карточек
        for i, plugin in enumerate(visible):
            card = self.create_plugin_card(plugin)
            self.plugin_layout.addWidget(card)

            # Разделитель (кроме последнего)
            if i < len(visible) - 1:
                separator = QFrame()
                separator.setObjectName("plugin_sep")
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet("background-color: #E8DFF0; margin: 4px 12px;")
                self.plugin_layout.addWidget(separator)

        self.plugin_layout.addStretch()

    def eventFilter(self, obj, event):
        """Обрабатывает клики по карточкам плагинов"""
        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(obj, "plugin_ref") and obj.objectName() == "plugin_card":
                plugin = obj.plugin_ref

                # Переключаем состояние
                if not plugin.get("has_error", False):
                    plugin["enabled"] = not plugin["enabled"]

                # Обновляем property для CSS
                if plugin.get("has_error", False):
                    obj.setProperty("state", "error")
                    status_text = "ОШИБКА"
                    status_color = "#F57C00"
                elif plugin["enabled"]:
                    obj.setProperty("state", "enabled")
                    status_text = "ВКЛ"
                    status_color = "#4CAF50"
                else:
                    obj.setProperty("state", "disabled")
                    status_text = "ВЫКЛ"
                    status_color = "#9b2d30"

                # Принудительно обновляем стиль карточки
                obj.style().unpolish(obj)
                obj.style().polish(obj)

                # Обновляем текст статуса
                if hasattr(obj, "status_label"):
                    obj.status_label.setText(status_text)
                    obj.status_label.setStyleSheet(f"""
                        color: {status_color};
                        font-size: 11px;
                        font-weight: bold;
                        min-width: 45px;
                        text-align: center;
                    """)

                self.append_log(f"[i] Плагин «{plugin['name']}» {'включён' if plugin['enabled'] else 'отключён'}")
                return True

        return super().eventFilter(obj, event)

    def filter_plugins(self, text):
        self.render_plugins(text)

    def view_full_description(self, plugin):
        desc = plugin.get("fullDescription", "Описание отсутствует.")
        QMessageBox.information(self, f"Описание: {plugin['name']}", desc)

    def show_plugin_menu(self, plugin):
        menu = QMenu(self)
        act_desc = menu.addAction("📖 Полное описание")

        # 🔧 Демо-пункт для переключения ошибки (удалишь позже)
        act_err = menu.addAction("🟡 Переключить ошибку" if not plugin.get("has_error") else "🟢 Убрать ошибку")

        menu.addSeparator()
        act_del = menu.addAction("🗑️ Удалить плагин")

        action = menu.exec(QCursor.pos())
        if action == act_desc:
            self.view_full_description(plugin)
        elif action == act_err:
            plugin["has_error"] = not plugin.get("has_error", False)
            self.render_plugins(self.plugin_search.text())
        elif action == act_del:
            self.delete_plugin(plugin)
    def delete_plugin(self, plugin):
        if QMessageBox.question(self, "Удаление", f"Удалить плагин «{plugin['name']}»?") == QMessageBox.StandardButton.Yes:
            self.plugins_data.remove(plugin)
            self.append_log(f"[i] Плагин «{plugin['name']}» удален")
            self.render_plugins(self.plugin_search.text())

    def toggle_plugin(self, plugin, state):
        plugin["enabled"] = (state == Qt.CheckState.Checked)
        status = "✅ включен" if plugin["enabled"] else "❌ выключен"
        self.append_log(f"[i] Плагин «{plugin['name']}» {status}")
        # 🔜 Здесь будет вызов PluginManager.enable/disable()

    def show_import_menu(self):
        """Меню импорта: с устройства или по ссылке"""
        menu = QMenu(self)
        act_file = menu.addAction("📁 Выбрать с устройства (.zip)")
        act_git = menu.addAction("🌐 Импорт по ссылке GitHub")

        action = menu.exec(self.plugin_add_btn.mapToGlobal(self.plugin_add_btn.rect().bottomRight()))
        if action == act_file:
            self.import_plugin_file()
        elif action == act_git:
            self.import_plugin_git()

    def import_plugin_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите архив плагина", "", "ZIP архивы (*.zip)")
        if path:
            # 🔜 Логика: копирование в plugins/, проверка plugin.json, распаковка
            self.append_log(f"[i] Выбран плагин: {Path(path).name}")
            self.plugins_data.append({
                "id": Path(path).stem.lower(),
                "name": f"📦 {Path(path).stem}",
                "desc": "Импортирован с устройства (ожидает активации)",
                "ver": "0.0.1",
                "enabled": True
            })
            self.render_plugins()
            QMessageBox.information(self, "Импорт",
                                    "Плагин добавлен в список!\nЛогика распаковки будет подключена на следующем этапе.")

    def import_plugin_git(self):
        url, ok = QInputDialog.getText(self, "GitHub ссылка", "Вставь прямую ссылку на .zip или репозиторий:")
        if ok and url.strip():
            # 🔜 Логика: requests.get(url) -> сохранение -> распаковка
            self.append_log(f"[i] Загрузка плагина из GitHub: {url}")
            self.plugins_data.append({
                "id": url.split("/")[-1].lower().replace(".zip", ""),
                "name": f"🌐 {url.split('/')[-1].replace('.zip', '')}",
                "desc": "Импортирован с GitHub (ожидает проверки)",
                "ver": "0.0.1",
                "enabled": True
            })
            self.render_plugins()
            QMessageBox.information(self, "Импорт",
                                    "Запрос на скачивание отправлен!\nЛогика загрузки будет подключена на следующем этапе.")

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
        # 🔧 Храним ссылку на cfg прямо в item — индексы больше не нужны
        item.setData(Qt.ItemDataRole.UserRole, cfg)
        card = ConfigCard(cfg, parent=lst)
        item.setSizeHint(card.sizeHint())
        lst.addItem(item)
        lst.setItemWidget(item, card)

    def refresh_config_list(self):
        self.config_list.clear()
        for c in self.configs:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, c)
            card = ConfigCard(c, parent=self.config_list)
            item.setSizeHint(card.sizeHint())
            self.config_list.addItem(item)
            self.config_list.setItemWidget(item, card)

    def on_config_select(self, item):
        # 🔧 Берём cfg из данных item — не из индекса
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.selected_config = cfg
            self.preview.setPlainText(cfg.get("content", "")[:2000] + (
                "..." if len(cfg.get("content", "")) > 2000 else ""))
            self._update_right_panel()

    def on_quick_select(self, item):
        # 🔧 Берём cfg из данных item — не из индекса
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.selected_config = cfg
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
        schemes = ", ".join(SUPPORTED_SCHEMES)
        url, ok = QInputDialog.getText(
            self, "Добавить по ссылке",
            f"Поддерживаемые протоколы:\n{schemes}\n\nВставь ссылку:"
        )
        if not ok or not url.strip():
            return

        url = url.strip()
        scheme = url.split("://")[0].lower() if "://" in url else ""

        # AWG/WireGuard
        if scheme in ("amneziawg", "wireguard") or (
                "[Interface]" in url and ("Jc" in url or "PrivateKey" in url)
        ):
            name, _ = QInputDialog.getText(self, "Название", "Название конфига:")
            safe_name = (name or "awg_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(url, encoding="utf-8")
            self.configs.append({
                "name": name or safe_name,
                "type": "amneziawg",
                "content": url,
                "path": str(new_path)
            })
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
            # 🔧 Фикс краша — отложенный показ
            QTimer.singleShot(0, lambda: QMessageBox.information(
                self, "Добавлено", "✓ AWG конфиг сохранён"
            ))
            return

        # Парсинг прокси-ссылки
        try:
            from utils.url_parser import parse_proxy_url
            config_dict, proto = parse_proxy_url(url)
            import json as _json
            content = _json.dumps(config_dict, ensure_ascii=False, indent=2)
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка парсинга", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разобрать ссылку:\n{e}")
            return

        # Имя конфига
        import urllib.parse as _up
        auto_name = _up.unquote(url.split("#")[1]) if "#" in url else ""
        name, _ = QInputDialog.getText(
            self, "Название", "Название конфига:",
            text=auto_name
        )
        final_name = name.strip() or auto_name or url[:30]
        safe_name = final_name.replace(" ", "_").replace("/", "_") + ".json"
        new_path = CONF_DIR / safe_name
        new_path.write_text(content, encoding="utf-8")

        self.configs.append({
            "name": final_name,
            "type": proto,
            "content": content,
            "path": str(new_path)
        })
        self.save_configs()

        # 🔧 Безопасное обновление списков
        try:
            self.refresh_config_list()
            self.refresh_quick_list()
        except Exception as e:
            logging.error(f"Ошибка обновления UI: {e}")
            return

        # 🔧 ГЛАВНЫЙ ФИКС — отложенный QMessageBox через QTimer
        QTimer.singleShot(0, lambda: QMessageBox.information(
            self, "Добавлено",
            f"✓ Конфиг «{final_name}» добавлен\n"
            f"Протокол: {proto.upper()}\n"
            f"Сохранён в папку configs/"
        ))

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
        item = self.config_list.currentItem()
        cfg = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not cfg or cfg not in self.configs:
            QMessageBox.warning(self, "Внимание", "Сначала выбери конфиг из списка!")
            return
        idx = self.configs.index(cfg)
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
        # 🔑 Защита от двойного клика: останавливаем предыдущий воркер
        if self.singbox_worker and self.singbox_worker.isRunning():
            self.disconnect_vpn()
            time.sleep(0.3)

        if not self.selected_config:
            QMessageBox.warning(self, "Нет конфига", "Сначала выбери конфиг!")
            return

        cfg = self.selected_config
        c = cfg.get("content", "")
        config_type = cfg.get('type', 'singbox')

        self.big_status.setText("● ОЖИДАНИЕ...")
        self.big_status.setStyleSheet(
            "color: #FFC107; font-size: 28px; font-weight: bold; background: transparent; padding: 0px;")
        self.status_dot.setObjectName("status_dot_waiting")
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
            self.on_status_changed(False)
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
            # 🔑 Безопасный вызов плагин-менеджера
            if hasattr(self, 'plugin_manager') and self.plugin_manager:
                self.plugin_manager.trigger_hook("on_connect", config=self.selected_config)
        else:
            st, clr = "ОТКЛЮЧЁН", "#C62828"
            self.status_dot.setObjectName("status_dot_disconnected")
            if hasattr(self, 'plugin_manager') and self.plugin_manager:
                self.plugin_manager.trigger_hook("on_disconnect")

        self.connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.top_connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.big_status.setText("● " + st)
        self.big_status.setStyleSheet(f"color: {clr}; font-size: 28px; font-weight: bold; background: transparent; padding: 0px;")
        self.status_text.setText(st)
        self.status_text.setStyleSheet(f"color: {clr}; font-size: 11px; letter-spacing: 1px; background: transparent;")

        if self.selected_config:
            self.active_label.setText(f"Конфиг: {self.selected_config['name']}")
        else:
            self.active_label.setText("Конфиг не выбран")

    def append_log(self, line):
        # 🔑 Безопасный вызов плагин-менеджера
        if hasattr(self, 'plugin_manager') and self.plugin_manager:
            self.plugin_manager.trigger_hook("on_log", line=line)
        try:
            low = line.lower()
            if "command" in low and "amneziawg" in low and "returned non-zero" in low:
                return
            self.log_view.append(line)
        except:
            pass
        low = line.lower()
        if "local ip" in low or "assigned local" in low:
            self.append_system_message(f"Найден локальный IP: {line}")
        if "handshake" in low:
            self.append_system_message(f"Handshake: {line}")

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