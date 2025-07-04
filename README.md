# ddino

pyinstaller --noconfirm --onefile --windowed quick_log_viewer.py


Traceback (most recent call last):
  File "quickviewer.py", line 111, in <module>
    create_gui()
  File "quickviewer.py", line 91, in create_gui
    summary_lines = extract_summary_lines(filepath)
  File "quickviewer.py", line 51, in extract_summary_lines
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
PermissionError: [Errno 13] Permission denied: 'C:\\errorlogtool\\project6'
무슨 에러지 해결방법은?
import sys
import xml.etree.ElementTree as ET
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QFileDialog
)

class ParameterFinder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fixed ParameterID Finder")
        self.setGeometry(300, 300, 600, 400)

        layout = QVBoxLayout()

        # [1] 파일 선택
        file_layout = QHBoxLayout()
        self.file_button = QPushButton("XML 파일 선택")
        self.file_button.clicked.connect(self.select_file)
        self.file_label = QLabel("선택된 파일 없음")
        file_layout.addWidget(self.file_button)
        file_layout.addWidget(self.file_label)
        layout.addLayout(file_layout)

        # [2] 고정된 Parameter 이름 출력
        fixed_names = [
            "e-Column.IGP1", "e-Column.IGP2", "e-Column.IGP3",
            "e-Column.IGP4", "e-Column.IGP5", "e-Column.IGP6",
            "e-Column.IGP7", "e-Column.IGP8", "e-Column.IGP9",
            "e-Column.IGP10", "e-Column.IGP11"
        ]
        self.fixed_names = fixed_names  # 고정 이름 저장

        # [3] 결과 출력
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        # [4] 검색 버튼
        self.search_button = QPushButton("ParameterID 검색")
        self.search_button.clicked.connect(self.search_parameter_ids)
        layout.addWidget(self.search_button)

        self.setLayout(layout)
        self.xml_file = None

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "XML 파일 선택", "", "XML Files (*.xml)")
        if file_path:
            self.xml_file = file_path
            self.file_label.setText(file_path)

    def search_parameter_ids(self):
        if not self.xml_file:
            self.result_area.setText("⚠ XML 파일을 먼저 선택하세요.")
            return

        try:
            tree = ET.parse(self.xml_file)
            root = tree.getroot()

            found_map = {name: None for name in self.fixed_names}

            for value_data in root.iter("ValueData"):
                pname = value_data.get("Parameter")
                pid = value_data.get("ParameterID")
                if pname in found_map and found_map[pname] is None:
                    found_map[pname] = pid

            result_lines = []
            for name in self.fixed_names:
                if found_map[name]:
                    result_lines.append(f"[{name}] → ParameterID: {found_map[name]}")
                else:
                    result_lines.append(f"[{name}] → ❌ 찾을 수 없음")

            self.result_area.setText("\n".join(result_lines))

        except Exception as e:
            self.result_area.setText(f"❌ XML 파싱 실패: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParameterFinder()
    window.show()
    sys.exit(app.exec_())
