from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QWidget
from core.app_context import AppContext

class BasePage(ABC):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.widget = self.build_ui()

    @abstractmethod
    def build_ui(self) -> QWidget: ...

    def on_show(self): pass
    def on_hide(self): pass