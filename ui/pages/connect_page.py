# ui/pages/connect_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QListWidget, QTextEdit, QSizePolicy, QPushButton
)
from PyQt6.QtCore import Qt
from ui.widgets import ConfigCard
from PyQt6.QtWidgets import QListWidgetItem


def build_connect_page(win) -> QWidget:
    """
    Страница «ПОДКЛЮЧЕНИЕ».
    win — ссылка на VPNManager (QMainWindow).
    Все нужные атрибуты (big_status, active_label, fav_list, quick_list,
    info_panel, …) привязываются прямо к win, как раньше.
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(12)

    # ── Кнопка подключения (вверху) ─────────────────────────────────────────
    top_row = QFrame()
    tr = QHBoxLayout(top_row)
    tr.setContentsMargins(0, 0, 0, 0)
    win.top_connect_btn = QPushButton("▶  ПОДКЛЮЧИТЬ")
    win.top_connect_btn.setObjectName("connect_btn")
    win.top_connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    win.top_connect_btn.clicked.connect(win.toggle_connection)
    tr.addStretch()
    tr.addWidget(win.top_connect_btn)
    l.addWidget(top_row)

    # ── Карточка статуса ─────────────────────────────────────────────────────
    t = QLabel("АКТИВНОЕ ПОДКЛЮЧЕНИЕ")
    t.setObjectName("section_title")
    l.addWidget(t)

    card = QFrame()
    card.setObjectName("card")
    cl = QVBoxLayout(card)
    win.big_status = QLabel("● ОТКЛЮЧЁН")
    win.big_status.setStyleSheet(
        "color: #C62828; font-size: 28px; font-weight: bold; "
        "background: transparent; padding: 0px;"
    )
    win.active_label = QLabel("Конфиг не выбран")
    win.active_label.setStyleSheet(
        "color: #7A5C9A; font-size: 12px; background: transparent; padding: 0px;"
    )
    cl.addWidget(win.big_status)
    cl.addWidget(win.active_label)
    l.addWidget(card)

    # ── Сплит: левая колонка (списки) + правая (инфо) ────────────────────────
    split_frame = QFrame()
    split_layout = QHBoxLayout(split_frame)
    split_layout.setContentsMargins(0, 0, 0, 0)
    split_layout.setSpacing(16)

    left_col = QVBoxLayout()

    # Избранное
    win.fav_title = QLabel("⭐ ИЗБРАННОЕ")
    win.fav_title.setObjectName("fav_section")
    left_col.addWidget(win.fav_title)

    _scrollbar_style = """
        QListWidget#config_list { background: transparent; border: none; outline: none; }
        QListWidget#config_list::item {
            background: transparent; border-radius: 8px;
            margin-bottom: 4px; padding: 4px;
        }
        QListWidget#config_list::item:hover  { background: rgba(122, 92, 154, 0.08); }
        QListWidget#config_list::item:selected { background: #E6D8FF; color: black; }
        QScrollBar:vertical { background: #F8F6F2; width: 6px; border-radius: 3px; }
        QScrollBar::handle:vertical {
            background: #D8C8E8; border-radius: 3px; min-height: 20px;
        }
        QScrollBar::handle:vertical:hover { background: #C8B8D8; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    """

    win.fav_list = QListWidget()
    win.fav_list.setObjectName("config_list")
    win.fav_list.itemClicked.connect(win.on_quick_select)
    win.fav_list.setMaximumHeight(110)
    win.fav_list.hide()
    win.fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    win.fav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    win.fav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    win.fav_list.setStyleSheet(_scrollbar_style)
    left_col.addWidget(win.fav_list)

    t2 = QLabel("ВСЕ КОНФИГУРАЦИИ")
    t2.setObjectName("section_title")
    left_col.addWidget(t2)

    win.quick_list = QListWidget()
    win.quick_list.setObjectName("config_list")
    win.quick_list.itemClicked.connect(win.on_quick_select)
    left_col.addWidget(win.quick_list, 1)

    # Правая панель (инфо о конфиге)
    win.info_panel = QWidget()
    info_layout = QVBoxLayout(win.info_panel)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(10)

    win.info_title = QLabel("ИНФОРМАЦИЯ О КОНФИГЕ")
    win.info_title.setObjectName("section_title")
    info_layout.addWidget(win.info_title)

    win.info_name = QLabel("Имя: —")
    win.info_name.setObjectName("card_title")
    info_layout.addWidget(win.info_name)

    win.info_type = QLabel("Тип: —")
    win.info_type.setObjectName("card_host")
    info_layout.addWidget(win.info_type)

    win.info_preview = QTextEdit()
    win.info_preview.setObjectName("log_view")
    win.info_preview.setReadOnly(True)
    win.info_preview.setPlaceholderText("Выбери конфиг из списка слева...")
    info_layout.addWidget(win.info_preview, 1)

    split_layout.addLayout(left_col, 1)
    split_layout.addWidget(win.info_panel, 1)
    l.addWidget(split_frame, 1)

    win.refresh_quick_list()
    return w
