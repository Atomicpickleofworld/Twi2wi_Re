# ui/main_window.py
"""
Ядро главного окна: инициализация, сайдбар, роутинг страниц.
Вся бизнес-логика вынесена в контроллеры страниц:
  - ConnectController   (ui/pages/connect_page.py)
  - ConfigsController   (ui/pages/configs_page.py)
  - PingController      (ui/pages/ping_page.py)
  - PluginsController   (ui/pages/plugins_page.py)
"""
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, QTimer

from security.sandbox import SandboxManager, PluginLoadError
from ui.styles import STYLE
from ui.pages import (
    build_connect_page,
    build_configs_page,
    build_ping_page,
    build_sys_page,
    build_plugins_page,
)
from ui.pages.connect_page import ConnectController
from ui.pages.configs_page import ConfigsController
from ui.pages.ping_page import PingController
from ui.pages.plugins_page import PluginsController
from utils.version import __version__, __app_name__
from utils.i18n import tr, load_language_preference, set_language, get_available_languages


class VPNManager(QMainWindow):

    # ── Жизненный цикл ──────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()

        # ── Общее состояние (shared state) ──────────────────────────────────
        self.is_busy = False
        self.is_connected = False
        self.selected_config: dict | None = None
        self.configs: list[dict] = []
        self.plugins_data: list[dict] = []

        # ── Sandbox / плагины ───────────────────────────────────────────────
        self.sandbox_manager = SandboxManager(
            plugins_root=Path(__file__).resolve().parent.parent / "plugins",
            on_log=self.append_log,
            on_notify=self._show_plugin_notification,
        )
        self.sandbox_manager.load_all()

        # ── Язык ────────────────────────────────────────────────────────────
        saved_lang = load_language_preference()
        if saved_lang and saved_lang in get_available_languages():
            set_language(saved_lang)

        # ── Таймер коннекта ─────────────────────────────────────────────────
        self.connect_timeout_timer = QTimer(self)
        self.connect_timeout_timer.setSingleShot(True)
        self.connect_timeout_timer.timeout.connect(self._handle_connect_timeout)

        # ── Контроллеры страниц ─────────────────────────────────────────────
        self.configs_ctrl  = ConfigsController(self)
        self.connect_ctrl  = ConnectController(self)
        self.ping_ctrl     = PingController(self)
        self.plugins_ctrl  = PluginsController(self)

        # ── Инициализация ───────────────────────────────────────────────────
        self.configs_ctrl.load_configs()
        self.init_ui()
        self.ping_ctrl.setup()
        self._setup_tray()

    # ── Делегаты (чтобы страницы могли вызывать self.append_log и т.д.) ──

    def append_log(self, line: str):
        if hasattr(self, "sandbox_manager"):
            self.sandbox_manager.trigger_hook("on_log", line=line)

        low = line.lower()
        if "command" in low and "amneziawg" in low and "returned non-zero" in low:
            return

        try:
            if hasattr(self, "log_view") and self.log_view:
                self.log_view.append(line)
        except Exception:
            pass

        try:
            from datetime import datetime
            log_file = Path(__file__).resolve().parent.parent / "vpn_runtime.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {line}\n")
        except Exception:
            pass

        if "local ip" in low or "assigned local" in low:
            self.append_system_message(tr("log_found_ip", line=line))
        if "handshake" in low:
            self.append_system_message(tr("log_handshake", line=line))

    def append_system_message(self, msg: str):
        try:
            self.sys_view.append(msg)
        except Exception:
            pass

    def _show_plugin_notification(self, message: str):
        from PyQt6.QtWidgets import QMessageBox
        safe_msg = str(message)[:200]
        QMessageBox.information(self, tr("dialog_plugin_title"), safe_msg)

    # ── Делегаты контроллеров (публичный API для страниц) ───────────────────

    def toggle_connection(self):
        self.connect_ctrl.toggle_connection()

    def connect_vpn(self):
        self.connect_ctrl.connect_vpn()

    def disconnect_vpn(self):
        self.connect_ctrl.disconnect_vpn()

    def _handle_connect_timeout(self):
        self.connect_ctrl.handle_connect_timeout()

    def on_status_changed(self, connected: bool):
        self.connect_ctrl.on_status_changed(connected)

    def load_configs(self):
        self.configs_ctrl.load_configs()

    def save_configs(self):
        self.configs_ctrl.save_configs()

    def refresh_config_list(self):
        self.configs_ctrl.refresh_config_list()

    def refresh_quick_list(self):
        self.configs_ctrl.refresh_quick_list()

    def add_config_file(self):
        self.configs_ctrl.add_config_file()

    def add_config_url(self):
        self.configs_ctrl.add_config_url()

    def add_config_text(self):
        self.configs_ctrl.add_config_text()

    def delete_config(self):
        self.configs_ctrl.delete_config()

    def delete_config_by_obj(self, cfg: dict):
        self.configs_ctrl.delete_config_by_obj(cfg)

    def rename_config_by_obj(self, cfg: dict):
        self.configs_ctrl.rename_config_by_obj(cfg)

    def on_config_select(self, item):
        self.configs_ctrl.on_config_select(item)

    def on_quick_select(self, item):
        self.connect_ctrl.on_quick_select(item)

    def add_ping_from_input(self):
        self.ping_ctrl.add_ping_from_input()

    def on_ping_result(self, name: str, ms: int, loss: float, stats: dict):
        self.ping_ctrl.on_ping_result(name, ms, loss, stats)

    def render_plugins(self, filter_text=""):
        self.plugins_ctrl.render_plugins(filter_text)

    def filter_plugins(self, text):
        self.plugins_ctrl.filter_plugins(text)

    def view_full_description(self, plugin):
        self.plugins_ctrl.view_full_description(plugin)

    def show_plugin_menu(self, plugin):
        self.plugins_ctrl.show_plugin_menu(plugin)

    def delete_plugin(self, plugin):
        self.plugins_ctrl.delete_plugin(plugin)

    def toggle_plugin(self, plugin, state):
        self.plugins_ctrl.toggle_plugin(plugin, state)

    def show_import_menu(self):
        self.plugins_ctrl.show_import_menu()

    def import_plugin_file(self):
        self.plugins_ctrl.import_plugin_file()

    def import_plugin_git(self):
        self.plugins_ctrl.import_plugin_git()

    def create_plugin_card(self, plugin):
        return self.plugins_ctrl.create_plugin_card(plugin)

    def apply_plugin_style(self, card, state):
        self.plugins_ctrl.apply_plugin_style(card, state)

    def eventFilter(self, obj, event):
        return self.plugins_ctrl.event_filter(obj, event)

    # ── UI: каркас + сайдбар ────────────────────────────────────────────────

    def init_ui(self):
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setMinimumSize(950, 620)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        main.addWidget(self.pages)
        self.pages.addWidget(build_connect_page(self))   # 0
        self.pages.addWidget(build_configs_page(self))   # 1
        self.pages.addWidget(build_ping_page(self))      # 2
        self.pages.addWidget(build_sys_page(self))       # 3
        self.pages.addWidget(build_plugins_page(self))   # 4

        self.switch_page(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        logo = QLabel("◈ Twi2wi_Re")
        logo.setObjectName("logo_label")
        sl.addWidget(logo)

        ver = QLabel(f"v{__version__} Re Edition")
        ver.setObjectName("version_label")
        sl.addWidget(ver)

        # Статус
        status_frame = QFrame()
        sf = QHBoxLayout(status_frame)
        sf.setContentsMargins(16, 8, 16, 8)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(0, 0)
        self.status_dot.hide()
        self.status_text = QLabel(tr("status_disconnected"))
        self.status_text.setStyleSheet("color: #C62828; font-size: 11px;")
        sf.addWidget(self.status_text)
        sf.addStretch()
        sl.addWidget(status_frame)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#D8C8E8; max-height:1px;")
        sl.addWidget(sep)
        sl.addSpacing(8)

        # Навигация
        self.nav_btns = []
        nav_items = [
            (tr("nav_connect"),  0),
            (tr("nav_configs"),  1),
            (tr("nav_ping"),     2),
            (tr("nav_system"),   3),
            (tr("nav_plugins"),  4),
        ]
        for name, page_idx in nav_items:
            b = QPushButton(name)
            b.setObjectName("nav_btn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, p=page_idx: self.switch_page(p))
            sl.addWidget(b)
            self.nav_btns.append(b)

        sl.addStretch()

        self.connect_btn = QPushButton("")
        self.connect_btn.setObjectName("connect_btn")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self.toggle_connection)
        sl.addSpacing(16)
        sl.addSpacing(16)

        return sidebar

    def switch_page(self, idx: int):
        self.pages.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)

    # ── Трей ────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("Twi2wi_Re")

        tray_menu = QMenu()
        act_show = tray_menu.addAction(tr("tray_show_window"))
        act_show.triggered.connect(self.show)
        act_show.triggered.connect(self.activateWindow)
        tray_menu.addSeparator()
        act_quit = tray_menu.addAction(tr("tray_menu_exit"))
        act_quit.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_clicked)
        self.tray_icon.show()

    def _tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    # ── Жизненный цикл ──────────────────────────────────────────────────────

    def closeEvent(self, event):
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
            self.tray_icon.showMessage(
                "Twi2wi_Re",
                tr("tray_minimized_msg"),
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self._do_full_cleanup()
            event.accept()

    def _do_full_cleanup(self):
        self.sandbox_manager.unload_all()
        self.connect_timeout_timer.stop()
        self.connect_ctrl.cleanup()
        self.ping_ctrl.cleanup()

    def quit_app(self):
        self.disconnect_vpn()
        self._do_full_cleanup()
        QApplication.quit()