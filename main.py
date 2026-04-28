# main.py
import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from ui.main_window import VPNManager
from utils.version import __version__, __app_name__


def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Ошибка", "Запустите приложение от имени администратора!")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)  

    win = VPNManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()