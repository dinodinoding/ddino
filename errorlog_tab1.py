import os
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QProgressBar, QStackedLayout, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
from utils.config_loader import load_config


class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # ▶ 설명 텍스트 (버튼 위에 표시)
        self.reload_desc = QLabel("ooooooooooooooooooooooooooooo")
        layout.addWidget(self.reload_desc)

        # ▶ 상단 HBox: 프로그래스바 + 버튼
        top_layout = QHBoxLayout()

        # 프로그래스바 (초기에는 숨겨짐)
        self.stretchy_layout = QStackedLayout()
        self.stretchy_layout.addWidget(QFrame())  # Spacer
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.stretchy_layout.addWidget(self.progress_bar)
        top_layout.addLayout(self.stretchy_layout, 1)  # 왼쪽에 확장 배치

        # 버튼 (오른쪽 고정 너비)
        self.reload_button = QPushButton("bat 실행 후 로그 다시 불러오기")
        self.reload_button.setFixedWidth(160)
        self.reload_button.clicked.connect(self.on_reload_clicked)
        top_layout.addWidget(self.reload_button)

        layout.addLayout(top_layout)

        # ▶ 로그 출력 영역
        layout.addWidget(QLabel("오류/경고 로그 보기:"))
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

        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)

    def on_reload_clicked(self):
        if not self.bat_path or not os.path.exists(self.bat_path):
            msg = f"[오류] 배치 파일이 존재하지 않습니다: {self.bat_path}"
            self.error_view.setPlainText(msg)
            return

        try:
            subprocess.Popen(self.bat_path, shell=True)
        except Exception as e:
            self.error_view.setPlainText(f"bat 실행 실패: {e}")
            return

        self.reload_button.setEnabled(False)
        self.stretchy_layout.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.elapsed_time = 0
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
        self.error_view.clear()
        if not self.error_files:
            self.error_view.setPlainText("에러 로그 파일이 지정되지 않았습니다.")
            return

        latest_time = None
        all_lines = []
        for path in self.error_files:
            if not os.path.exists(path):
                continue
            name = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.lower().startswith("time pid tid"):
                            continue
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
                continue

        if latest_time is None:
            self.error_view.setPlainText("로그에서 유효한 시간 정보를 찾을 수 없습니다.")
            return

        cutoff = latest_time - timedelta(days=1)
        levels = ['error', 'warning']

        html_lines = []
        max_len = max((len(f"[{os.path.basename(p)}]") for p in self.error_files), default=20)
        file_col_width = max_len + 2

        for ts, lvl, msg, name in sorted(all_lines, key=lambda x: x[0], reverse=True):
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

