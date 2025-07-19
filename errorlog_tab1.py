import os
import sys
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog, QPlainTextEdit
)
from PySide2.QtCore import Qt, QProcess
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

class GUI_App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating Monitor Setup")
        self.setGeometry(100, 100, 500, 300)

        self.worker_process = None
        self.init_ui()
        self.load_settings()
        self.check_worker_running()

    def init_ui(self):
        main_layout = QVBoxLayout()

        interval_layout = QHBoxLayout()
        interval_label = QLabel("Monitoring Interval (minutes):")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 1440)
        self.interval_spinbox.setValue(60)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)
        main_layout.addLayout(interval_layout)

        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (occurrences):")
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 100)
        self.threshold_spinbox.setValue(3)
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        main_layout.addLayout(threshold_layout)

        log_path_layout = QHBoxLayout()
        monitoring_log_label = QLabel("CSV Log File Path (for Worker):")
        self.monitoring_log_input = QLineEdit()
        self.monitoring_log_input.setPlaceholderText("Select the path to your CSV log file.")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_log_file)
        log_path_layout.addWidget(monitoring_log_label)
        log_path_layout.addWidget(self.monitoring_log_input)
        log_path_layout.addWidget(browse_button)
        main_layout.addLayout(log_path_layout)

        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(500)
        self.console_output.setFixedHeight(150)
        main_layout.addWidget(QLabel("Worker Console Output (debug):"))
        main_layout.addWidget(self.console_output)

        self.setLayout(main_layout)

    def browse_log_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            self.monitoring_log_input.setText(file_path)

    def load_settings(self):
        config_path = get_path("settings.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.interval_spinbox.setValue(settings.get("interval_minutes", 60))
                    self.threshold_spinbox.setValue(settings.get("threshold", 3))
                    self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
            except Exception as e:
                QMessageBox.warning(self, "Load Settings Error", f"Failed to load settings.json: {e}")
                self.status_label.setText("Status: Error loading settings.")
        else:
            self.status_label.setText("Status: settings.json not found. Using defaults.")

    def save_settings(self):
        config_path = get_path("settings.json")
        settings = {
            "interval_minutes": self.interval_spinbox.value(),
            "threshold": self.threshold_spinbox.value(),
            "monitoring_log_file_path": self.monitoring_log_input.text()
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.status_label.setText("Status: Settings saved.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Settings Error", f"Failed to save settings.json: {e}")
            self.status_label.setText("Status: Error saving settings.")
            return False

    def check_worker_running(self):
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read())
                os.kill(pid, 0)
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.status_label.setText("Status: Monitoring Running (resumed)")
                self.console_output.appendPlainText("[INFO] Worker already running.")
            except Exception:
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def register_worker_autostart(self):
        exe_path = os.path.abspath(get_path("heating_worker.exe"))
        task_name = "HeatingWorkerAutoRun"

        cmd = [
            "schtasks", "/Create",
            "/TN", task_name,
            "/TR", f'"{exe_path}"',
            "/SC", "ONSTART",
            "/RL", "HIGHEST",
            "/F"
        ]
        try:
            subprocess.run(" ".join(cmd), shell=True, check=True)
            self.console_output.appendPlainText("[INFO] Worker autostart 등록 완료.")
        except subprocess.CalledProcessError as e:
            self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 등록 실패: {e}")

    def unregister_worker_autostart(self):
        task_name = "HeatingWorkerAutoRun"
        try:
            subprocess.run(f'schtasks /Delete /TN {task_name} /F', shell=True, check=True)
            self.console_output.appendPlainText("[INFO] Worker autostart 제거 완료.")
        except subprocess.CalledProcessError as e:
            self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 제거 실패: {e}")

    def start_monitoring(self):
        if not self.save_settings():
            return

        log_path = self.monitoring_log_input.text()
        if not log_path or not os.path.exists(log_path):
            QMessageBox.warning(self, "Invalid Path", "Log file path is missing or invalid.")
            return

        self.stop_monitoring()

        worker_exe_path = os.path.abspath(get_path("heating_worker.exe"))
        if not os.path.exists(worker_exe_path):
            QMessageBox.warning(self, "Executable Not Found", "heating_worker.exe not found.")
            return

        try:
            self.worker_process = QProcess(self)
            self.worker_process.setWorkingDirectory(os.path.dirname(worker_exe_path))
            self.worker_process.setProcessChannelMode(QProcess.MergedChannels)
            self.worker_process.readyReadStandardOutput.connect(self.handle_worker_output)

            self.worker_process.start(worker_exe_path)

            if self.worker_process.waitForStarted(3000):
                self.status_label.setText("Status: Monitoring Started.")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.console_output.appendPlainText("[INFO] Worker started.")
                self.register_worker_autostart()
            else:
                self.console_output.appendPlainText("[ERROR] Failed to start worker.")

        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Failed to start worker: {e}")
            self.status_label.setText("Status: Error starting worker.")

    def handle_worker_output(self):
        if self.worker_process:
            output = self.worker_process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            self.console_output.appendPlainText(output.strip())

    def stop_monitoring(self):
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
            except Exception as e:
                self.console_output.appendPlainText(f"[GUI WARNING] Couldn't kill worker via PID: {e}")
        if self.worker_process:
            self.worker_process.kill()
            self.worker_process.waitForFinished()
            self.worker_process = None

        self.unregister_worker_autostart()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: Idle")
        self.console_output.appendPlainText("[INFO] Worker stopped.")

    def closeEvent(self, event):
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec_())