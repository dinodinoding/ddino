import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QComboBox, QCheckBox, QProgressBar,
    QStackedLayout, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from utils.config_loader import load_config
import subprocess


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        print(">> ErrorLogTab 초기화 시작")

        layout = QVBoxLayout(self)

        # 상단 필터 옵션
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        filter_layout.addWidget(QLabel("기간 선택:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["30분", "1시간", "6시간", "12시간", "1일"])
        self.time_combo.currentTextChanged.connect(self.load_error_log)
        filter_layout.addWidget(self.time_combo)

        self.include_warning = QCheckBox("Warning 포함")
        self.include_warning.stateChanged.connect(self.load_error_log)
        filter_layout.addWidget(self.include_warning)

        self.stretchy_layout = QStackedLayout()
        spacer = QFrame()
        spacer.setFrameShape(QFrame.NoFrame)
        self.stretchy_layout.addWidget(spacer)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 20000)
        self.progress_bar.setTextVisible(True)
        self.stretchy_layout.addWidget(self.progress_bar)

        filter_layout.addLayout(self.stretchy_layout, 1)

        self.reload_button = QPushButton("bat 실행 후 로그 다시 불러오기")
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        layout.addWidget(QLabel("선택한 기간의 오류/경고 로그:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        # 설정 로드
        try:
            cfg = load_config()
        except Exception as e:
            print(f"[에러] config 로드 실패: {e}")
            cfg = {}
        self.error_files = cfg.get("error_logs", [])
        self.bat_path = cfg.get("batch_file", "")
        if not self.error_files:
            print("[경고] error_logs가 비어있음")
        if not self.bat_path:
            print("[경고] batch_file 경로가 비어있음")
        print(f">> 로드된 로그 파일 목록: {self.error_files}")
        print(f">> 실행할 배치 파일 경로: {self.bat_path}")

        self.load_error_log()
        print(">> ErrorLogTab 초기화 완료")

    def on_reload_clicked(self):
        print(">> [사용자 클릭] bat 실행 및 로그 재로드 요청")
        if not self.bat_path or not os.path.exists(self.bat_path):
            msg = f"[오류] 배치 파일이 존재하지 않습니다: {self.bat_path}"
            self.error_view.setPlainText(msg)
            print(msg)
            return

        try:
            subprocess.Popen(self.bat_path, shell=True)
            print(f">> bat 실행: {self.bat_path}")
        except Exception as e:
            print(f"[예외] bat 실행 실패: {e}")
            self.error_view.setPlainText(f"bat 실행 실패: {e}")
            return

        self.reload_button.setEnabled(False)
        self.stretchy_layout.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.elapsed_time = 0
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(100)

    def _update_progress(self):
        self.elapsed_time += 100
        self.progress_bar.setValue(self.elapsed_time)
        if self.elapsed_time >= 20000:
            self.progress_timer.stop()
            self.stretchy_layout.setCurrentIndex(0)
            self.reload_button.setEnabled(True)
            self.load_error_log()

    def try_parse_time(self, text):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
        return None

    def load_error_log(self):
        print(">> 로그 로드 시작")
        self.error_view.clear()

        if not self.error_files:
            self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
            return

        selected = self.time_combo.currentText()
        delta_map = {
            "30분": timedelta(minutes=30),
            "1시간": timedelta(hours=1),
            "6시간": timedelta(hours=6),
            "12시간": timedelta(hours=12),
            "1일": timedelta(days=1),
        }
        time_range = delta_map.get(selected, timedelta(minutes=30))

        try:
            max_len = max(len(f"[{os.path.basename(p)}]") for p in self.error_files)
            file_col_width = max_len + 2
        except Exception as e:
            print(f"[경고] 파일명 길이 계산 실패: {e}")
            file_col_width = 20

        all_lines = []
        latest_time = None

        for path in self.error_files:
            if not os.path.exists(path):
                print(f"!! 로그 파일 없음: {path}")
                continue
            name = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.lower().startswith("time pid tid"):
                            continue  # 헤더 스킵
                        parts = line.strip().split(None, 6)
                        if len(parts) < 7:
                            continue

                        ts = self.try_parse_time(f"{parts[0]} {parts[1]}")
                        if not ts:
                            continue
                        lvl = parts[4].lower()
                        msg = parts[6].strip()

                        latest_time = ts if latest_time is None or ts > latest_time else latest_time
                        all_lines.append((ts, lvl, msg, name))
            except Exception as e:
                print(f"!! 파일 처리 중 예외: {e}")
                continue

        if latest_time is None:
            self.error_view.setPlainText("로그에서 유효한 시간 정보를 찾을 수 없습니다.")
            return

        cutoff = latest_time - time_range
        levels = ['error']
        if self.include_warning.isChecked():
            levels.append('warning')

        html_lines = []
        for ts, lvl, msg, name in all_lines:
            if ts < cutoff or lvl not in levels:
                continue
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red;">ERROR</span>',
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper())

            html_lines.append(
                f'<span style="color:black; font-family:Courier New;">'
                f'{file_col:<{file_col_width}}{ts_str:<25}'
                f'{level_colored:<10}{msg}</span>'
            )

        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("해당 시간 구간의 로그가 없습니다.")