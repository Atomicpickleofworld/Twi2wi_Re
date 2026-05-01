# ui/pages/plugins_page.py
"""
PluginsController — управление плагинами: рендер карточек, меню, импорт, eventFilter.
build_plugins_page() — фабрика UI-виджета страницы (без изменений).

Все свободные функции (render_plugins, create_plugin_card, …) сохранены
для обратной совместимости с ui/pages/__init__.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QCheckBox, QMessageBox,
    QInputDialog, QFileDialog, QMenu,
)

from security.sandbox import PluginLoadError, SandboxManager
from utils.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import VPNManager


class PluginsController:
    """Управляет UI плагинов и делегирует в sandbox_manager."""

    def __init__(self, win: "VPNManager"):
        self.win = win

    # ── Рендер ──────────────────────────────────────────────────────────────

    def render_plugins(self, filter_text: str = ""):
        win = self.win
        # Используем list_all_plugins и ПРАВИЛЬНО мапим ключи
        raw = win.sandbox_manager.list_all_plugins()
        win.plugins_data = [
            {
                "id": p["id"],
                "name": p["name"],
                "desc": p.get("description", f"Права: {', '.join(p.get('permissions', []))}"),
                "ver": p.get("version", "?"),  # ← version → ver
                "enabled": p["running"],  # ← running → enabled
                "icon": "🧩",
            }
            for p in raw
        ]
        render_plugins(win, filter_text)

    def create_plugin_card(self, plugin):
        return create_plugin_card(self.win, plugin)

    def apply_plugin_style(self, card, state):
        apply_plugin_style(self.win, card, state)

    def filter_plugins(self, text: str):
        filter_plugins(self.win, text)

    def view_full_description(self, plugin):
        view_full_description(self.win, plugin)

    def show_plugin_menu(self, plugin):
        show_plugin_menu(self.win, plugin)

    def delete_plugin(self, plugin):
        delete_plugin(self.win, plugin)

    def toggle_plugin(self, plugin, state):
        toggle_plugin(self.win, plugin, state)

    def show_import_menu(self):
        show_import_menu(self.win)

    def import_plugin_file(self):
        win = self.win
        path, _ = QFileDialog.getOpenFileName(
            win, tr("dialog_select_plugin_title"), "", tr("dialog_plugin_filter")
        )
        if not path:
            return
        try:
            plugin_id = win.sandbox_manager.install_from_zip(Path(path))
            if plugin_id:
                win.append_log(tr("log_plugin_installed", id=plugin_id))
                self.render_plugins()
                QMessageBox.information(
                    win, tr("dialog_success_title"), tr("dialog_plugin_loaded", id=plugin_id)
                )
            else:
                QMessageBox.warning(win, tr("dialog_error_title"), tr("dialog_plugin_load_error"))
        except PluginLoadError as e:
            QMessageBox.critical(win, tr("dialog_plugin_error_title"), str(e))

    def import_plugin_git(self):
        import_plugin_git(self.win)

    # ── eventFilter (только plugin-часть) ───────────────────────────────────

    def event_filter(self, obj, event) -> bool:
        win = self.win
        if event.type() == QEvent.Type.MouseButtonPress:
            if hasattr(obj, "plugin_ref") and obj.objectName() == "plugin_card":
                plugin = obj.plugin_ref
                plugin_id = plugin["id"]

                if plugin.get("running"):  # ← running!
                    win.sandbox_manager.unload(plugin_id)
                    plugin["running"] = False
                    if hasattr(win, "remove_plugin_tab"):
                        win.remove_plugin_tab(plugin_id)
                else:
                    plugins_root = Path(__file__).resolve().parent.parent.parent / "plugins"
                    plugin_dir = plugins_root / plugin_id
                    if plugin_dir.exists():
                        try:
                            loaded_id = win.sandbox_manager._load_one(plugin_dir)
                            plugin["running"] = bool(loaded_id)
                        except Exception as e:
                            win.append_log(tr("log_plugin_error", e=e))
                            plugin["running"] = False

                win.save_plugins_state()

                state = "enabled" if plugin.get("running") else "disabled"
                obj.setProperty("state", state)
                obj.style().unpolish(obj)
                obj.style().polish(obj)

                if hasattr(obj, "status_label"):
                    if plugin.get("running"):
                        obj.status_label.setText(tr("plugin_status_on"))
                        obj.status_label.setStyleSheet(
                            "color: #4CAF50; font-size: 11px; font-weight: bold; min-width: 45px;"
                        )
                    else:
                        obj.status_label.setText(tr("plugin_status_off"))
                        obj.status_label.setStyleSheet(
                            "color: #9b2d30; font-size: 11px; font-weight: bold; min-width: 45px;"
                        )

                log_key = "log_plugin_toggle_on" if plugin.get("running") else "log_plugin_toggle_off"
                win.append_log(tr(log_key, name=plugin["name"]))
                return True

        from PyQt6.QtWidgets import QMainWindow
        return QMainWindow.eventFilter(win, obj, event)


# ── Свободные функции (оригинал, для обратной совместимости) ─────────────────

def build_plugins_page(win: "VPNManager") -> QWidget:
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    # Заголовок + поиск
    top = QHBoxLayout()
    t = QLabel(tr("nav_plugins"))
    t.setObjectName("section_title")
    top.addWidget(t)
    top.addStretch()

    win.plugin_search = QLineEdit()
    win.plugin_search.setPlaceholderText(tr("plugins_search_placeholder"))
    win.plugin_search.textChanged.connect(win.filter_plugins)
    win.plugin_search.setFixedWidth(200)
    top.addWidget(win.plugin_search)

    win.plugin_add_btn = QPushButton(tr("btn_plugin_add"))
    win.plugin_add_btn.setObjectName("add_btn")
    win.plugin_add_btn.clicked.connect(win.show_import_menu)
    top.addWidget(win.plugin_add_btn)
    l.addLayout(top)

    # Скроллируемый список карточек
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

    win.plugins_container = QWidget()
    win.plugins_layout = QVBoxLayout(win.plugins_container)
    win.plugins_layout.setSpacing(8)
    win.plugins_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    scroll.setWidget(win.plugins_container)
    l.addWidget(scroll, 1)

    win.plugins_data = []
    win.render_plugins()
    return w


def render_plugins(win: "VPNManager", filter_text: str = ""):
    layout = win.plugins_layout

    # 🔄 Применяем сохранённое состояние плагинов перед рендером
    saved_state = win.load_plugins_state()
    for plugin in win.plugins_data:
        plugin_id = plugin.get("id")
        if plugin_id in saved_state:
            should_be_running = saved_state[plugin_id]
            if plugin.get("running") != should_be_running:
                plugin["running"] = should_be_running
                if should_be_running:
                    plugins_root = Path(__file__).resolve().parent.parent.parent / "plugins"
                    plugin_dir = plugins_root / plugin_id
                    if plugin_dir.exists():
                        try:
                            win.sandbox_manager._load_one(plugin_dir)
                        except Exception as e:
                            win.append_log(tr("log_plugin_error", e=e))
                            plugin["running"] = False
                else:
                    win.sandbox_manager.unload(plugin_id)

    # Очищаем старые карточки
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    text = filter_text.lower().strip()
    shown = 0

    for plugin in win.plugins_data:
        if text and text not in plugin.get("name", "").lower() and text not in plugin.get("desc", "").lower():
            continue
        card = create_plugin_card(win, plugin)
        layout.addWidget(card)
        shown += 1

    if shown == 0:
        empty = QLabel("— нет плагинов —")
        empty.setStyleSheet("color: #9B8AAE; font-size: 12px;")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(empty)


def create_plugin_card(win: "VPNManager", plugin: dict) -> QFrame:
    card = QFrame()
    card.setObjectName("plugin_card")
    card.plugin_ref = plugin
    state = "enabled" if plugin.get("running") else "disabled"  # ← running!
    card.setProperty("state", state)
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    win.installEventFilter(win)

    cl = QHBoxLayout(card)
    cl.setContentsMargins(12, 10, 12, 10)
    cl.setSpacing(10)

    icon = QLabel(plugin.get("icon", "🧩"))
    icon.setStyleSheet("font-size: 22px;")
    icon.setFixedWidth(32)
    cl.addWidget(icon)

    info = QVBoxLayout()
    info.setSpacing(2)
    name_lbl = QLabel(f"{plugin.get('name', '?')}  <span style='color:#9B8AAE;font-size:10px;'>v{plugin.get('ver','?')}</span>")
    name_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #2C2430;")
    desc_lbl = QLabel(plugin.get("desc", ""))
    desc_lbl.setStyleSheet("font-size: 11px; color: #7A5C9A;")
    desc_lbl.setWordWrap(True)
    info.addWidget(name_lbl)
    info.addWidget(desc_lbl)
    cl.addLayout(info, 1)

    status_lbl = QLabel(tr("plugin_status_on") if plugin.get("running") else tr("plugin_status_off"))  # ← running!
    status_lbl.setStyleSheet(
        ("color: #4CAF50;" if plugin.get("running") else "color: #9b2d30;")
        + " font-size: 11px; font-weight: bold; min-width: 45px;"
    )
    card.status_label = status_lbl
    cl.addWidget(status_lbl)

    apply_plugin_style(win, card, state)
    card.installEventFilter(win)
    return card


def apply_plugin_style(win, card: QFrame, state: str):
    card.setProperty("state", state)
    card.style().unpolish(card)
    card.style().polish(card)


def plugin_event_filter(win, obj, event):
    if event.type() == QEvent.Type.MouseButtonPress:
        if hasattr(obj, "plugin_ref") and obj.objectName() == "plugin_card":
            plugin = obj.plugin_ref
            plugin_id = plugin["id"]

            if plugin["enabled"]:
                win.sandbox_manager.unload(plugin_id)
                plugin["enabled"] = False
                if hasattr(win, "remove_plugin_tab"):
                    win.remove_plugin_tab(plugin_id)
            # В event_filter (PluginsController):
            else:
                plugins_root = Path(__file__).resolve().parent.parent.parent / "plugins"
                plugin_dir = plugins_root / plugin_id
                if plugin_dir.exists():
                    try:
                        loaded_id = win.sandbox_manager._load_one(plugin_dir)
                        plugin["running"] = bool(loaded_id)  # ← running, не enabled!
                    except Exception as e:
                        win.append_log(tr("log_plugin_error", e=e))
                        plugin["running"] = False

            # ✅ СОХРАНЯЕМ СОСТОЯНИЕ
            win.save_plugins_state()

            # Обновляем UI карточки
            state = "enabled" if plugin["enabled"] else "disabled"
            obj.setProperty("state", state)
            obj.style().unpolish(obj)
            obj.style().polish(obj)

            if hasattr(obj, "status_label"):
                if plugin["enabled"]:
                    obj.status_label.setText(tr("plugin_status_on"))
                    obj.status_label.setStyleSheet(
                        "color: #4CAF50; font-size: 11px; font-weight: bold; min-width: 45px;")
                else:
                    obj.status_label.setText(tr("plugin_status_off"))
                    obj.status_label.setStyleSheet(
                        "color: #9b2d30; font-size: 11px; font-weight: bold; min-width: 45px;")

            win.append_log(
                tr("log_plugin_toggle_on" if plugin["enabled"] else "log_plugin_toggle_off", name=plugin["name"]))
            return True
    return False


def filter_plugins(win: "VPNManager", text: str):
    render_plugins(win, text)


def view_full_description(win: "VPNManager", plugin: dict):
    desc = plugin.get("desc") or tr("dialog_desc_missing")
    QMessageBox.information(
        win,
        tr("dialog_desc_title", name=plugin.get("name", "?")),
        desc
    )


def show_plugin_menu(win: "VPNManager", plugin: dict):
    menu = QMenu(win)
    act_desc = menu.addAction(tr("plugin_menu_desc"))
    act_del  = menu.addAction(tr("plugin_menu_delete"))
    action   = menu.exec(win.cursor().pos())
    if action == act_desc:
        view_full_description(win, plugin)
    elif action == act_del:
        delete_plugin(win, plugin)


def delete_plugin(win: "VPNManager", plugin: dict):
    if QMessageBox.question(
        win,
        tr("dialog_delete_plugin_title"),
        tr("dialog_delete_plugin_confirm", name=plugin["name"])
    ) == QMessageBox.StandardButton.Yes:
        win.plugins_data.remove(plugin)
        win.append_log(tr("log_plugin_toggle_off", name=plugin["name"]))
        render_plugins(win, win.plugin_search.text())


def toggle_plugin(win: "VPNManager", plugin: dict, state):
    plugin["enabled"] = (state == Qt.CheckState.Checked)
    key = "log_plugin_toggle_on" if plugin["enabled"] else "log_plugin_toggle_off"
    win.append_log(tr(key, name=plugin["name"]))


def show_import_menu(win: "VPNManager"):
    menu = QMenu(win)
    act_file = menu.addAction(tr("import_menu_file"))
    act_git  = menu.addAction(tr("import_menu_git"))
    action   = menu.exec(
        win.plugin_add_btn.mapToGlobal(win.plugin_add_btn.rect().bottomRight())
    )
    if action == act_file:
        win.import_plugin_file()
    elif action == act_git:
        win.import_plugin_git()


def import_plugin_file(win: "VPNManager"):
    """Оставлена для обратной совместимости; реальная логика в PluginsController."""
    win.plugins_ctrl.import_plugin_file()


def import_plugin_git(win: "VPNManager"):
    url, ok = QInputDialog.getText(
        win, tr("dialog_github_title"), tr("dialog_github_msg")
    )
    if ok and url.strip():
        win.append_log(f"[i] Загрузка плагина из GitHub: {url}")
        win.plugins_data.append({
            "id":      url.split("/")[-1].lower().replace(".zip", ""),
            "name":    f"🌐 {url.split('/')[-1].replace('.zip', '')}",
            "desc":    "Импортирован с GitHub (ожидает проверки)",
            "ver":     "0.0.1",
            "enabled": True,
        })
        render_plugins(win)
        QMessageBox.information(
            win, tr("dialog_import_title"), tr("dialog_import_git_msg")
        )