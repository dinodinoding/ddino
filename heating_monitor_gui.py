# GUI 스크립트 파일 전체를 이 코드로 교체하세요.

import os
import sys
import json
import subprocess
import signal
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog, QPlainTextEdit
)
from PySide2.QtCore import Qt, QProcess

if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

class GUI_App(QWidget):
    def __init__(self):
        super(GUI_App, self).__init__()
        self.worker_exe_name = "heating_monitor_worker.exe"
        self.setWindowTitle("Heating Monitor - Control Panel")
        self.setGeometry(100, 100, 600, 420)

        self.worker_process = None
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout()
        interval_layout = QHBoxLayout()
        interval_label = QLabel("LOG Mode Timeout (minutes):")
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
        main_layout.addLayout(self._make_path_input(
            "CSV Log File Path:", "monitoring_log_input", "Browse...", self.browse_csv_file))
        main_layout.addLayout(self._make_path_input(
            "Raw .LOG File Path:", "log_file_input", "Browse...", self.browse_log_file))
        main_layout.addLayout(self._make_path_input(
            "Converted Log TXT File Path:", "converted_log_input", "Save As...", self.browse_txt_file_save))
        converter_layout = QHBoxLayout()
        converter_label = QLabel("Converter Executable Name:")
        self.converter_name_input = QLineEdit("g4_converter.exe")
        converter_layout.addWidget(converter_label)
        converter_layout.addWidget(self.converter_name_input)
        main_layout.addLayout(converter_layout)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(500)
        self.console_output.setFixedHeight(150)
        main_layout.addWidget(QLabel("Worker Console Output:"))
        main_layout.addWidget(self.console_output)
        self.setLayout(main_layout)

    def _make_path_input(self, label_text, attr_name, button_text, callback):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit()
        button = QPushButton(button_text)
        button.clicked.connect(callback)
        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        setattr(self, attr_name, line_edit)
        return layout

    def browse_csv_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if path: self.monitoring_log_input.setText(path)

    def browse_log_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Raw .log File", "", "Log Files (*.log);;All Files (*)")
        if path: self.log_file_input.setText(path)

    def browse_txt_file_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Converted TXT Output Path", "", "Text Files (*.txt);;All Files (*)")
        if path: self.converted_log_input.setText(path)

    def load_settings(self):
        config_path = get_path("settings.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.interval_spinbox.setValue(settings.get("interval_minutes", 60))
                self.threshold_spinbox.setValue(settings.get("threshold", 3))
                self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
                self.log_file_input.setText(settings.get("log_file_path", ""))
                self.converted_log_input.setText(settings.get("converted_log_file_path", ""))
                self.converter_name_input.setText(settings.get("converter_exe_name", "g4_converter.exe"))
                self.status_label.setText("Status: Settings loaded.")
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"settings.json 읽기 실패: {e}")
        else:
            self.status_label.setText("Status: Default settings in use.")

    def save_settings(self):
        config_path = get_path("settings.json")
        settings = {
            "interval_minutes": self.interval_spinbox.value(),
            "threshold": self.threshold_spinbox.value(),
            "monitoring_log_file_path": self.monitoring_log_input.text(),
            "log_file_path": self.log_file_input.text(),
            "converted_log_file_path": self.converted_log_input.text(),
            "converter_exe_name": self.converter_name_input.text(),
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.status_label.setText("Status: Settings saved.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"설정 저장 실패: {e}")
            return False
            
    def register_worker_autostart(self):
        exe_path = os.path.abspath(get_path(self.worker_exe_name))
        task_name = "HeatingWorkerAutoRun"
        cmd = ["schtasks", "/Create", "/TN", task_name, "/TR", f'"{exe_path}"', "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"]
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            self.console_output.appendPlainText("[INFO] Worker autostart 등록 완료.")
        except subprocess.CalledProcessError as e:
            self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 등록 실패: {e.stderr}")

    def unregister_worker_autostart(self):
        task_name = "HeatingWorkerAutoRun"
        try:
            subprocess.run(f'schtasks /Delete /TN {task_name} /F', shell=True, check=True, capture_output=True, text=True)
            self.console_output.appendPlainText("[INFO] Worker autostart 제거 완료.")
        except subprocess.CalledProcessError as e:
            self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 제거 실패: {e.stderr}")
            
    def start_monitoring(self):
        if not self.save_settings(): return
        worker_exe_path = os.path.abspath(get_path(self.worker_exe_name))
        if not os.path.exists(worker_exe_path):
            QMessageBox.warning(self, "Executable Not Found", f"{self.worker_exe_name} not found.")
            return
        self.stop_monitoring()
        self.worker_process = QProcess(self)
        self.worker_process.setWorkingDirectory(os.path.dirname(worker_exe_path))
        self.worker_process.setProcessChannelMode(QProcess.MergedChannels)
        self.worker_process.readyReadStandardOutput.connect(self.handle_worker_output)
        self.worker_process.start(worker_exe_path)
        if self.worker_process.waitForStarted(3000):
            self.status_label.setText("Status: Monitoring Started.")
            self.console_output.appendPlainText("[INFO] Worker started.")
            self.register_worker_autostart()
        else:
            self.console_output.appendPlainText(f"[ERROR] Failed to start worker: {self.worker_process.errorString()}")

    # --- 최종 핵심 수정 부분 ---
    # 워커가 보내는 출력을 'cp949'로 해석하여 한글이 깨지지 않게 합니다.
    def handle_worker_output(self):
        if self.worker_process:
            output = self.worker_process.readAllStandardOutput().data().decode("cp949", errors="ignore")
            self.console_output.appendPlainText(output.strip())
    # --- 수정 끝 ---

    def stop_monitoring(self):
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                self.console_output.appendPlainText(f"[INFO] Sent SIGTERM to PID {pid}.")
            except Exception as e:
                self.console_output.appendPlainText(f"[GUI WARNING] Couldn't kill worker via PID: {e}")
        if self.worker_process and self.worker_process.state() != QProcess.NotRunning:
            self.worker_process.kill()
            self.worker_process.waitForFinished()
        self.worker_process = None
        self.unregister_worker_autostart()
        self.status_label.setText("Status: Idle")
        self.console_output.appendPlainText("[INFO] Worker stopped.")

    def closeEvent(self, event):
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec())
