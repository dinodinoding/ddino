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
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 파일을 찾을 수 없습니다. 빈 설정으로 시작합니다.")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 로드 성공: {settings}")
        return settings
    except json.JSONDecodeError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 파싱 오류: {e}. 파일을 확인해주세요.")
        QMessageBox.critical(None, "설정 파일 오류", f"{filename} 파일을 읽는 중 오류가 발생했습니다.\n파일 내용을 확인해주세요.\n오류: {e}")
        return {}
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 로드 중 알 수 없는 오류: {e}")
        QMessageBox.critical(None, "설정 파일 오류", f"{filename} 파일을 읽는 중 알 수 없는 오류가 발생했습니다.\n오류: {e}")
        return {}


def save_json(filename, data):
    path = get_path(filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 저장 성공.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] {filename} 저장 실패: {e}")
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
        log_path_layout.addWidget(QLabel("원본 로그 파일 경로:"))
        self.log_path_input = QLineEdit()
        # 기존 설정에서 경로 불러오기, 없으면 빈 문자열
        self.log_path_input.setText(self.settings.get("original_log_file_path", ""))
        log_path_layout.addWidget(self.log_path_input)
        
        browse_button = QPushButton("찾아보기")
        browse_button.clicked.connect(self.browse_log_file)
        log_path_layout.addWidget(browse_button)
        layout.addLayout(log_path_layout)


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

    def browse_log_file(self):
        # 파일 대화 상자를 열어 로그 파일 선택
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] '찾아보기' 버튼 클릭됨.")
        file_path, _ = QFileDialog.getOpenFileName(self, "원본 로그 파일 선택", "", "Log Files (*.log *.txt);;All Files (*)")
        if file_path:
            self.log_path_input.setText(file_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] 원본 로그 파일 경로 선택됨: {file_path}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] 파일 선택 취소됨.")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{timestamp}] {message}")
        self.status_label.setText(f"상태: {message}")
        print(f"[{timestamp}] [GUI] {message}") # 콘솔에도 출력

    def update_settings(self):
        new_settings = {
            "interval_minutes": self.interval_spin.value(),
            "threshold": self.threshold_spin.value(),
            "original_log_file_path": self.log_path_input.text() # 새로운 경로 추가
        }
        save_json("settings.json", new_settings)
        self.log("설정 저장됨")

    def start_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] '모니터링 시작' 버튼 클릭됨.")
        self.update_settings() # 시작 전 설정 저장

        original_log_path = self.log_path_input.text()
        if not original_log_path or not os.path.exists(original_log_path):
            self.log("유효한 원본 로그 파일 경로를 지정해주세요.")
            QMessageBox.warning(self, "경고", "유효한 원본 로그 파일 경로를 지정해주세요.")
            return

        worker_exe = get_path(self.worker_exe_name)

        if not os.path.exists(worker_exe):
            self.log(f"오류: {self.worker_exe_name}를(을) 찾을 수 없습니다.")
            QMessageBox.critical(self, "오류", f"{self.worker_exe_name}를(을) 찾을 수 없습니다.\n{worker_exe}\n워커 스크립트가 컴파일되었는지 확인해주세요.")
            return

        try:
            # 콘솔 창이 보이도록 creationflags 옵션을 제거하거나 수정합니다.
            # PyInstaller로 --noconsole 없이 빌드되면 기본적으로 콘솔이 보입니다.
            self.worker_process = subprocess.Popen(worker_exe, cwd=BASE_PATH) 
            
            self.log("모니터링 시작됨")
            QMessageBox.information(self, "시작됨", "Heating 모니터링이 백그라운드에서 시작되었습니다.\n워커 콘솔 창을 확인하여 디버그 메시지를 확인하세요.")
        except Exception as e:
            self.log(f"워커 실행 실패: {e}")
            QMessageBox.critical(self, "워커 실행 실패", str(e))

    def stop_monitoring(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [GUI] '모니터링 중지' 버튼 클릭됨.")
        pid_path = get_path("worker.pid")

        if not os.path.exists(pid_path):
            self.log("PID 파일 없음 - 워커가 이미 중지되었거나 실행 중이 아닙니다.")
            QMessageBox.warning(self, "PID 없음", "작동 중인 워커 프로세스를 찾을 수 없습니다.")
            return

        try:
            with open(pid_path, "r") as f:
                pid = int(f.read().strip())
            
            self.log(f"PID {pid}를 가진 워커 프로세스 종료 시도 중...")
            # 윈도우에서 프로세스 강제 종료 (taskkill 사용)
            subprocess.run(f"taskkill /PID {pid} /F", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            
            os.remove(pid_path)
            self.log("모니터링 중지됨")
            QMessageBox.information(self, "종료됨", "Heating 모니터링이 중지되었습니다.")
        except FileNotFoundError:
            self.log("PID 파일이 이미 삭제되었거나 존재하지 않습니다.")
        except subprocess.CalledProcessError as e:
            self.log(f"프로세스 종료 명령 실패. PID {pid}를 찾을 수 없거나 권한 부족일 수 있습니다. 오류: {e.stderr.decode(errors='ignore')}")
            QMessageBox.critical(self, "종료 실패", f"프로세스 종료 명령 실패: {e.stderr.decode(errors='ignore')}")
        except Exception as e:
            self.log(f"모니터링 중지 중 예외 발생: {e}")
            QMessageBox.critical(self, "종료 실패", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = HeatingMonitorGUI()
    gui.show()
    sys.exit(app.exec_())

