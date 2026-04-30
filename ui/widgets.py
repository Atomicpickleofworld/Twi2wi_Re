from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu
from PyQt6.QtCore import Qt
from utils.i18n import tr


class ConfigCard(QWidget):
    def __init__(self, cfg, parent=None, compact=False):
        super().__init__(parent)
        self.cfg = cfg
        self.setObjectName("card")
        self.setStyleSheet("background: transparent; border: none;")

        name = QLabel(cfg.get("name", "Без имени"))
        name.setObjectName("card_title")
        typ = QLabel(cfg.get("type", " ").upper())
        typ.setObjectName("card_host")

        btn = QPushButton("⋮")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet("border:none; background:transparent; font-size:16px; color: #7A5C9A;")
        btn.setToolTip(tr("widget_menu_tooltip"))
        btn.clicked.connect(self.show_menu)

        left = QVBoxLayout()
        left.addWidget(name)
        if not compact: left.addWidget(typ)
        left.setSpacing(2)
        left.setContentsMargins(8, 6, 8, 6)

        h = QHBoxLayout(self)
        h.addLayout(left)
        h.addStretch()
        h.addWidget(btn)
        h.setContentsMargins(0, 0, 0, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent_list = self.parent()
            if parent_list and hasattr(parent_list, 'setCurrentRow'):
                for i in range(parent_list.count()):
                    if parent_list.itemWidget(parent_list.item(i)) is self:
                        parent_list.setCurrentRow(i)
                        break
        super().mousePressEvent(event)

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
            QMenu::separator {
                height: 1px;
                background: #D8C8E8;
                margin: 4px 0;
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