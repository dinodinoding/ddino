import os
import sys
import json
import subprocess
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog, QPlainTextEdit
)
from PySide2.QtCore import Qt, QProcess, QTimer
from datetime import datetime

# PyInstaller 또는 .py 실행 모두 대응 가능한 경로 설정
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    """지정된 파일의 전체 경로를 반환합니다."""
    return os.path.join(BASE_PATH, filename)

class GUI_App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heating Monitor Setup")
        self.setGeometry(100, 100, 500, 300)

        # QProcess 인스턴스 대신 None으로 초기화 (워커가 이제 독립적으로 실행됨)
        self.worker_process = None
        # worker.log 파일의 읽기 위치 저장
        self.worker_log_read_pos = 0
        # 로그 파일을 주기적으로 읽을 타이머
        self.log_read_timer = QTimer(self)

        self.init_ui()
        self.load_settings()
        self.check_worker_running()
        self.setup_log_reader() # 로그 리더 설정 함수 호출

    def init_ui(self):
        """사용자 인터페이스를 초기화합니다."""
        main_layout = QVBoxLayout()

        # 모니터링 간격 설정
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Monitoring Interval (minutes):")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 1440) # 1분 ~ 24시간
        self.interval_spinbox.setValue(60)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)
        main_layout.addLayout(interval_layout)

        # 임계값 설정
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (occurrences):")
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 100)
        self.threshold_spinbox.setValue(3)
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        main_layout.addLayout(threshold_layout)

        # 모니터링할 로그 파일 경로 설정
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

        # 시작/중지 버튼
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False) # 초기에는 중지 버튼 비활성화
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # 상태 표시 레이블
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        # 워커 콘솔 출력 (worker.log에서 읽어옴)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(500) # 최대 500줄 유지
        self.console_output.setFixedHeight(150)
        main_layout.addWidget(QLabel("Worker Console Output (from worker.log):"))
        main_layout.addWidget(self.console_output)

        self.setLayout(main_layout)

    def browse_log_file(self):
        """로그 파일을 찾아 선택하는 대화 상자를 엽니다."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            self.monitoring_log_input.setText(file_path)

    def load_settings(self):
        """settings.json 파일에서 설정을 로드합니다."""
        config_path = get_path("settings.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.interval_spinbox.setValue(settings.get("interval_minutes", 60))
                    self.threshold_spinbox.setValue(settings.get("threshold", 3))
                    self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
            except Exception as e:
                QMessageBox.warning(self, "Load Settings Error", f"Failed to load settings.json: {e}")
                self.status_label.setText("Status: Error loading settings.")
        else:
            self.status_label.setText("Status: settings.json not found. Using defaults.")

    def save_settings(self):
        """현재 GUI 설정을 settings.json 파일에 저장합니다."""
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
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Settings Error", f"Failed to save settings.json: {e}")
            self.status_label.setText("Status: Error saving settings.")
            return False

    def check_worker_running(self):
        """worker.pid 파일을 확인하여 워커 프로세스가 실행 중인지 확인하고 GUI 상태를 업데이트합니다."""
        pid_path = get_path("worker.pid")
        is_running = False
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read().strip())
                
                if sys.platform == "win32":
                    # Windows에서 PID가 유효한지 확인하기 위해 tasklist 사용
                    # /FI "PID eq <pid>" 필터로 특정 PID의 프로세스만 검색
                    # creationflags=subprocess.CREATE_NO_WINDOW: 새 콘솔 창을 생성하지 않음
                    result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    if str(pid) in result.stdout: # tasklist 출력에 PID가 포함되어 있으면 실행 중
                        is_running = True
                else: # Unix-like systems (Linux, macOS)
                    os.kill(pid, 0) # 프로세스 존재 여부만 확인 (시그널을 보내지 않음)
                    is_running = True
            except Exception as e:
                # PID 파일은 있지만 해당 프로세스가 없거나 접근 불가
                self.console_output.appendPlainText(f"[INFO] PID file exists but worker process not found or accessible: {e}")
                if os.path.exists(pid_path):
                    try:
                        os.remove(pid_path) # 유효하지 않은 PID 파일 삭제
                        self.console_output.appendPlainText("[INFO] Invalid worker.pid removed.")
                    except Exception as rm_e:
                        self.console_output.appendPlainText(f"[ERROR] Failed to remove invalid worker.pid: {rm_e}")

        if is_running:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText("Status: Monitoring Running (detected)")
            self.console_output.appendPlainText("[INFO] Worker detected as running.")
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("Status: Idle")
            self.console_output.appendPlainText("[INFO] Worker not running.")


    def register_worker_autostart(self):
        """Windows 작업 스케줄러에 워커를 자동 시작하도록 등록합니다."""
        exe_path = os.path.abspath(get_path("heating_worker.exe"))
        task_name = "HeatingWorkerAutoRun"

        if sys.platform == "win32":
            cmd = [
                "schtasks", "/Create",
                "/TN", task_name, # 작업 이름
                "/TR", f'"{exe_path}"', # 실행할 프로그램 경로
                "/SC", "ONLOGON", # 로그인 시 실행
                "/RL", "HIGHEST", # 최고 권한으로 실행
                "/F" # 이미 존재하는 경우 강제로 덮어쓰기
            ]
            try:
                # shell=True는 보안상 권장되지 않지만, schtasks 명령어가 복잡하여 사용
                # creationflags=subprocess.CREATE_NO_WINDOW: 새 콘솔 창을 생성하지 않음
                subprocess.run(" ".join(cmd), shell=True, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.console_output.appendPlainText("[INFO] Worker autostart 등록 완료.")
            except subprocess.CalledProcessError as e:
                self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 등록 실패: {e.stderr.strip() if e.stderr else e}")
            except Exception as e:
                self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 등록 중 오류 발생: {e}")
        else:
            self.console_output.appendPlainText("[INFO] Autostart registration is only supported on Windows.")


    def unregister_worker_autostart(self):
        """Windows 작업 스케줄러에서 워커 자동 시작 등록을 제거합니다."""
        task_name = "HeatingWorkerAutoRun"
        if sys.platform == "win32":
            try:
                subprocess.run(f'schtasks /Delete /TN {task_name} /F', shell=True, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.console_output.appendPlainText("[INFO] Worker autostart 제거 완료.")
            except subprocess.CalledProcessError as e:
                self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 제거 실패: {e.stderr.strip() if e.stderr else e}")
            except Exception as e:
                self.console_output.appendPlainText(f"[ERROR] 작업 스케줄러 제거 중 오류 발생: {e}")
        else:
            self.console_output.appendPlainText("[INFO] Autostart unregistration is only supported on Windows.")


    def start_monitoring(self):
        """모니터링 워커를 시작합니다."""
        if not self.save_settings():
            return

        log_path = self.monitoring_log_input.text()
        if not log_path or not os.path.exists(log_path):
            QMessageBox.warning(self, "Invalid Path", "로그 파일 경로가 없거나 유효하지 않습니다.")
            return

        # 기존 워커가 실행 중이면 중지 (PID 파일 기반)
        self.stop_monitoring() # 이 함수는 PID 파일 삭제 및 schtasks 해제 포함

        worker_exe_path = os.path.abspath(get_path("heating_worker.exe"))
        if not os.path.exists(worker_exe_path):
            QMessageBox.warning(self, "Executable Not Found", "heating_worker.exe를 찾을 수 없습니다.")
            return

        try:
            # 워커를 GUI와 분리된 프로세스로 시작 (detached)
            # QProcess 대신 subprocess.Popen을 사용하여 독립적으로 실행
            # GUI 종료 시 워커가 함께 종료되지 않도록 함
            creation_flags = 0
            if sys.platform == "win32":
                # DETACHED_PROCESS: 자식 프로세스를 호출 프로세스의 콘솔에서 분리
                # CREATE_NEW_PROCESS_GROUP: 새 프로세스 그룹 생성 (Ctrl+C 등 시그널 영향 방지)
                # CREATE_NO_WINDOW: 새 콘솔 창을 생성하지 않음 (백그라운드 실행)
                creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW

            # Popen은 프로세스 객체를 반환하지만, detached이므로 stdout/stderr 직접 연결은 어려움
            # 워커의 로그는 자체 worker.log 파일에 기록되므로, GUI는 이 파일을 읽어서 표시
            subprocess.Popen([worker_exe_path], cwd=os.path.dirname(worker_exe_path),
                             creationflags=creation_flags,
                             stdout=subprocess.DEVNULL, # 표준 출력 무시
                             stderr=subprocess.DEVNULL) # 표준 에러 무시

            # 워커가 PID 파일을 생성할 시간을 줌 (더 견고하게는 PID 파일 존재 여부 확인 루프가 좋음)
            import time
            time.sleep(1)

            self.status_label.setText("Status: Monitoring Started (detached).")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.console_output.appendPlainText("[INFO] Worker started as a detached process.")
            self.register_worker_autostart() # 자동 시작 등록

            # 시작 후 worker.log의 읽기 위치를 재설정하여 새 로그부터 표시
            self.worker_log_read_pos = 0
            self.read_worker_log_output() # 즉시 로그 읽기

        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"워커 시작 실패: {e}")
            self.status_label.setText("Status: Error starting worker.")
            self.check_worker_running() # 실패 시 버튼 상태 재확인

    def setup_log_reader(self):
        """worker.log 파일을 주기적으로 읽기 위한 타이머를 설정합니다."""
        # worker.log 파일의 초기 읽기 위치 설정
        worker_log_path = get_path("worker.log")
        if os.path.exists(worker_log_path):
            try:
                # 바이트 모드로 열어 정확한 바이트 위치를 얻음
                with open(worker_log_path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    self.worker_log_read_pos = f.tell()
            except Exception as e:
                self.console_output.appendPlainText(f"[ERROR] Failed to get initial worker.log position: {e}")
                self.worker_log_read_pos = 0 # 오류 발생 시 처음부터 읽도록 설정

        # 1초마다 worker.log 파일을 읽도록 타이머 설정
        self.log_read_timer.setInterval(1000) # 1초
        self.log_read_timer.timeout.connect(self.read_worker_log_output)
        self.log_read_timer.start()

    def read_worker_log_output(self):
        """worker.log 파일의 새로운 내용을 읽어 콘솔 출력에 추가합니다."""
        worker_log_path = get_path("worker.log")
        if not os.path.exists(worker_log_path):
            return

        try:
            with open(worker_log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self.worker_log_read_pos)
                new_output = f.read()
                if new_output:
                    self.console_output.appendPlainText(new_output.strip())
                    self.worker_log_read_pos = f.tell() # 새 읽기 위치 저장
        except Exception as e:
            self.console_output.appendPlainText(f"[ERROR] Failed to read worker.log: {e}")


    def stop_monitoring(self):
        """모니터링 워커를 중지합니다."""
        pid_path = get_path("worker.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    pid = int(f.read().strip())
                
                # 프로세스에 종료 시그널 전송
                if sys.platform == "win32":
                    # Windows에서는 taskkill /PID <pid> /T /F를 사용하여 프로세스 강제 종료
                    # /T: 지정된 프로세스 및 해당 자식 프로세스 종료
                    # /F: 강제 종료
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.console_output.appendPlainText(f"[INFO] Sent termination signal to PID {pid} via taskkill.")
                else: # Unix-like systems
                    os.kill(pid, 15)  # SIGTERM (정상 종료 요청)
                    self.console_output.appendPlainText(f"[INFO] Sent SIGTERM to PID {pid}.")

                # 워커가 종료될 시간을 줌 (PID 파일을 정리할 시간을 포함)
                time.sleep(2)

            except Exception as e:
                self.console_output.appendPlainText(f"[GUI WARNING] Couldn't kill worker via PID or taskkill: {e}")
        
        # PID 파일이 남아있다면 삭제 시도 (워커가 종료되면서 삭제하지 못했을 경우)
        if os.path.exists(pid_path):
            try:
                os.remove(pid_path)
                self.console_output.appendPlainText("[INFO] worker.pid deleted by GUI.")
            except Exception as e:
                self.console_output.appendPlainText(f"[ERROR] Failed to delete worker.pid by GUI: {e}")

        # 자동 시작 등록 해제
        self.unregister_worker_autostart()
        # GUI 버튼 상태 업데이트
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: Idle")
        self.console_output.appendPlainText("[INFO] Worker stopped.")
        # 로그 읽기 위치 재설정
        self.worker_log_read_pos = 0


    def closeEvent(self, event):
        """GUI 창이 닫힐 때 발생하는 이벤트를 처리합니다."""
        # GUI 종료 시 워커는 계속 실행되도록 함 (detached 되었으므로)
        # 만약 GUI 종료 시 워커도 종료되기를 원한다면, 아래 주석을 해제
        # self.stop_monitoring()
        self.log_read_timer.stop() # 로그 읽기 타이머 중지
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec_())
