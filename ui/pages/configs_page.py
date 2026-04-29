# ui/pages/configs_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QTextEdit, QSizePolicy, QPushButton
)
from PyQt6.QtCore import Qt


def build_configs_page(win) -> QWidget:
    """
    Страница «МЕНЕДЖЕР КОНФИГОВ».
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(12)

    t = QLabel("МЕНЕДЖЕР КОНФИГОВ")
    t.setObjectName("section_title")
    l.addWidget(t)

    # ── Панель кнопок ────────────────────────────────────────────────────────
    r = QHBoxLayout()
    for btn_text, handler in [
        ("+ ФАЙЛ",   win.add_config_file),
        ("+ ССЫЛКА", win.add_config_url),
        ("+ ТЕКСТ",  win.add_config_text),
        (" УДАЛИТЬ", win.delete_config),
    ]:
        b = QPushButton(btn_text)
        b.setObjectName("add_btn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(handler)
        r.addWidget(b)
    l.addLayout(r)

    # ── Список конфигов ──────────────────────────────────────────────────────
    win.config_list = QListWidget()
    win.config_list.setObjectName("config_list")
    win.config_list.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    win.config_list.itemClicked.connect(win.on_config_select)
    l.addWidget(win.config_list, 1)

    # ── Предпросмотр ─────────────────────────────────────────────────────────
    t2 = QLabel("ПРЕДПРОСМОТР")
    t2.setObjectName("section_title")
    l.addWidget(t2)

    win.preview = QTextEdit()
    win.preview.setObjectName("log_view")
    win.preview.setReadOnly(True)
    win.preview.setMaximumHeight(150)
    win.preview.setPlaceholderText("Выбери конфиг...")
    l.addWidget(win.preview)

    win.refresh_config_list()
    return w
