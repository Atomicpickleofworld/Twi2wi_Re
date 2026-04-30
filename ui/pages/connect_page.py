# ui/pages/connect_page.py
"""
ConnectController — вся логика подключения/отключения VPN.
build_connect_page() — фабрика UI-виджета страницы (без изменений).
"""
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
from utils.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import VPNManager


class ConnectController:
    """Управляет VPN-соединением и правой панелью страницы ПОДКЛЮЧЕНИЕ."""

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

    # ── Выбор конфига на странице ПОДКЛЮЧЕНИЕ ───────────────────────────────

    def on_quick_select(self, item: QListWidgetItem):
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            self.win.selected_config = cfg
            self._update_right_panel()

    def _update_right_panel(self):
        win = self.win
        if not win.selected_config:
            return
        win.info_name.setText(
            tr("connect_page_info_name", name=win.selected_config.get("name", "—"))
        )
        win.info_type.setText(
            tr("connect_page_info_type", type=win.selected_config.get("type", "singbox").upper())
        )
        win.info_preview.setPlainText(win.selected_config.get("content", ""))
        win.active_label.setText(
            tr("status_config_label", name=win.selected_config["name"])
        )

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
        """Вызывается из VPNManager._do_full_cleanup()."""
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

    # ── Кнопка подключения сверху ─────────────────────────────────────
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

    # ── Карточка статуса ──────────────────────────────────────────────
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

    # ── Сплит: списки слева + инфо справа ─────────────────────────────
    split_frame = QFrame()
    split_layout = QHBoxLayout(split_frame)
    split_layout.setContentsMargins(0, 0, 0, 0)
    split_layout.setSpacing(16)

    left_col = QVBoxLayout()
    win.fav_title = QLabel(tr("connect_page_fav"))
    win.fav_title.setObjectName("fav_section")
    left_col.addWidget(win.fav_title)

    win.fav_list = QListWidget()
    win.fav_list.setObjectName("config_list")
    win.fav_list.itemClicked.connect(win.on_quick_select)
    win.fav_list.setMaximumHeight(110)
    win.fav_list.hide()
    win.fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    win.fav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    win.fav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    left_col.addWidget(win.fav_list)

    t2 = QLabel(tr("connect_page_all"))
    t2.setObjectName("section_title")
    left_col.addWidget(t2)

    win.quick_list = QListWidget()
    win.quick_list.setObjectName("config_list")
    win.quick_list.itemClicked.connect(win.on_quick_select)
    win.quick_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    win.quick_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    left_col.addWidget(win.quick_list, 1)

    split_layout.addLayout(left_col, 1)

    # Правая панель (инфо)
    win.info_panel = QWidget()
    info_layout = QVBoxLayout(win.info_panel)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(10)

    win.info_title = QLabel(tr("connect_page_info_title"))
    win.info_title.setObjectName("section_title")
    info_layout.addWidget(win.info_title)

    win.info_name = QLabel(tr("connect_page_info_name", name="—"))
    win.info_name.setObjectName("card_title")
    info_layout.addWidget(win.info_name)

    win.info_type = QLabel(tr("connect_page_info_type", type="—"))
    win.info_type.setObjectName("card_host")
    info_layout.addWidget(win.info_type)

    win.info_preview = QTextEdit()
    win.info_preview.setObjectName("log_view")
    win.info_preview.setReadOnly(True)
    win.info_preview.setPlaceholderText(tr("connect_page_placeholder"))
    info_layout.addWidget(win.info_preview, 1)

    split_layout.addWidget(win.info_panel, 1)
    l.addWidget(split_frame, 1)

    win.refresh_quick_list()
    return w

    win.fav_title = QLabel(tr("connect_page_fav"))
    win.fav_title.setObjectName("fav_section")
    ll.addWidget(win.fav_title)

    win.fav_list = QListWidget()
    win.fav_list.setObjectName("config_list")
    win.fav_list.setSpacing(2)
    win.fav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    win.fav_list.itemClicked.connect(win.on_quick_select)
    ll.addWidget(win.fav_list)

    all_lbl = QLabel(tr("connect_page_all"))
    all_lbl.setObjectName("fav_section")
    ll.addWidget(all_lbl)

    win.quick_list = QListWidget()
    win.quick_list.setObjectName("config_list")
    win.quick_list.setSpacing(2)
    win.quick_list.itemClicked.connect(win.on_quick_select)
    ll.addWidget(win.quick_list)

    # ── Правая панель: инфо о конфиге ───────────────────────────────────────
    right = QWidget()
    rl = QVBoxLayout(right)
    rl.setContentsMargins(32, 32, 32, 32)
    rl.setSpacing(12)

    t = QLabel(tr("connect_page_info_title"))
    t.setObjectName("section_title")
    rl.addWidget(t)

    win.info_name = QLabel("—")
    win.info_name.setStyleSheet("color: #4A3B52; font-size: 13px; font-weight: bold;")
    rl.addWidget(win.info_name)

    win.info_type = QLabel("—")
    win.info_type.setStyleSheet("color: #9B8AAE; font-size: 11px;")
    rl.addWidget(win.info_type)

    win.info_preview = QTextEdit()
    win.info_preview.setReadOnly(True)
    win.info_preview.setPlaceholderText(tr("connect_page_placeholder"))
    win.info_preview.setStyleSheet(
        "background: #FFFFFF; border: 1px solid #E8DFF0; border-radius: 8px; "
        "color: #4A3B52; font-family: 'Consolas', monospace; font-size: 11px; padding: 12px;"
    )
    rl.addWidget(win.info_preview, 1)

    root.addWidget(left)
    root.addWidget(right, 1)

    win.refresh_quick_list()
    return w