# 파일명: error_log_viewer_tab.py

# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QCheckBox,
    QTextEdit, QMessageBox, QScrollArea, QComboBox
)
from PySide2.QtGui import QFont
from PySide2.QtCore import Qt
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from collections import OrderedDict

# ----------------------------------------------------------------------
# 🔹 [메인 클래스] 오류 로그를 변환하고 표시하는 UI 탭 (ErrorLogTab)
# ----------------------------------------------------------------------
class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)

        # --- UI 요소 생성 및 배치 ---
        # 1. 설명 라벨
        desc = QLabel(
            "이 탭은 g4_converter.exe를 실행하여 지정된 로그 파일을 변환하고, "
            "변환된 파일에서 최근 24시간 이내의 오류(ERROR) 및 경고(WARNING) 로그를 표시합니다."
        )
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # 2. 컨트롤 패널 (진행률 바 + 실행 버튼)
        controls_layout = QHBoxLayout()
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(True); self.progress_bar.setFixedHeight(10)
        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시"); self.reload_button.setFixedWidth(200)
        controls_layout.addWidget(self.progress_bar, 1); controls_layout.addWidget(self.reload_button)
        main_layout.addLayout(controls_layout)
        
        # 3. 필터링 옵션 체크박스
        filter_layout = QHBoxLayout()
        self.all_checkbox = QCheckBox("모든 로그 (All)")
        self.selected_checkbox = QCheckBox("선택된 로그 그룹 (Selected)")
        self.warning_checkbox = QCheckBox("경고 (WARNING)")
        filter_layout.addWidget(self.all_checkbox); filter_layout.addWidget(self.selected_checkbox)
        filter_layout.addSpacing(20); filter_layout.addWidget(self.warning_checkbox); filter_layout.addStretch(1)
        main_layout.addLayout(filter_layout)

        # 4. 로그 그룹 선택 UI (가로 스크롤)
        main_layout.addWidget(QLabel("변환할 로그 그룹 선택 (개별 로그 선택 가능):"))
        self.group_scroll_area = QScrollArea(); self.group_scroll_area.setWidgetResizable(True)
        self.group_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.group_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container_widget = QWidget()
        self.group_container_layout = QHBoxLayout(container_widget)
        self.group_container_layout.setAlignment(Qt.AlignLeft)
        self.group_scroll_area.setWidget(container_widget)
        main_layout.addWidget(self.group_scroll_area)

        # 5. 로그 표시 영역
        main_layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit(); self.error_view.setReadOnly(True); self.error_view.setFont(QFont("Courier New"))
        main_layout.addWidget(self.error_view, 1)

        # --- 변수 초기화 및 설정 로드 ---
        self.group_checkboxes, self.group_comboboxes = {}, {}
        self.cached_log_data, self.latest_log_time = [], None

        # 설정 파일 경로 설정 및 로드
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(base_dir, "settings", "config.json")
        self.config = self._load_config()
        if not self.config:
            self.reload_button.setEnabled(False) # 설정 없으면 버튼 비활성화
            return

        self.converter_path = self.config.get("converter_path")
        self.output_dir = self.config.get("output_dir")
        self._ensure_output_dir()

        # 설정 파일의 상대 경로를 절대 경로로 변환
        self.conversion_group_files = OrderedDict()
        for group, path in self.config.get("conversion_groups", {}).items():
            self.conversion_group_files[group] = path if os.path.isabs(path) else os.path.join(base_dir, "settings", path)

        # --- 시그널 연결 및 초기 UI 설정 ---
        self.reload_button.clicked.connect(self.on_reload_clicked)
        self.all_checkbox.toggled.connect(self._handle_all_selected_toggled)
        self.selected_checkbox.toggled.connect(self._handle_all_selected_toggled)
        self.warning_checkbox.toggled.connect(self._display_filtered_logs)
        
        self.log_groups = self._parse_all_group_files()
        self._create_group_widgets()
        
        self.all_checkbox.setChecked(True) # 기본값으로 'All' 선택
        self.warning_checkbox.setChecked(True) # 기본값으로 'Warning' 포함

    def _load_config(self):
        """config.json 파일을 안전하게 로드합니다."""
        if not os.path.exists(self.config_path):
            QMessageBox.critical(self, "설정 파일 없음", f"설정 파일 '{self.config_path}'을(를) 찾을 수 없습니다."); return None
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "설정 파일 오류", f"설정 파일 '{self.config_path}' 로드 중 오류 발생: {e}"); return None

    def _ensure_output_dir(self):
        """출력 디렉토리가 없으면 생성합니다."""
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _parse_all_group_files(self):
        """모든 그룹 목록 파일을 파싱하여 {그룹명: [로그파일 경로들]} 딕셔너리를 만듭니다."""
        all_groups = OrderedDict()
        for group_name, file_path in self.conversion_group_files.items():
            files_in_group = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'): files_in_group.append(line)
            all_groups[group_name] = files_in_group
        return all_groups

    def _create_group_widgets(self):
        """파싱된 그룹 정보를 바탕으로 UI에 체크박스와 콤보박스를 동적으로 생성합니다."""
        # 기존 위젯들 제거
        while self.group_container_layout.count():
            self.group_container_layout.takeAt(0).widget().setParent(None)
        
        for group_name, log_files in self.log_groups.items():
            chk = QCheckBox(group_name)
            combo = QComboBox()
            combo.addItem("--- 그룹 내 모든 로그 ---")
            combo.addItems([os.path.basename(f) for f in log_files])
            
            chk.toggled.connect(combo.setEnabled) # 체크박스 상태에 따라 콤보박스 활성화/비활성화
            
            group_layout = QVBoxLayout()
            group_layout.addWidget(chk); group_layout.addWidget(combo)
            self.group_container_layout.addLayout(group_layout)
            self.group_checkboxes[group_name] = chk
            self.group_comboboxes[group_name] = combo
        
        self.group_container_layout.addStretch(1)

    def _handle_all_selected_toggled(self):
        """'All' 또는 'Selected' 체크박스가 변경될 때의 UI 로직을 처리합니다."""
        sender = self.sender()
        is_all = sender == self.all_checkbox and self.all_checkbox.isChecked()
        is_selected = sender == self.selected_checkbox and self.selected_checkbox.isChecked()
        
        if is_all: self.selected_checkbox.setChecked(False)
        if is_selected: self.all_checkbox.setChecked(False)
        
        enable_groups = self.selected_checkbox.isChecked()
        for chk in self.group_checkboxes.values():
            chk.setEnabled(enable_groups)
            if not enable_groups: chk.setChecked(False)

    def on_reload_clicked(self):
        """'실행' 버튼 클릭 시 로그 변환 및 표시 프로세스를 시작합니다."""
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.error_view.clear()
        
        # 1. 변환할 로그 파일 목록 결정
        files_to_convert = []
        if self.all_checkbox.isChecked():
            files_to_convert = [f for files in self.log_groups.values() for f in files]
        elif self.selected_checkbox.isChecked():
            for name, chk in self.group_checkboxes.items():
                if chk.isChecked():
                    combo = self.group_comboboxes[name]
                    if combo.currentIndex() == 0: # '-- 모든 로그 --' 선택 시
                        files_to_convert.extend(self.log_groups[name])
                    else: # 특정 로그 선택 시
                        selected_basename = combo.currentText()
                        full_path = next((p for p in self.log_groups[name] if os.path.basename(p) == selected_basename), None)
                        if full_path: files_to_convert.append(full_path)
        
        files_to_convert = list(set(files_to_convert)) # 중복 제거
        if not files_to_convert:
            QMessageBox.warning(self, "선택 필요", "변환할 로그 파일이 없습니다."); self.reload_button.setEnabled(True); return

        # 2. 변환 실행 및 진행률 업데이트
        total = len(files_to_convert)
        self.progress_bar.setRange(0, total * 2) # 변환 + 파싱
        step = 0
        converted_paths = []
        
        for i, log_path in enumerate(files_to_convert):
            self.error_view.setPlainText(f"변환 중 ({i+1}/{total}): {os.path.basename(log_path)}"); QApplication.processEvents()
            step += 1; self.progress_bar.setValue(step)
            
            if not os.path.exists(log_path): continue
            
            out_path = os.path.join(self.output_dir, os.path.basename(log_path).replace(".log", ".txt"))
            try:
                # 콘솔 창이 나타나지 않도록 실행
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
                subprocess.run([self.converter_path, log_path, out_path], check=True, startupinfo=si)
                converted_paths.append(out_path)
            except Exception as e:
                print(f"변환 오류: {e}")
        
        # 3. 변환된 파일 로드, 캐싱, 필터링 후 표시
        self._load_and_cache_logs(converted_paths, step)
        self._display_filtered_logs()
        self.reload_button.setEnabled(True)

    def _load_and_cache_logs(self, file_paths, progress_step):
        """변환된 로그 파일들을 읽어 파싱하고 캐시에 저장합니다."""
        self.cached_log_data, self.latest_log_time = [], None
        total = len(file_paths)
        
        for i, path in enumerate(file_paths):
            self.error_view.setPlainText(f"분석 중 ({i+1}/{total}): {os.path.basename(path)}"); QApplication.processEvents()
            progress_step += 1; self.progress_bar.setValue(progress_step)
            
            if not os.path.exists(path): continue
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parts = line.strip().split(None, 6)
                    if len(parts) < 7: continue
                    ts_str = f"{parts[0]} {parts[1]}"
                    ts = self._try_parse_time(ts_str)
                    if not ts: continue
                    
                    lvl, msg = parts[4].lower(), parts[6].strip()
                    self.cached_log_data.append((ts, lvl, msg, os.path.basename(path)))
                    if self.latest_log_time is None or ts > self.latest_log_time:
                        self.latest_log_time = ts

    def _display_filtered_logs(self):
        """캐시된 로그 데이터를 필터링하여 뷰어에 표시합니다."""
        self.error_view.clear()
        if not self.cached_log_data:
            self.error_view.setPlainText("표시할 로그가 없습니다."); return

        levels = ['error']
        if self.warning_checkbox.isChecked(): levels.append('warning')
        
        cutoff = self.latest_log_time - timedelta(days=1) if self.latest_log_time else datetime.min
        
        filtered = [log for log in self.cached_log_data if log[0] >= cutoff and log[1] in levels]
        
        html = []
        for ts, lvl, msg, name in sorted(filtered, key=lambda x: x[0], reverse=True):
            ts_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            color = "red" if lvl == 'error' else 'orange'
            html.append(f'<span style="white-space:pre-wrap;">[{name[:15]:<15}] {ts_str} '
                        f'<b style="color:{color};">{lvl.upper():<7}</b> {msg}</span>')
        
        if html: self.error_view.setHtml("<br>".join(html))
        else: self.error_view.setPlainText("최근 24시간 내에 필터에 맞는 로그가 없습니다.")

    def _try_parse_time(self, text):
        """다양한 형식의 시간 문자열을 파싱합니다."""
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try: return datetime.strptime(text.strip(), fmt)
            except ValueError: continue
        return None
