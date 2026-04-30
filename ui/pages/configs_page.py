# ui/pages/configs_page.py
"""
ConfigsController — загрузка, сохранение, добавление, удаление, переименование конфигов.
build_configs_page() — фабрика UI-виджета страницы (без изменений).
"""
from __future__ import annotations

import json
import logging
import urllib.parse as _up
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QFrame,
    QFileDialog, QInputDialog, QMessageBox, QSizePolicy
)

from utils.config import CONF_DIR, CONFIGS_FILE
from utils.helpers import detect_type
from utils.url_parser import SUPPORTED_SCHEMES, parse_proxy_url
from utils.i18n import tr
from ui.widgets import ConfigCard

if TYPE_CHECKING:
    from ui.main_window import VPNManager


class ConfigsController:
    """Управляет списком конфигов: I/O, добавление, удаление, переименование."""

    def __init__(self, win: "VPNManager"):
        self.win = win

    # ── Персистентность ──────────────────────────────────────────────────────

    def load_configs(self):
        win = self.win
        try:
            CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            if CONFIGS_FILE.exists():
                content = CONFIGS_FILE.read_text(encoding="utf-8")
                if content.strip():
                    win.configs = json.loads(content)
                    logging.info(f"Загружено {len(win.configs)} конфигов")
                else:
                    win.configs = []
                    logging.warning("configs.json пустой")
            else:
                win.configs = []
                logging.info("configs.json не найден, создан пустой список")
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигов: {e}")
            win.configs = []
        for c in win.configs:
            c.setdefault("favorite", False)

    def save_configs(self):
        win = self.win
        try:
            CONFIGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            CONFIGS_FILE.write_text(
                json.dumps(win.configs, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logging.info(f"Сохранено {len(win.configs)} конфигов")
        except Exception as e:
            logging.error(f"Ошибка сохранения конфигов: {e}")
            QMessageBox.critical(win, tr("dialog_error_title"), tr("dialog_save_error", e=e))

    # ── Добавление конфигов ──────────────────────────────────────────────────

    def add_config_file(self):
        win = self.win
        p, _ = QFileDialog.getOpenFileName(
            win, tr("dialog_open_config_title"), "",
            tr("dialog_open_config_filter")
        )
        if not p:
            return
        c = Path(p).read_text(encoding="utf-8", errors="replace")
        new_name = Path(p).name
        new_path = CONF_DIR / new_name
        new_path.write_text(c, encoding="utf-8")
        win.configs.append({
            "name": new_name, "type": detect_type(c),
            "content": c, "path": str(new_path)
        })
        self.save_configs()
        self.refresh_config_list()
        self.refresh_quick_list()

    def add_config_url(self):
        win = self.win
        schemes = ", ".join(SUPPORTED_SCHEMES)
        url, ok = QInputDialog.getText(
            win, tr("dialog_add_url_title"),
            tr("dialog_add_url_msg", schemes=schemes)
        )
        if not ok or not url.strip():
            return

        url = url.strip()

        # Автоматически определяем, это готовая ссылка или raw AWG конфиг
        if "[Interface]" in url and ("PrivateKey" in url or "Jc" in url):
            # Это raw WireGuard/AmneziaWG конфиг
            name, ok_name = QInputDialog.getText(
                win, tr("dialog_name_label"), tr("dialog_config_name_label")
            )
            if not ok_name:
                return
            safe_name = (name or tr("config_default_name")).replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(url, encoding="utf-8")
            win.configs.append({
                "name": name or safe_name,
                "type": "amneziawg",
                "content": url,
                "path": str(new_path)
            })
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
            QTimer.singleShot(0, lambda: QMessageBox.information(
                win, tr("dialog_added_title"), tr("dialog_awg_saved")
            ))
            return

        # Пробуем обработать как прокси-ссылку
        try:
            config_dict, proto = parse_proxy_url(url)
        except ValueError as e:
            QMessageBox.critical(win, tr("dialog_error_title"), str(e))
            return
        except Exception as e:
            QMessageBox.critical(win, tr("dialog_error_title"),
                                 tr("dialog_save_error", e=str(e)))
            return

        # Генерируем имя
        import urllib.parse as _up
        auto_name = _up.unquote(url.split("#")[1]) if "#" in url else ""
        name, ok_name = QInputDialog.getText(
            win, tr("dialog_name_label"),
            tr("dialog_config_name_label"),
            text=auto_name
        )
        if not ok_name:
            return

        final_name = name.strip() or auto_name or f"config_{proto}"
        safe_name = final_name.replace(" ", "_").replace("/", "_") + ".json"
        new_path = CONF_DIR / safe_name

        content = json.dumps(config_dict, ensure_ascii=False, indent=2)
        new_path.write_text(content, encoding="utf-8")

        win.configs.append({
            "name": final_name,
            "type": proto,
            "content": content,
            "path": str(new_path)
        })
        self.save_configs()

        try:
            self.refresh_config_list()
            self.refresh_quick_list()
        except Exception as e:
            logging.error(f"Ошибка обновления UI: {e}")

        QTimer.singleShot(0, lambda: QMessageBox.information(
            win, tr("dialog_added_title"),
            tr("dialog_config_added", name=final_name, proto=proto.upper())
        ))

    def add_config_text(self):
        win = self.win
        t, ok = QInputDialog.getMultiLineText(
            win, tr("dialog_input_config_title"), tr("dialog_input_config_label")
        )
        if ok and t.strip():
            name, _ = QInputDialog.getText(win, tr("dialog_name_title"), tr("dialog_name_label"))
            safe_name = (name or tr("config_default_name")).replace(" ", "_") + ".conf"
            new_path = CONF_DIR / safe_name
            new_path.write_text(t, encoding="utf-8")
            win.configs.append({
                "name": name or tr("config_default_name"),
                "type": detect_type(t), "content": t, "path": str(new_path)
            })
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()

    # ── Удаление / переименование ────────────────────────────────────────────

    def delete_config(self):
        win = self.win
        item = win.config_list.currentItem()
        cfg = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not cfg or cfg not in win.configs:
            QMessageBox.warning(win, tr("dialog_attention_title"), tr("dialog_select_first"))
            return
        idx = win.configs.index(cfg)
        if QMessageBox.question(
            win, tr("dialog_delete_title"),
            tr("dialog_delete_confirm", name=cfg.get("name"))
        ) == QMessageBox.StandardButton.Yes:
            cfg_path = cfg.get("path", "")
            if cfg_path and Path(cfg_path).exists():
                try:
                    Path(cfg_path).unlink()
                except Exception:
                    pass
            win.configs.pop(idx)
            self.save_configs()
            self.refresh_config_list()
            self.refresh_quick_list()
            if win.selected_config == cfg:
                win.selected_config = None

    def delete_config_by_obj(self, cfg: dict):
        win = self.win
        for i, c in enumerate(win.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                if QMessageBox.question(
                    win, tr("dialog_delete_title"),
                    tr("dialog_delete_confirm", name=c.get("name"))
                ) == QMessageBox.StandardButton.Yes:
                    cfg_path = c.get("path", "")
                    if cfg_path and Path(cfg_path).exists():
                        try:
                            Path(cfg_path).unlink()
                        except Exception:
                            pass
                    win.configs.pop(i)
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                return

    def rename_config_by_obj(self, cfg: dict):
        win = self.win
        for i, c in enumerate(win.configs):
            if c is cfg or c.get("name") == cfg.get("name"):
                new_name, ok = QInputDialog.getText(
                    win, tr("dialog_rename_title"), tr("dialog_rename_label"),
                    text=c.get("name", "")
                )
                if ok and new_name.strip():
                    win.configs[i]["name"] = new_name.strip()
                    self.save_configs()
                    self.refresh_config_list()
                    self.refresh_quick_list()
                    if win.selected_config == c:
                        win.selected_config = win.configs[i]
                    win.active_label.setText(tr("status_config_label", name=new_name))
                return

    # ── Обновление UI-списков ────────────────────────────────────────────────

    def refresh_quick_list(self):
        win = self.win
        win.fav_list.clear()
        win.quick_list.clear()
        favs   = [c for c in win.configs if c.get("favorite")]
        others = [c for c in win.configs if not c.get("favorite")]
        if favs:
            win.fav_list.show(); win.fav_title.show()
        else:
            win.fav_list.hide(); win.fav_title.hide()
        if not win.configs:
            win.quick_list.addItem(tr("config_list_empty"))
            return
        for c in favs:   self._add_card_to_list(win.fav_list, c)
        for c in others: self._add_card_to_list(win.quick_list, c)

    def _add_card_to_list(self, lst: QListWidget, cfg: dict):
        win = self.win
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, cfg)
        card = ConfigCard(cfg, parent=lst)
        item.setSizeHint(card.sizeHint())
        lst.addItem(item)
        lst.setItemWidget(item, card)

    def refresh_config_list(self):
        win = self.win
        win.config_list.clear()
        for c in win.configs:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, c)
            card = ConfigCard(c, parent=win.config_list)
            item.setSizeHint(card.sizeHint())
            win.config_list.addItem(item)
            win.config_list.setItemWidget(item, card)

    def on_config_select(self, item: QListWidgetItem):
        win = self.win
        cfg = item.data(Qt.ItemDataRole.UserRole)
        if cfg:
            win.selected_config = cfg
            preview_text = cfg.get("content", "")
            win.preview.setPlainText(
                preview_text[:2000] + ("..." if len(preview_text) > 2000 else "")
            )
            win.connect_ctrl._update_right_panel()


# ── UI-фабрика ──────────────────────────────────────────────────────────────

def build_configs_page(win: "VPNManager") -> QWidget:
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(12)

    t = QLabel(tr("configs_page_title"))
    t.setObjectName("section_title")
    l.addWidget(t)

    # ── Кнопки управления ─────────────────────────────────────────────
    r = QHBoxLayout()
    for btn_key, handler in [
        ("btn_add_file", win.add_config_file),
        ("btn_add_url",  win.add_config_url),
        ("btn_add_text", win.add_config_text),
        ("btn_delete",   win.delete_config),
    ]:
        b = QPushButton(tr(btn_key))
        b.setObjectName("add_btn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(handler)
        r.addWidget(b)
    l.addLayout(r)

    # ── Список конфигов (занимает всё доступное место) ─────────────────
    win.config_list = QListWidget()
    win.config_list.setObjectName("config_list")
    win.config_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    win.config_list.itemClicked.connect(win.on_config_select)
    l.addWidget(win.config_list, 1)

    # ── Предпросмотр (фиксированная высота, не ломает вёрстку) ─────────
    t2 = QLabel(tr("configs_page_preview"))
    t2.setObjectName("section_title")
    l.addWidget(t2)

    win.preview = QTextEdit()
    win.preview.setObjectName("log_view")
    win.preview.setReadOnly(True)
    win.preview.setMaximumHeight(150)
    win.preview.setPlaceholderText(tr("configs_page_preview_placeholder"))
    l.addWidget(win.preview)

    win.refresh_config_list()
    return w