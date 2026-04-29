# ui/main_window.py
"""
Ядро главного окна: инициализация, сайдбар, роутинг страниц
и вся бизнес-логика (VPN, пинг, конфиги).
UI каждой страницы живёт в ui/pages/*.
"""

import json
import time
import logging
import urllib.parse as _up
from security.sandbox import SandboxManager, PluginLoadError
from security.permissions import PluginPermissions
from security import *
from pathlib import Path

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QInputDialog, QMessageBox, QFrame, QStackedWidget,
    QTextEdit, QScrollArea, QLineEdit, QSizePolicy, QMenu, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QEvent

from ui.styles import STYLE
from ui.widgets import ConfigCard
from ui.pages import (
    build_connect_page,
    build_configs_page,
    build_ping_page,
    build_sys_page,
    build_plugins_page,
    # методы плагинов
    create_plugin_card,
    apply_plugin_style,
    render_plugins,
    plugin_event_filter,
    filter_plugins,
    view_full_description,
    show_plugin_menu,
    delete_plugin,
    toggle_plugin,
    show_import_menu,
    import_plugin_file,
    import_plugin_git,
)
from core.ping_worker import PingWorker
from core.vpn_worker import SingBoxWorker
from utils.config import CONF_DIR, CONFIGS_FILE, ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF
from utils.helpers import detect_type, get_system_info
from utils.url_parser import url_to_singbox_json, SUPPORTED_SCHEMES, parse_proxy_url
from utils.version import __version__, __app_name__


class VPNManager(QMainWindow):

    # ── Жизненный цикл ──────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.configs: list[dict] = []
        self.selected_config: dict | None = None
        self.singbox_worker: SingBoxWorker | None = None
        self.ping_worker: PingWorker | None = None
        self.is_connected = False
        self.ping_cards: dict = {}
        self.ping_hosts: dict = {}
        self.active_config_path: Path | None = None

        self.sandbox_manager = SandboxManager(
                    plugins_root=Path(__file__).resolve().parent.parent / "plugins",
                    on_log=self.append_log,
                    on_notify=self._show_plugin_notification,
                )
        self.sandbox_manager.load_all()


        self.connect_timeout_timer = QTimer(self)
        self.connect_timeout_timer.setSingleShot(True)
        self.connect_timeout_timer.timeout.connect(self._handle_connect_timeout)

        self.load_configs()
        self.init_ui()
        self.start_ping_monitor()


    def closeEvent(self, event):
        self.sandbox_manager.unload_all()
        print("Закрытие приложения...")
        self.connect_timeout_timer.stop()
        try:
            if (hasattr(self, "singbox_worker") and self.singbox_worker
                    and self.singbox_worker.isRunning()):
                self.singbox_worker.stop()
                self.singbox_worker.quit()
                if not self.singbox_worker.wait(3000):
                    self.singbox_worker.terminate()
        except Exception as e:
            print("Ошибка остановки:", e)
        if hasattr(self, "ping_worker") and self.ping_worker:
            self.ping_worker.stop()
            self.ping_worker.wait(1000)
        event.accept()

    # ── Конфиги ─────────────────────────────────────────────────────────────

    def load_configs(self):
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
        for c in self.configs:
            c.setdefault("favorite", False)

    def save_configs(self):
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
        self.status_text = QLabel("ОТКЛЮЧЁН")
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
            ("ПОДКЛЮЧЕНИЕ", 0),
            ("КОНФИГИ",     1),
            ("ПИНГ",        2),
            ("СИСТЕМА",     3),
            ("ПЛАГИНЫ",     4),
        ]
        for name, page_idx in nav_items:
            b = QPushButton(name)
            b.setObjectName("nav_btn")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, p=page_idx: self.switch_page(p))
            sl.addWidget(b)
            self.nav_btns.append(b)

        sl.addStretch()

        # self.connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ")
        # self.connect_btn.setObjectName("connect_btn")
        # self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # self.connect_btn.clicked.connect(self.toggle_connection)
        # sl.addSpacing(16)
        # sl.addWidget(self.connect_btn)
        # sl.addSpacing(16)

        #nah ts bullsh*t

        return sidebar

    def switch_page(self, idx: int):
        self.pages.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)

    # ── Пинг ────────────────────────────────────────────────────────────────

    def start_ping_monitor(self):
        hosts = list(self.ping_hosts.items())
        self.ping_worker = PingWorker(hosts)
        self.ping_worker.result.connect(self.on_ping_result)
        self.ping_worker.start()

    def on_ping_result(self, name: str, ms: int, loss: float):
        if name not in self.ping_cards:
            return
        lbl_v, lbl_l = self.ping_cards[name]
        lbl_v.setText(f"{ms} ms" if ms >= 0 else "timeout")
        lbl_l.setText(f"Потери: {loss:.0f}%")
        if ms == -1:
            lbl_v.setStyleSheet("color: #000000;")
        elif ms < 100:
            lbl_v.setStyleSheet("color: #2E7D32;")
        elif ms <= 200:
            lbl_v.setStyleSheet("color: #F57C00;")
        else:
            lbl_v.setStyleSheet("color: #C62828;")
        self.sandbox_manager.trigger_hook("on_ping_result", name=name, ms=ms, loss=loss)

    def _add_ping_card(self, name: str, host: str):
        if name in self.ping_cards:
            return
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setSpacing(4)
        lbl_n = QLabel(name);  lbl_n.setObjectName("card_title")
        lbl_h = QLabel(host);  lbl_h.setObjectName("card_host")
        lbl_v = QLabel("...");  lbl_v.setObjectName("card_value_none")
        lbl_l = QLabel("Потери: —")
        lbl_l.setStyleSheet("color: #7A5C9A; font-size: 11px;")
        for lbl in (lbl_n, lbl_h, lbl_v, lbl_l):
            cl.addWidget(lbl)
        col = self.row_idx % 2
        row = self.row_idx // 2
        self.ping_layout.addWidget(card, row, col)
        self.row_idx += 1
        self.ping_cards[name] = (lbl_v, lbl_l)
        self.ping_hosts[name] = host

    def add_ping_from_input(self):
        txt = self.ping_input.text().strip()
        if not txt:
            return
        host = txt.split(":")[0]
        name = host.upper() if "." not in host else host.split(".")[0].upper()
        if name not in self.ping_cards:
            self._add_ping_card(name, host)
            if self.ping_worker:
                self.ping_worker.add_host(name, host)
        self.ping_input.clear()

    # ── VPN-подключение ─────────────────────────────────────────────────────

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect_vpn()
        else:
            self.connect_vpn()

    def connect_vpn(self):
        self.connect_timeout_timer.stop()
        if self.singbox_worker and self.singbox_worker.isRunning():
            self.disconnect_vpn()
            time.sleep(0.3)

        if not self.selected_config:
            QMessageBox.warning(self, "Нет конфига", "Сначала выбери конфиг!")
            return

        cfg = self.selected_config
        c = cfg.get("content", "")
        config_type = cfg.get("type", "singbox")

        self.big_status.setText("● ОЖИДАНИЕ...")
        self.big_status.setStyleSheet(
            "color: #FFC107; font-size: 28px; font-weight: bold; "
            "background: transparent; padding: 0px;"
        )
        self.status_dot.setObjectName("status_dot_waiting")
        self.status_text.setText("ОЖИДАНИЕ...")
        self.status_text.setStyleSheet(
            "color: #FFC107; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )

        self.active_config_path = (
            ACTIVE_CONFIG_CONF
            if config_type.lower() in ("amneziawg", "wireguard")
            else ACTIVE_CONFIG_JSON
        )

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
        for f in (ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF):
            try:
                if f.exists():
                    f.unlink()
            except Exception:
                pass
        self.on_status_changed(False)

    def on_status_changed(self, connected: bool):
        self.connect_timeout_timer.stop()
        self.is_connected = connected

        if connected:
            st, clr = "ПОДКЛЮЧЁН", "#4CAF50"
            self.status_dot.setObjectName("status_dot_connected")
            if hasattr(self, "plugin_manager") and self.plugin_manager:
                self.sandbox_manager.trigger_hook("on_connect", config=self.selected_config)
        else:
            st, clr = "ОТКЛЮЧЁН", "#C62828"
            self.status_dot.setObjectName("status_dot_disconnected")
            if hasattr(self, "plugin_manager") and self.plugin_manager:
                self.sandbox_manager.trigger_hook("on_disconnect")

        self.connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.top_connect_btn.setText("■  ОТКЛЮЧИТЬ" if connected else "▶  ПОДКЛЮЧИТЬ")
        self.big_status.setText("● " + st)
        self.big_status.setStyleSheet(
            f"color: {clr}; font-size: 28px; font-weight: bold; "
            "background: transparent; padding: 0px;"
        )
        self.status_text.setText(st)
        self.status_text.setStyleSheet(
            f"color: {clr}; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )
        self.active_label.setText(
            f"Конфиг: {self.selected_config['name']}"
            if self.selected_config else "Конфиг не выбран"
        )

    # ── Логи ────────────────────────────────────────────────────────────────

    def append_log(self, line: str):
        if hasattr(self, "plugin_manager") and self.plugin_manager:
            self.sandbox_manager.trigger_hook("on_log", line=line)
        try:
            low = line.lower()
            if "command" in low and "amneziawg" in low and "returned non-zero" in low:
                return
            self.log_view.append(line)
        except Exception:
            pass
        low = line.lower()
        if "local ip" in low or "assigned local" in low:
            self.append_system_message(f"Найден локальный IP: {line}")
        if "handshake" in low:
            self.append_system_message(f"Handshake: {line}")

    def append_system_message(self, msg: str):
        try:
            self.sys_view.append(msg)
        except Exception:
            pass

    # ── Управление списками конфигов ────────────────────────────────────────

    def refresh_quick_list(self):
        self.fav_list.clear()
        self.quick_list.clear()
        favs   = [c for c in self.configs if c.get("favorite")]
        others = [c for c in self.configs if not c.get("favorite")]
        if favs:
            self.fav_list.show();  self.fav_title.show()
        else:
            self.fav_list.hide();  self.fav_title.hide()
        if not self.configs:
            self.quick_list.addItem("Нет конфигов")
            return
        for c in favs:   self._add_card_to_list(self.fav_list, c)
        for c in others: self._add_card_to_list(self.quick_list, c)

    def _add_card_to_list(self, lst: QListWidget, cfg: dict):
        item = QListWidgetItem()
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

    def on_config_select(self, item: QListWidgetItem):
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.selected_config = cfg
            preview_text = cfg.get("content", "")
            self.preview.setPlainText(
                preview_text[:2000] + ("..." if len(preview_text) > 2000 else "")
            )
            self._update_right_panel()

    def on_quick_select(self, item: QListWidgetItem):
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.selected_config = cfg
            self._update_right_panel()

    def _update_right_panel(self):
        if not self.selected_config:
            return
        self.info_name.setText(f"Имя: {self.selected_config.get('name', '—')}")
        self.info_type.setText(f"Тип: {self.selected_config.get('type', 'singbox').upper()}")
        self.info_preview.setPlainText(self.selected_config.get("content", ""))
        self.active_label.setText(f"Конфиг: {self.selected_config['name']}")

    # ── Добавление / удаление / переименование конфигов ─────────────────────

    def add_config_file(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Открыть конфиг", "",
            "JSON/Conf (*.json *.conf *.yaml *.yml);;Все файлы (*)"
        )
        if not p:
            return
        c = Path(p).read_text(encoding="utf-8", errors="replace")
        new_name = Path(p).name
        new_path = CONF_DIR / new_name
        new_path.write_text(c, encoding="utf-8")
        self.configs.append({"name": new_name, "type": detect_type(c), "content": c, "path": str(new_path)})
        self.save_configs()
        self.refresh_config_list()
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

        if scheme in ("amneziawg", "wireguard") or (
            "[Interface]" in url and ("Jc" in url or "PrivateKey" in url)
        ):
            name, _ = QInputDialog.getText(self, "Название", "Название конфига:")
            safe_name = (name or "awg_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(url, encoding="utf-8")
            self.configs.append({"name": name or safe_name, "type": "amneziawg",
                                  "content": url, "path": str(new_path)})
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "Добавлено", "✓ AWG конфиг сохранён"))
            return

        try:
            config_dict, proto = parse_proxy_url(url)
            content = json.dumps(config_dict, ensure_ascii=False, indent=2)
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка парсинга", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разобрать ссылку:\n{e}")
            return

        auto_name = _up.unquote(url.split("#")[1]) if "#" in url else ""
        name, _ = QInputDialog.getText(self, "Название", "Название конфига:", text=auto_name)
        final_name = name.strip() or auto_name or url[:30]
        safe_name = final_name.replace(" ", "_").replace("/", "_") + ".json"
        new_path = CONF_DIR / safe_name
        new_path.write_text(content, encoding="utf-8")
        self.configs.append({"name": final_name, "type": proto, "content": content, "path": str(new_path)})
        self.save_configs()

        try:
            self.refresh_config_list()
            self.refresh_quick_list()
        except Exception as e:
            logging.error(f"Ошибка обновления UI: {e}")
            return

        QTimer.singleShot(0, lambda: QMessageBox.information(
            self, "Добавлено",
            f"✓ Конфиг «{final_name}» добавлен\n"
            f"Протокол: {proto.upper()}\nСохранён в папку configs/"
        ))

    def add_config_text(self):
        t, ok = QInputDialog.getMultiLineText(self, "Вставить конфиг", "JSON или raw-конфиг:")
        if ok and t.strip():
            name, _ = QInputDialog.getText(self, "Название", "Название:")
            safe_name = (name or "text_config").replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(t, encoding="utf-8")
            self.configs.append({"name": name or "Новый конфиг", "type": detect_type(t),
                                  "content": t, "path": str(new_path)})
            self.save_configs()
            self.refresh_config_list()
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
                except Exception:
                    pass
            self.configs.pop(idx)
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
            if self.selected_config == cfg:
                self.selected_config = None

    def delete_config_by_obj(self, cfg: dict):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                if QMessageBox.question(
                    self, "Удалить", f"Удалить «{c.get('name')}»?"
                ) == QMessageBox.StandardButton.Yes:
                    cfg_path = c.get("path", "")
                    if cfg_path and Path(cfg_path).exists():
                        try:
                            Path(cfg_path).unlink()
                        except Exception:
                            pass
                    self.configs.pop(i)
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                return

    def rename_config_by_obj(self, cfg: dict):
        for i, c in enumerate(self.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                new_name, ok = QInputDialog.getText(
                    self, "Переименовать", "Новое имя:", text=c.get("name", "")
                )
                if ok and new_name.strip():
                    self.configs[i]["name"] = new_name.strip()
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                    if self.selected_config == c:
                        self.selected_config = self.configs[i]
                    self.active_label.setText(f"Конфиг: {new_name}")
                return

    # ── Плагины (делегируем в ui/pages/plugins_page.py) ─────────────────────

    def _show_plugin_notification(self, message: str):
        """Показывает уведомление от плагина (только текст, без HTML)."""
        from PyQt6.QtWidgets import QMessageBox
        safe_msg = str(message)[:200]
        QMessageBox.information(self, "Плагин", safe_msg)

    def create_plugin_card(self, plugin):
        return create_plugin_card(self, plugin)

    def apply_plugin_style(self, card, state):
        apply_plugin_style(self, card, state)

    def render_plugins(self, filter_text=""):
        # Синхронизируем plugins_data из sandbox_manager перед отрисовкой
        self.plugins_data = [
            {
                "id": p["id"],
                "name": p["name"],
                "desc": f"Права: {', '.join(p['permissions'])}",
                "ver": self.sandbox_manager._sandboxes[p["id"]].manifest.get("version", "?"),
                "enabled": p["running"],
                "icon": "🧩",
            }
            for p in self.sandbox_manager.list_plugins()
        ]
        render_plugins(self, filter_text)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(obj, "plugin_ref") and obj.objectName() == "plugin_card":
                plugin = obj.plugin_ref
                plugin_id = plugin["id"]

                if plugin["enabled"]:
                    # Выключаем — останавливаем subprocess
                    self.sandbox_manager.unload(plugin_id)
                    plugin["enabled"] = False
                else:
                    # Включаем — запускаем subprocess заново
                    plugins_root = Path(__file__).resolve().parent.parent / "plugins"
                    plugin_dir = plugins_root / plugin_id
                    if plugin_dir.exists():
                        try:
                            loaded_id = self.sandbox_manager._load_one(plugin_dir)
                            plugin["enabled"] = bool(loaded_id)
                        except Exception as e:
                            self.append_log(f"[!] Ошибка запуска плагина: {e}")
                            plugin["enabled"] = False

                # Обновляем карточку
                state = "enabled" if plugin["enabled"] else "disabled"
                obj.setProperty("state", state)
                obj.style().unpolish(obj)
                obj.style().polish(obj)

                if hasattr(obj, "status_label"):
                    if plugin["enabled"]:
                        obj.status_label.setText("ВКЛ")
                        obj.status_label.setStyleSheet(
                            "color: #4CAF50; font-size: 11px; font-weight: bold; min-width: 45px;"
                        )
                    else:
                        obj.status_label.setText("ВЫКЛ")
                        obj.status_label.setStyleSheet(
                            "color: #9b2d30; font-size: 11px; font-weight: bold; min-width: 45px;"
                        )

                self.append_log(
                    f"[i] Плагин «{plugin['name']}» "
                    f"{'включён' if plugin['enabled'] else 'отключён'}"
                )
                return True

        return super().eventFilter(obj, event)

    def filter_plugins(self, text):
        filter_plugins(self, text)

    def view_full_description(self, plugin):
        view_full_description(self, plugin)

    def show_plugin_menu(self, plugin):
        show_plugin_menu(self, plugin)

    def delete_plugin(self, plugin):
        delete_plugin(self, plugin)

    def toggle_plugin(self, plugin, state):
        toggle_plugin(self, plugin, state)

    def show_import_menu(self):
        show_import_menu(self)

        def import_plugin_file(self):
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getOpenFileName(
                self, "Выберите архив плагина", "", "ZIP архивы (*.zip)"
            )
            if not path:
                return
            try:
                plugin_id = self.sandbox_manager.install_from_zip(Path(path))
                if plugin_id:
                    self.append_log(f"[+] Плагин '{plugin_id}' установлен и запущен")
                    self.render_plugins()   # обновить UI
                    QMessageBox.information(self, "Успех", f"Плагин '{plugin_id}' загружен!")
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось загрузить плагин.")
            except PluginLoadError as e:
                QMessageBox.critical(self, "Ошибка плагина", str(e))

    def import_plugin_git(self):
        import_plugin_git(self)