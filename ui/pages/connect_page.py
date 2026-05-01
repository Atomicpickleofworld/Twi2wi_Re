# ui/pages/connect_page.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QFrame,
    QSizePolicy, QMessageBox,
)

from core.vpn_worker import SingBoxWorker
from utils.config import ACTIVE_CONFIG_JSON, ACTIVE_CONFIG_CONF
from utils.helpers import extract_config_info
from utils.i18n import tr
from ui.widgets import ConfigCard

if TYPE_CHECKING:
    from ui.main_window import VPNManager


class ConnectController:
    """Управляет VPN-соединением, избранным и правой панелью."""

    def __init__(self, win: "VPNManager"):
        self.win = win
        self.singbox_worker: SingBoxWorker | None = None


    # ── VPN toggle ──────────────────────────────────────────────────────────

    def toggle_connection(self):
        if self.win.is_busy:
            return
        if self.win.is_connected:
            self.disconnect_vpn()
        else:
            self.connect_vpn()

    def connect_vpn(self):
        win = self.win
        win.is_busy = True
        self._set_connect_buttons_enabled(False)
        win.connect_timeout_timer.stop()

        if self.singbox_worker and self.singbox_worker.isRunning():
            self.singbox_worker.stop()
            self.singbox_worker = None
            QTimer.singleShot(300, self._continue_connection)
        else:
            self._continue_connection()

    def _continue_connection(self):
        win = self.win
        if not win.selected_config:
            self._reset_busy_state()
            QMessageBox.warning(win, tr("dialog_no_config_title"), tr("dialog_no_config_msg"))
            return

        cfg = win.selected_config
        c = cfg.get("content", "")
        config_type = cfg.get("type", "singbox")

        win.big_status.setText(f"● {tr('status_waiting')}")
        win.big_status.setStyleSheet(
            "color: #FFC107; font-size: 28px; font-weight: bold; "
            "background: transparent; padding: 0px;"
        )
        win.status_dot.setObjectName("status_dot_waiting")
        win.status_text.setText(tr("status_waiting"))
        win.status_text.setStyleSheet(
            "color: #FFC107; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )

        active_config_path = (
            ACTIVE_CONFIG_CONF
            if config_type.lower() in ("amneziawg", "wireguard")
            else ACTIVE_CONFIG_JSON
        )
        win.active_config_path = active_config_path

        try:
            active_config_path.write_text(c, encoding="utf-8")
        except Exception as e:
            logging.error(f"Ошибка записи: {e}")
            self._reset_busy_state()
            QMessageBox.critical(win, tr("dialog_error_title"), tr("dialog_save_error", e=e))
            return

        win.append_log(tr("log_config_active", name=active_config_path.name))
        win.append_log(tr("log_config_type", type=config_type))

        self.singbox_worker = SingBoxWorker(str(active_config_path), config_type)
        self.singbox_worker.log_line.connect(win.append_log)
        self.singbox_worker.status_changed.connect(win.on_status_changed)
        self.singbox_worker.start()
        win.connect_timeout_timer.start(10000)

    def handle_connect_timeout(self):
        if not self.win.is_connected:
            self.win.append_log(tr("log_timeout"))
            self.disconnect_vpn()
            QMessageBox.warning(self.win, tr("dialog_timeout_title"), tr("dialog_timeout_msg"))

    def disconnect_vpn(self):
        win = self.win
        win.connect_timeout_timer.stop()
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
        win = self.win
        win.connect_timeout_timer.stop()
        self._reset_busy_state()
        win.is_connected = connected

        if connected:
            st, clr = tr("status_connected"), "#4CAF50"
            win.status_dot.setObjectName("status_dot_connected")
            win.sandbox_manager.trigger_hook("on_connect", config=win.selected_config)
        else:
            st, clr = tr("status_disconnected"), "#C62828"
            win.status_dot.setObjectName("status_dot_disconnected")
            win.sandbox_manager.trigger_hook("on_disconnect")

        if hasattr(win, "connect_btn"):
            win.connect_btn.setText(
                f"■ {tr('btn_disconnect')}" if connected else f"▶ {tr('btn_connect')}"
            )
        if hasattr(win, "top_connect_btn"):
            win.top_connect_btn.setText(
                f"■ {tr('btn_disconnect')}" if connected else f"▶ {tr('btn_connect')}"
            )

        win.big_status.setText(f"● {st}")
        win.big_status.setStyleSheet(
            f"color: {clr}; font-size: 28px; font-weight: bold; "
            "background: transparent; padding: 0px;"
        )
        win.status_text.setText(st)
        win.status_text.setStyleSheet(
            f"color: {clr}; font-size: 11px; letter-spacing: 1px; background: transparent;"
        )
        if win.selected_config:
            win.active_label.setText(tr("status_config_label", name=win.selected_config["name"]))
        else:
            win.active_label.setText(tr("status_no_config"))

    # ── Избранное и порядок ────────────────────────────────────────────────

    def toggle_favorite_config(self, cfg: dict):
        """Переключает звезду, обновляет порядок и перерисовывает списки."""
        current = cfg.get("favorite", False)
        cfg["favorite"] = not current

        # Если добавляем в избранное, даём ему максимальный fav_order
        if cfg["favorite"]:
            max_order = max((c.get("fav_order", 0) for c in self.win.configs if c.get("favorite")), default=0)
            cfg["fav_order"] = max_order + 1
        else:
            cfg["fav_order"] = 0

        self.win.save_configs()
        # Обновить внешний вид звезды в карточке (перерисовываем списки)
        self.refresh_connect_lists()
        self.win.refresh_config_list()   # чтобы и на странице "КОНФИГИ" звезда тоже обновилась

    def refresh_connect_lists(self):
        win = self.win
        if not hasattr(win, "fav_list"):
            return

        favs = [c for c in win.configs if c.get("favorite")]
        favs.sort(key=lambda c: c.get("fav_order", 0))
        others = [c for c in win.configs if not c.get("favorite")]

        win.fav_list.clear()
        win.quick_list.clear()

        for cfg in favs:
            self._add_card_to_list(win.fav_list, cfg, show_fav_star=True, show_order_arrows=True)
        for cfg in others:
            self._add_card_to_list(win.quick_list, cfg, show_fav_star=True, show_order_arrows=False)

        win.fav_list.setVisible(len(favs) > 0)
        win.fav_title.setVisible(len(favs) > 0)
        self._adjust_fav_list_height()

        # Принудительно пересчитать размеры
        win.fav_list.updateGeometry()
        win.quick_list.updateGeometry()

    def _add_card_to_list(self, lst: QListWidget, cfg: dict, show_fav_star: bool, show_order_arrows: bool, fav_order=0):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, cfg)
        card = ConfigCard(cfg, parent=lst, compact=False,
                          show_fav_star=show_fav_star,
                          show_order_arrows=show_order_arrows,
                          fav_order=fav_order)
        item.setSizeHint(card.sizeHint())
        lst.addItem(item)
        lst.setItemWidget(item, card)

    def move_favorite_up(self, cfg: dict):
        """Переместить избранный конфиг вверх по порядку."""
        if not cfg.get("favorite"):
            return
        favs = [c for c in self.win.configs if c.get("favorite")]
        favs.sort(key=lambda c: c.get("fav_order", 0))
        idx = None
        for i, c in enumerate(favs):
            if c is cfg or c.get("name") == cfg.get("name"):
                idx = i
                break
        if idx is None or idx == 0:
            return
        # Меняем fav_order местами
        favs[idx]["fav_order"], favs[idx-1]["fav_order"] = favs[idx-1].get("fav_order", idx), favs[idx].get("fav_order", idx+1)
        self.win.save_configs()
        self.refresh_connect_lists()

    def move_favorite_down(self, cfg: dict):
        if not cfg.get("favorite"):
            return
        favs = [c for c in self.win.configs if c.get("favorite")]
        favs.sort(key=lambda c: c.get("fav_order", 0))
        idx = None
        for i, c in enumerate(favs):
            if c is cfg or c.get("name") == cfg.get("name"):
                idx = i
                break
        if idx is None or idx == len(favs)-1:
            return
        favs[idx]["fav_order"], favs[idx+1]["fav_order"] = favs[idx+1].get("fav_order", idx+2), favs[idx].get("fav_order", idx+1)
        self.win.save_configs()
        self.refresh_connect_lists()

    # ── Выбор конфига и отображение информации ──────────────────────────────

    def on_quick_select(self, item: QListWidgetItem):
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.win.selected_config = cfg
            self._update_right_panel()
            # # Запрос статуса (пинг) – он будет обновляться автоматически через PingController
            # self.win.ping_ctrl.request_ping_for_config(cfg)


    def _update_right_panel(self):
        win = self.win
        if not win.selected_config:
            return

        cfg = win.selected_config
        name = cfg.get("name", "—")
        ctype = cfg.get("type", "singbox").upper()
        info = extract_config_info(cfg)
        # print("📦 extract_config_info =", info)

        host = info.get("host") or "—"
        port = info.get("port")
        if port and host != "—":
            server_str = f"{host}:{port}"
        elif host != "—":
            server_str = host
        else:
            server_str = "—"

        method = info.get("method") or "—"

        win.info_name.setText(tr("connect_page_info_name", name=name))
        win.info_type.setText(tr("connect_page_info_type", type=ctype))
        win.info_server.setText(server_str)

        win.info_method.setText(method)

        # Статус и пинг будут обновляться через update_status_from_ping
        # win.info_status.setText(tr("config_info_status_offline"))
        # win.info_ping.setText("—")

        # Сохраняем хост для пинга
        # win.current_ping_host = info.get("host") if info.get("host") else None

    def update_status_from_ping(self, ms: int, loss: float):
        """Вызывается из PingController при поступлении результата пинга для выбранного конфига."""
        win = self.win
        if not win.selected_config:
            return
        if ms < 0:
            win.info_status.setText(tr("config_info_status_offline"))
            win.info_ping.setText(tr("config_info_ping", ms=tr("ping_unknown")))
        else:
            win.info_status.setText(tr("config_info_status_online"))
            win.info_ping.setText(tr("config_info_ping", ms=ms))

    def _adjust_fav_list_height(self):
        """Подгоняет высоту fav_list под количество карточек."""
        win = self.win
        if not hasattr(win, "fav_list"):
            return
        total = 0
        for i in range(win.fav_list.count()):
            item = win.fav_list.item(i)
            widget = win.fav_list.itemWidget(item)
            if widget:
                total += widget.sizeHint().height()
            else:
                total += 40  # запас
        # Отступы
        margins = win.fav_list.contentsMargins()
        total += margins.top() + margins.bottom() + 10
        win.fav_list.setFixedHeight(max(total, 50))  # минимум 50px

    # ── Вспомогательные ─────────────────────────────────────────────────────

    def _set_connect_buttons_enabled(self, enabled: bool):
        win = self.win
        if hasattr(win, "top_connect_btn"):
            win.top_connect_btn.setEnabled(enabled)
        if hasattr(win, "connect_btn"):
            win.connect_btn.setEnabled(enabled)

    def _reset_busy_state(self):
        self.win.is_busy = False
        self._set_connect_buttons_enabled(True)

    def cleanup(self):
        if self.singbox_worker and self.singbox_worker.isRunning():
            self.singbox_worker.stop()
            self.singbox_worker.quit()
            if not self.singbox_worker.wait(2000):
                self.singbox_worker.terminate()


# ── UI-фабрика ──────────────────────────────────────────────────────────────

def build_connect_page(win: "VPNManager") -> QWidget:
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(12)

    # Кнопка подключения сверху
    top_row = QFrame()
    top_row_layout = QHBoxLayout(top_row)
    top_row_layout.setContentsMargins(0, 0, 0, 0)
    win.top_connect_btn = QPushButton(tr("btn_connect"))
    win.top_connect_btn.setObjectName("connect_btn")
    win.top_connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win.top_connect_btn.clicked.connect(win.toggle_connection)
    top_row_layout.addStretch()
    top_row_layout.addWidget(win.top_connect_btn)
    l.addWidget(top_row)

    # Карточка статуса
    t = QLabel(tr("connect_page_title"))
    t.setObjectName("section_title")
    l.addWidget(t)

    card = QFrame()
    card.setObjectName("card")
    cl = QVBoxLayout(card)
    win.big_status = QLabel(f"●  {tr('status_disconnected')}")
    win.big_status.setStyleSheet("color: #C62828; font-size: 28px; font-weight: bold; background: transparent; padding: 0px;")
    win.active_label = QLabel(tr("status_no_config"))
    win.active_label.setStyleSheet("color: #7A5C9A; font-size: 12px; background: transparent; padding: 0px;")
    cl.addWidget(win.big_status)
    cl.addWidget(win.active_label)
    l.addWidget(card)

    # Сплит: левая колонка (списки) + правая панель (инфо)
    split_frame = QFrame()
    split_layout = QHBoxLayout(split_frame)
    split_layout.setContentsMargins(0, 0, 0, 0)
    split_layout.setSpacing(16)

    # Левая колонка
    left_col = QVBoxLayout()
    win.fav_title = QLabel(tr("connect_page_fav_title"))
    win.fav_title.setObjectName("fav_section")
    left_col.addWidget(win.fav_title)

    win.fav_list = QListWidget()
    win.fav_list.setObjectName("config_list")
    win.fav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    win.fav_list.itemClicked.connect(win.on_quick_select)
    win.fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    left_col.addWidget(win.fav_list)

    all_title = QLabel(tr("connect_page_all_title"))
    all_title.setObjectName("section_title")
    left_col.addWidget(all_title)

    win.quick_list = QListWidget()
    win.quick_list.setObjectName("config_list")
    win.quick_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    win.quick_list.itemClicked.connect(win.on_quick_select)
    win.quick_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    left_col.addWidget(win.quick_list, 1)  # Растягивается

    split_layout.addLayout(left_col, 1)

    # Правая панель (информация)
    win.info_panel = QWidget()
    info_layout = QVBoxLayout(win.info_panel)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(10)

    info_title = QLabel(tr("connect_page_info_title"))
    info_title.setObjectName("section_title")
    info_layout.addWidget(info_title)

    win.info_name = QLabel(tr("connect_page_info_name", name="—"))
    win.info_name.setObjectName("card_title")
    info_layout.addWidget(win.info_name)

    win.info_type = QLabel(tr("connect_page_info_type", type="—"))
    win.info_type.setObjectName("card_host")
    info_layout.addWidget(win.info_type)

    win.info_server = QLabel("—")
    win.info_server.setObjectName("card_host")
    info_layout.addWidget(win.info_server)

    win.info_method = QLabel("—")
    win.info_method.setObjectName("card_host")
    info_layout.addWidget(win.info_method)

    # win.info_status = QLabel(tr("config_info_status_offline"))
    # win.info_status.setObjectName("card_host")
    # info_layout.addWidget(win.info_status)

    # win.info_ping = QLabel("—")
    # win.info_ping.setObjectName("card_host")
    # info_layout.addWidget(win.info_ping)

    info_layout.addStretch()
    split_layout.addWidget(win.info_panel, 1)
    l.addWidget(split_frame, 1)

    win.refresh_connect_lists()
    return w