# main.py
import multiprocessing
import sys
import ctypes

from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtWidgets import QApplication
from ui.main_window import VPNManager
from utils.version import __version__, __app_name__, __server_name__
from utils.i18n import tr

def main():
    # Защита от бесконечного спама окон в скомпилированном EXE
    if getattr(sys, 'frozen', False):
        multiprocessing.freeze_support()

    if not ctypes.windll.shell32.IsUserAnAdmin():
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, tr._("dialog_error_title"), tr._("main_admin_required"))
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)

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