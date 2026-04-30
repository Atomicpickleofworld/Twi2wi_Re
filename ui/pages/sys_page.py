# ui/pages/sys_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QComboBox
)
from utils.helpers import get_system_info
from utils.i18n import tr, get_available_languages, set_language, save_language_preference


def build_sys_page(win) -> QWidget:
    """
    Страница «СИСТЕМА И ЛОГИ» с авто-списком языков.
    """
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    # ── Заголовок + язык (в одну строку) ───────────────────────────────────
    header_row = QHBoxLayout()
    header_row.setContentsMargins(0, 0, 0, 0)
    header_row.setSpacing(12)

    # Заголовок слева
    t = QLabel(tr("system_page_title"))
    t.setObjectName("section_title")
    header_row.addWidget(t)

    # Язык справа (авто-сканирование)
    lang_row = QHBoxLayout()
    lang_row.setContentsMargins(0, 0, 0, 0)
    lang_row.setSpacing(8)

    lang_label = QLabel(tr("sys_language_label"))
    lang_label.setObjectName("lang_label")
    lang_label.setStyleSheet("color: #7A5C9A; font-size: 11px; letter-spacing: 1px;")

    win.lang_combo = QComboBox()
    win.lang_combo.setObjectName("lang_combo")

    # 🔍 Авто-сканирование locales/*.json
    available = get_available_languages()
    current_lang = tr._lang
    current_index = 0

    for i, (lang_code, display_name) in enumerate(available.items()):
        win.lang_combo.addItem(display_name, userData=lang_code)
        if lang_code == current_lang:
            current_index = i
    win.lang_combo.setCurrentIndex(current_index)

    # Стиль под тему
    win.lang_combo.setStyleSheet("""
        QComboBox {
            background: #FFFFFF;
            border: 1px solid #D8C8E8;
            border-radius: 6px;
            padding: 4px 8px;
            color: #2C2430;
            font-size: 11px;
            min-width: 140px;
        }
        QComboBox:hover { border-color: #FF9E43; }
        QComboBox:focus { border-color: #FF9E43; outline: none; }
        QComboBox::drop-down { border: none; width: 20px; }
        QComboBox::down-arrow { image: none; }
        QComboBox QAbstractItemView {
            background: #FFFFFF;
            border: 1px solid #D8C8E8;
            selection-background-color: #E6D8FF;
            selection-color: #2C2430;
        }
    """)

    win.lang_combo.currentIndexChanged.connect(
        lambda i: _change_lang(win.lang_combo.itemData(i), win)
    )

    lang_row.addWidget(lang_label)
    lang_row.addWidget(win.lang_combo)
    header_row.addStretch()
    header_row.addLayout(lang_row)
    l.addLayout(header_row)

    # ── Системная информация ─────────────────────────────────────────────────
    win.sys_view = QTextEdit()
    win.sys_view.setObjectName("sys_view")
    win.sys_view.setReadOnly(True)
    win.sys_view.setText(get_system_info())
    l.addWidget(win.sys_view, 1)

    # ── Журнал работы ────────────────────────────────────────────────────────
    t2 = QLabel(tr("system_page_log_title"))
    t2.setObjectName("section_title")
    l.addWidget(t2)

    win.log_view = QTextEdit()
    win.log_view.setObjectName("log_view")
    win.log_view.setReadOnly(True)
    win.log_view.setPlaceholderText(tr("system_page_log_placeholder"))
    l.addWidget(win.log_view, 1)

    # ── Кнопка очистки ───────────────────────────────────────────────────────
    r = QHBoxLayout()
    r.addStretch()
    clr = QPushButton(tr("btn_clear_log"))
    clr.setObjectName("add_btn")
    clr.clicked.connect(lambda: win.log_view.clear())
    r.addWidget(clr)
    l.addLayout(r)

    return w


def _change_lang(lang: str, win):
    """Смена языка + перерисовка интерфейса + сохранение предпочтения."""
    if not lang:
        return

    set_language(lang)
    save_language_preference(lang)  # ✅ Сохраняем выбор

    # Перерисовываем текущую страницу
    current_idx = win.pages.currentIndex()
    win.pages.setCurrentIndex(current_idx)

    # Обновляем системную инфу (там тоже есть локализуемые строки)
    if hasattr(win, "sys_view"):
        win.sys_view.setText(get_system_info())

    # Обновляем плейсхолдер лога
    if hasattr(win, "log_view"):
        win.log_view.setPlaceholderText(tr("system_page_log_placeholder"))