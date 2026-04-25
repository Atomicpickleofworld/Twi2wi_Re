import sys
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import VPNManager

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        QMessageBox.critical(None, "Ошибка", "Запустите приложение от имени администратора!")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("Twi2wi Re")
    app.setApplicationVersion("1.3.0")
    win = VPNManager()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()