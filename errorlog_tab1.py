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

# 콘솔 한글 깨짐 방지 설정 추가 (GUI의 print문에도 영향)
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding = 'utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding = 'utf-8')

# 🔧 [1] 실행 위치 정확하게 판단: .py, .exe 모두 호환
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)  # exe로 실행되는 경우
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))  # py로 실행되는 경우

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

def load_json(filename):
    path = get_path(filename)
    if not os.path.exists(path):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} 파일을 찾을 수 없습니다. 빈 설정으로 시작합니다.")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} 로드 성공: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] {filename} 파일 파싱 오류: {e}. 파일을 확인해주세요.")
        QMessageBox.critical(None, "설정 파일 오류", f"{filename} 파일을 읽는 중 오류가 발생했습니다.\n파일 내용을 확인해주세요.\n오류: {e}")
        return {}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] {filename} 로드 중 알 수 없는 오류: {e}")
        QMessageBox.critical(None, "설정 파일 오류", f"{filename} 파일을 읽는 중 알 수 없는 오류가 발생했습니다.\n오류: {e}")
        return {}


def save_json(filename, data):
    path = get_path(filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] {filename} 저장 성공.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] {filename} 저장 실패: {e}")
        QMessageBox.critical(None, "설정 파일 저장 오류", f"{filename} 파일을 저장할 수 없습니다.\n오류: {e}")


class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating 모니터링 설정")
        self.setGeometry(300, 300, 600, 400) # 창 크기 약간 증가

        self.settings = load_json("settings.json")
        self.worker_process = None
        self.worker_exe_name = "heating_worker.exe" # 워커 실행 파일 이름 통일

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 원본 로그 파일 경로 설정
        log_path_layout = QHBoxLayout()
        log_path_layout.addWidget(QLabel("Original Log File Path:"))
        self.log_path_input = QLineEdit()
        # 기존 설정에서 경로 불러오기, 없으면 빈 문자열
        self.log_path_input.setText(self.settings.get("original_log_file_path", ""))
        log_path_layout.addWidget(self.log_path_input)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_log_file)
        log_path_layout.addWidget(browse_button)
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

    def browse_log_file(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Browse' button clicked.")
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Original Log File", "", "Log Files (*.log *.txt);;All Files (*)")
        if file_path:
            self.log_path_input.setText(file_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Original log file path selected: {file_path}")
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
            "original_log_file_path": self.log_path_input.text()
        }
        save_json("settings.json", new_settings)
        self.log("Settings saved.")

    def start_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Start Monitoring' button clicked.")
        self.update_settings() # Save settings before starting

        original_log_path = self.log_path_input.text()
        if not original_log_path or not os.path.exists(original_log_path):
            self.log("Please specify a valid original log file path.")
            QMessageBox.warning(self, "Warning", "Please specify a valid original log file path.")
            return

        worker_exe = get_path(self.worker_exe_name)

        if not os.path.exists(worker_exe):
            self.log(f"Error: {self.worker_exe_name} not found.")
            QMessageBox.critical(self, "Error", f"{self.worker_exe_name} not found.\n{worker_exe}\nPlease ensure the worker script is compiled and in the same directory.")
            return

        try:
            # Subprocess Popen to run worker_exe, console will show if not --noconsole build
            self.worker_process = subprocess.Popen(worker_exe, cwd=BASE_PATH) 
            
            self.log("Monitoring started.")
            QMessageBox.information(self, "Started", "Heating monitoring has started in the background.\nCheck the worker console for debug messages.")
        except Exception as e:
            self.log(f"Failed to start worker: {e}")
            QMessageBox.critical(self, "Worker Start Failed", str(e))

    def stop_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI DEBUG] 'Stop Monitoring' button clicked.")
        pid_path = get_path("worker.pid")

        if not os.path.exists(pid_path):
            self.log("PID file not found - worker might be stopped or not running.")
            QMessageBox.warning(self, "PID Not Found", "No running worker process found.")
            return

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            
            self.log(f"Attempting to terminate worker process with PID {pid}...")
            # Terminate process on Windows using taskkill
            subprocess.run(f"taskkill /PID {pid} /F", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            
            os.remove(pid_path)
            self.log("Monitoring stopped.")
            QMessageBox.information(self, "Stopped", "Heating monitoring has been stopped.")
        except FileNotFoundError:
            self.log("PID file was already deleted.")
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
