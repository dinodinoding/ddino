import os
import sys
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QTextEdit, QLineEdit, QFileDialog
)
from PySide2.QtCore import Qt
from datetime import datetime
import time
import signal # 시그널 처리를 위해 필요

# PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
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

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Monitoring Interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Monitoring Interval (minutes):")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 1440) # 1분 ~ 24시간
        self.interval_spinbox.setValue(60) # 기본값 60분
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)
        main_layout.addLayout(interval_layout)

        # Threshold
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (occurrences):")
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 100)
        self.threshold_spinbox.setValue(3) # 기본값 3회
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        main_layout.addLayout(threshold_layout)

        # ** 모니터링할 CSV 로그 파일 경로 입력 **
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
        
        # Action Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False) # 처음에는 비활성화
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # Status Label
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        # Console Output (for debugging) - Optional, can be removed if not needed for end-user
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFixedHeight(100) # 높이 제한
        main_layout.addWidget(QLabel("Worker Console Output (for debug):"))
        main_layout.addWidget(self.console_output)
        
        self.setLayout(main_layout)

    def browse_log_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;Log Files (*.log *.txt);;All Files (*)")
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
                    # 'monitoring_log_file_path' 사용
                    self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
            except Exception as e:
                QMessageBox.warning(self, "Load Settings Error", f"Failed to load settings.json: {e}")
                self.status_label.setText(f"Status: Error loading settings. ({e})")
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Settings saved: {settings}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Settings Error", f"Failed to save settings.json: {e}")
            self.status_label.setText(f"Status: Error saving settings. ({e})")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Failed to save settings: {e}")
            return False

    def start_monitoring(self):
        if not self.save_settings():
            return # 설정 저장 실패 시 시작하지 않음

        # 모니터링할 로그 파일 경로 확인
        monitoring_log_path = self.monitoring_log_input.text()
        if not monitoring_log_path:
            QMessageBox.warning(self, "Missing Path", "Please select the CSV Log File Path to monitor.")
            self.status_label.setText("Status: Waiting for log path.")
            return
        if not os.path.exists(monitoring_log_path):
            QMessageBox.warning(self, "File Not Found", f"The specified CSV log file does not exist: {monitoring_log_path}")
            self.status_label.setText("Status: CSV log file not found.")
            return

        # 이전 프로세스 정리 (안전하게)
        self.stop_monitoring()
        time.sleep(1) # 프로세스 종료 대기

        try:
            # heating_worker.exe 실행 (이제 직접 CSV 파일을 모니터링)
            worker_exe_path = get_path("heating_worker.exe")
            if os.path.exists(worker_exe_path):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Starting heating_worker.exe...")
                # worker.py는 settings.json에서 'monitoring_log_file_path'를 읽음
                self.worker_process = subprocess.Popen(
                    [worker_exe_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE, # 콘솔 창을 띄웁니다.
                )
                self.status_label.setText("Status: Monitoring Started.")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] heating_worker.exe started (PID: {self.worker_process.pid}).")

            else:
                QMessageBox.warning(self, "Executable Not Found", "heating_worker.exe not found in the current directory.")
                self.status_label.setText("Status: heating_worker.exe missing.")
                self.stop_monitoring() # 실패 시 정리
                return

        except Exception as e:
            QMessageBox.critical(self, "Start Error", f"Failed to start process: {e}")
            self.status_label.setText(f"Status: Error starting monitoring. ({e})")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Failed to start process: {e}")
            self.stop_monitoring() # 실패 시 정리

    def stop_monitoring(self):
        self.status_label.setText("Status: Stopping Monitoring...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Stopping monitoring initiated.")

        # 워커 프로세스 종료
        if self.worker_process and self.worker_process.poll() is None:
            try:
                pid_path = get_path("worker.pid")
                if os.path.exists(pid_path):
                    with open(pid_path, "r") as f:
                        pid = int(f.read().strip())
                    os.kill(pid, signal.SIGTERM) # SIGTERM 시그널 전송
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Sent SIGTERM to worker PID: {pid}")
                    self.worker_process.wait(timeout=5)
                else:
                    self.worker_process.terminate()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Terminated worker process directly (PID file not found or corrupted).")
                
                if self.worker_process.poll() is None:
                    self.worker_process.kill()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI WARNING] Worker process killed forcefully.")
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Error stopping worker process: {e}")
                self.worker_process = None
            self.worker_process = None
        elif self.worker_process:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Worker process already terminated.")
            self.worker_process = None


        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: Idle")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Monitoring stopped.")

    def closeEvent(self, event):
        self.stop_monitoring() # GUI 종료 시 워커도 종료
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec_())

