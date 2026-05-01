from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu
from PyQt6.QtCore import Qt
from utils.i18n import tr


class ConfigCard(QWidget):
    def __init__(self, cfg, parent=None, compact=False, show_fav_star=True, show_order_arrows=False, fav_order=0):
        super().__init__(parent)
        self.cfg = cfg
        self.setObjectName("card")
        self.setStyleSheet("background: transparent; border: none;")

        # Имя конфига
        name = QLabel(cfg.get("name", "Без имени"))
        name.setObjectName("card_title")

        # Тип
        typ = QLabel(cfg.get("type", " ").upper())
        typ.setObjectName("card_host")

        # Кнопки
        star_btn = None
        if show_fav_star:
            star_btn = QPushButton("★" if cfg.get("favorite") else "☆")
            star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            star_btn.setFixedSize(24, 24)
            star_btn.setStyleSheet(
                "QPushButton { border: none; color: #FFB74D; font-size: 16px; background: transparent; }"
                "QPushButton:hover { color: #FF9E43; }"
            )
            star_btn.clicked.connect(self.toggle_favorite)

        up_btn = None
        down_btn = None
        if show_order_arrows:
            up_btn = QPushButton("▲")
            up_btn.setFixedSize(24, 20)
            up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            up_btn.setStyleSheet(
                "QPushButton { border: none; color: #7A5C9A; font-size: 12px; background: transparent; }"
                "QPushButton:hover { color: #FF9E43; }"
            )
            up_btn.clicked.connect(self.move_up)

            down_btn = QPushButton("▼")
            down_btn.setFixedSize(24, 20)
            down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            down_btn.setStyleSheet(
                "QPushButton { border: none; color: #7A5C9A; font-size: 12px; background: transparent; }"
                "QPushButton:hover { color: #FF9E43; }"
            )
            down_btn.clicked.connect(self.move_down)

        menu_btn = QPushButton("⋮")
        menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_btn.setFixedSize(24, 24)
        menu_btn.setStyleSheet("border:none; background:transparent; font-size:16px; color: #7A5C9A;")
        menu_btn.setToolTip(tr("widget_menu_tooltip"))
        menu_btn.clicked.connect(self.show_menu)

        # Layout
        left = QVBoxLayout()
        left.addWidget(name)
        if not compact:
            left.addWidget(typ)
        left.setSpacing(2)
        left.setContentsMargins(8, 6, 8, 6)

        h = QHBoxLayout(self)
        h.addLayout(left)
        h.addStretch()
        if star_btn:
            h.addWidget(star_btn)
        if up_btn:
            h.addWidget(up_btn)
        if down_btn:
            h.addWidget(down_btn)
        h.addWidget(menu_btn)
        h.setContentsMargins(0, 0, 0, 0)

        self.star_btn = star_btn

    def toggle_favorite(self):
        top = self.window()
        if hasattr(top, "toggle_favorite_config"):
            top.toggle_favorite_config(self.cfg)

    def move_up(self):
        top = self.window()
        if hasattr(top, "move_favorite_up"):
            top.move_favorite_up(self.cfg)

    def move_down(self):
        top = self.window()
        if hasattr(top, "move_favorite_down"):
            top.move_favorite_down(self.cfg)

    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #D8C8E8;
                border-radius: 6px;
                padding: 4px 0;
            }
            QMenu::item {
                color: #2C2430;
                padding: 8px 20px;
                margin: 0 4px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #E6D8FF;
                color: #2C2430;
            }
        """)
        rename = menu.addAction(tr("config_rename"))
        delete = menu.addAction(tr("config_delete"))
        act = menu.exec(self.mapToGlobal(self.rect().bottomRight()))
        top = self.window()
        if act == rename and hasattr(top, "rename_config_by_obj"):
            top.rename_config_by_obj(self.cfg)
        elif act == delete and hasattr(top, "delete_config_by_obj"):
            top.delete_config_by_obj(self.cfg)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_list = self.parent()
            if parent_list and hasattr(parent_list, 'setCurrentRow'):
                for i in range(parent_list.count()):
                    if parent_list.itemWidget(parent_list.item(i)) is self:
                        parent_list.setCurrentRow(i)
                        break
        super().mousePressEvent(event)