# ui/pages/plugin_tab_page.py
"""
PluginTabPage — виджет-вкладка для плагина.

Рендерит HTML-контент переданный плагином через ctx.register_tab().
Использует QTextBrowser (встроен в PyQt6, без лишних зависимостей).
Поддерживает обновление контента без пересоздания вкладки.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton,
)
from PyQt6.QtCore import Qt


class PluginTabPage(QWidget):
    """
    Страница-контейнер для вкладки плагина.

    Параметры:
        plugin_id  — идентификатор плагина (для логирования и удаления)
        title      — заголовок вкладки
        icon       — эмодзи иконка
        html       — начальный HTML-контент
    """

    def __init__(
        self,
        plugin_id: str,
        title: str,
        icon: str = "🔌",
        html: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self._title = title
        self._icon  = icon

        self._build_ui(html)

    def _build_ui(self, html: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # ── Заголовок ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title_lbl = QLabel(f"{self._icon}  {self._title}")
        title_lbl.setObjectName("section_title")
        header.addWidget(title_lbl)
        header.addStretch()

        # Бейдж «плагин»
        badge = QLabel("PLUGIN")
        badge.setStyleSheet(
            "background: rgba(122,92,154,0.12); color: #7A5C9A; "
            "font-size: 9px; letter-spacing: 2px; font-weight: bold; "
            "padding: 2px 8px; border-radius: 4px;"
        )
        header.addWidget(badge)
        layout.addLayout(header)

        # ── HTML-контент ─────────────────────────────────────────────────────
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)  # безопасность: не открываем ссылки
        self._browser.setStyleSheet(
            "QTextBrowser {"
            "  background: #FFFFFF;"
            "  border: 1px solid #E8DFF0;"
            "  border-radius: 8px;"
            "  color: #2C2430;"
            "  font-family: 'Segoe UI', sans-serif;"
            "  font-size: 12px;"
            "  padding: 16px;"
            "}"
        )
        self._set_html(html)
        layout.addWidget(self._browser, 1)

    def _set_html(self, html: str):
        """Устанавливает HTML, оборачивая в базовый стиль."""
        wrapped = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                color: #2C2430;
                margin: 0;
                padding: 0;
            }}
            h1, h2, h3 {{
                color: #7A5C9A;
                font-weight: bold;
            }}
            p {{ margin: 6px 0; }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            td, th {{
                border: 1px solid #E8DFF0;
                padding: 6px 10px;
                text-align: left;
            }}
            th {{
                background: #EDE5F5;
                color: #7A5C9A;
                font-size: 10px;
                letter-spacing: 1px;
            }}
            code {{
                background: #F0EAF8;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }}
            .badge {{
                background: #E6D8FF;
                color: #7A5C9A;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
            .good {{ color: #2E7D32; font-weight: bold; }}
            .bad  {{ color: #C62828; font-weight: bold; }}
            .warn {{ color: #F57C00; font-weight: bold; }}
        </style>
        </head>
        <body>
        {html if html.strip() else "<p style='color:#9B8AAE;'>Плагин не предоставил контент.</p>"}
        </body>
        </html>
        """
        self._browser.setHtml(wrapped)

    def update_content(self, html: str):
        """Обновить HTML-контент без пересоздания вкладки."""
        self._set_html(html)