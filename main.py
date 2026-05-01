# main.py
import multiprocessing
import sys
import ctypes
from pathlib import Path

from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import VPNManager
from utils.version import __version__, __app_name__, __server_name__
from utils.i18n import tr


def main():
    if getattr(sys, 'frozen', False):
        multiprocessing.freeze_support()

    if not ctypes.windll.shell32.IsUserAnAdmin():
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, tr._("dialog_error_title"), tr._("main_admin_required"))
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)

    if getattr(sys, 'frozen', False):
        icon_path = Path(sys._MEIPASS) / "assets" / "icon.ico"
    else:
        icon_path = Path(__file__).resolve().parent / "assets" / "icon.ico"

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # ✅ Windows AppUserModelID (чтобы иконка не слетала)
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(__app_name__)
        except Exception:
            pass

    socket = QLocalSocket()
    socket.connectToServer(__server_name__)

    if socket.waitForConnected(500):
        print(tr._("main_already_running"))
        sys.exit(0)

    local_server = QLocalServer()
    local_server.listen(__server_name__)

    win = VPNManager()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()