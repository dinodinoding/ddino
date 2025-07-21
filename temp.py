### Heating Monitor GUI
### PySide6 기반 GUI 앱으로 Start / Stop 버튼을 통해 worker를 제어합니다.
### Start 시: heating_monitor_worker.exe 실행 및 작업 스케줄러 등록
### Stop 시: worker 종료 및 작업 스케줄러 제거

import os
import subprocess
import signal
import json
import psutil
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QMessageBox, QLabel
from PySide6.QtCore import QProcess

class HeatingMonitorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating Monitor GUI")

        # 레이아웃 구성
        self.layout = QVBoxLayout()

        # 버튼 및 상태 라벨 생성
        self.start_button = QPushButton("Start Monitoring")
        self.stop_button = QPushButton("Stop Monitoring")
        self.status_label = QLabel("Status: Ready")

        # 레이아웃에 추가
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.stop_button)
        self.layout.addWidget(self.status_label)
        self.setLayout(self.layout)

        # 버튼 클릭 이벤트 연결
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)

        # 기본 파일 및 태스크 이름 정의
        self.worker_pid_file = "worker.pid"
        self.worker_exe_path = os.path.abspath("heating_monitor_worker.exe")
        self.task_name = "HeatingWorkerAutoRun"

    ### Start 버튼 클릭 시 호출
    def start_monitoring(self):
        self.kill_existing_worker()  # 이전 PID 프로세스 종료
        try:
            subprocess.Popen(self.worker_exe_path, creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.register_task()
            self.status_label.setText("Status: Monitoring Started")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start monitoring: {e}")

    ### Stop 버튼 클릭 시 호출
    def stop_monitoring(self):
        self.kill_existing_worker()  # 현재 PID 종료
        self.delete_task()           # 작업 스케줄러 제거
        self.status_label.setText("Status: Monitoring Stopped")

    ### 실행 중인 worker 프로세스가 있으면 종료
    def kill_existing_worker(self):
        if not os.path.exists(self.worker_pid_file):
            return
        try:
            with open(self.worker_pid_file, "r") as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                proc.terminate()
        except Exception:
            pass  # 에러 발생해도 무시
        try:
            os.remove(self.worker_pid_file)
        except Exception:
            pass

    ### 작업 스케줄러 등록
    def register_task(self):
        try:
            subprocess.run([
                "schtasks", "/Create", "/TN", self.task_name,
                "/TR", self.worker_exe_path,
                "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"
            ], check=True)
        except subprocess.CalledProcessError:
            pass  # 실패해도 무시

    ### 작업 스케줄러 제거
    def delete_task(self):
        try:
            result = subprocess.run([
                "schtasks", "/Query", "/TN", self.task_name
            ], capture_output=True, text=True)
            if result.returncode == 0:
                subprocess.run([
                    "schtasks", "/Delete", "/TN", self.task_name, "/F"
                ], check=True)
        except subprocess.CalledProcessError:
            pass  # 실패해도 무시

### 앱 실행 진입점
if __name__ == "__main__":
    app = QApplication([])
    gui = HeatingMonitorGUI()
    gui.show()
    app.exec()
