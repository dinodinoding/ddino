# text_view_tab.py

# --- 1. 모듈 임포트 ---
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtGui import QFont
import os
from utils.config_loader import load_config
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# --- 2. StigGraphBox 클래스 ---
# 기능: Stig 좌표 '하나'를 그리는 '부품' 클래스. (변경 없음)
class StigGraphBox(QWidget):
    def __init__(self, title, x_val, y_val):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        fig = Figure(figsize=(1.2, 1.2), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot([x_val], [y_val], 'ro', markersize=5)
        ax.set_xlim(-0.75, 0.75)
        ax.set_ylim(-0.75, 0.75)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.axhline(0, color='grey', linewidth=0.8)
        ax.axvline(0, color='grey', linewidth=0.8)
        ax.set_title(title, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout(pad=0.5)
        canvas = FigureCanvas(fig)
        main_layout.addWidget(canvas)

# --- 3. BoxWithTitle 클래스 ---
# 기능: 일반 텍스트를 표시하는 범용 '부품' 클래스. (변경 없음)
class BoxWithTitle(QWidget):
    def __init__(self, title, file_path, keywords, templates=None):
        super().__init__()
        # ... (이전 코드와 완전히 동일) ...
        if templates is None: templates = {}
        content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if isinstance(keywords, str): keywords = [keywords]
            filtered_content = []
            for line in lines:
                matched_keyword = next((k for k in keywords if line.startswith(k)), None)
                if matched_keyword:
                    stripped_line = line.strip()
                    if matched_keyword == 'aperture':
                        value = stripped_line.split('aperture', 1)[-1].strip()
                        filtered_content.append(value.replace('/', '\n'))
                    elif matched_keyword in templates and ' data ' in stripped_line:
                        template = templates[matched_keyword]
                        value = stripped_line.split(' data ', 1)[-1].strip()
                        filtered_content.append(f"{template} {value}")
                    else:
                        filtered_content.append(stripped_line)
            if filtered_content: content = "\n".join(filtered_content)
            else: content = f"[{', '.join(keywords)}로 시작하는 줄 없음]"
        else: content = f"[{file_path}] 파일이 존재하지 않습니다"
        layout = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setFont(QFont("Courier", 10))
        content_label.setStyleSheet("background-color: transparent; padding: 4px;")
        layout.addWidget(title_label)
        layout.addWidget(content_label)
        self.setLayout(layout)

# --- 4. SemAlignStigSection 클래스 ---
# 기능: 'SEM Align&stig' 섹션을 만드는 '부품' 클래스. (생성자만 약간 수정)
class SemAlignStigSection(QWidget):
    # 'title', 'keywords'를 받도록 하여 다른 위젯과 형식을 통일합니다. (keywords는 사용하지 않음)
    def __init__(self, title, file_path, keywords, templates):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(title, font=QFont("Arial", 12, QFont.Bold)))

        semalign_text = ""
        stig_coords = {}
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("semalign"):
                        template = templates.get("semalign")
                        value = line.strip().split(' data ', 1)[-1].strip()
                        semalign_text = f"{template} {value}"
                    elif line.startswith("stig"):
                        parts = line.strip().split()
                        if len(parts) == 3:
                            key, axis, val_str = parts
                            try:
                                if key not in stig_coords: stig_coords[key] = {}
                                stig_coords[key][axis] = float(val_str)
                            except ValueError: continue
        
        if semalign_text:
            main_layout.addWidget(QLabel(semalign_text, font=QFont("Courier", 10)))

        stig_graphs_layout = QHBoxLayout()
        stig_keys_to_display = ['stig20K', 'stig10k', 'stig5k', 'stig2k', 'stig1k']
        for key in stig_keys_to_display:
            coords = stig_coords.get(key, {'x': 0, 'y': 0}) 
            graph_box = StigGraphBox(key.upper(), coords.get('x', 0), coords.get('y', 0))
            stig_graphs_layout.addWidget(graph_box)
        
        main_layout.addLayout(stig_graphs_layout)

##############리팩토링################
# --- 5. TextViewTab 클래스 ---
# 기능: 모든 UI '부품'들을 조립하는 '조립 공장' 역할을 합니다.
# 이유: 기존의 복잡한 로직 대신, '설계도(LAYOUT_DEFINITIONS)'를 읽어 UI를 동적으로 생성하는
#      훨씬 더 단순하고 유지보수하기 쉬운 구조로 변경했습니다.
class TextViewTab(QWidget):
    # UI 레이아웃을 정의하는 '설계도'.
    # 각 항목은 어떤 클래스를 사용할지, 제목은 무엇인지, 어떤 키워드를 찾을지 정의합니다.
    LAYOUT_DEFINITIONS = {
        'left': [
            {'widget_class': BoxWithTitle, 'title': "FEG", 'keywords': "feg"},
            {'widget_class': SemAlignStigSection, 'title': "SEM Align&stig", 'keywords': None},
            {'widget_class': BoxWithTitle, 'title': "SGIS", 'keywords': "sgis"},
            {'widget_class': BoxWithTitle, 'title': "MIS", 'keywords': ["mis1", "mis2", "mis3"]},
        ],
        'right': [
            {'widget_class': BoxWithTitle, 'title': "IPG", 'keywords': ["ipg1", "ipg2", "ipg3", "ipg4"]},
            {'widget_class': BoxWithTitle, 'title': "LMIS", 'keywords': ["lmis1", "lmis2", "lmis3"]},
            {'widget_class': BoxWithTitle, 'title': "Aperture", 'keywords': "aperture"},
        ]
    }

    def __init__(self):
        super().__init__()
        # 메인 레이아웃 및 좌/우 레이아웃 생성
        layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # 설정 및 데이터 파일 경로 로드
        config = load_config()
        data_file = config.get("data_file")

        # 텍스트 변환 규칙 정의
        self.TEMPLATES = {
            "feg": "feg setup data", "sgis": "sgis setup data", "semalign": "semalign setup data",
            "mis1": "mis1 setup data", "mis2": "mis2 setup data", "mis3": "mis3 setup data",
            "ipg1": "ipg1 setup data", "ipg2": "ipg2 setup data", "ipg3": "ipg3 setup data", "ipg4": "ipg4 setup data",
            "lmis1": "lmis1 setup data", "lmis2": "lmis2 setup data", "lmis3": "lmis3 setup data",
        }

        # '설계도'를 바탕으로 왼쪽 열의 위젯들을 동적으로 생성하고 배치
        for definition in self.LAYOUT_DEFINITIONS['left']:
            widget_class = definition['widget_class']
            widget = widget_class(
                title=definition['title'],
                file_path=data_file,
                keywords=definition['keywords'],
                templates=self.TEMPLATES
            )
            left_layout.addWidget(widget)

        # '설계도'를 바탕으로 오른쪽 열의 위젯들을 동적으로 생성하고 배치
        for definition in self.LAYOUT_DEFINITIONS['right']:
            widget_class = definition['widget_class']
            widget = widget_class(
                title=definition['title'],
                file_path=data_file,
                keywords=definition['keywords'],
                templates=self.TEMPLATES
            )
            right_layout.addWidget(widget)

        # 최종 조립
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        layout.addStretch(1)
############리팩토링 끝#################