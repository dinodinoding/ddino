# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##
# 이 코드에 필요한 여러 기능들을 미리 만들어진 '도구 상자'에서 가져오는 과정입니다.

import os  # 운영체제(Windows)와 상호작용하기 위한 도구 (예: 파일 경로 다루기)
import sys  # 파이썬 프로그램 자체를 제어하기 위한 도구 (예: 프로그램이 .exe로 실행 중인지 확인)
import json  # 설정 같은 데이터를 파일로 저장하고 불러올 때 사용하는 도구 (JSON 형식)
import subprocess  # 현재 파이썬 프로그램 바깥의 다른 프로그램(예: cmd 명령어)을 실행하기 위한 도구
import locale # 시스템의 언어/국가 설정(로케일)을 가져와서 글자를 올바르게 변환하기 위한 도구

# PySide6는 파이썬으로 화면에 보이는 프로그램(GUI)을 만들게 해주는 도구 상자입니다.
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt # Qt의 추가적인 기능들(여기서는 사용되지 않지만 기본적으로 포함)

# ## 프로그램의 기준 경로 설정 ##
# 이 코드가 .py 파일로 실행되든, .exe 파일로 실행되든
# 항상 프로그램이 위치한 폴더를 기준으로 파일을 찾게 해줍니다.
if getattr(sys, 'frozen', False):
    # 프로그램이 .exe 파일로 변환되어 '얼려진' 상태일 때의 경로
    BASE_PATH = os.path.dirname(sys.executable)
else:
    # 일반적인 .py 스크립트 파일로 실행될 때의 경로
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# ## 편의 기능 함수 만들기 ##
# 자주 사용될 것 같은 기능들을 미리 짧은 이름의 함수로 만들어 둡니다.

def get_path(filename):
    """프로그램 폴더 안의 파일 경로를 쉽게 만들어주는 함수"""
    return os.path.join(BASE_PATH, filename)

def decode_bytes(b: bytes) -> str:
    """컴퓨터가 이해하는 언어(bytes)를 사람이 읽는 글자(str)로 변환하는 함수"""
    # Windows 명령어 실행 결과가 한글일 때 깨지지 않게 하기 위함
    enc = locale.getpreferredencoding(False) or "cp1252" # 시스템 기본 인코딩 가져오기
    return (b or b"").decode(enc, errors="ignore") # 변환 시도 (오류 나면 무시)

def is_process_running(exe_name: str) -> bool:
    """특정 이름의 프로그램(.exe)이 현재 실행 중인지 확인하는 함수"""
    try:
        # Windows의 'tasklist' 명령어를 사용해서 현재 실행 중인 프로그램 목록을 가져옴
        # /FI "IMAGENAME eq ..." 부분은 이름이 정확히 일치하는 프로그램만 찾아달라는 의미
        out = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {exe_name}" /NH',
            shell=True
        )
        # 명령어 실행 결과를 사람이 읽을 수 있는 글자로 변환
        txt = decode_bytes(out).strip()
        # 결과가 비어있거나 '정보: 프로세스가 없습니다' 같은 메시지면 실행 중이 아닌 것
        if not txt or txt.lower().startswith(("정보:", "info:")):
            return False
        # 결과에 프로그램 이름이 포함되어 있으면 실행 중인 것으로 판단
        return exe_name.lower() in txt.lower()
    except Exception:
        # 명령 실행 중 오류가 발생하면 일단은 실행되지 않는 것으로 간주
        return False

# ## 메인 프로그램 화면(GUI)을 정의하는 클래스 ##
# QWidget을 상속받아 우리만의 창을 만듭니다.
class GUI_App(QWidget):
    # __init__ 메서드는 이 클래스로 객체를 만들 때 가장 먼저 실행되는 '설정' 부분입니다.
    def __init__(self):
        super(GUI_App, self).__init__() # 부모 클래스(QWidget)의 설정 기능을 먼저 실행

        # 모니터링할 워커 프로그램의 파일 이름 (나중에 계속 사용됨)
        self.worker_exe_name = "heating_monitor_worker.exe"
        
        # 창의 제목과 크기, 위치를 설정
        self.setWindowTitle("Heating Monitor - Control Panel")
        self.setGeometry(100, 100, 600, 270) # x, y, 너비, 높이
        
        # 화면에 보일 구성 요소들(버튼, 입력창 등)을 만드는 함수 호출
        self.init_ui()
        
        # 프로그램 시작 시 'settings.json' 파일에서 이전 설정을 불러오는 함수 호출
        self.load_settings()

    # 화면 구성 요소들을 만들고 배치하는 함수
    def init_ui(self):
        # 위젯들을 위에서 아래로 차곡차곡 쌓는 '수직 레이아웃'을 만듦
        main_layout = QVBoxLayout()

        # --- 1. 로그 모드 타임아웃 설정 ---
        interval_layout = QHBoxLayout() # 위젯을 왼쪽에서 오른쪽으로 배치하는 '수평 레이아웃'
        interval_label = QLabel("LOG Mode Timeout (minutes):") # 설명 글자
        self.interval_spinbox = QSpinBox() # 숫자를 올리고 내릴 수 있는 입력창
        self.interval_spinbox.setRange(1, 1440) # 입력 가능한 숫자 범위 (1분 ~ 24시간)
        self.interval_spinbox.setValue(60) # 기본값 60
        interval_layout.addWidget(interval_label) # 수평 레이아웃에 글자 추가
        interval_layout.addWidget(self.interval_spinbox) # 수평 레이아웃에 숫자 입력창 추가
        main_layout.addLayout(interval_layout) # 이 수평 레이아웃을 메인 수직 레이아웃에 추가

        # --- 2. 임계값(Threshold) 설정 ---
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (occurrences):")
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 100)
        self.threshold_spinbox.setValue(3)
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        main_layout.addLayout(threshold_layout)

        # --- 3. 파일 경로 입력창들 ---
        # 반복되는 '라벨 - 텍스트입력 - 버튼' 구조를 함수로 만들어 간단하게 호출
        main_layout.addLayout(self._make_path_input(
            "CSV Log File Path:", "monitoring_log_input", "Browse...", self.browse_csv_file))
        main_layout.addLayout(self._make_path_input(
            "Raw .LOG File Path:", "log_file_input", "Browse...", self.browse_log_file))
        main_layout.addLayout(self._make_path_input(
            "Converted Log TXT File Path:", "converted_log_input", "Save As...", self.browse_txt_file_save))

        # --- 4. 변환기 실행 파일 이름 입력창 ---
        converter_layout = QHBoxLayout()
        converter_label = QLabel("Converter Executable Name:")
        self.converter_name_input = QLineEdit("g4_converter.exe") # 한 줄 텍스트 입력창
        converter_layout.addWidget(converter_label)
        converter_layout.addWidget(self.converter_name_input)
        main_layout.addLayout(converter_layout)

        # --- 5. 시작/정지 버튼 ---
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start / Register Monitor") # '시작' 버튼
        self.start_button.clicked.connect(self.start_monitoring) # 버튼을 클릭하면 start_monitoring 함수 실행
        self.stop_button = QPushButton("Stop Monitoring") # '정지' 버튼
        self.stop_button.clicked.connect(self.stop_monitoring) # 버튼을 클릭하면 stop_monitoring 함수 실행
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # --- 6. 상태 표시줄 ---
        self.status_label = QLabel("Status: Idle") # 현재 프로그램 상태를 보여줄 글자
        main_layout.addWidget(self.status_label)

        # 최종적으로 완성된 메인 레이아웃을 이 창의 레이아웃으로 설정
        self.setLayout(main_layout)

    # '라벨 - 텍스트입력 - 버튼' UI 세트를 만드는 도우미 함수
    def _make_path_input(self, label_text, attr_name, button_text, callback):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit() # 텍스트 입력창
        button = QPushButton(button_text) # 파일 찾아보기 버튼
        button.clicked.connect(callback) # 버튼 클릭 시 실행할 함수(callback) 연결
        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        # 나중에 다른 곳에서 텍스트 입력창(line_edit)에 접근할 수 있도록 self에 저장
        setattr(self, attr_name, line_edit)
        return layout

    # ------- 파일 선택 대화상자 관련 함수들 -------
    def browse_csv_file(self):
        # "파일 열기" 대화상자를 띄움
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if path: # 사용자가 파일을 선택했다면
            self.monitoring_log_input.setText(path) # 해당 경로를 텍스트 입력창에 표시

    def browse_log_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Raw .log File", "", "Log Files (*.log);;All Files (*)")
        if path:
            self.log_file_input.setText(path)

    def browse_txt_file_save(self):
        # "파일 저장" 대화상자를 띄움
        path, _ = QFileDialog.getSaveFileName(self, "Select Converted TXT Output Path", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.converted_log_input.setText(path)

    # ------- 설정 저장 및 불러오기 관련 함수들 -------
    def load_settings(self):
        """프로그램 시작 시 settings.json 파일에서 설정을 불러와 화면에 적용"""
        config_path = get_path("settings.json")
        if os.path.exists(config_path): # 설정 파일이 존재하면
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f) # JSON 파일을 읽어 파이썬 딕셔너리로 변환
                # 읽어온 값들을 화면의 각 입력창에 설정
                self.interval_spinbox.setValue(settings.get("interval_minutes", 60))
                self.threshold_spinbox.setValue(settings.get("threshold", 3))
                self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
                self.log_file_input.setText(settings.get("log_file_path", ""))
                self.converted_log_input.setText(settings.get("converted_log_file_path", ""))
                self.converter_name_input.setText(settings.get("converter_exe_name", "g4_converter.exe"))
                self.status_label.setText("Status: Settings loaded.")
            except Exception as e:
                # 파일 읽기 실패 시 경고창 표시
                QMessageBox.warning(self, "Load Error", f"settings.json 읽기 실패: {e}")
        else:
            # 설정 파일이 없으면 기본값 상태임을 알림
            self.status_label.setText("Status: Default settings in use.")

    def save_settings(self) -> bool:
        """현재 화면에 입력된 값들을 settings.json 파일에 저장"""
        config_path = get_path("settings.json")
        settings = { # 화면의 값들을 딕셔너리 형태로 정리
            "interval_minutes": self.interval_spinbox.value(),
            "threshold": self.threshold_spinbox.value(),
            "monitoring_log_file_path": self.monitoring_log_input.text(),
            "log_file_path": self.log_file_input.text(),
            "converted_log_file_path": self.converted_log_input.text(),
            "converter_exe_name": self.converter_name_input.text(),
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                # 딕셔너리를 JSON 형식의 문자열로 변환하여 파일에 쓰기
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.status_label.setText("Status: Settings saved.")
            return True # 저장 성공
        except Exception as e:
            # 저장 실패 시 오류창 표시
            QMessageBox.critical(self, "Save Error", f"설정 저장 실패: {e}")
            return False # 저장 실패

    # ------- 모니터링 시작/정지 핵심 기능 -------
    def start_monitoring(self):
        """'시작' 버튼을 눌렀을 때 실행되는 모든 작업"""
        if not self.save_settings(): # 먼저 현재 설정을 파일에 저장하고, 실패하면 중단
            return

        # 혹시 이전에 등록된 작업이 있다면 깨끗하게 지우고 새로 시작하기 위함
        self.stop_monitoring(is_starting=True) # is_starting=True는 불필요한 메시지 창을 띄우지 않기 위함

        try:
            # 1. 워커(.exe) 파일 경로 확인
            worker_exe_path = os.path.abspath(get_path(self.worker_exe_name))
            if not os.path.exists(worker_exe_path): # 파일이 없으면 오류 메시지 후 중단
                QMessageBox.critical(self, "Start Error", f"Worker executable not found:\n{worker_exe_path}")
                return

            worker_dir = os.path.dirname(worker_exe_path) # 워커가 있는 폴더
            worker_name_no_ext = os.path.splitext(os.path.basename(self.worker_exe_name))[0] # 확장자(.exe)를 뺀 이름

            # 2. PowerShell 스크립트 파일 동적 생성
            # 이 스크립트의 역할: "워커 프로그램이 실행 중인지 확인하고, 꺼져있으면 켜줘"
            ps1_path = os.path.abspath(get_path("monitor_worker.ps1"))
            ps1_content = f"""\
# monitor_worker.ps1
# 존재하면 아무 것도 안 함, 없으면 워커 실행 (작업 디렉터리 고정)
$ErrorActionPreference = 'SilentlyContinue'
$n = '{worker_name_no_ext}'
$exe = '{worker_exe_path.replace("'", "''")}'
$wd  = '{worker_dir.replace("'", "''")}'

$p = Get-Process -Name $n -ErrorAction SilentlyContinue
if (-not $p) {{
    Start-Process -FilePath $exe -WorkingDirectory $wd -WindowStyle Hidden
}}
"""
            with open(ps1_path, "w", encoding="utf-8") as f:
                f.write(ps1_content)

            # 3. VBScript 파일 동적 생성
            # 이 스크립트의 역할: "위에서 만든 PowerShell 스크립트를 '완전 몰래' (까만 창 없이) 실행해줘"
            vbs_path = os.path.abspath(get_path("run_monitor_silent.vbs"))
            vbs_content = f'''\
Set WshShell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{ps1_path}"""
WshShell.Run cmd, 0, False
Set WshShell = Nothing
'''
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write(vbs_content)

            # 4. Windows 작업 스케줄러에 등록
            # "위에서 만든 VBScript를 5분마다 한 번씩 실행해줘" 라고 Windows에 예약하는 작업
            monitor_task_name = "HeatingWorkerMonitor"
            cmd_monitor = f'schtasks /Create /TN "{monitor_task_name}" /TR "{vbs_path}" /SC MINUTE /MO 5 /F'
            subprocess.run(cmd_monitor, check=True, shell=True, capture_output=True)

            # 5. (옵션) 로그인 시 자동 실행 등록
            # "컴퓨터를 켤 때마다 워커 프로그램을 한 번 실행해줘" 라고 Windows에 예약
            self.register_worker_autostart()

            # 6. [이번 코드의 변경점] 'Start' 버튼 클릭 시, 워커가 꺼져있으면 즉시 1회 실행
            if not is_process_running(self.worker_exe_name):
                subprocess.Popen([worker_exe_path], # Popen은 다른 프로그램을 실행하고 기다리지 않음
                                 creationflags=subprocess.DETACHED_PROCESS, # 이 GUI 프로그램과 완전히 독립적으로 실행
                                 close_fds=True)

            # 모든 작업이 성공했음을 사용자에게 알림
            QMessageBox.information(self, "Success", "Monitoring registered: every 5 min hidden check & autorun at logon. (Started now if it wasn't running.)")
            self.status_label.setText("Status: Monitoring Registered & Started.")

        except subprocess.CalledProcessError as e: # 명령어 실행 실패 시
            QMessageBox.critical(self, "Start Error", f"작업 스케줄러 등록 실패: {decode_bytes(e.stderr)}")
            self.status_label.setText("Status: Start Failed.")
        except Exception as e: # 그 외 모든 예외 상황
            QMessageBox.critical(self, "Start Error", f"Failed to register monitoring.\nError: {e}")
            self.status_label.setText("Status: Start Failed.")

    def stop_monitoring(self, is_starting: bool = False):
        """'정지' 버튼을 눌렀을 때 실행. 등록된 모든 작업을 해제하고 워커 프로세스를 종료."""
        # 로그인 시 자동 실행되도록 등록한 작업 스케줄을 제거
        self.unregister_worker_autostart()

        # 5분마다 실행되도록 등록한 작업 스케줄을 제거
        monitor_task_name = "HeatingWorkerMonitor"
        try:
            subprocess.run(f'schtasks /Delete /TN "{monitor_task_name}" /F',
                           shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # 작업이 원래 없어서 삭제 실패해도 오류를 내지 않고 그냥 넘어감
            pass

        # 현재 실행 중인 워커 프로세스를 강제 종료
        try:
            subprocess.run(f'taskkill /F /IM "{self.worker_exe_name}"',
                           shell=True, check=True, capture_output=True)
            # start_monitoring 내부에서 호출된 게 아닐 때만 성공 메시지를 보여줌
            if not is_starting:
                QMessageBox.information(self, "Success", "Monitoring stopped and auto-run unregistered.")
        except subprocess.CalledProcessError:
            # 프로세스가 원래 없어서 종료 실패해도 그냥 넘어감
            pass

        # 상태 표시줄을 초기 상태로 변경
        self.status_label.setText("Status: Idle.")

    def register_worker_autostart(self):
        """로그인 시 워커를 한 번 실행하도록 작업 스케줄러에 등록"""
        exe_path = os.path.abspath(get_path(self.worker_exe_name))
        task_name = "HeatingWorkerAutoRun"
        cmd = f'schtasks /Create /TN "{task_name}" /TR "{exe_path}" /SC ONLOGON /F'
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Register Error", f"작업 스케줄러 등록 실패: {decode_bytes(e.stderr)}")

    def unregister_worker_autostart(self):
        """로그인 시 자동 실행 작업을 스케줄러에서 제거"""
        task_name = "HeatingWorkerAutoRun"
        try:
            subprocess.run(f'schtasks /Delete /TN "{task_name}" /F',
                           shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # 작업이 없어서 삭제 실패해도 그냥 넘어감
            pass

    def closeEvent(self, event):
        """창의 X 버튼을 눌렀을 때 호출되는 함수"""
        event.accept() # 창이 정상적으로 닫히도록 허용

# ## 이 스크립트 파일을 직접 실행했을 때만 아래 코드를 실행 ##
# 다른 파이썬 파일에서 이 파일을 import해서 사용할 때는 실행되지 않음
if __name__ == "__main__":
    # .exe 파일로 만들었을 때 일부 충돌을 방지하기 위한 코드
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except ImportError:
        pass

    # GUI 프로그램을 실행하기 위한 기본 준비
    app = QApplication(sys.argv) # QApplication 객체 생성 (모든 PySide 앱에 필수)
    window = GUI_App()           # 우리가 위에서 만든 GUI_App 클래스로 창 객체 생성
    window.show()                # 창을 화면에 보여주기
    sys.exit(app.exec())         # 프로그램이 바로 꺼지지 않고, 사용자의 입력을 계속 기다리도록 함
