# registry_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox, QFrame,
    QScrollArea, QTabWidget, QGridLayout, QGraphicsDropShadowEffect
)
from PySide6.QtGui import QFont
import winreg
import json
import os

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
                if self.parent_group:
                    self.parent_group.save_settings()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"레지스트리 저장 실패: {e}")

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
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
        for entry, data in zip(self.get_all_entries(), all_data):
            entry.set_data(data)

