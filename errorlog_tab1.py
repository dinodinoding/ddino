import sys
import os
import subprocess
import threading
import datetime
import csv
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread

# --- 여기부터는 사용자의 GUI.py 코드 내용이라고 가정합니다 ---
# 만약 실제 GUI.py 내용과 다르면 당신의 코드를 사용하되, 아래 start_monitoring 부분만 수정하시면 됩니다.

class WorkerThread(QThread):
    # 이 클래스는 개념적인 예시이며, heating_worker.py가 별도의 실행 파일인 경우
    # GUI.py에서 직접 사용되지 않을 수도 있습니다.
    finished = Signal()
    progress = Signal(str)

    def run(self):
        self.progress.emit("워커 스레드 시작 (개념적)...")
        time.sleep(2) # 작업 시뮬레이션
        self.progress.emit("워커 스레드 종료 (개념적).")
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("히팅 모니터 GUI")
        self.setGeometry(100, 100, 600, 400)

        self.worker_process = None
        self.log_file_path = ""

        self.init_ui()
        self.check_worker_process_timer = QTimer(self)
        self.check_worker_process_timer.timeout.connect(self.check_worker_status)
        self.check_worker_process_timer.start(1000) # 1초마다 워커 상태 확인

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 로그 파일 경로 선택
        log_path_layout = QHBoxLayout()
        self.log_path_label = QLabel("CSV 로그 경로:")
        self.log_path_line_edit = QLineEdit()
        self.log_path_button = QPushButton("찾아보기")
        self.log_path_button.clicked.connect(self.select_log_file)
        log_path_layout.addWidget(self.log_path_label)
        log_path_layout.addWidget(self.log_path_line_edit)
        log_path_layout.addWidget(self.log_path_button)
        main_layout.addLayout(log_path_layout)

        # 제어 버튼
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("모니터링 시작")
        self.stop_button = QPushButton("모니터링 중지")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False) # 처음에는 중지 버튼 비활성화
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # 상태 표시
        self.status_label = QLabel("상태: 유휴")
        main_layout.addWidget(self.status_label)

        # 로그 표시 (선택 사항, 워커 출력을 연결했다면 여기에 표시될 수 있음)
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)

    def select_log_file(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getSaveFileName(self, "CSV 로그 파일 선택", "", "CSV Files (*.csv);;All Files (*)")
        if file_path:
            self.log_file_path = file_path
            self.log_path_line_edit.setText(self.log_file_path)
            self.status_label.setText(f"상태: 로그 경로가 {self.log_file_path} (으)로 설정됨")

    def start_monitoring(self):
        if not self.log_file_path:
            QMessageBox.warning(self, "경고", "먼저 CSV 로그 파일 경로를 선택해주세요.")
            return

        if self.worker_process and self.worker_process.poll() is None:
            QMessageBox.information(self, "정보", "모니터링이 이미 실행 중입니다.")
            return

        worker_exe_name = "heating_worker.exe" # 컴파일된 워커 실행 파일 이름과 일치해야 합니다.
        # 워커 실행 파일의 경로를 결정합니다.
        # PyInstaller 원파일(onefile) 앱에서는 __file__이 임시 폴더 내에 있습니다.
        # sys._MEIPASS는 리소스가 추출된 임시 폴더의 경로입니다.
        if getattr(sys, 'frozen', False):
            # PyInstaller 번들로 실행 중인 경우
            application_path = os.path.dirname(sys.executable)
        else:
            # 일반 Python 스크립트로 실행 중인 경우
            application_path = os.path.dirname(os.path.abspath(__file__))

        worker_exe_path = os.path.join(application_path, worker_exe_name)

        if not os.path.exists(worker_exe_path):
            QMessageBox.critical(self, "오류", f"워커 실행 파일을 찾을 수 없습니다: {worker_exe_path}")
            self.status_label.setText("상태: 오류 - 워커를 찾을 수 없습니다.")
            return

        try:
            # *** 여기에 수정된 부분이 있습니다! ***
            # 워커 프로세스를 콘솔 없이 백그라운드에서 실행하고 stdout/stderr을 DEVNULL로 리다이렉션합니다.
            self.worker_process = subprocess.Popen(
                [worker_exe_path, self.log_file_path], # 로그 파일 경로를 인수로 워커에 전달
                creationflags=subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,   # 표준 출력(print)을 무시합니다.
                stderr=subprocess.DEVNULL    # 표준 에러 출력을 무시합니다.
            )
            # *** 수정된 부분 끝 ***

            self.status_label.setText(f"상태: 모니터링 시작됨. 워커 PID: {self.worker_process.pid}")
            self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 워커 프로세스 {self.worker_process.pid} 시작됨")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "오류", f"워커 프로세스 시작 실패: {e}")
            self.status_label.setText("상태: 모니터링 시작 실패.")

    def stop_monitoring(self):
        if self.worker_process and self.worker_process.poll() is None:
            try:
                # 먼저 프로세스를 부드럽게 종료 시도
                self.worker_process.terminate()
                self.status_label.setText("상태: 워커에게 종료 신호 전송 중...")
                # 종료될 때까지 잠시 기다립니다.
                time.sleep(1)
                if self.worker_process.poll() is None: # 아직 실행 중이라면 강제 종료
                    self.worker_process.kill()
                    self.status_label.setText("상태: 워커 프로세스 강제 종료됨.")
                else:
                    self.status_label.setText("상태: 모니터링 중지됨.")
                self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 워커 프로세스 중지됨.")

            except Exception as e:
                QMessageBox.critical(self, "오류", f"워커 프로세스 중지 실패: {e}")
                self.status_label.setText("상태: 모니터링 중지 실패.")
            finally:
                self.worker_process = None
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
        else:
            self.status_label.setText("상태: 모니터링이 실행 중이 아닙니다.")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False) # 워커가 실행 중이 아니면 중지 버튼 비활성화

    def check_worker_status(self):
        if self.worker_process:
            if self.worker_process.poll() is not None: # 워커가 종료됨
                self.status_label.setText("상태: 워커 프로세스가 예기치 않게 중지되었습니다.")
                self.log_display.append(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 워커 프로세스 종료됨.")
                self.worker_process = None
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
            else:
                self.status_label.setText(f"상태: 모니터링 실행 중. 워커 PID: {self.worker_process.pid}")


    def closeEvent(self, event):
        # GUI가 닫힐 때 워커 프로세스가 중지되도록 합니다.
        self.stop_monitoring()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
