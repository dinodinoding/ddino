import os
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox
)
from PySide2.QtCore import Qt
import sys

# === [1] 현재 gui.py 파일 위치 기준 경로 고정 ===
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

# === [2] JSON 로드 및 저장 ===
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

# === [3] GUI 메인 클래스 ===
class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating 모니터링 설정")
        self.setGeometry(300, 300, 400, 200)

        self.settings = load_json("settings.json")
        self.worker_process = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 감시 시간 설정
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("감시 시간 (분):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 360)
        self.interval_spin.setValue(self.settings.get("interval_minutes", 60))
        time_layout.addWidget(self.interval_spin)
        layout.addLayout(time_layout)

        # 허용 횟수 설정
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("허용 횟수:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setValue(self.settings.get("threshold", 3))
        count_layout.addWidget(self.threshold_spin)
        layout.addLayout(count_layout)

        # ON/OFF 버튼
        self.on_button = QPushButton("모니터링 시작")
        self.on_button.clicked.connect(self.start_monitoring)
        layout.addWidget(self.on_button)

        self.off_button = QPushButton("모니터링 중지")
        self.off_button.clicked.connect(self.stop_monitoring)
        layout.addWidget(self.off_button)

        self.setLayout(layout)

    def update_settings(self):
        new_settings = {
            "interval_minutes": self.interval_spin.value(),
            "threshold": self.threshold_spin.value()
        }
        save_json("settings.json", new_settings)

    def start_monitoring(self):
        self.update_settings()
        worker_exe = get_path("heating_worker.exe")

        if not os.path.exists(worker_exe):
            QMessageBox.critical(self, "오류", f"heating_worker.exe를 찾을 수 없습니다:\n{worker_exe}")
            return

        try:
            self.worker_process = subprocess.Popen(worker_exe, shell=False)
            QMessageBox.information(self, "시작됨", "Heating 모니터링이 시작되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "실행 실패", str(e))

    def stop_monitoring(self):
        pid_path = get_path("worker.pid")

        if not os.path.exists(pid_path):
            QMessageBox.warning(self, "PID 없음", "작동 중인 heating_worker를 찾을 수 없습니다.")
            return

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 9)  # 강제 종료
            os.remove(pid_path)
            QMessageBox.information(self, "종료됨", "Heating 모니터링이 중지되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "종료 실패", str(e))

# === [4] GUI 실행 ===
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = HeatingMonitorGUI()
    gui.show()
    sys.exit(app.exec_())