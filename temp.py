# registry_tab.py (RegistryTabGroup, RegistryTab, RegistryEntry, CompareTab, RegistryStatusButton)

from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFrame,
    QScrollArea, QTabWidget, QGridLayout, QGraphicsDropShadowEffect
)
from PySide2.QtGui import QFont
import winreg
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from collections import OrderedDict
from PySide2.QtCore import Qt, QTimer # QTimer 임포트 추가

# --- 경로 설정 (현재 파일 기준) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(BASE_DIR, "settings")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
print("[설정 파일 경로]", SETTINGS_FILE)

# --- RegistryEntry 클래스 ---
class RegistryEntry(QFrame):
    def __init__(self, index, parent_group=None):
        super().__init__()
        self.parent_group = parent_group
        self.is_locked = False # 잠금 상태 초기화

        layout = QVBoxLayout(self)
        row0, row1, row2 = QHBoxLayout(), QHBoxLayout(), QHBoxLayout()

        self.title_input = QLineEdit()
        self.description_input = QLineEdit()
        self.root_combo = QComboBox(); self.root_combo.addItems(["HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"])
        self.path_input = QLineEdit()
        self.key_input = QLineEdit()
        self.type_combo = QComboBox(); self.type_combo.addItems(["REG_DWORD", "REG_SZ"])
        self.default_input = QLineEdit()
        self.value_input = QLineEdit()

        self.save_button = QPushButton(f"저장 {index+1}")
        self.save_button.clicked.connect(self.save_registry_value)

        self.lock_button = QPushButton("잠금") # 잠금 버튼 추가
        self.lock_button.clicked.connect(self.toggle_lock_fields)
        self.lock_button.setCheckable(True) # 토글 가능하게 설정

        row0.addWidget(QLabel("제목:")); row0.addWidget(self.title_input)
        row0.addWidget(QLabel("설명:")); row0.addWidget(self.description_input)
        row1.addWidget(QLabel("루트 키:")); row1.addWidget(self.root_combo)
        row1.addWidget(QLabel("경로:")); row1.addWidget(self.path_input)
        row2.addWidget(QLabel("키 이름:")); row2.addWidget(self.key_input)
        row2.addWidget(self.type_combo); row2.addWidget(QLabel("default value:")); row2.addWidget(self.default_input)
        row2.addWidget(QLabel("수정값:")); row2.addWidget(self.value_input)
        row2.addWidget(self.save_button)
        row2.addWidget(self.lock_button) # 잠금 버튼 배치

        layout.addLayout(row0); layout.addLayout(row1); layout.addLayout(row2)

    def get_data(self):
        # is_locked 상태도 함께 반환
        return {"title": self.title_input.text(), "description": self.description_input.text(),
                "root": self.root_combo.currentText(), "path": self.path_input.text(),
                "key": self.key_input.text(), "type": self.type_combo.currentText(),
                "default": self.default_input.text(), "value": self.value_input.text(),
                "is_locked": self.is_locked}

    def set_data(self, data):
        self.title_input.setText(data.get("title", "")); self.description_input.setText(data.get("description", ""))
        self.root_combo.setCurrentText(data.get("root", "HKEY_CURRENT_USER"))
        self.path_input.setText(data.get("path", "")); self.key_input.setText(data.get("key", ""))
        self.type_combo.setCurrentText(data.get("type", "REG_SZ")); self.default_input.setText(data.get("default", ""))
        self.value_input.setText(data.get("value", ""))
        # 저장된 잠금 상태를 불러와 적용
        self.is_locked = data.get("is_locked", False)
        self.lock_button.setChecked(self.is_locked)
        self.toggle_lock_fields(self.is_locked) # 잠금 상태에 따라 필드 업데이트

    def save_registry_value(self):
        if self.is_locked: # 잠금 상태일 때는 저장 불가
            QMessageBox.warning(self, "경고", "항목이 잠금 상태여서 저장할 수 없습니다.")
            return

        try:
            root = winreg.HKEY_CURRENT_USER if self.root_combo.currentText() == "HKEY_CURRENT_USER" else winreg.HKEY_LOCAL_MACHINE
            path = self.path_input.text()
            key_name = self.key_input.text()

            if not path or not key_name:
                QMessageBox.warning(self, "경고", "경로와 키 이름을 입력해야 합니다.")
                return

            with winreg.CreateKey(root, path) as key_handle:
                val = self.value_input.text()
                reg_type = winreg.REG_SZ

                if self.type_combo.currentText() == "REG_DWORD":
                    try:
                        val = int(val)
                        reg_type = winreg.REG_DWORD
                    except ValueError:
                        QMessageBox.critical(self, "오류", "REG_DWORD 타입은 유효한 정수여야 합니다.")
                        return

                winreg.SetValueEx(key_handle, key_name, 0, reg_type, val)
                QMessageBox.information(self, "성공", "레지스트리 저장 완료")
                if self.parent_group:
                    self.parent_group.save_settings()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"레지스트리 저장 실패: {e}")

    def toggle_lock_fields(self, checked):
        self.is_locked = checked
        self.title_input.setReadOnly(checked)
        self.description_input.setReadOnly(checked)
        self.root_combo.setEnabled(not checked)
        self.path_input.setReadOnly(checked)
        self.key_input.setReadOnly(checked)
        self.type_combo.setEnabled(not checked)
        self.default_input.setReadOnly(checked)
        self.value_input.setReadOnly(checked)
        self.save_button.setEnabled(not checked) # 저장 버튼도 잠금 상태에 따라 활성화/비활성화
        self.lock_button.setText("잠금 해제" if checked else "잠금")

        if self.parent_group:
            self.parent_group.save_settings() # 잠금 상태 변경 시 설정 저장

# --- RegistryTab 클래스 ---
class RegistryTab(QWidget):
    def __init__(self, tab_index, parent_group=None):
        super().__init__()
        self.entries = []
        layout = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content_widget = QWidget(); content_layout = QVBoxLayout(content_widget)
        for i in range(10):
            entry = RegistryEntry(i + tab_index * 10, parent_group=parent_group)
            self.entries.append(entry)
            content_layout.addWidget(entry)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

# --- CompareTab 클래스 (버튼 가운데 정렬 포함) ---
class CompareTab(QWidget):
    def __init__(self, get_all_entries_func):
        super().__init__()
        self.get_all_entries = get_all_entries_func
        layout = QVBoxLayout(self)

        refresh = QPushButton("Refresh")
        refresh.setFixedSize(200, 40)
        font = QFont(); font.setPointSize(12); font.setBold(True)
        refresh.setFont(font)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(refresh)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        refresh.clicked.connect(self.refresh)

        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        self.buttons = []
        self.refresh()

    def refresh(self):
        for btn in self.buttons:
            self.grid.removeWidget(btn)
            btn.deleteLater()
        self.buttons = []

        all_entries = self.get_all_entries()
        for i, entry in enumerate(all_entries):
            btn = RegistryStatusButton(entry, i)
            btn.update_status()
            self.buttons.append(btn)
            self.grid.addWidget(btn, i // 5, i % 5)

# --- RegistryStatusButton 클래스 ---
class RegistryStatusButton(QPushButton):
    def __init__(self, entry_widget, index):
        super().__init__(f"item {index+1}")
        self.entry = entry_widget
        self.setFixedSize(200, 80)
        shadow = QGraphicsDropShadowEffect(blurRadius=15, xOffset=5, yOffset=5)
        self.setGraphicsEffect(shadow)
        font = QFont(); font.setBold(True)
        self.setFont(font)

    def update_status(self):
        title = self.entry.title_input.text() or f"item {self.entry.save_button.text().split()[-1]}"
        display_lines = [title]
        status = ""
        style_sheet = ""

        if not self.entry.path_input.text() or not self.entry.key_input.text():
            status = "EMPTY"
            style_sheet = "QPushButton { color: black; }"
        else:
            root = winreg.HKEY_CURRENT_USER if self.entry.root_combo.currentText() == "HKEY_CURRENT_USER" else winreg.HKEY_LOCAL_MACHINE
            try:
                with winreg.OpenKey(root, self.entry.path_input.text()) as k:
                    current_val, _ = winreg.QueryValueEx(k, self.entry.key_input.text())
                    default_val = self.entry.default_input.text()
                    display_lines.append(f"{default_val} -> {current_val}")
                    if str(current_val) == default_val:
                        status = "DEFAULT"
                        style_sheet = "QPushButton { color: blue; }"
                    else:
                        status = "MODIFY"
                        style_sheet = "QPushButton { color: orange; }"
            except Exception as e:
                display_lines.append(f"Error: {e.__class__.__name__}")
                status = "오류"
                style_sheet = "QPushButton { color: grey; }"

        display_lines.append(status)
        self.setText("\n".join(display_lines))
        self.setStyleSheet(style_sheet)

# --- RegistryTabGroup 클래스 ---
class RegistryTabGroup(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.data_tabs = [RegistryTab(i, parent_group=self) for i in range(3)]
        for i, tab in enumerate(self.data_tabs):
            self.tabs.addTab(tab, f"LIST {i+1}")

        self.compare_tab = CompareTab(self.get_all_entries)
        self.tabs.insertTab(0, self.compare_tab, "REGISTRY STATUS")
        self.tabs.setCurrentIndex(0)

        layout.addWidget(self.tabs)
        self.load_settings()

    def get_all_entries(self):
        return [entry for tab in self.data_tabs for entry in tab.entries]

    def save_settings(self):
        all_data = [entry.get_data() for entry in self.get_all_entries()]
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            print("[⚠️ 설정 파일 없음 - 기본값 사용]")
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
            for entry, data in zip(self.get_all_entries(), all_data):
                entry.set_data(data)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "설정 파일 오류", f"설정 파일을 읽는 중 오류가 발생했습니다: {e}\n파일을 삭제하고 다시 시도하세요.")
            print(f"[❌ 설정 파일 로드 오류] {e}")
        except Exception as e:
            QMessageBox.critical(self, "설정 파일 오류", f"설정 파일을 로드하는 중 알 수 없는 오류가 발생했습니다: {e}")
            print(f"[❌ 설정 파일 로드 알 수 없는 오류] {e}")


# --- ErrorLogTab 클래스 ---
class ErrorLogTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # 설명 라벨
        self.description_label = QLabel(
            "이 탭은 g4_converter.exe를 실행하여 지정된 로그 파일을 변환하고, "
            "변환된 파일에서 최근 24시간 이내의 오류(ERROR) 및 경고(WARNING) 로그를 표시합니다. "
            "'config.json' 파일에 정의된 그룹별 로그를 선택하여 변환할 수 있습니다."
        )
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        # 상단 레이아웃 (진행률 + 버튼)
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        filter_layout.addWidget(self.progress_bar, stretch=1)

        self.reload_button = QPushButton("g4_converter 실행 및 로그 표시")
        self.reload_button.setFixedWidth(200)
        self.reload_button.clicked.connect(self.on_reload_clicked)
        filter_layout.addWidget(self.reload_button)

        # "All", "Selected", "Warning" 체크박스 섹션
        selection_layout = QHBoxLayout()
        self.all_checkbox = QCheckBox("모든 로그 (All)")
        self.selected_checkbox = QCheckBox("선택된 로그 그룹 (Selected)")
        self.warning_checkbox = QCheckBox("경고 (WARNING)")

        selection_layout.addWidget(self.all_checkbox)
        selection_layout.addWidget(self.selected_checkbox)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.warning_checkbox)
        selection_layout.addStretch(1)
        layout.addLayout(selection_layout)

        # 로그 그룹 선택 체크박스 + 드롭다운 섹션 (가로 정렬)
        layout.addWidget(QLabel("변환할 로그 그룹 선택 (개별 로그 선택 가능):"))

        self.group_selection_layout = QVBoxLayout() # 그룹별 QHBoxLayout을 담을 QVBoxLayout
        self.group_checkboxes = {}
        self.group_comboboxes = {} # 새 딕셔너리 추가: {그룹명: QComboBox}

        self.group_scroll_area = QScrollArea()
        self.group_scroll_area.setWidgetResizable(True)
        self.group_scroll_area_content = QWidget()
        self.group_scroll_area_content_layout = QVBoxLayout(self.group_scroll_area_content)
        self.group_scroll_area_content_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft) # 정렬 설정
        self.group_scroll_area.setWidget(self.group_scroll_area_content)
        layout.addWidget(self.group_scroll_area, stretch=0) # stretch=0으로 고정 높이 또는 최소 높이 유지

        # 스크롤 영역 안에 그룹별 레이아웃을 직접 추가할 것이므로 기존 group_checkbox_layout은 제거
        # self.group_checkbox_layout = QHBoxLayout() # QHBoxLayout 직접 생성
        # self.group_checkbox_layout.setAlignment(Qt.AlignLeft)
        # self.group_checkbox_layout.addStretch(1)
        # layout.addLayout(self.group_checkbox_layout) # 레이아웃을 메인 레이아웃에 직접 추가


        layout.addWidget(QLabel("오류/경고 로그 보기:"))
        self.error_view = QTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(QFont("Courier New"))
        layout.addWidget(self.error_view, 1)

        # --- 설정 파일 로드 및 경로 초기화 ---
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(current_script_dir, "settings", "config.json")

        self.config = self._load_config()
        if not self.config:
            self.reload_button.setEnabled(False)
            # 모든 위젯을 비활성화하는 대신, 특정 위젯만 비활성화 (설명 라벨 제외)
            for widget in self.findChildren(QWidget):
                if widget not in [self, layout, self.description_label]: # 기본 레이아웃과 자신, 설명 라벨 제외
                    widget.setEnabled(False)
            return

        self.converter_path = self.config.get("converter_path")
        self.output_dir = self.config.get("output_dir")

        updated_conversion_group_files = OrderedDict()
        for group_name, relative_path in self.config.get("conversion_groups", {}).items():
            if not os.path.isabs(relative_path):
                updated_conversion_group_files[group_name] = os.path.join(current_script_dir, "settings", relative_path)
            else:
                updated_conversion_group_files[group_name] = relative_path
        self.conversion_group_files = updated_conversion_group_files

        self._ensure_output_directory_exists()

        # 체크박스 시그널 연결
        self.all_checkbox.toggled.connect(self._handle_all_checkbox_toggled)
        self.selected_checkbox.toggled.connect(self._handle_selected_checkbox_toggled)

        self.warning_checkbox.toggled.connect(self._display_filtered_logs)

        # 시작 시 그룹 정보 로드 및 체크박스 생성
        self.log_groups = self._parse_all_group_files()
        self._create_group_checkboxes()

        # 초기 상태 설정
        self.all_checkbox.setChecked(True)
        self.warning_checkbox.setChecked(True)

        # 캐시 초기화
        self.cached_log_data = []

    def _ensure_output_directory_exists(self):
        """출력 디렉토리가 존재하는지 확인하고, 없으면 생성합니다."""
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                print(f"출력 디렉토리 생성: {self.output_dir}")
            except OSError as e:
                QMessageBox.critical(self, "디렉토리 생성 오류",
                                     f"출력 디렉토리 '{self.output_dir}'를 생성할 수 없습니다: {e}\n"
                                     "프로그램 실행에 문제가 있을 수 있습니다.")
                print(f"오류: 출력 디렉토리 생성 실패: {e}")

    def _load_config(self):
        """
        config.json 파일을 로드하여 설정을 반환합니다.
        """
        if not os.path.exists(self.config_path):
            QMessageBox.critical(self, "설정 파일 없음",
                                 f"설정 파일 '{self.config_path}'을(를) 찾을 수 없습니다.\n"
                                 "애플리케이션을 시작할 수 없습니다.")
            return None
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "설정 파일 오류",
                                 f"설정 파일 '{self.config_path}' 파싱 중 오류 발생: {e}\n"
                                 "JSON 형식을 확인해주세요. 애플리케이션을 시작할 수 없습니다.")
            return None
        except Exception as e:
            QMessageBox.critical(self, "설정 파일 오류",
                                 f"설정 파일 '{self.config_path}' 로드 중 알 수 없는 오류 발생: {e}\n"
                                 "애플리케이션을 시작할 수 없습니다.")
            return None

    def _parse_all_group_files(self):
        """
        config.json에 정의된 모든 그룹 파일들을 파싱하여
        그룹명과 해당 그룹에 속하는 로그 파일 경로 목록을 로드합니다.
        반환 형식: OrderedDict[str, List[str]]
        """
        all_parsed_groups = OrderedDict()
        for group_name, file_path in self.conversion_group_files.items():
            parsed_files = self._parse_single_list_file(file_path)
            all_parsed_groups[group_name] = parsed_files
        return all_parsed_groups

    def _parse_single_list_file(self, file_path):
        """
        단일 그룹 목록 파일(예: convert_motor_list.txt)을 파싱하여
        해당 그룹에 속하는 로그 파일 경로 목록을 반환합니다.
        """
        files_in_group = []
        if not os.path.exists(file_path):
            print(f"경고: 그룹 목록 파일 '{file_path}'을(를) 찾을 수 없습니다. 이 그룹은 비어있습니다.")
            return files_in_group

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    files_in_group.append(line)
        except Exception as e:
            QMessageBox.warning(self, "그룹 파일 읽기 오류",
                                 f"그룹 파일 '{os.path.basename(file_path)}'을(를) 읽는 중 오류 발생: {e}\n"
                                 "일부 로그가 누락될 수 있습니다.")
            print(f"오류: 그룹 파일 읽기 실패 '{file_path}': {e}")
        return files_in_group

    def _create_group_checkboxes(self):
        """
        로드된 그룹 정보를 기반으로 UI에 그룹 선택 체크박스와 드롭다운을 동적으로 생성합니다.
        """
        # 기존 위젯 제거
        while self.group_scroll_area_content_layout.count():
            item = self.group_scroll_area_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # QLayout.deleteLater() is not available, so manually clear
                self._clear_layout(item.layout())
        self.group_checkboxes = {}
        self.group_comboboxes = {}

        for group_name, log_files in self.log_groups.items():
            group_h_layout = QHBoxLayout()
            group_h_layout.setAlignment(Qt.AlignLeft)

            chk_box = QCheckBox(group_name)
            chk_box.toggled.connect(lambda checked, name=group_name: self._handle_group_checkbox_toggled(name, checked))
            self.group_checkboxes[group_name] = chk_box

            combo_box = QComboBox()
            # 파일 경로의 베이스네임만 보이도록 아이템 추가
            combo_box.addItem("--- 그룹 내 모든 로그 ---")
            for file_path in log_files:
                combo_box.addItem(os.path.basename(file_path))
            combo_box.setEnabled(False) # 기본적으로 비활성화
            self.group_comboboxes[group_name] = combo_box

            # 체크박스 상태에 따라 콤보박스 활성화/비활성화
            chk_box.toggled.connect(combo_box.setEnabled)

            group_h_layout.addWidget(chk_box)
            group_h_layout.addWidget(combo_box)
            group_h_layout.addStretch(1) # 우측 정렬을 위해 stretch 추가

            self.group_scroll_area_content_layout.addLayout(group_h_layout)

        # 초기 상태에서 모든 체크박스와 콤보박스 비활성화 (All/Selected에 따라 제어)
        for chk_box in self.group_checkboxes.values():
            chk_box.setEnabled(False)
        for combo_box in self.group_comboboxes.values():
            combo_box.setEnabled(False)

    def _clear_layout(self, layout):
        """Recursively clears a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())

    def _handle_all_checkbox_toggled(self, checked):
        """
        'All' 체크박스가 토글될 때 다른 체크박스와 콤보박스의 상태를 제어합니다.
        """
        if checked:
            self.selected_checkbox.setChecked(False)
            for group_name, chk_box in self.group_checkboxes.items():
                chk_box.setChecked(False)
                chk_box.setEnabled(False)
                self.group_comboboxes[group_name].setEnabled(False) # 콤보박스도 비활성화
        else:
            if not self.selected_checkbox.isChecked():
                for group_name, chk_box in self.group_checkboxes.items():
                    chk_box.setEnabled(True)
                    # chk_box가 활성화될 때 콤보박스도 활성화 (toggled 시그널로 연결됨)

    def _handle_selected_checkbox_toggled(self, checked):
        """
        'Selected' 체크박스가 토글될 때 다른 체크박스와 콤보박스의 상태를 제어합니다.
        """
        if checked:
            self.all_checkbox.setChecked(False)
            for group_name, chk_box in self.group_checkboxes.items():
                chk_box.setEnabled(True)
                # chk_box가 활성화될 때 콤보박스도 활성화 (toggled 시그널로 연결됨)
        else:
            if not self.all_checkbox.isChecked():
                for group_name, chk_box in self.group_checkboxes.items():
                    chk_box.setEnabled(False)
                    chk_box.setChecked(False) # 선택 해제 시 체크박스도 해제
                    self.group_comboboxes[group_name].setEnabled(False) # 콤보박스도 비활성화

    def _handle_group_checkbox_toggled(self, group_name, checked):
        """
        개별 그룹 체크박스가 토글될 때 'All'/'Selected' 체크박스와 콤보박스의 상태를 제어합니다.
        """
        # 콤보박스 활성화/비활성화는 이미 chk_box.toggled.connect(combo_box.setEnabled)로 연결됨

        if checked:
            if self.all_checkbox.isChecked():
                self.all_checkbox.setChecked(False)
                QApplication.processEvents() # UI 업데이트 강제
                self.group_checkboxes[group_name].setChecked(True) # 다시 체크되도록

            if not self.selected_checkbox.isChecked():
                self.selected_checkbox.setChecked(True)
        else:
            any_group_selected = any(chk.isChecked() for chk in self.group_checkboxes.values())
            if not any_group_selected and self.selected_checkbox.isChecked():
                self.selected_checkbox.setChecked(False)

    def on_reload_clicked(self):
        self.reload_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.error_view.clear()
        self.cached_log_data = []

        if not self.converter_path or not os.path.exists(self.converter_path):
            QMessageBox.critical(self, "파일 없음",
                                 f"g4_converter.exe를 찾을 수 없거나 경로가 유효하지 않습니다: {self.converter_path}\n"
                                 "config.json 파일을 확인해주세요.")
            self.error_view.setPlainText(f"오류: g4_converter.exe 파일 경로가 유효하지 않습니다.")
            self.reload_button.setEnabled(True)
            return

        log_files_to_convert = []
        if self.all_checkbox.isChecked():
            # "All" 선택 시, 드롭다운 메뉴 선택은 무시하고 모든 로그를 포함
            for files in self.log_groups.values():
                log_files_to_convert.extend(files)
            log_files_to_convert = list(set(log_files_to_convert))
            self.error_view.setPlainText("모든 로그 파일을 변환합니다...")
            QApplication.processEvents()
        elif self.selected_checkbox.isChecked():
            selected_groups = [name for name, chk_box in self.group_checkboxes.items() if chk_box.isChecked()]
            if not selected_groups:
                QMessageBox.warning(self, "선택 필요", "선택된 로그 그룹이 없습니다. 변환할 로그를 선택해주세요.")
                self.reload_button.setEnabled(True)
                self.error_view.setPlainText("변환할 로그 그룹이 선택되지 않았습니다.")
                return

            for group_name in selected_groups:
                combo_box = self.group_comboboxes[group_name]
                selected_log_display_name = combo_box.currentText()

                if selected_log_display_name == "--- 그룹 내 모든 로그 ---":
                    # 드롭다운에서 '모든 로그'가 선택된 경우 해당 그룹의 모든 로그 추가
                    log_files_to_convert.extend(self.log_groups.get(group_name, []))
                else:
                    # 특정 로그 파일이 선택된 경우 해당 로그만 추가
                    # 원본 파일 경로를 찾아야 함 (현재는 베이스네임만 드롭다운에 표시)
                    # self.log_groups[group_name]에서 베이스네임과 일치하는 전체 경로 찾기
                    found_path = next((full_path for full_path in self.log_groups.get(group_name, [])
                                       if os.path.basename(full_path) == selected_log_display_name), None)
                    if found_path:
                        log_files_to_convert.append(found_path)
                    else:
                        print(f"경고: 선택된 로그 파일 '{selected_log_display_name}'의 전체 경로를 찾을 수 없습니다.")

            log_files_to_convert = list(set(log_files_to_convert)) # 중복 제거
            self.error_view.setPlainText(f"선택된 그룹의 로그 파일을 변환합니다...")
            QApplication.processEvents()
        else:
            QMessageBox.warning(self, "선택 필요", "변환할 로그 그룹 옵션 ('모든 로그' 또는 '선택된 로그 그룹')을 선택해주세요.")
            self.reload_button.setEnabled(True)
            self.error_view.setPlainText("변환 옵션이 선택되지 않았습니다.")
            return

        if not log_files_to_convert:
            self.error_view.setPlainText("정보: 변환할 로그 파일 경로가 없습니다. 'config.json' 및 그룹 파일들을 확인해주세요.")
            self.reload_button.setEnabled(True)
            return

        total_files = len(log_files_to_convert)
        self.total_steps = total_files * 2 # 변환 + 로드/파싱
        self.progress_bar.setRange(0, self.total_steps)
        self.current_step = 0

        converted_paths = []
        for i, log_path in enumerate(log_files_to_convert):
            self.error_view.setPlainText(f"변환 중... ({i+1}/{total_files}): {os.path.basename(log_path)}")
            QApplication.processEvents()

            if not os.path.exists(log_path):
                print(f"경고: 원본 파일 없음 (변환 스킵): {log_path}")
                self._increment_progress()
                continue

            base_name = os.path.basename(log_path).replace(".log", ".txt")
            out_path = os.path.join(self.output_dir, base_name)

            try:
                # PySide2에서는 CREATE_NO_WINDOW 대신 win32con 사용 또는 None
                startupinfo = None
                if sys.platform == "win32":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
                    startupinfo = si

                result = subprocess.run(
                    [self.converter_path, log_path, out_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    encoding='utf-8',
                    startupinfo=startupinfo # PySide2 호환성 위해 수정
                )

                if result.returncode == 0:
                    converted_paths.append(out_path)
                    print(f"변환 성공: {log_path} -> {out_path}")
                else:
                    error_message = result.stderr or result.stdout or "알 수 없는 오류"
                    print(f"오류: 변환 실패 (Return Code: {result.returncode}): {log_path}")
                    self.error_view.setPlainText(f"오류: 변환 실패: {os.path.basename(log_path)}\n{error_message.strip()}")
                    QApplication.processEvents()

            except FileNotFoundError:
                QMessageBox.critical(self, "실행 파일 없음",
                                     f"g4_converter.exe를 찾을 수 없습니다: {self.converter_path}")
                print(f"오류: g4_converter.exe 실행 파일 찾을 수 없음: {self.converter_path}")
                break
            except Exception as e:
                QMessageBox.critical(self, "변환 중 오류",
                                     f"파일 '{os.path.basename(log_path)}' 변환 중 예외 발생: {e}")
                print(f"오류: 변환 중 예외 발생: {e}")
                break

            self._increment_progress()

        self.error_files = converted_paths
        self._load_and_cache_logs()
        self._display_filtered_logs()

        self.reload_button.setEnabled(True)

    def _increment_progress(self):
        """진행률 바를 한 단계 증가시킵니다."""
        self.current_step += 1
        if self.current_step > self.total_steps:
            self.current_step = self.total_steps
        self.progress_bar.setValue(self.current_step)
        QApplication.processEvents()

    def try_parse_time(self, text):
        """
        주어진 텍스트에서 시간 정보를 파싱합니다.
        예상되는 시간 형식: "YYYY-MM-DD HH:MM:SS.ms" 또는 "YYYY-MM-DD HH:MM:SS"
        """
        if not isinstance(text, str) or len(text) > 50:
            return None

        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt_obj = datetime.strptime(text.strip(), fmt)
                return dt_obj
            except ValueError:
                continue
            except Exception as e:
                print(f"디버그: try_parse_time에서 알 수 없는 예외 발생: {e}, 입력 텍스트: '{text}'")
                return None
        return None

    def _load_and_cache_logs(self):
        """
        변환된 로그 파일들을 읽어 파싱하고 캐시에 저장합니다.
        """
        self.cached_log_data = []
        if not self.error_files:
            self.error_view.setPlainText("변환된 에러 로그 파일이 없습니다.")
            return

        total_files_to_process = len(self.error_files)
        processed_files_count = 0

        latest_time = None

        for path in self.error_files:
            self.error_view.setPlainText(f"로그 로딩 및 분석 중... ({processed_files_count+1}/{total_files_to_process}): {os.path.basename(path)}")
            QApplication.processEvents()

            self._increment_progress()

            if not os.path.exists(path):
                print(f"경고: 변환된 파일 없음 (로딩 스킵): {path}")
                processed_files_count += 1
                continue

            name = os.path.basename(path)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f):
                        if line.strip().lower().startswith("time pid tid"):
                            continue

                        # PySide2 환경에서 필요한 수정: split(None, 6)은 동일하게 작동
                        parts = line.strip().split(None, 6)

                        if len(parts) < 7:
                            continue

                        timestamp_str = f"{parts[0]} {parts[1]}"
                        ts = self.try_parse_time(timestamp_str)
                        if not ts:
                            continue

                        lvl = parts[4].lower()
                        msg = parts[6].strip()

                        self.cached_log_data.append((ts, lvl, msg, name))
                        if latest_time is None or ts > latest_time:
                            latest_time = ts

            except Exception as e:
                print(f"오류: 파일 '{name}' 처리 중 예외 발생: {e}")
                QMessageBox.warning(self, "파일 처리 오류",
                                     f"'{name}' 파일을 읽는 중 오류가 발생했습니다: {e}\n"
                                     "해당 파일의 로그는 표시되지 않을 수 있습니다.")
            processed_files_count += 1

        self.latest_log_time = latest_time
        # 마지막 진행률 업데이트 보정
        if self.current_step < self.total_steps:
             self.progress_bar.setValue(self.total_steps)
        QApplication.processEvents()


    def _display_filtered_logs(self):
        """
        캐시된 로그 데이터를 바탕으로 필터링하여 표시합니다.
        """
        self.error_view.clear()
        if not self.cached_log_data:
            self.error_view.setPlainText("표시할 로그 데이터가 없습니다. 먼저 'g4_converter 실행 및 로그 표시' 버튼을 눌러 로그를 변환하고 불러오세요.")
            return

        levels_to_display = ['error']
        if self.warning_checkbox.isChecked():
            levels_to_display.append('warning')

        time_range = timedelta(days=1)
        cutoff = self.latest_log_time - time_range if self.latest_log_time else datetime.min

        html_lines = []

        filtered_logs = []
        for ts, lvl, msg, name in self.cached_log_data:
            if ts >= cutoff and lvl in levels_to_display:
                filtered_logs.append((ts, lvl, msg, name))

        # 최신 로그부터 표시하기 위해 정렬
        for ts, lvl, msg, name in sorted(filtered_logs, key=lambda x: x[0], reverse=True):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # 밀리초를 세 자리로
            file_col = f"[{name}]"
            level_colored = {
                "error": '<span style="color:red; font-weight:bold;">ERROR</span>',
                "warning": '<span style="color:orange;">WARNING</span>'
            }.get(lvl, lvl.upper())

            html_lines.append(
                f'<span style="font-family:Courier New; white-space:pre-wrap;">'
                f'{file_col:<30}{ts_str:<25}' # 파일명 컬럼 너비 조정 (예: 30)
                f'{level_colored:<10}{msg}</span>'
            )

        if html_lines:
            self.error_view.setHtml("<br>".join(html_lines))
        else:
            self.error_view.setPlainText("정보: 선택된 필터에 해당하는 로그가 최근 24시간 이내에 없습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("로그 뷰어 및 레지스트리 관리")
            self.setGeometry(100, 100, 1200, 800) # 윈도우 크기 확대

            tab_widget = QTabWidget()
            self.setCentralWidget(tab_widget)

            registry_tab_group = RegistryTabGroup()
            tab_widget.addTab(registry_tab_group, "레지스트리 관리")

            error_log_tab = ErrorLogTab()
            tab_widget.addTab(error_log_tab, "오류/경고 로그")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) # PySide2에서는 app.exec_() 사용
