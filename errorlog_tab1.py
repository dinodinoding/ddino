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

# 콘솔 한글 깨짐 방지 설정 (GUI의 print문에도 영향)
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

# 실행 위치 정확하게 판단: .py, .exe 모두 호환
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)  # exe로 실행되는 경우
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))  # py로 실행되는 경우

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

def load_json(filename):
    path = get_path(filename)
    if not os.path.exists(path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} file not found. Starting with empty settings.")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} loaded successfully: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] {filename} file parsing error: {e}. Please check the file.")
        QMessageBox.critical(None, "Settings File Error", f"Error reading {filename} file.\nPlease check file content.\nError: {e}")
        return {}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Unknown error loading {filename}: {e}")
        QMessageBox.critical(None, "Settings File Error", f"Unknown error reading {filename} file.\nError: {e}")
        return {}

def save_json(filename, data):
    path = get_path(filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} saved successfully.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Failed to save {filename}: {e}")
        QMessageBox.critical(None, "Settings File Save Error", f"Failed to save {filename} file.\nError: {e}")

class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating Monitoring Settings")
        self.setGeometry(300, 300, 600, 400) # Window size slightly increased

        self.settings = load_json("settings.json")
        self.worker_process = None
        self.log_copier_process = None # log_copier 프로세스 추가
        self.worker_exe_name = "heating_worker.exe" # Worker executable name
        self.log_copier_exe_name = "log_copier.exe" # Log Copier executable name
        self.temp_log_file_name = "temp_log_for_worker.txt" # Log copier output file

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 원본 로그 파일 경로 설정 (이제 log_copier가 읽을 실제 원본 파일)
        log_path_layout = QHBoxLayout()
        log_path_layout.addWidget(QLabel("Original Log Source Path (for Log Copier):"))
        self.log_source_path_input = QLineEdit()
        # 기존 설정에서 경로 불러오기, 없으면 빈 문자열
        self.log_source_path_input.setText(self.settings.get("original_log_source_path", ""))
        log_path_layout.addWidget(self.log_source_path_input)
        
        browse_source_button = QPushButton("Browse...")
        browse_source_button.clicked.connect(self.browse_log_source_file)
        log_path_layout.addWidget(browse_source_button)
        layout.addLayout(log_path_layout)

        # 감시 시간 입력
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Monitoring Interval (minutes):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 360)
        self.interval_spin.setValue(self.settings.get("interval_minutes", 60))
        time_layout.addWidget(self.interval_spin)
        layout.addLayout(time_layout)

        # 허용 횟수 입력
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Threshold (occurrences):"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setValue(self.settings.get("threshold", 3))
        count_layout.addWidget(self.threshold_spin)
        layout.addLayout(count_layout)

        # 버튼
        self.on_button = QPushButton("Start Monitoring")
        self.on_button.clicked.connect(self.start_monitoring)
        layout.addWidget(self.on_button)

        self.off_button = QPushButton("Stop Monitoring")
        self.off_button.clicked.connect(self.stop_monitoring)
        layout.addWidget(self.off_button)

        # 상태 표시
        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        # 로그 창
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.setLayout(layout)

    def browse_log_source_file(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Browse Source' button clicked.")
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Original Log File Source", "", "Log Files (*.log *.txt);;All Files (*)")
        if file_path:
            self.log_source_path_input.setText(file_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Original log source path selected: {file_path}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] File selection cancelled.")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        self.status_label.setText(f"Status: {message}")
        # print(f"[{timestamp}] [GUI LOG] {message}") # GUI 로그는 GUI에만 표시

    def update_settings(self):
        new_settings = {
            "interval_minutes": self.interval_spin.value(),
            "threshold": self.threshold_spin.value(),
            "original_log_source_path": self.log_source_path_input.text(), # 이제 원본 로그 소스 경로
            "worker_target_log_file_path": get_path(self.temp_log_file_name) # 워커가 읽을 임시 파일 경로
        }
        save_json("settings.json", new_settings)
        self.log("Settings saved.")

    def start_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Start Monitoring' button clicked.")
        self.update_settings() # Save settings before starting

        original_log_source_path = self.log_source_path_input.text()
        if not original_log_source_path or not os.path.exists(original_log_source_path):
            self.log("Please specify a valid original log file source path.")
            QMessageBox.warning(self, "Warning", "Please specify a valid original log file source path.")
            return

        log_copier_exe = get_path(self.log_copier_exe_name)
        worker_exe = get_path(self.worker_exe_name)

        if not os.path.exists(log_copier_exe):
            self.log(f"Error: {self.log_copier_exe_name} not found.")
            QMessageBox.critical(self, "Error", f"{self.log_copier_exe_name} not found.\nPlease ensure the log copier is compiled and in the same directory.")
            return
        
        if not os.path.exists(worker_exe):
            self.log(f"Error: {self.worker_exe_name} not found.")
            QMessageBox.critical(self, "Error", f"{self.worker_exe_name} not found.\nPlease ensure the worker is compiled and in the same directory.")
            return

        try:
            # 1. Start Log Copier
            self.log_copier_process = subprocess.Popen([log_copier_exe, original_log_source_path, get_path(self.temp_log_file_name)], cwd=BASE_PATH)
            self.log(f"Log copier started from: '{original_log_source_path}' to: '{get_path(self.temp_log_file_name)}'")
            time.sleep(2) # Give a moment for copier to start and perhaps create the file

            # 2. Start Worker Process
            # No 'creationflags' to ensure console window appears for debugging
            self.worker_process = subprocess.Popen(worker_exe, cwd=BASE_PATH) 
            
            self.log("Monitoring started.")
            QMessageBox.information(self, "Started", "Heating monitoring has started in the background.\nCheck the worker console for debug messages.")
        except Exception as e:
            self.log(f"Failed to start processes: {e}")
            QMessageBox.critical(self, "Process Start Failed", str(e))

    def stop_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Stop Monitoring' button clicked.")
        
        # Stop Log Copier
        if self.log_copier_process and self.log_copier_process.poll() is None:
            try:
                self.log_copier_process.terminate()
                self.log(f"Log copier process terminated.")
                time.sleep(1) # Give process time to terminate
            except Exception as e:
                self.log(f"Failed to terminate log copier: {e}")

        # Stop Worker Process using PID file
        pid_path = get_path("worker.pid")

        if not os.path.exists(pid_path):
            self.log("Worker PID file not found - worker might be stopped or not running.")
            QMessageBox.warning(self, "PID Not Found", "No running worker process found for termination.")
            return

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            
            self.log(f"Attempting to terminate worker process with PID {pid}...")
            subprocess.run(f"taskkill /PID {pid} /F", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Clean up PID and temporary log files
            os.remove(pid_path)
            temp_log_path = get_path(self.temp_log_file_name)
            if os.path.exists(temp_log_path):
                os.remove(temp_log_path)
                self.log(f"Temporary log file '{temp_log_path}' deleted.")
            
            self.log("Monitoring stopped.")
            QMessageBox.information(self, "Stopped", "Heating monitoring has been stopped.")
        except FileNotFoundError:
            self.log("PID file was already deleted or not found.")
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to terminate process. PID {pid} not found or permission issue. Error: {e.stderr.decode(errors='ignore')}")
            QMessageBox.critical(self, "Termination Failed", f"Failed to terminate process: {e.stderr.decode(errors='ignore')}")
        except Exception as e:
            self.log(f"An error occurred while stopping monitoring: {e}")
            QMessageBox.critical(self, "Termination Failed", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = HeatingMonitorGUI()
    gui.show()
    sys.exit(app.exec_())

