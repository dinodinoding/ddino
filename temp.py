from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QMessageBox
)
from PySide2.QtCore import QThread, Signal
from datetime import datetime, timedelta
import sys, time, os, json, subprocess


class MonitorThread(QThread):
    alert_signal = Signal(str)

    def __init__(self, config, interval_minutes, threshold):
        super().__init__()
        self.config = config
        self.interval = timedelta(minutes=interval_minutes)
        self.threshold = threshold
        self.running = True
        self.heating_times = []

    def run(self):
        raw_log = self.config["raw_log_path"]
        bat_file = self.config["bat_file_path"]
        converted_log = self.config["converted_log_path"]
        last_modified_time = 0

        while self.running:
            try:
                current_modified_time = os.path.getmtime(raw_log)
            except FileNotFoundError:
                time.sleep(5)
                continue

            if current_modified_time != last_modified_time:
                last_modified_time = current_modified_time

                try:
                    subprocess.run(bat_file, shell=True, check=True)
                except subprocess.CalledProcessError:
                    continue

                try:
                    with open(converted_log, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except:
                    continue

                now = datetime.now()

                for line in lines:
                    if 'heating' in line.lower():
                        try:
                            timestamp = datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
                            self.heating_times.append(timestamp)
                        except:
                            continue

                # 시간 기준 필터링
                self.heating_times = [t for t in self.heating_times if now - t <= self.interval]

                if len(self.heating_times) >= self.threshold:
                    self.alert_signal.emit(f"{self.interval.total_seconds()//60:.0f}분 안에 heating {self.threshold}회 감지됨")
                    self.heating_times.clear()

            time.sleep(10)

    def stop(self):
        self.running = False
        self.wait()


class MonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating 감지 모니터")
        self.setFixedSize(300, 200)
        self.load_config()

        layout = QVBoxLayout(self)

        # 입력 필드
        input_layout = QHBoxLayout()
        self.interval_input = QLineEdit("60")
        self.threshold_input = QLineEdit("3")
        input_layout.addWidget(QLabel("감시 시간(분):"))
        input_layout.addWidget(self.interval_input)
        layout.addLayout(input_layout)

        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("감지 횟수:"))
        threshold_layout.addWidget(self.threshold_input)
        layout.addLayout(threshold_layout)

        # 버튼
        button_layout = QHBoxLayout()
        self.on_button = QPushButton("▶ ON")
        self.off_button = QPushButton("■ OFF")
        button_layout.addWidget(self.on_button)
        button_layout.addWidget(self.off_button)
        layout.addLayout(button_layout)

        self.status_label = QLabel("상태: 대기 중")
        layout.addWidget(self.status_label)

        self.on_button.clicked.connect(self.start_monitoring)
        self.off_button.clicked.connect(self.stop_monitoring)
        self.monitor_thread = None

    def load_config(self):
        with open("config.json", 'r') as f:
            self.config = json.load(f)

    def start_monitoring(self):
        try:
            interval = int(self.interval_input.text())
            threshold = int(self.threshold_input.text())
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "숫자를 입력해주세요.")
            return

        self.monitor_thread = MonitorThread(self.config, interval, threshold)
        self.monitor_thread.alert_signal.connect(self.show_alert)
        self.monitor_thread.start()
        self.status_label.setText("상태: 모니터링 중")

    def stop_monitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None
            self.status_label.setText("상태: 대기 중")

    def show_alert(self, message):
        QMessageBox.warning(self, "Heating 감지", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MonitorApp()
    window.show()
    sys.exit(app.exec_())