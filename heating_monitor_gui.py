# GUI 스크립트 파일 전체를 이 코드로 교체하세요.

import os
import sys
import json
import subprocess
import signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt

# QProcess와 QPlainTextEdit는 더 이상 필요 없으므로 import에서 제거해도 됩니다.

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
        self.setGeometry(100, 100, 600, 270) # 콘솔이 없으므로 높이 조절
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
        self.start_button = QPushButton("Start / Restart Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)
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

    # --- 최종 수정된 start_monitoring 함수 ---
    def start_monitoring(self):
        if not self.save_settings():
            return
        
        self.stop_monitoring(is_starting=True)
        self.register_worker_autostart()
        
        try:
            worker_exe_path = os.path.abspath(get_path(self.worker_exe_name))
            if not os.path.exists(worker_exe_path):
                QMessageBox.critical(self, "Start Error", f"Worker executable not found:\n{worker_exe_path}")
                return

            # DETACHED_PROCESS 플래그를 사용하여 GUI와 완전히 독립된 프로세스를 생성합니다.
            # 이것이 GUI를 닫아도 워커가 꺼지지 않게 하는 핵심입니다.
            subprocess.Popen([worker_exe_path], creationflags=subprocess.DETACHED_PROCESS, close_fds=True)
            
            QMessageBox.information(self, "Success", "Monitoring started and registered for auto-run.")
            self.status_label.setText("Status: Monitoring Running.")

        except Exception as e:
            QMessageBox.critical(self, "Start Error", f"Failed to start the monitoring process directly.\nError: {e}")
            self.status_label.setText("Status: Start Failed.")

    def stop_monitoring(self, is_starting=False):
        self.unregister_worker_autostart()
        try:
            kill_command = f"taskkill /F /IM {self.worker_exe_name}"
            subprocess.run(kill_command, shell=True, check=True, capture_output=True)
            if not is_starting:
                QMessageBox.information(self, "Success", "Monitoring stopped and auto-run unregistered.")
        except subprocess.CalledProcessError:
            pass
        self.status_label.setText("Status: Idle.")

    def register_worker_autostart(self):
        exe_path = os.path.abspath(get_path(self.worker_exe_name))
        task_name = "HeatingWorkerAutoRun"
        cmd = ["schtasks", "/Create", "/TN", task_name, "/TR", f'"{exe_path}"', "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"]
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Register Error", f"작업 스케줄러 등록 실패: {e.stderr.decode('cp949', errors='ignore')}")

    def unregister_worker_autostart(self):
        task_name = "HeatingWorkerAutoRun"
        try:
            subprocess.run(f'schtasks /Delete /TN {task_name} /F', shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass
            
    def closeEvent(self, event):
        event.accept()

if __name__ == "__main__":
    # PyInstaller의 유령 프로세스 문제를 방지하기 위한 코드
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except ImportError:
        pass

    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec_())
