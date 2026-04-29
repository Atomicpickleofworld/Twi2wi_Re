# ui/pages/plugins_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QMenu, QMessageBox,
    QFileDialog, QInputDialog
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QCursor
from pathlib import Path


def build_plugins_page(win) -> QWidget:
    """
    Страница «ПЛАГИНЫ».
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    # ── Поиск + кнопка добавления ────────────────────────────────────────────
    top_bar = QHBoxLayout()
    top_bar.setSpacing(12)

    win.plugin_search = QLineEdit()
    win.plugin_search.setPlaceholderText("🔍 Поиск плагинов по названию...")
    win.plugin_search.textChanged.connect(win.filter_plugins)
    top_bar.addWidget(win.plugin_search, 1)

    win.plugin_add_btn = QPushButton("+")
    win.plugin_add_btn.setObjectName("add_btn")
    win.plugin_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win.plugin_add_btn.setToolTip("Добавить плагин")
    win.plugin_add_btn.clicked.connect(win.show_import_menu)
    top_bar.addWidget(win.plugin_add_btn)
    l.addLayout(top_bar)

    # ── Список плагинов (scroll) ─────────────────────────────────────────────
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border:none; background:transparent;")

    win.plugin_container = QWidget()
    win.plugin_layout = QVBoxLayout(win.plugin_container)
    win.plugin_layout.setSpacing(8)
    win.plugin_layout.setContentsMargins(0, 0, 0, 0)
    scroll.setWidget(win.plugin_container)
    l.addWidget(scroll, 1)

    win.plugins_data = []
    win.render_plugins()
    return w


# ── VPNManager ─────────────

def create_plugin_card(win, plugin):
    """Создаёт карточку плагина."""
    from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout

    card = QFrame()
    card.setObjectName("plugin_card")
    card.plugin_ref = plugin
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.installEventFilter(win)

    if plugin.get("has_error", False):
        card.setProperty("state", "error")
    elif plugin["enabled"]:
        card.setProperty("state", "enabled")
    else:
        card.setProperty("state", "disabled")

    layout = QHBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(12)

    icon = QLabel(plugin.get("icon", "🧩"))
    icon.setStyleSheet("font-size: 22px; min-width: 28px;")
    layout.addWidget(icon)

    info_widget = QWidget()
    info_layout = QVBoxLayout(info_widget)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(2)

    name_lbl = QLabel(plugin["name"])
    name_lbl.setObjectName("card_title")
    desc_lbl = QLabel(plugin["desc"])
    desc_lbl.setWordWrap(True)
    desc_lbl.setStyleSheet("color: #7A5C9A; font-size: 11px;")
    ver_lbl = QLabel(f"v{plugin['ver']}")
    ver_lbl.setStyleSheet("color: #9B8AAE; font-size: 10px;")

    info_layout.addWidget(name_lbl)
    info_layout.addWidget(desc_lbl)
    info_layout.addWidget(ver_lbl)
    layout.addWidget(info_widget, 1)

    if plugin.get("has_error", False):
        status_text, status_color = "ОШИБКА", "#F57C00"
    elif plugin["enabled"]:
        status_text, status_color = "ВКЛ", "#4CAF50"
    else:
        status_text, status_color = "ВЫКЛ", "#9b2d30"

    status_label = QLabel(status_text)
    status_label.setStyleSheet(
        f"color: {status_color}; font-size: 11px; font-weight: bold;"
        " min-width: 45px; text-align: center;"
    )
    layout.addWidget(status_label)

    menu_btn = QPushButton("⋮")
    menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    menu_btn.setFixedSize(28, 28)
    menu_btn.setStyleSheet("""
        QPushButton { border: none; background: transparent; font-size: 18px; color: #7A5C9A; }
        QPushButton:hover { color: #FF9E43; }
    """)
    menu_btn.clicked.connect(lambda checked=False, p=plugin: win.show_plugin_menu(p))
    layout.addWidget(menu_btn)

    card.status_label = status_label
    return card


def apply_plugin_style(win, card, state):
    card.setProperty("state", state)
    card.style().unpolish(card)
    card.style().polish(card)
    from PyQt6.QtWidgets import QWidget as _QW
    for child in card.findChildren(_QW):
        child.style().unpolish(child)
        child.style().polish(child)


def render_plugins(win, filter_text=""):
    while win.plugin_layout.count():
        item = win.plugin_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

    visible = [
        p for p in win.plugins_data
        if not filter_text or filter_text.lower() in p["name"].lower()
    ]

    for i, plugin in enumerate(visible):
        card = win.create_plugin_card(plugin)
        win.plugin_layout.addWidget(card)
        if i < len(visible) - 1:
            sep = QFrame()
            sep.setObjectName("plugin_sep")
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #E8DFF0; margin: 4px 12px;")
            win.plugin_layout.addWidget(sep)

    win.plugin_layout.addStretch()


def plugin_event_filter(win, obj, event):
    if event.type() == QEvent.Type.MouseButtonPress:
        if hasattr(obj, "plugin_ref") and obj.objectName() == "plugin_card":
            plugin = obj.plugin_ref
            if not plugin.get("has_error", False):
                plugin["enabled"] = not plugin["enabled"]

            if plugin.get("has_error", False):
                state, status_text, status_color = "error", "ОШИБКА", "#F57C00"
            elif plugin["enabled"]:
                state, status_text, status_color = "enabled", "ВКЛ", "#4CAF50"
            else:
                state, status_text, status_color = "disabled", "ВЫКЛ", "#9b2d30"

            obj.setProperty("state", state)
            obj.style().unpolish(obj)
            obj.style().polish(obj)

            if hasattr(obj, "status_label"):
                obj.status_label.setText(status_text)
                obj.status_label.setStyleSheet(
                    f"color: {status_color}; font-size: 11px; font-weight: bold;"
                    " min-width: 45px; text-align: center;"
                )

            win.append_log(
                f"[i] Плагин «{plugin['name']}» "
                f"{'включён' if plugin['enabled'] else 'отключён'}"
            )
            return True
    return False


def filter_plugins(win, text):
    win.render_plugins(text)


def view_full_description(win, plugin):
    desc = plugin.get("fullDescription", "Описание отсутствует.")
    QMessageBox.information(win, f"Описание: {plugin['name']}", desc)


def show_plugin_menu(win, plugin):
    menu = QMenu(win)
    act_desc = menu.addAction("📖 Полное описание")
    act_err = menu.addAction(
        "🟡 Переключить ошибку" if not plugin.get("has_error") else "🟢 Убрать ошибку"
    )
    menu.addSeparator()
    act_del = menu.addAction("🗑️ Удалить плагин")

    action = menu.exec(QCursor.pos())
    if action == act_desc:
        win.view_full_description(plugin)
    elif action == act_err:
        plugin["has_error"] = not plugin.get("has_error", False)
        win.render_plugins(win.plugin_search.text())
    elif action == act_del:
        win.delete_plugin(plugin)


def delete_plugin(win, plugin):
    if QMessageBox.question(
        win, "Удаление", f"Удалить плагин «{plugin['name']}»?"
    ) == QMessageBox.StandardButton.Yes:
        win.plugins_data.remove(plugin)
        win.append_log(f"[i] Плагин «{plugin['name']}» удален")
        win.render_plugins(win.plugin_search.text())


def toggle_plugin(win, plugin, state):
    plugin["enabled"] = (state == Qt.CheckState.Checked)
    status = "✅ включен" if plugin["enabled"] else "❌ выключен"
    win.append_log(f"[i] Плагин «{plugin['name']}» {status}")


def show_import_menu(win):
    menu = QMenu(win)
    act_file = menu.addAction("📁 Выбрать с устройства (.zip)")
    act_git = menu.addAction("🌐 Импорт по ссылке GitHub")
    action = menu.exec(
        win.plugin_add_btn.mapToGlobal(win.plugin_add_btn.rect().bottomRight())
    )
    if action == act_file:
        win.import_plugin_file()
    elif action == act_git:
        win.import_plugin_git()


def import_plugin_file(win):
    path, _ = QFileDialog.getOpenFileName(
        win, "Выберите архив плагина", "", "ZIP архивы (*.zip)"
    )
    if path:
        win.append_log(f"[i] Выбран плагин: {Path(path).name}")
        win.plugins_data.append({
            "id": Path(path).stem.lower(),
            "name": f"📦 {Path(path).stem}",
            "desc": "Импортирован с устройства (ожидает активации)",
            "ver": "0.0.1",
            "enabled": True,
        })
        win.render_plugins()
        QMessageBox.information(
            win, "Импорт",
            "Плагин добавлен в список!\n"
            "Логика распаковки будет подключена на следующем этапе."
        )


def import_plugin_git(win):
    url, ok = QInputDialog.getText(
        win, "GitHub ссылка", "Вставь прямую ссылку на .zip или репозиторий:"
    )
    if ok and url.strip():
        win.append_log(f"[i] Загрузка плагина из GitHub: {url}")
        win.plugins_data.append({
            "id": url.split("/")[-1].lower().replace(".zip", ""),
            "name": f"🌐 {url.split('/')[-1].replace('.zip', '')}",
            "desc": "Импортирован с GitHub (ожидает проверки)",
            "ver": "0.0.1",
            "enabled": True,
        })
        win.render_plugins()
        QMessageBox.information(
            win, "Импорт",
            "Запрос на скачивание отправлен!\n"
            "Логика загрузки будет подключена на следующем этапе."
        )
