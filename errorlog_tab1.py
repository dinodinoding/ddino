import os
import subprocess
import sys
import json
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton,
    QHBoxLayout, QProgressBar, QCheckBox, QGroupBox, QMessageBox, QApplication
)
from PySide6.QtGui import QFont

class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.description_label = QLabel(
            "이 탭은 g4_converter.exe를 실행하여 선택된 항목에 해당하는 로그 파일을 변환하고, "
            "변환된 파일에서 최근 24시간 이내의 오류(ERROR) 및 경고(WARNING) 로그를 표시합니다. "
            "변환 대상 파일은 config.json에 정의된 분류 항목에 따라 분리됩니다."
        )
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.checkbox_group = QGroupBox("변환 항목 선택")
        checkbox_layout = QHBoxLayout()
        self.checkbox_group.setLayout(checkbox_layout)
        layout.addWidget(self.checkbox_group)

        self.checkboxes = {}
        self.selected_mode = None
        self.config_path = "config.json"
        self.converter_path = "C:/monitoring/g4_converter.exe"
        self.output_dir = "C:/monitoring/errorlog"
        self.error_files = []

        self.load_config()

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        layout.addWidget(self.progress_bar)

        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시")
        self.reload_button.clicked.connect(self.on_reload_clicked)
        layout.addWidget(self.reload_button)

        layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view)

        self._ensure_output_directory_exists()
    def load_config(self):
        if not os.path.exists(self.config_path):
            QMessageBox.critical(self, "설정 파일 없음", f"config.json 파일을 찾을 수 없습니다.")
            return

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.group_map = config.get("conversion_groups", {})
        for key in self.group_map:
            cb = QCheckBox(key.capitalize())
            cb.stateChanged.connect(self.on_checkbox_state_changed)
            self.checkboxes[key] = cb
            self.checkbox_group.layout().addWidget(cb)

    def on_checkbox_state_changed(self):
        selected_keys = [k for k, cb in self.checkboxes.items() if cb.isChecked()]
        if "all" in selected_keys or "selected" in selected_keys:
            for k, cb in self.checkboxes.items():
                if k not in ("all", "selected"):
                    cb.setEnabled(False)
        else:
            for k, cb in self.checkboxes.items():
                cb.setEnabled(True)

    def _ensure_output_directory_exists(self):
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
            except OSError as e:
                QMessageBox.critical(self, "디렉토리 생성 오류",
                                     f"출력 디렉토리 생성 실패: {e}")

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.error_view.clear()

        if not os.path.exists(self.converter_path):
            QMessageBox.critical(self, "파일 없음",
                                 f"g4_converter.exe 경로가 유효하지 않습니다.")
            self.reload_button.setEnabled(True)
            return

        selected_keys = [k for k, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected_keys:
            QMessageBox.information(self, "선택 없음", "하나 이상의 항목을 선택해주세요.")
            self.reload_button.setEnabled(True)
            return

        convert_files = []
        for key in selected_keys:
            list_path = self.group_map.get(key)
            if list_path and os.path.exists(list_path):
                with open(list_path, 'r', encoding='utf-8') as f:
                    convert_files.extend([line.strip() for line in f if line.strip()])
            else:
                print(f"리스트 파일 누락: {list_path}")

        if not convert_files:
            self.error_view.setPlainText("선택한 항목에 대한 로그 파일이 없습니다.")
            self.reload_button.setEnabled(True)
            return

        self.total_steps = len(convert_files) * 2
        self.progress_bar.setRange(0, self.total_steps)
        self.current_step = 0

        converted_paths = []
        for log_path in convert_files:
            if not os.path.exists(log_path):
                self._increment_progress()
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            result = subprocess.run(
                [self.converter_path, log_path, out_path],
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False
            )

            if result.returncode == 0:
                converted_paths.append(out_path)
            else:
                self.error_view.setPlainText(f"변환 실패: {log_path}")
            self._increment_progress()

        self.error_files = converted_paths
        self.load_error_log()
        self.reload_button.setEnabled(True)
    def _increment_progress(self):
        self.current_step += 1
        if self.current_step > self.total_steps:
            self.current_step = self.total_steps
        self.progress_bar.setValue(self.current_step)
        QApplication.processEvents()

    def try_parse_time(self, text):
        if not isinstance(text, str) or len(text) > 50:
            return None
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

        time_range = timedelta(days=1)
        all_lines = []
        latest_time = None

        for path in self.error_files:
            self._increment_progress()
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.strip().lower().startswith("time pid tid"):
                        continue
                    parts = line.strip().split(None, 6)
                    if len(parts) < 7:
                        continue
                    timestamp_str = f"{parts[0]} {parts[1]}"
                    ts = self.try_parse_time(timestamp_str)
                    if not ts:
                        continue
                    lvl = parts[4].lower()
                    msg = parts[6].strip()
                    name = os.path.basename(path)
                    if latest_time is None or ts > latest_time:
                        latest_time = ts
                    all_lines.append((ts, lvl, msg, name))

        if latest_time is None:
            self.error_view.setPlainText("로그에서 시간 정보를 찾을 수 없습니다.")
            return

        cutoff = latest_time - time_range
        levels_to_display = ['error', 'warning']
        html_lines = []
        for ts, lvl, msg, name in sorted(all_lines, key=lambda x: x[0], reverse=True):
            if ts < cutoff or lvl not in levels_to_display:
                continue
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red; font-weight:bold;">ERROR</span>',
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper())
            html_lines.append(
                f'<span style="font-family:Courier New; white-space:pre-wrap;">'
                f'{file_col:<30}{ts_str:<25}'
                f'{level_colored:<10}{msg}</span>'
            )

        self.progress_bar.setValue(self.total_steps)
        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("최근 24시간 내 오류 또는 경고 로그가 없습니다.")
            