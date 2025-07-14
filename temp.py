import json
import os
import signal
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QMessageBox
)
import sys

class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating 감지 모니터 (GUI)")
        self.setFixedSize(320, 200)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # 감시 시간 입력
        time_layout = QHBoxLayout()
        self.time_input = QLineEdit("60")
        time_layout.addWidget(QLabel("감시 시간(분):"))
        time_layout.addWidget(self.time_input)
        self.layout.addLayout(time_layout)

        # 감지 횟수 입력
        count_layout = QHBoxLayout()
        self.count_input = QLineEdit("3")
        count_layout.addWidget(QLabel("감지 횟수:"))
        count_layout.addWidget(self.count_input)
        self.layout.addLayout(count_layout)

        # 버튼
        button_layout = QHBoxLayout()
        self.on_button = QPushButton("▶ ON")
        self.off_button = QPushButton("■ OFF")
        button_layout.addWidget(self.on_button)
        button_layout.addWidget(self.off_button)
        self.layout.addLayout(button_layout)

        self.status_label = QLabel("상태: 대기 중")
        self.layout.addWidget(self.status_label)

        self.on_button.clicked.connect(self.start_worker)
        self.off_button.clicked.connect(self.stop_worker)

    def start_worker(self):
        try:
            interval = int(self.time_input.text())
            threshold = int(self.count_input.text())
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "숫자를 정확히 입력해주세요.")
            return

        settings = {
            "interval_minutes": interval,
            "threshold": threshold
        }

        with open("settings.json", "w") as f:
            json.dump(settings, f)

        # heating_worker.exe 실행
        try:
            subprocess.Popen(["heating_worker.exe"], shell=True)
            self.status_label.setText("상태: 모니터링 중")
        except Exception as e:
            QMessageBox.critical(self, "실행 오류", str(e))

    def stop_worker(self):
        if not os.path.exists("worker.pid"):
            QMessageBox.information(self, "정보", "실행 중인 워커가 없습니다.")
            return

        try:
            with open("worker.pid", "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            os.remove("worker.pid")
            self.status_label.setText("상태: 대기 중")
        except Exception as e:
            QMessageBox.critical(self, "종료 오류", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HeatingMonitorGUI()
    window.show()
    sys.exit(app.exec_())