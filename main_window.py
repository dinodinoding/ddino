# main_window.py

import os
import sys
import logging
import traceback
from datetime import datetime
import io # Import io module for StringIO

from PySide6.QtWidgets import QMainWindow, QTabWidget

# Import tab classes
from text_view_tab import TextViewTab
from graph_tab import GraphTab
from error_log_tab import ErrorLogTab
from registry_tab import RegistryTabGroup

# ===== [1] Log Directory and File Settings ===== #
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    filename=log_filename,
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8" # Explicitly set encoding to UTF-8
)

# Set up logging to console as well
class LoggerWriter:
    def __init__(self, stream, level):
        # If the original stream is None, use a dummy stream (io.StringIO)
        # This ensures self.stream always has a 'write' method.
        self.stream = stream if stream is not None else io.StringIO()
        self.level = level

    def write(self, message):
        if message.strip():
            self.level(message.strip())
        self.stream.write(message)

    def flush(self):
        self.stream.flush()

# Before redirecting, ensure sys.stdout and sys.stderr are not None
if sys.stdout is None:
    sys.stdout = io.StringIO() # Set to a dummy stream
if sys.stderr is None:
    sys.stderr = io.StringIO() # Set to a dummy stream

sys.stdout = LoggerWriter(sys.stdout, logging.info)
sys.stderr = LoggerWriter(sys.stderr, logging.error)

# Automatic exception logging
def exception_hook(exctype, value, tb):
    logging.error("Unhandled exception occurred", exc_info=(exctype, value, tb))
    traceback.print_exception(exctype, value, tb)

sys.excepthook = exception_hook

# ===== [2] Define MainWindow ===== #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        logging.info("Starting MainWindow initialization")
        self.setWindowTitle("Multi-Tool Application")
        self.setGeometry(100, 100, 1400, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab definition and creation order
        tab_list = [
            (RegistryTabGroup, "Registry Editor"),
            (TextViewTab,      "Text Viewer"),
            (GraphTab,         "Graph Log"),
            (ErrorLogTab,      "Error Logs"),
        ]

        for TabClass, title in tab_list:
            logging.info(f"Attempting to create {title} tab")
            try:
                tab = TabClass()
                self.tabs.addTab(tab, title)
                logging.info(f"{title} tab created successfully")
            except Exception as e:
                logging.error(f"[Tab Creation Failed] {title}: {e}")
                traceback.print_exc()

        logging.info("MainWindow initialization complete")

    def closeEvent(self, event):
        try:
            # Assuming 'registry_view' is an attribute of MainWindow
            # or accessible in some way. If RegistryTabGroup creates
            # this, you might need to access it differently, e.g.,
            # through self.tabs.widget(index) if it's the RegistryTabGroup instance.
            # For now, keeping as is, assuming it gets set directly on MainWindow.
            if hasattr(self, 'registry_view'):
                self.registry_view.save_settings()
                logging.info("Registry settings saved")
        except Exception as e:
            logging.error(f"[Shutdown Error] Error while saving registry settings: {e}")
            traceback.print_exc()
        super().closeEvent(event)
