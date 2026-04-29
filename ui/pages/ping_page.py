# ui/pages/ping_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt


# Хосты по умолчанию: (display_name, host)
DEFAULT_PING_HOSTS = [
    ("GOOGLE DNS",    "8.8.8.8"),
    ("CLOUDFLARE",    "1.1.1.1"),
    ("YANDEX DNS",    "77.88.8.8"),
    ("STRINOVA JP",   "101.32.143.247"),
]


def build_ping_page(win) -> QWidget:
    """
    Страница «МОНИТОРИНГ ПИНГА».
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    t = QLabel("МОНИТОРИНГ ПИНГА")
    t.setObjectName("section_title")
    l.addWidget(t)

    # ── Поле ввода нового хоста ──────────────────────────────────────────────
    input_frame = QFrame()
    input_frame.setObjectName("card")
    input_frame.setStyleSheet("border: 1px solid #FF9E43;")
    ifr = QHBoxLayout(input_frame)
    ifr.setContentsMargins(10, 6, 10, 6)
    ifr.setSpacing(10)

    win.ping_input = QLineEdit()
    win.ping_input.setPlaceholderText("host:port или домен")
    win.ping_input.returnPressed.connect(win.add_ping_from_input)

    win.ping_add_btn = QPushButton("+ ДОБАВИТЬ")
    win.ping_add_btn.setObjectName("add_btn")
    win.ping_add_btn.clicked.connect(win.add_ping_from_input)

    ifr.addWidget(win.ping_input)
    ifr.addWidget(win.ping_add_btn)
    l.addWidget(input_frame)

    # ── Сетка карточек ───────────────────────────────────────────────────────
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border:none; background:transparent;")

    win.ping_container = QWidget()
    win.ping_layout = QGridLayout(win.ping_container)
    win.ping_layout.setSpacing(12)
    win.ping_layout.setContentsMargins(0, 0, 0, 0)
    scroll.setWidget(win.ping_container)
    l.addWidget(scroll, 1)

    # Счётчик позиции для сетки (нужен в _add_ping_card)
    win.row_idx = 0

    # Добавляем стандартные хосты
    for name, host in DEFAULT_PING_HOSTS:
        win._add_ping_card(name, host)

    return w
