# ui/pages/sys_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton
)
from utils.helpers import get_system_info


def build_sys_page(win) -> QWidget:
    """
    Страница «СИСТЕМА И ЛОГИ».
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    # ── Системная информация ─────────────────────────────────────────────────
    t = QLabel("СИСТЕМА И ЛОГИ")
    t.setObjectName("section_title")
    l.addWidget(t)

    win.sys_view = QTextEdit()
    win.sys_view.setObjectName("sys_view")
    win.sys_view.setReadOnly(True)
    win.sys_view.setText(get_system_info())
    l.addWidget(win.sys_view, 1)

    # ── Журнал работы ────────────────────────────────────────────────────────
    t2 = QLabel("ЖУРНАЛ РАБОТЫ")
    t2.setObjectName("section_title")
    l.addWidget(t2)

    win.log_view = QTextEdit()
    win.log_view.setObjectName("log_view")
    win.log_view.setReadOnly(True)
    win.log_view.append("[i] Логи появятся после подключения...")
    l.addWidget(win.log_view, 1)

    # ── Кнопка очистки ───────────────────────────────────────────────────────
    r = QHBoxLayout()
    r.addStretch()
    clr = QPushButton("ОЧИСТИТЬ ЛОГ")
    clr.setObjectName("add_btn")
    clr.clicked.connect(lambda: win.log_view.clear())
    r.addWidget(clr)
    l.addLayout(r)

    return w
