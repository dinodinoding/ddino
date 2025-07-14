import os
import sys
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QTextEdit
)
from PySide2.QtCore import Qt
from datetime import datetime

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
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    path = get_path(filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating 모니터링 설정")
        self.setGeometry(300, 300, 500, 350)

        self.settings = load_json("settings.json")
        self.worker_process = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 감시 시간 입력
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("감시 시간 (분):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 360)
        self.interval_spin.setValue(self.settings.get("interval_minutes", 60))
        time_layout.addWidget(self.interval_spin)
        layout.addLayout(time_layout)

        # 허용 횟수 입력
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("허용 횟수:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setValue(self.settings.get("threshold", 3))
        count_layout.addWidget(self.threshold_spin)
        layout.addLayout(count_layout)

        # 버튼
        self.on_button = QPushButton("모니터링 시작")
        self.on_button.clicked.connect(self.start_monitoring)
        layout.addWidget(self.on_button)

        self.off_button = QPushButton("모니터링 중지")
        self.off_button.clicked.connect(self.stop_monitoring)
        layout.addWidget(self.off_button)

        # 상태 표시
        self.status_label = QLabel("상태: 대기 중")
        layout.addWidget(self.status_label)

        # 로그 창
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        self.setLayout(layout)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        self.status_label.setText(f"상태: {message}")

    def update_settings(self):
        new_settings = {
            "interval_minutes": self.interval_spin.value(),
            "threshold": self.threshold_spin.value()
        }
        save_json("settings.json", new_settings)
        self.log("설정 저장됨")

    def start_monitoring(self):
        self.update_settings()
        worker_exe = get_path("heating_worker.exe")

        if not os.path.exists(worker_exe):
            QMessageBox.critical(self, "오류", f"heating_worker.exe를 찾을 수 없습니다:\n{worker_exe}")
            return

        try:
            self.worker_process = subprocess.Popen(worker_exe, shell=False, cwd=BASE_PATH)
            self.log("모니터링 시작됨")
            QMessageBox.information(self, "시작됨", "Heating 모니터링이 시작되었습니다.")
        except Exception as e:
            self.log(f"실행 실패: {e}")
            QMessageBox.critical(self, "실행 실패", str(e))

    def stop_monitoring(self):
        pid_path = get_path("worker.pid")

        if not os.path.exists(pid_path):
            self.log("PID 파일 없음 - 이미 중지됨")
            QMessageBox.warning(self, "PID 없음", "작동 중인 heating_worker를 찾을 수 없습니다.")
            return

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 9)
            os.remove(pid_path)
            self.log("모니터링 중지됨")
            QMessageBox.information(self, "종료됨", "Heating 모니터링이 중지되었습니다.")
        except Exception as e:
            self.log(f"중지 실패: {e}")
            QMessageBox.critical(self, "종료 실패", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = HeatingMonitorGUI()
    gui.show()
    sys.exit(app.exec_())