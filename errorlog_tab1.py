import sys
import os
import subprocess
import threading
import datetime
import csv
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread

# --- Assume the rest of your GUI.py code is here ---
# Since I don't have your full GUI.py, I'm providing a conceptual full file.
# You should replace this with YOUR ACTUAL GUI.py content
# and then apply the change below in your start_monitoring method.

class WorkerThread(QThread):
    # This is a placeholder. In your actual setup, heating_worker.py is a separate executable.
    # This class might not be directly used in GUI.py if it's launching an EXE.
    # However, a QThread could be used for other background tasks within the GUI itself.
    finished = Signal()
    progress = Signal(str)

    def run(self):
        # This part would typically interact with the worker if it were a function
        # or module directly imported. Since it's an EXE, this QThread might be
        # for a different purpose or not present.
        self.progress.emit("Worker thread started (conceptual)...")
        time.sleep(2) # Simulate work
        self.progress.emit("Worker thread finished (conceptual).")
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating Monitor GUI")
        self.setGeometry(100, 100, 600, 400)

        self.worker_process = None
        self.log_file_path = ""

        self.init_ui()
        self.check_worker_process_timer = QTimer(self)
        self.check_worker_process_timer.timeout.connect(self.check_worker_status)
        self.check_worker_process_timer.start(1000) # Check every 1 second

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Log File Path Selection
        log_path_layout = QHBoxLayout()
        self.log_path_label = QLabel("CSV Log Path:")
        self.log_path_line_edit = QLineEdit()
        self.log_path_button = QPushButton("Browse")
        self.log_path_button.clicked.connect(self.select_log_file)
        log_path_layout.addWidget(self.log_path_label)
        log_path_layout.addWidget(self.log_path_line_edit)
        log_path_layout.addWidget(self.log_path_button)
        main_layout.addLayout(log_path_layout)

        # Control Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.stop_button = QPushButton("Stop Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False) # Disable stop initially
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # Status Display
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        # Log Display (Optional, for showing what heating_worker might output if it were connected)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)

    def select_log_file(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getSaveFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            self.log_file_path = file_path
            self.log_path_line_edit.setText(self.log_file_path)
            self.status_label.setText(f"Status: Log path set to {self.log_file_path}")

    def start_monitoring(self):
        if not self.log_file_path:
            QMessageBox.warning(self, "Warning", "Please select a CSV log file path first.")
            return

        if self.worker_process and self.worker_process.poll() is None:
            QMessageBox.information(self, "Info", "Monitoring is already running.")
            return

        worker_exe_name = "heating_worker.exe" # This should match your compiled worker name
        # Determine the path to the worker executable
        # In a PyInstaller onefile app, __file__ is inside a temp folder.
        # sys._MEIPASS is the path to the temp folder where resources are extracted.
        if getattr(sys, 'frozen', False):
            # Running as a PyInstaller bundle
            application_path = os.path.dirname(sys.executable)
        else:
            # Running as a normal Python script
            application_path = os.path.dirname(os.path.abspath(__file__))

        worker_exe_path = os.path.join(application_path, worker_exe_name)

        if not os.path.exists(worker_exe_path):
            QMessageBox.critical(self, "Error", f"Worker executable not found at: {worker_exe_path}")
            self.status_label.setText("Status: Error - Worker not found.")
            return

        try:
            # *** THE MODIFIED PART IS HERE ***
            # Launch the worker process detached and redirect stdout/stderr to DEVNULL
            self.worker_process = subprocess.Popen(
                [worker_exe_path, self.log_file_path], # Pass log file path as an argument
                creationflags=subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,   # Redirect standard output to null
                stderr=subprocess.DEVNULL    # Redirect standard error to null
            )
            # *** END OF MODIFIED PART ***

            self.status_label.setText(f"Status: Monitoring started. Worker PID: {self.worker_process.pid}")
            self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Started worker process {self.worker_process.pid}")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start worker process: {e}")
            self.status_label.setText("Status: Failed to start monitoring.")

    def stop_monitoring(self):
        if self.worker_process and self.worker_process.poll() is None:
            try:
                # Terminate the process gently first
                self.worker_process.terminate()
                self.status_label.setText("Status: Sending terminate signal to worker...")
                # Give it a moment to terminate
                time.sleep(1)
                if self.worker_process.poll() is None: # If it's still running, kill it
                    self.worker_process.kill()
                    self.status_label.setText("Status: Worker process forcefully terminated.")
                else:
                    self.status_label.setText("Status: Monitoring stopped.")
                self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Stopped worker process.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to stop worker process: {e}")
                self.status_label.setText("Status: Failed to stop monitoring.")
            finally:
                self.worker_process = None
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
        else:
            self.status_label.setText("Status: Monitoring is not running.")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False) # Ensure stop button is disabled if worker is not running

    def check_worker_status(self):
        if self.worker_process:
            if self.worker_process.poll() is not None: # Worker has terminated
                self.status_label.setText("Status: Worker process has stopped unexpectedly.")
                self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Worker process terminated.")
                self.worker_process = None
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
            else:
                self.status_label.setText(f"Status: Monitoring running. Worker PID: {self.worker_process.pid}")


    def closeEvent(self, event):
        # Ensure worker process is stopped when GUI closes
        self.stop_monitoring()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
