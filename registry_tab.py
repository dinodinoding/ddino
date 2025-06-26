# registry_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFrame,
    QScrollArea, QTabWidget, QGridLayout, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QFont
import winreg
import json
import os

# --- 1. RegistryEntry 클래스 ---
# 기능: 단일 레지스트리 항목의 입력 필드들을 관리합니다. (변경 없음)
class RegistryEntry(QFrame):
    def __init__(self, index):
        super().__init__()
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
        
        row0.addWidget(QLabel("제목:")); row0.addWidget(self.title_input)
        row0.addWidget(QLabel("설명:")); row0.addWidget(self.description_input)
        row1.addWidget(QLabel("루트 키:")); row1.addWidget(self.root_combo)
        row1.addWidget(QLabel("경로:")); row1.addWidget(self.path_input)
        row2.addWidget(QLabel("키 이름:")); row2.addWidget(self.key_input)
        row2.addWidget(self.type_combo); row2.addWidget(QLabel("default value:")); row2.addWidget(self.default_input)
        row2.addWidget(QLabel("수정값:")); row2.addWidget(self.value_input); row2.addWidget(self.save_button)
        
        layout.addLayout(row0); layout.addLayout(row1); layout.addLayout(row2)

    def get_data(self):
        return {"title": self.title_input.text(), "description": self.description_input.text(),
                "root": self.root_combo.currentText(), "path": self.path_input.text(),
                "key": self.key_input.text(), "type": self.type_combo.currentText(),
                "default": self.default_input.text(), "value": self.value_input.text()}

    def set_data(self, data):
        self.title_input.setText(data.get("title", "")); self.description_input.setText(data.get("description", ""))
        self.root_combo.setCurrentText(data.get("root", "HKEY_CURRENT_USER"))
        self.path_input.setText(data.get("path", "")); self.key_input.setText(data.get("key", ""))
        self.type_combo.setCurrentText(data.get("type", "REG_SZ")); self.default_input.setText(data.get("default", ""))
        self.value_input.setText(data.get("value", ""))

    def save_registry_value(self):
        try:
            root = winreg.HKEY_CURRENT_USER if self.root_combo.currentText() == "HKEY_CURRENT_USER" else winreg.HKEY_LOCAL_MACHINE
            with winreg.CreateKey(root, self.path_input.text()) as key_handle:
                val = int(self.value_input.text()) if self.type_combo.currentText() == "REG_DWORD" else self.value_input.text()
                reg_type = winreg.REG_DWORD if self.type_combo.currentText() == "REG_DWORD" else winreg.REG_SZ
                winreg.SetValueEx(key_handle, self.key_input.text(), 0, reg_type, val)
                QMessageBox.information(self, "성공", "레지스트리 저장 완료")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"레지스트리 저장 실패: {e}")

# --- 2. RegistryTab 클래스 ---
# 기능: 10개의 RegistryEntry를 모아 하나의 'LIST' 탭을 구성합니다. (변경 없음)
class RegistryTab(QWidget):
    def __init__(self, tab_index):
        super().__init__()
        self.entries = []
        layout = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content_widget = QWidget(); content_layout = QVBoxLayout(content_widget)
        for i in range(10):
            entry = RegistryEntry(i + tab_index * 10)
            self.entries.append(entry)
            content_layout.addWidget(entry)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

##############리팩토링################
# --- 3. RegistryStatusButton 클래스 (새로 분리된 클래스) ---
# 기능: 상태 버튼 '하나'의 모든 로직(UI, 레지스트리 접근, 상태 결정, 스타일 변경)을 책임집니다.
# 이유: CompareTab의 복잡성을 크게 낮추고, 각 버튼이 자신의 상태를 스스로 관리하게 하여 코드의 응집도를 높입니다.
class RegistryStatusButton(QPushButton):
    def __init__(self, entry_widget, index):
        super().__init__(f"item {index+1}")
        self.entry = entry_widget # 이 버튼이 참조할 RegistryEntry 위젯
        
        # UI 스타일 초기화
        self.setFixedSize(200, 80)
        shadow = QGraphicsDropShadowEffect(blurRadius=15, xOffset=5, yOffset=5)
        self.setGraphicsEffect(shadow)
        font = QFont(); font.setBold(True)
        self.setFont(font)
        
    def update_status(self):
        """이 버튼과 연결된 레지스트리 항목의 상태를 확인하고 스스로 UI를 업데이트합니다."""
        title = self.entry.title_input.text() or f"item {self.entry.save_button.text().split()[-1]}"
        
        display_lines = [title]
        status = ""
        style_sheet = ""

        # 경로/키 유효성 검사
        if not self.entry.path_input.text() or not self.entry.key_input.text():
            status = "EMPTY"
            style_sheet = "QPushButton { color: black; }"
        else:
            # 레지스트리 접근 및 비교
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

# --- 4. CompareTab 클래스 (리팩토링 후 매우 단순해짐) ---
# 기능: 30개의 RegistryStatusButton을 격자 형태로 배치하고, Refresh 시 각 버튼의 업데이트를 지시합니다.
# 이유: 복잡한 로직을 모두 RegistryStatusButton으로 옮겼기 때문에, 이 클래스는 이제 '배치'와 '명령'이라는 단순한 역할만 수행합니다.
class CompareTab(QWidget):
    def __init__(self, tabs):
        super().__init__()
        layout = QVBoxLayout(self)

        # Refresh 버튼 스타일 및 레이아웃
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        refresh.setFixedSize(200, 40)
        font = QFont(); font.setPointSize(12); font.setBold(True)
        refresh.setFont(font)
        button_layout = QHBoxLayout(); button_layout.addStretch(); button_layout.addWidget(refresh); button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 그리드 레이아웃 생성
        grid = QGridLayout()
        self.buttons = []
        for i in range(30):
            # i번째 버튼에 해당하는 RegistryEntry 위젯을 찾아 연결
            entry_widget = tabs[i // 10].entries[i % 10]
            # RegistryStatusButton 인스턴스 생성
            btn = RegistryStatusButton(entry_widget, i)
            self.buttons.append(btn)
            grid.addWidget(btn, i // 5, i % 5)
        
        layout.addLayout(grid)
        self.refresh() # 초기 상태 업데이트

    def refresh(self):
        """모든 상태 버튼에게 각자 자신의 상태를 업데이트하라고 명령합니다."""
        for button in self.buttons:
            button.update_status()

# --- 5. RegistryTabGroup 클래스 (리팩토링 후 거의 변경 없음) ---
# 기능: 모든 탭들을 모아 최종 UI를 조립하고, 설정을 저장/로드하는 최상위 클래스입니다.
class RegistryTabGroup(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        self.data_tabs = [RegistryTab(i) for i in range(3)]
        for i, tab in enumerate(self.data_tabs):
            self.tabs.addTab(tab, f"LIST {i+1}")
        
        self.compare_tab = CompareTab(self.data_tabs)
        self.tabs.insertTab(0, self.compare_tab, "REGISTRY STATUS")
        self.tabs.setCurrentIndex(0)

        layout.addWidget(self.tabs)
        self.load_settings()

    def save_settings(self):
        all_data = [entry.get_data() for tab in self.data_tabs for entry in tab.entries]
        os.makedirs("settings", exist_ok=True)
        with open("settings/settings.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

    def load_settings(self):
        settings_file = "settings/settings.json"
        if not os.path.exists(settings_file): return
        with open(settings_file, "r", encoding="utf-8") as f:
            all_data = json.load(f)
        idx = 0
        for tab in self.data_tabs:
            for entry in tab.entries:
                if idx < len(all_data):
                    entry.set_data(all_data[idx]); idx += 1
############리팩토링 끝#################