import os
import sys
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QTextEdit, QLineEdit, QFileDialog
)
from PySide2.QtCore import Qt, QTimer # QTimer 추가 (워커 상태 확인용)
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

        self.worker_process = None # 워커 프로세스 객체 (None일 수도 있음)
        self.worker_pid = None     # 워커 프로세스의 PID를 저장할 변수

        self.init_ui()
        self.load_settings()

        # 1초마다 워커 프로세스 상태를 확인하는 타이머
        self.check_worker_timer = QTimer(self)
        self.check_worker_timer.timeout.connect(self.check_worker_status)
        self.check_worker_timer.start(1000) # 1초마다 실행

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

        # Console Output (for debugging) - GUI에서 콘솔 출력은 이제 필요 없으므로 제거 또는 주석 처리 권장
        # self.console_output = QTextEdit()
        # self.console_output.setReadOnly(True)
        # self.console_output.setFixedHeight(100) # 높이 제한
        # main_layout.addWidget(QLabel("Worker Console Output (for debug):"))
        # main_layout.addWidget(self.console_output)
        
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
                    self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
                    # 워커 PID 로드 시도
                    self.worker_pid = settings.get("worker_pid", None)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] Settings loaded: {settings}")
            except Exception as e:
                QMessageBox.warning(self, "Load Settings Error", f"Failed to load settings.json: {e}")
                self.status_label.setText(f"Status: Error loading settings. ({e})")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Failed to load settings: {e}")
        else:
            self.status_label.setText("Status: settings.json not found. Using defaults.")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] settings.json not found. Using defaults.")
        # 로드 후 워커 상태 업데이트
        self.check_worker_status()


    def save_settings(self):
        config_path = get_path("settings.json")
        settings = {
            "interval_minutes": self.interval_spinbox.value(),
            "threshold": self.threshold_spinbox.value(),
            "monitoring_log_file_path": self.monitoring_log_input.text(),
            "worker_pid": self.worker_pid # 현재 워커 PID 저장
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
        # 1. 설정 저장
        if not self.save_settings():
            return # 설정 저장 실패 시 시작하지 않음

        # 2. 모니터링할 로그 파일 경로 확인
        monitoring_log_path = self.monitoring_log_input.text()
        if not monitoring_log_path:
            QMessageBox.warning(self, "경로 누락", "모니터링할 CSV 로그 파일 경로를 선택해주세요.")
            self.status_label.setText("Status: 로그 경로 대기 중.")
            return
        if not os.path.exists(monitoring_log_path):
            QMessageBox.warning(self, "파일 없음", f"지정된 CSV 로그 파일이 존재하지 않습니다: {monitoring_log_path}")
            self.status_label.setText("Status: CSV 로그 파일을 찾을 수 없습니다.")
            return

        # 3. 기존 워커 프로세스가 실행 중인지 확인하고 종료 (새로운 워커 시작 전)
        # 이 부분은 GUI를 닫아도 워커가 유지되어야 하므로,
        # 'GUI를 통해 다시 시작할 때만' 기존 워커를 종료하고 새로 시작하도록 변경합니다.
        # 즉, 'self.worker_pid'를 이용하여 실제 프로세스를 확인하고 종료합니다.
        if self.worker_pid:
            try:
                # PID를 통해 프로세스가 아직 살아있는지 확인
                os.kill(self.worker_pid, 0) # 0 시그널은 프로세스 존재 여부만 확인
                reply = QMessageBox.question(self, "워커 실행 중",
                                             "워커 프로세스가 이미 실행 중입니다. 기존 프로세스를 종료하고 다시 시작하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.stop_monitoring()
                    time.sleep(1) # 종료 대기
                else:
                    self.status_label.setText(f"Status: 워커가 이미 PID {self.worker_pid}로 실행 중입니다.")
                    self.start_button.setEnabled(False)
                    self.stop_button.setEnabled(True)
                    return
            except OSError: # 프로세스가 이미 종료된 경우
                self.worker_pid = None # PID 초기화


        # 4. heating_worker.exe 실행 (이제 직접 CSV 파일을 모니터링)
        try:
            worker_exe_path = get_path("heating_worker.exe")
            if os.path.exists(worker_exe_path):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] heating_worker.exe 시작 시도...")
                
                # *** 핵심 변경 사항: subprocess.DEVNULL 사용 및 DETACHED_PROCESS ***
                # 콘솔 창 없이 백그라운드에서 실행하고, 출력은 모두 무시
                self.worker_process = subprocess.Popen(
                    [worker_exe_path],
                    creationflags=subprocess.DETACHED_PROCESS, # GUI 종료 후에도 워커 유지
                    stdout=subprocess.DEVNULL,   # 표준 출력(print)을 무시
                    stderr=subprocess.DEVNULL    # 표준 에러 출력을 무시
                )
                self.worker_pid = self.worker_process.pid # 실행된 워커의 PID 저장
                self.save_settings() # PID를 settings.json에 저장

                self.status_label.setText(f"Status: 모니터링 시작됨. 워커 PID: {self.worker_pid}")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] heating_worker.exe 시작됨 (PID: {self.worker_pid}).")

            else:
                QMessageBox.warning(self, "실행 파일 없음", "현재 디렉터리에 heating_worker.exe를 찾을 수 없습니다.")
                self.status_label.setText("Status: heating_worker.exe 없음.")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] heating_worker.exe not found.")
                self.stop_monitoring() # 실패 시 정리
                return

        except Exception as e:
            QMessageBox.critical(self, "시작 오류", f"프로세스 시작 실패: {e}")
            self.status_label.setText(f"Status: 모니터링 시작 오류. ({e})")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] Failed to start process: {e}")
            self.stop_monitoring() # 실패 시 정리

    def stop_monitoring(self):
        self.status_label.setText("Status: 모니터링 중지 중...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] 모니터링 중지 시작.")

        # PID를 통해 워커 프로세스 종료 시도
        if self.worker_pid:
            try:
                # 프로세스가 살아있는지 확인 (0 시그널)
                os.kill(self.worker_pid, 0)
                # 살아있다면 SIGTERM (종료 요청) 전송
                os.kill(self.worker_pid, signal.SIGTERM)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] 워커 PID {self.worker_pid} 에 SIGTERM 전송.")
                time.sleep(2) # 종료될 시간 부여

                try:
                    # 여전히 살아있다면 SIGKILL (강제 종료) 전송
                    os.kill(self.worker_pid, 0)
                    os.kill(self.worker_pid, signal.SIGKILL)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI WARNING] 워커 PID {self.worker_pid} 강제 종료됨 (SIGKILL).")
                except OSError:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] 워커 PID {self.worker_pid} 정상 종료됨.")

            except OSError as e: # PID에 해당하는 프로세스가 없거나 권한 문제
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI ERROR] 워커 PID {self.worker_pid} 종료 실패 (프로세스 없음 또는 오류): {e}")
            
            self.worker_pid = None # PID 초기화
            self.save_settings() # PID 업데이트된 설정 저장

        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] 종료할 워커 프로세스가 없습니다.")

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: 유휴")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] 모니터링 중지 완료.")

    def check_worker_status(self):
        # GUI가 실행될 때마다 또는 타이머에 의해 워커 프로세스 상태를 확인하고 GUI 버튼 상태를 업데이트합니다.
        if self.worker_pid:
            try:
                # PID를 통해 프로세스가 살아있는지 확인
                os.kill(self.worker_pid, 0)
                self.status_label.setText(f"Status: 모니터링 실행 중 (PID: {self.worker_pid})")
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
            except OSError: # 프로세스가 종료되었거나 존재하지 않는 경우
                self.worker_pid = None
                self.save_settings() # PID가 더 이상 유효하지 않으므로 settings.json 업데이트
                self.status_label.setText("Status: 유휴 (워커 프로세스가 중지되었거나 발견되지 않음)")
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
        else:
            self.status_label.setText("Status: 유휴")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)


    def closeEvent(self, event):
        # GUI 창을 닫을 때 워커 프로세스를 자동으로 종료하지 않도록 변경했습니다.
        # 워커는 이제 'Stop Monitoring' 버튼을 통해서만 종료됩니다.
        # 따라서 여기서는 아무것도 하지 않고 이벤트를 수락합니다.
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI INFO] GUI 창이 닫히지만 워커는 계속 실행됩니다 (만약 실행 중이었다면).")
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec_())

