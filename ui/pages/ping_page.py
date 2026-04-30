# ui/pages/ping_page.py
from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize, QRect, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QLayout, QSizePolicy,
)
from core.ping_worker import PingWorker
from utils.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import VPNManager

# ── Стандартные хосты (их нельзя удалить, но можно скрыть) ────────────────
DEFAULT_PING_HOSTS = [
    ("GOOGLE DNS",    "8.8.8.8"),
    ("CLOUDFLARE",    "1.1.1.1"),
    ("YANDEX DNS",    "77.88.8.8"),
    ("STRINOVA JP",   "101.32.143.247"),
]

# Имена стандартных хостов для отделения от пользовательских
DEFAULT_NAMES = {name for name, _ in DEFAULT_PING_HOSTS}

# ────────────────────────────────────────────────────────────────────────
# FlowLayout – адаптивная раскладка виджетов с переносом строк
# ────────────────────────────────────────────────────────────────────────

class FlowLayout(QLayout):
    """Раскладывает виджеты слева направо, сверху вниз, автоматически перенося строки."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[tuple[QLayoutItem, QRect]] = []

    def addItem(self, item):
        self._items.append((item, QRect()))

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index][0]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            item, _ = self._items.pop(index)
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item, _ in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool):
        margin = self.contentsMargins()
        max_width = rect.width() - margin.left() - margin.right()
        x = margin.left()
        y = margin.top()
        line_height = 0
        spacing = self.spacing()

        for item, _ in self._items:
            size = item.sizeHint()
            if x + size.width() > max_width and line_height > 0:
                x = margin.left()
                y += line_height + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + spacing
            line_height = max(line_height, size.height())

        total_height = y + line_height + margin.bottom()
        return total_height

# ────────────────────────────────────────────────────────────────────────
# Контроллер пинга
# ────────────────────────────────────────────────────────────────────────

class PingController:
    def __init__(self, win: "VPNManager"):
        self.win = win
        self.ping_hosts: dict[str, str] = {}   # name -> host
        self.ping_order: list[str] = []        # порядок отображения
        self.ping_favorites: set[str] = set()
        self.ping_cards: dict[str, QFrame] = {}# активные карточки
        self.ping_worker: PingWorker | None = None

    def setup(self):
        self.load_ping_state()
        # Добавляем стандартные хосты, если их ещё нет
        for name, host in DEFAULT_PING_HOSTS:
            if name not in self.ping_hosts:
                self.ping_hosts[name] = host
                self.ping_order.append(name)
        self.refresh_ping_grid()
        self.start_ping_monitor()

    def cleanup(self):
        if self.ping_worker and self.ping_worker.isRunning():
            self.ping_worker.stop()
            self.ping_worker.wait(1000)

    def start_ping_monitor(self):
        hosts = [(name, self.ping_hosts[name]) for name in self.ping_order if name in self.ping_hosts]
        self.ping_worker = PingWorker(hosts)
        self.ping_worker.result.connect(self.on_ping_result)
        self.ping_worker.start()

    # ── Управление хостами ─────────────────────────────────────────────

    def add_ping_from_input(self):
        txt = self.win.ping_input.text().strip()
        if not txt:
            return
        host = txt.split(":")[0]
        name = host.upper() if "." not in host else host.split(".")[0].upper()
        base = name
        cnt = 1
        while name in self.ping_hosts:
            name = f"{base}({cnt})"
            cnt += 1
        self.ping_hosts[name] = host
        self.ping_order.append(name)
        if self.ping_worker:
            self.ping_worker.add_host(name, host)
        self.refresh_ping_grid()
        self.save_ping_state()
        self.win.ping_input.clear()

    def remove_ping_host(self, name: str):
        if name not in self.ping_hosts or name in DEFAULT_NAMES:
            return   # стандартные не удаляем
        del self.ping_hosts[name]
        self.ping_order.remove(name)
        self.ping_favorites.discard(name)
        if self.ping_worker:
            self.ping_worker.remove_host(name)
        self.refresh_ping_grid()
        self.save_ping_state()

    def toggle_favorite(self, name: str):
        if name in self.ping_favorites:
            self.ping_favorites.remove(name)
        else:
            self.ping_favorites.add(name)
        self.save_ping_state()
        self.refresh_ping_grid()

    def move_host_up(self, name: str):
        idx = self.ping_order.index(name) if name in self.ping_order else -1
        if idx > 0:
            self.ping_order[idx], self.ping_order[idx-1] = self.ping_order[idx-1], self.ping_order[idx]
            self.save_ping_state()
            self.refresh_ping_grid()

    def move_host_down(self, name: str):
        idx = self.ping_order.index(name) if name in self.ping_order else -1
        if 0 <= idx < len(self.ping_order) - 1:
            self.ping_order[idx], self.ping_order[idx+1] = self.ping_order[idx+1], self.ping_order[idx]
            self.save_ping_state()
            self.refresh_ping_grid()

    # ── Отрисовка сетки ────────────────────────────────────────────────

    def refresh_ping_grid(self):
        container = self.win.ping_container
        # Удаляем всё, что было
        layout = container.layout()
        if layout is None:
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # очищаем вложенные лэйауты
                self._clear_layout(item.layout())
        self.ping_cards.clear()

        # Собираем списки в нужном порядке
        fav_names = [n for n in self.ping_order if n in self.ping_favorites and n in self.ping_hosts]
        default_names = [n for n in self.ping_order if n in DEFAULT_NAMES and n not in self.ping_favorites and n in self.ping_hosts]
        user_names = [n for n in self.ping_order if n not in DEFAULT_NAMES and n not in self.ping_favorites and n in self.ping_hosts]

        sections = []
        if fav_names:
            sections.append((tr("ping_section_favorites"), fav_names))
        if default_names:
            sections.append((tr("ping_section_defaults"), default_names))
        if user_names:
            sections.append((tr("ping_section_user"), user_names))

        for title, names in sections:
            # Подпись секции
            lbl = QLabel(title)
            lbl.setObjectName("section_title")
            lbl.setStyleSheet("color: #7A5C9A; font-size: 11px; letter-spacing: 2px; margin-top: 8px;")
            layout.addWidget(lbl)

            # Flow-контейнер для карточек
            flow_widget = QWidget()
            flow_layout = FlowLayout(flow_widget, margin=0, spacing=12)
            for name in names:
                host = self.ping_hosts[name]
                is_fav = name in self.ping_favorites
                card = create_ping_card(self.win, name, host, is_fav)
                card.setFixedWidth(280)
                flow_layout.addWidget(card)
                self.ping_cards[name] = card
            layout.addWidget(flow_widget)

        # Растягивающийся спейсер, если карточек нет
        if not self.ping_cards:
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout.addWidget(spacer)

    def _clear_layout(self, layout):
        """Рекурсивно удаляет все элементы лэйаута."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ── Обработка результатов пинга ───────────────────────────────────

    def on_ping_result(self, name: str, ms: int, loss: float, stats: dict):
        card = self.ping_cards.get(name)
        if not card:
            return
        value_label = card.value_label
        if ms == -1:
            value_label.setText(tr("ping_timeout"))
            value_label.setStyleSheet("color: #000000;")
        else:
            value_label.setText(f"{ms} ms")
            if ms < 100:
                color = "#2E7D32"
            elif ms <= 200:
                color = "#F57C00"
            else:
                color = "#C62828"
            value_label.setStyleSheet(f"color: {color};")

        loss_int = int(loss)
        loss_label = card.loss_label
        loss_label.setText(tr("ping_loss_label", loss=loss_int))
        if loss_int == 0:
            loss_color = "#2E7D32"
        elif loss_int <= 10:
            loss_color = "#F57C00"
        else:
            loss_color = "#C62828"
        loss_label.setStyleSheet(f"color: {loss_color}; font-size: 11px;")

        stats_label = card.stats_label
        if stats["min"] >= 0:
            stats_label.setText(f"min {stats['min']}  avg {stats['avg']}  max {stats['max']} ms")
        else:
            stats_label.setText("—")

        self.win.sandbox_manager.trigger_hook("on_ping_result", name=name, ms=ms, loss=loss)

    # ── Сохранение / загрузка ─────────────────────────────────────────

    def load_ping_state(self):
        cfg_path = self._config_file()
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                saved_hosts = data.get("ping_hosts", {})
                if isinstance(saved_hosts, dict):
                    self.ping_hosts = {k: v for k, v in saved_hosts.items() if isinstance(v, str)}
                order = data.get("ping_order", [])
                self.ping_order = [n for n in order if n in self.ping_hosts]
                for name in self.ping_hosts:
                    if name not in self.ping_order:
                        self.ping_order.append(name)
                favs = data.get("ping_favorites", [])
                self.ping_favorites = set(favs) if isinstance(favs, list) else set()
            except Exception:
                self.ping_order = list(self.ping_hosts.keys())
                self.ping_favorites = set()
        else:
            self.ping_order = list(self.ping_hosts.keys())

    def save_ping_state(self):
        cfg_path = self._config_file()
        try:
            data = {}
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            data["ping_hosts"] = self.ping_hosts
            data["ping_order"] = self.ping_order
            data["ping_favorites"] = list(self.ping_favorites)
            cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Failed to save ping state: {e}")

    def _config_file(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "ui_config.json"


# ────────────────────────────────────────────────────────────────────────
# UI фабрика
# ────────────────────────────────────────────────────────────────────────

def build_ping_page(win: "VPNManager") -> QWidget:
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(32, 32, 32, 32)
    l.setSpacing(16)

    t = QLabel(tr("ping_page_title"))
    t.setObjectName("section_title")
    l.addWidget(t)

    # Поле ввода
    input_frame = QFrame()
    input_frame.setObjectName("card")
    input_frame.setStyleSheet("border: 1px solid #FF9E43;")
    ifr = QHBoxLayout(input_frame)
    ifr.setContentsMargins(10, 6, 10, 6)
    ifr.setSpacing(10)

    win.ping_input = QLineEdit()
    win.ping_input.setPlaceholderText(tr("ping_input_placeholder"))
    win.ping_input.returnPressed.connect(win.add_ping_from_input)

    win.ping_add_btn = QPushButton(tr("btn_add_ping"))
    win.ping_add_btn.setObjectName("add_btn")
    win.ping_add_btn.clicked.connect(win.add_ping_from_input)

    ifr.addWidget(win.ping_input)
    ifr.addWidget(win.ping_add_btn)
    l.addWidget(input_frame)

    # Скроллируемая область
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border:none; background:transparent;")

    # Контейнер с вертикальным лэйаутом (будет заполняться в refresh_ping_grid)
    win.ping_container = QWidget()
    win.ping_container.setLayout(QVBoxLayout())
    scroll.setWidget(win.ping_container)
    l.addWidget(scroll, 1)

    return w


def create_ping_card(win: "VPNManager", name: str, host: str, is_fav: bool) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    cl = QVBoxLayout(card)
    cl.setSpacing(4)

    # Верхняя строка: звезда, имя, кнопки
    top_row = QHBoxLayout()
    star_btn = QPushButton("★" if is_fav else "☆")
    star_btn.setFixedSize(24, 24)
    star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    star_btn.setStyleSheet(
        "QPushButton { border: none; color: #FFB74D; font-size: 16px; background: transparent; }"
        "QPushButton:hover { color: #FF9E43; }"
    )
    star_btn.clicked.connect(lambda _, n=name: win.ping_ctrl.toggle_favorite(n))
    top_row.addWidget(star_btn)

    lbl_n = QLabel(name)
    lbl_n.setObjectName("card_title")
    top_row.addWidget(lbl_n)
    top_row.addStretch()

    btn_up = QPushButton("▲")
    btn_up.setFixedSize(24, 20)
    btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_up.setStyleSheet(
        "QPushButton { border: none; color: #7A5C9A; font-size: 12px; background: transparent; }"
        "QPushButton:hover { color: #FF9E43; }"
    )
    btn_up.clicked.connect(lambda _, n=name: win.ping_ctrl.move_host_up(n))
    top_row.addWidget(btn_up)

    btn_down = QPushButton("▼")
    btn_down.setFixedSize(24, 20)
    btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_down.setStyleSheet(
        "QPushButton { border: none; color: #7A5C9A; font-size: 12px; background: transparent; }"
        "QPushButton:hover { color: #FF9E43; }"
    )
    btn_down.clicked.connect(lambda _, n=name: win.ping_ctrl.move_host_down(n))
    top_row.addWidget(btn_down)

    btn_remove = QPushButton("✕")
    btn_remove.setFixedSize(24, 20)
    btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_remove.setStyleSheet(
        "QPushButton { border: none; color: #C62828; font-size: 14px; font-weight: bold; background: transparent; }"
        "QPushButton:hover { color: #ff5252; }"
    )
    btn_remove.clicked.connect(lambda _, n=name: win.ping_ctrl.remove_ping_host(n))
    top_row.addWidget(btn_remove)

    cl.addLayout(top_row)

    lbl_h = QLabel(host)
    lbl_h.setObjectName("card_host")
    cl.addWidget(lbl_h)

    lbl_v = QLabel(tr("ping_loading"))
    lbl_v.setObjectName("card_value_none")
    cl.addWidget(lbl_v)

    lbl_l = QLabel(tr("ping_loss_none"))
    lbl_l.setStyleSheet("color: #7A5C9A; font-size: 11px;")
    cl.addWidget(lbl_l)

    lbl_stats = QLabel("—")
    lbl_stats.setStyleSheet("color: #9B8AAE; font-size: 10px; margin-top: 2px;")
    cl.addWidget(lbl_stats)

    card.value_label = lbl_v
    card.loss_label = lbl_l
    card.stats_label = lbl_stats
    return card