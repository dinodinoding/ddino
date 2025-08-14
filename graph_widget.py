# GUI 스크립트 파일 전체를 이 코드로 교체하세요.

import os
import sys
import json
import subprocess
import locale

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QSpinBox, QHBoxLayout, QMessageBox, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt

# ----------------- Path helpers -----------------
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_PATH, filename)

def decode_bytes(b: bytes) -> str:
    enc = locale.getpreferredencoding(False) or "cp1252"
    return (b or b"").decode(enc, errors="ignore")

def is_process_running(exe_name: str) -> bool:
    """정확 매칭으로 프로세스 동작 여부 확인 (확장자 포함 이름)"""
    try:
        out = subprocess.check_output(
            f'tasklist /FI "IMAGENAME eq {exe_name}" /NH',
            shell=True
        )
        txt = decode_bytes(out).strip()
        if not txt or txt.lower().startswith(("정보:", "info:")):
            return False
        return exe_name.lower() in txt.lower()
    except Exception:
        return False

# ----------------- GUI -----------------
class GUI_App(QWidget):
    def __init__(self):
        super(GUI_App, self).__init__()
        self.worker_exe_name = "heating_monitor_worker.exe"
        self.setWindowTitle("Heating Monitor - Control Panel")
        self.setGeometry(100, 100, 700, 320)
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Monitor check interval (스케줄러 주기 - 기본 30분)
        mon_layout = QHBoxLayout()
        mon_label = QLabel("Monitor Check Interval (minutes):")
        self.monitor_interval_spinbox = QSpinBox()
        self.monitor_interval_spinbox.setRange(1, 1440)
        self.monitor_interval_spinbox.setValue(30)  # default 30
        mon_layout.addWidget(mon_label)
        mon_layout.addWidget(self.monitor_interval_spinbox)
        main_layout.addLayout(mon_layout)

        # (기존) LOG timeout - 네가 쓰던 값, 저장만 유지
        interval_layout = QHBoxLayout()
        interval_label = QLabel("LOG Mode Timeout (minutes):")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 1440)
        self.interval_spinbox.setValue(60)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spinbox)
        main_layout.addLayout(interval_layout)

        # Threshold
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold (occurrences):")
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 100)
        self.threshold_spinbox.setValue(3)
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_spinbox)
        main_layout.addLayout(threshold_layout)

        # Paths
        main_layout.addLayout(self._make_path_input(
            "CSV Log File Path:", "monitoring_log_input", "Browse...", self.browse_csv_file))
        main_layout.addLayout(self._make_path_input(
            "Raw .LOG File Path:", "log_file_input", "Browse...", self.browse_log_file))
        main_layout.addLayout(self._make_path_input(
            "Converted Log TXT File Path:", "converted_log_input", "Save As...", self.browse_txt_file_save))

        # Converter exe name (설정 저장용)
        converter_layout = QHBoxLayout()
        converter_label = QLabel("Converter Executable Name:")
        self.converter_name_input = QLineEdit("g4_converter.exe")
        converter_layout.addWidget(converter_label)
        converter_layout.addWidget(self.converter_name_input)
        main_layout.addLayout(converter_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start / Register Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # Status
        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def _make_path_input(self, label_text, attr_name, button_text, callback):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit()
        button = QPushButton(button_text)
        button.clicked.connect(callback)
        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        setattr(self, attr_name, line_edit)
        return layout

    # ------- File dialogs
    def browse_csv_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV Log File", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            self.monitoring_log_input.setText(path)

    def browse_log_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Raw .log File", "", "Log Files (*.log);;All Files (*)")
        if path:
            self.log_file_input.setText(path)

    def browse_txt_file_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Converted TXT Output Path", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.converted_log_input.setText(path)

    # ------- Settings
    def load_settings(self):
        config_path = get_path("settings.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.monitor_interval_spinbox.setValue(settings.get("monitor_check_minutes", 30))
                self.interval_spinbox.setValue(settings.get("interval_minutes", 60))
                self.threshold_spinbox.setValue(settings.get("threshold", 3))
                self.monitoring_log_input.setText(settings.get("monitoring_log_file_path", ""))
                self.log_file_input.setText(settings.get("log_file_path", ""))
                self.converted_log_input.setText(settings.get("converted_log_file_path", ""))
                self.converter_name_input.setText(settings.get("converter_exe_name", "g4_converter.exe"))
                self.status_label.setText("Status: Settings loaded.")
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"settings.json 읽기 실패: {e}")
        else:
            self.status_label.setText("Status: Default settings in use.")

    def save_settings(self) -> bool:
        config_path = get_path("settings.json")
        settings = {
            "monitor_check_minutes": self.monitor_interval_spinbox.value(),
            "interval_minutes": self.interval_spinbox.value(),
            "threshold": self.threshold_spinbox.value(),
            "monitoring_log_file_path": self.monitoring_log_input.text(),
            "log_file_path": self.log_file_input.text(),
            "converted_log_file_path": self.converted_log_input.text(),
            "converter_exe_name": self.converter_name_input.text(),
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.status_label.setText("Status: Settings saved.")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"설정 저장 실패: {e}")
            return False

    # ------- Scheduler registration (완전 숨김 + 정확 체크 + 즉시 1회 실행)
    def start_monitoring(self):
        if not self.save_settings():
            return

        # 기존 스케줄/자동실행 제거 후 새로 세팅
        self.stop_monitoring(is_starting=True)

        try:
            worker_exe_path = os.path.abspath(get_path(self.worker_exe_name))
            if not os.path.exists(worker_exe_path):
                QMessageBox.critical(self, "Start Error", f"Worker executable not found:\n{worker_exe_path}")
                return

            worker_dir = os.path.dirname(worker_exe_path)
            worker_name_no_ext = os.path.splitext(os.path.basename(self.worker_exe_name))[0]
            monitor_minutes = max(1, int(self.monitor_interval_spinbox.value()))

            # 1) PowerShell 스크립트(.ps1) 생성: 없을 때만 실행 + 작업 디렉터리 지정
            ps1_path = os.path.abspath(get_path("monitor_worker.ps1"))
            ps1_content = f"""\
# monitor_worker.ps1  (UTF-8 with BOM 권장)
$ErrorActionPreference = 'SilentlyContinue'
$n  = '{worker_name_no_ext}'
$exe = '{worker_exe_path.replace("'", "''")}'
$wd  = '{worker_dir.replace("'", "''")}'
$p = Get-Process -Name $n -ErrorAction SilentlyContinue
if (-not $p) {{
    Start-Process -FilePath $exe -WorkingDirectory $wd -WindowStyle Hidden
}}
"""
            # UTF-8 with BOM으로 저장(한글 경로 안전)
            with open(ps1_path, "w", encoding="utf-8-sig") as f:
                f.write(ps1_content)

            # 2) VBS로 PowerShell을 '완전 숨김' 호출 (콘솔 깜빡임 제거)
            vbs_path = os.path.abspath(get_path("run_monitor_silent.vbs"))
            vbs_content = f'''\
' run_monitor_silent.vbs
On Error Resume Next
Dim shell, psPath, cmd, fso
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

psPath = shell.ExpandEnvironmentStrings("%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe")
If Not fso.FileExists(psPath) Then
    psPath = "powershell.exe"
End If

cmd = """" & psPath & """" & " -NoProfile -NonInteractive -ExecutionPolicy Bypass -File " & """" & "{ps1_path}" & """"
shell.Run cmd, 0, False  ' 0 = 숨김
Set shell = Nothing
Set fso = Nothing
'''.format(ps1_path=ps1_path.replace('"', '""'))
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write(vbs_content)

            # 3) 작업 스케줄러 등록: N분마다 VBS 실행
            monitor_task_name = "HeatingWorkerMonitor"
            cmd_monitor = f'schtasks /Create /TN "{monitor_task_name}" /TR "{vbs_path}" /SC MINUTE /MO {monitor_minutes} /F'
            subprocess.run(cmd_monitor, check=True, shell=True, capture_output=True)

            # 4) (옵션) 로그인 시 자동 실행 등록
            self.register_worker_autostart()

            # 5) 즉시 1회 실행: 워커가 없으면 지금 켜준다 (30분 기다리지 않게)
            if not is_process_running(self.worker_exe_name):
                subprocess.Popen(
                    [worker_exe_path],
                    creationflags=subprocess.DETACHED_PROCESS,
                    close_fds=True
                )

            QMessageBox.information(self, "Success", f"Monitoring registered: every {monitor_minutes} min hidden check & autorun at logon. (Started now if it wasn't running.)")
            self.status_label.setText("Status: Monitoring Registered & Started.")

        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Start Error", f"작업 스케줄러 등록 실패: {decode_bytes(e.stderr)}")
            self.status_label.setText("Status: Start Failed.")
        except Exception as e:
            QMessageBox.critical(self, "Start Error", f"Failed to register monitoring.\nError: {e}")
            self.status_label.setText("Status: Start Failed.")

    def stop_monitoring(self, is_starting: bool = False):
        self.unregister_worker_autostart()

        monitor_task_name = "HeatingWorkerMonitor"
        try:
            subprocess.run(f'schtasks /Delete /TN "{monitor_task_name}" /F',
                           shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass

        try:
            subprocess.run(f'taskkill /F /IM "{self.worker_exe_name}"',
                           shell=True, check=True, capture_output=True)
            if not is_starting:
                QMessageBox.information(self, "Success", "Monitoring stopped and auto-run unregistered.")
        except subprocess.CalledProcessError:
            pass

        self.status_label.setText("Status: Idle.")

    def register_worker_autostart(self):
        """로그온 시 한 번 실행. 원치 않으면 start_monitoring에서 이 함수 호출을 주석 처리."""
        exe_path = os.path.abspath(get_path(self.worker_exe_name))
        task_name = "HeatingWorkerAutoRun"
        cmd = f'schtasks /Create /TN "{task_name}" /TR "{exe_path}" /SC ONLOGON /F'
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Register Error", f"작업 스케줄러 등록 실패: {decode_bytes(e.stderr)}")

    def unregister_worker_autostart(self):
        task_name = "HeatingWorkerAutoRun"
        try:
            subprocess.run(f'schtasks /Delete /TN "{task_name}" /F',
                           shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass

    def closeEvent(self, event):
        event.accept()

# ----------------- Main -----------------
if __name__ == "__main__":
    try:
        import multiprocessing
        multiprocessing.freeze_support()
    except ImportError:
        pass

    app = QApplication(sys.argv)
    window = GUI_App()
    window.show()
    sys.exit(app.exec())