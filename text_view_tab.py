# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

# PySide6 라이브러리에서 GUI를 구성하는 데 필요한 기본 부품들을 가져옵니다.
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit
)
# PySide6 라이브Triton에서 글꼴(Font)을 다루기 위한 클래스를 가져옵니다.
from PySide6.QtGui import QFont
# os 모듈은 파일 경로를 다루거나 파일 존재 여부를 확인하는 등 운영체제 관련 기능을 제공합니다.
import os
# re 모듈은 정규 표현식을 사용하여 복잡한 텍스트 패턴을 검색하고 분석하는 데 사용됩니다.
import re
# 다른 파일에 정의된 설정 로딩 함수들을 가져옵니다. (코드는 없지만 역할을 추측할 수 있습니다.)
from utils.config_loader import load_config
from utils.summary_loader import load_summary_config
# Matplotlib 라이브러리는 파이썬에서 그래프를 그리는 데 사용됩니다.
from matplotlib.figure import Figure
# FigureCanvasQTAgg는 Matplotlib으로 그린 그래프를 PySide(Qt) 창 안에 표시할 수 있도록 연결해주는 다리 역할을 합니다.
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# ─────────────────────────────────────────────────────────────
# 🔹 [부품 1] STIG 그래프를 표시하는 위젯 (StigGraphBox)
# -------------------------------------------------------------
# 작은 좌표평면에 점 하나를 찍어 STIG 값을 시각적으로 보여주는 네모난 박스입니다.
class StigGraphBox(QWidget):
    # __init__ 메서드는 이 StigGraphBox 객체를 생성할 때 호출되는 초기 설정 함수입니다.
    # title: 그래프 위에 표시될 제목 (예: "STIG20K")
    # x_val, y_val: 그래프에 표시할 점의 x, y 좌표
    def __init__(self, title, x_val, y_val):
        super().__init__() # 부모 클래스(QWidget)의 초기화 코드를 먼저 실행합니다.
        
        # QVBoxLayout: 위젯들을 수직(위에서 아래로)으로 쌓는 레이아웃입니다.
        layout = QVBoxLayout(self)
        
        # --- Matplotlib를 사용하여 그래프 생성 ---
        # Figure: 그래프를 그릴 도화지(Figure)를 생성합니다. 크기와 해상도(dpi)를 지정합니다.
        fig = Figure(figsize=(1.2, 1.2), dpi=100)
        # add_subplot(111): 도화지에 그래프를 그릴 실제 영역(axes)을 추가합니다.
        ax = fig.add_subplot(111)
        
        # --- 그래프 내용 그리기 ---
        # ax.plot: 주어진 x, y 좌표에 점을 찍습니다. 'ro'는 'red'(빨간색) 'o'(원) 모양을 의미합니다.
        ax.plot([x_val], [y_val], 'ro', markersize=5)
        # set_xlim, set_ylim: x축과 y축의 표시 범위를 -0.75에서 0.75로 고정합니다.
        ax.set_xlim(-0.75, 0.75)
        ax.set_ylim(-0.75, 0.75)
        # set_aspect: 그래프의 가로세로 비율을 동일하게 만들어 정사각형으로 보이게 합니다.
        ax.set_aspect('equal', adjustable='box')
        # grid: 배경에 격자 무늬(그리드)를 추가합니다. 점선 스타일과 약간의 투명도를 적용합니다.
        ax.grid(True, linestyle='--', alpha=0.6)
        # axhline, axvline: y=0 위치에 수평선, x=0 위치에 수직선을 회색으로 얇게 그립니다.
        ax.axhline(0, color='grey', linewidth=0.8)
        ax.axvline(0, color='grey', linewidth=0.8)
        # set_title: 그래프 상단에 제목을 설정하고 글자 크기를 지정합니다.
        ax.set_title(title, fontsize=9)
        # set_xticks, set_yticks: x축과 y축의 숫자 눈금을 숨겨서 깔끔하게 만듭니다.
        ax.set_xticks([])
        ax.set_yticks([])
        # tight_layout: 그래프의 구성요소(제목 등)들이 서로 겹치지 않도록 여백을 자동으로 조절합니다.
        fig.tight_layout(pad=0.5)
        
        # --- 그래프를 GUI에 연결 ---
        # FigureCanvas: Matplotlib으로 그린 그래프(fig)를 Qt 위젯으로 변환합니다.
        canvas = FigureCanvas(fig)
        # layout.addWidget: 변환된 그래프 위젯(canvas)을 레이아웃에 추가하여 화면에 보이도록 합니다.
        layout.addWidget(canvas)

# ─────────────────────────────────────────────────────────────
# 🔹 [부품 2] 텍스트 파일 내용을 요약해서 보여주는 박스 (MultiLineSummaryBox)
# -------------------------------------------------------------
# 지정된 파일에서 특정 키워드로 시작하는 줄을 찾아 그 값을 예쁘게 정리하여 보여줍니다.
class MultiLineSummaryBox(QWidget):
    # file_path: 분석할 텍스트 파일의 경로
    # label_mapping: {'찾을 키워드': '화면에 표시할 라벨'} 형태의 규칙 딕셔너리
    # title: 이 요약 박스 전체의 제목
    def __init__(self, file_path, label_mapping, title=None):
        super().__init__()
        layout = QVBoxLayout(self)
        font = QFont("Arial", 10) # 사용할 기본 글꼴 설정
        layout.setSpacing(0) # 줄 사이의 간격을 없애 촘촘하게 보이도록 함

        if title: # 만약 제목이 주어졌다면
            title_label = QLabel(title) # 제목 라벨을 생성
            title_label.setFont(QFont("Arial", 12, QFont.Bold)) # 제목 폰트를 굵게 설정
            layout.addWidget(title_label) # 레이아웃에 추가

        results = [] # 찾은 결과들을 저장할 리스트

        if os.path.exists(file_path): # 파일이 실제로 존재하는지 확인
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines() # 파일의 모든 줄을 읽어옴

            # label_mapping에 정의된 규칙(키워드, 라벨) 만큼 반복
            for keyword, label_prefix in label_mapping:
                matched = False # 현재 키워드를 파일에서 찾았는지 여부를 기록하는 변수
                for line in lines: # 파일의 각 줄을 확인
                    line = line.strip() # 줄 앞뒤의 공백 제거
                    # 현재 줄이 키워드로 시작하고 'data'라는 단어를 포함하는지 확인
                    if line.startswith(keyword) and 'data' in line:
                        # ' data '를 기준으로 줄을 나누어 [키워드 부분, 값 부분]으로 분리
                        parts = re.split(r'\s+data\s+', line.strip())
                        if len(parts) == 2: # 정확히 두 부분으로 나뉘었다면
                            value = parts[1].strip() # 값 부분을 추출

                            # 'apercurr' 키워드는 특별 처리
                            if keyword == "apercurr":
                                # 값에 포함된 '/' 문자를 줄바꿈(\n)으로 변경
                                value = value.replace("/", "\n")
                                results.append(f"{label_prefix}\n{value}")
                            else:
                                results.append(f"{label_prefix} {value}")
                            
                            matched = True # 찾았다고 표시
                            break # 해당 키워드를 찾았으므로 더 이상 파일의 다른 줄을 볼 필요 없음
                
                if not matched: # 파일 전체를 다 봤는데도 키워드를 못 찾았다면
                    results.append(f"{label_prefix} [값 없음]")
        else:
            results = ["[파일 없음]"] # 파일이 존재하지 않는 경우

        # results 리스트에 저장된 결과들을 화면에 라벨로 만들어 추가
        for line in results:
            if '\n' in line: # 결과에 줄바꿈이 포함된 경우 (apercurr 같은)
                # 줄바꿈을 기준으로 나누어 여러 개의 라벨로 만듦
                for i, subline in enumerate(line.split('\n')):
                    subline = subline.strip()
                    if not subline: continue # 빈 줄은 무시
                    if i == 0: # 첫 번째 줄은 그대로
                        lbl = QLabel(subline)
                    else: # 두 번째 줄부터는 들여쓰기 효과를 줌
                        lbl = QLabel(f"    {subline}")
                    lbl.setFont(font)
                    lbl.setStyleSheet("margin:0px; padding:0px; line-height:90%;") # 여백과 줄간격을 미세 조정
                    layout.addWidget(lbl)
            else: # 일반적인 한 줄짜리 결과
                lbl = QLabel(line)
                lbl.setFont(font)
                lbl.setStyleSheet("margin:0px; padding:0px; line-height:90%;")
                layout.addWidget(lbl)

        self.setLayout(layout)

# ─────────────────────────────────────────────────────────────
# 🔹 [부품 3] SEM Align 텍스트와 STIG 그래프들을 묶어서 보여주는 섹션 (SemAlignStigSection)
# -------------------------------------------------------------
class SemAlignStigSection(QWidget):
    def __init__(self, data_file):
        super().__init__()
        layout = QVBoxLayout(self)
        # 섹션 제목 라벨 추가
        layout.addWidget(QLabel("SEM Align&stig", font=QFont("Arial", 12, QFont.Bold)))

        semalign_text = "" # sem_align 값을 저장할 변수
        stig_coords = {} # stig 값들을 {'stig20k': {'x': 0.1, 'y': -0.2}, ...} 형태로 저장할 딕셔너리

        if os.path.exists(data_file): # 데이터 파일이 존재하는지 확인
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f: # 파일을 한 줄씩 읽음
                    line = line.strip()
                    # "sem_align"으로 시작하고 "data"를 포함하는 줄을 찾음
                    if line.startswith("sem_align") and 'data' in line:
                        value = re.split(r'\s+data\s+', line)[-1].strip()
                        semalign_text = f"Last SEM_Align Data {value}"
                    # "stig_"로 시작하는 줄을 찾음
                    elif line.startswith("stig_"):
                        # 정규 표현식을 사용하여 "stig_레벨_축 data 값" 형식의 줄을 분석
                        match = re.match(r"stig_(\w+?)_(x|y)\s+data\s+([-\d\.eE]+)", line)
                        if match: # 패턴과 일치하는 줄을 찾았다면
                            level, axis, val_str = match.groups() # 그룹으로 묶은 부분들을 추출 (예: '20k', 'x', '0.123')
                            key = f"stig{level.lower()}" # 딕셔너리 키 생성 (예: 'stig20k')
                            try:
                                value = float(val_str) # 값 문자열을 실수(float)로 변환
                                if key not in stig_coords:
                                    stig_coords[key] = {} # 해당 키가 처음이면 빈 딕셔너리 생성
                                stig_coords[key][axis] = value # {'stig20k': {'x': 0.123}} 와 같이 저장
                            except ValueError:
                                continue # 숫자로 변환 실패 시 무시

        if semalign_text: # sem_align 값을 찾았다면
            layout.addWidget(QLabel(semalign_text, font=QFont("Courier", 10))) # 고정폭 글꼴로 라벨 추가

        # STIG 그래프들을 수평으로 배치할 레이아웃 생성
        graph_layout = QHBoxLayout()
        # 정해진 순서대로 STIG 그래프를 생성하여 추가
        for key in ['stig20k', 'stig10k', 'stig5k', 'stig2k', 'stig1k']:
            # get 메서드를 사용하여 해당 키의 좌표를 가져오되, 없으면 기본값 (0,0)을 사용
            coords = stig_coords.get(key, {'x': 0, 'y': 0})
            # StigGraphBox 부품을 생성하여 수평 레이아웃에 추가
            graph_layout.addWidget(StigGraphBox(key.upper(), coords['x'], coords['y']))
        layout.addLayout(graph_layout) # 완성된 그래프 레이아웃을 메인 수직 레이아웃에 추가

# ─────────────────────────────────────────────────────────────
# 🔹 [부품 4] 메모를 입력하고 저장하는 박스 (MemoBoardBox)
# -------------------------------------------------------------
class MemoBoardBox(QWidget):
    def __init__(self, note_path=None):
        super().__init__()
        
        # 메모를 저장할 파일 경로를 결정
        if note_path is None: # 만약 경로가 주어지지 않았다면
            # 현재 파일이 있는 폴더를 기준으로 기본 경로를 설정
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.note_path = os.path.join(base_dir, "settings", "user_notes.txt")
        else: # 경로가 주어졌다면
            self.note_path = note_path

        layout = QVBoxLayout(self)

        label = QLabel("NOTEPAD")
        label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(label)

        self.text_edit = QTextEdit() # 여러 줄 텍스트 편집이 가능한 위젯 생성
        self.text_edit.setPlaceholderText("메모를 입력하세요...") # 아무것도 입력되지 않았을 때 안내 문구
        self.text_edit.setMinimumWidth(450) # 최소 너비 지정
        self.text_edit.setFixedHeight(350) # 높이 고정
        
        # textChanged 시그널: 텍스트 상자의 내용이 변경될 때마다 발생
        # connect(self.save_notes): 내용이 변경되면 self.save_notes 함수를 자동으로 호출하도록 연결 (자동 저장 기능)
        self.text_edit.textChanged.connect(self.save_notes)
        layout.addWidget(self.text_edit)

        self.load_notes() # 프로그램 시작 시 저장된 메모를 불러옴

    def load_notes(self):
        """파일에 저장된 메모를 불러와 텍스트 상자에 표시하는 함수"""
        if os.path.exists(self.note_path):
            with open(self.note_path, "r", encoding="utf-8") as f:
                self.text_edit.setPlainText(f.read())

    def save_notes(self):
        """현재 텍스트 상자의 내용을 파일에 저장하는 함수"""
        # os.makedirs: 파일이 저장될 폴더가 없으면 자동으로 생성 (exist_ok=True는 폴더가 이미 있어도 오류를 내지 않음)
        os.makedirs(os.path.dirname(self.note_path), exist_ok=True)
        with open(self.note_path, "w", encoding="utf-8") as f:
            f.write(self.text_edit.toPlainText())

# ─────────────────────────────────────────────────────────────
# 🔹 [최종 조립] 위에서 만든 모든 부품들을 조립하여 탭 화면을 구성 (TextViewTab)
# -------------------------------------------------------------
class TextViewTab(QWidget):
    def __init__(self):
        super().__init__()
        # 전체 화면을 가로로 크게 나누는 수평 레이아웃
        layout = QHBoxLayout(self)
        # 왼쪽 열을 담당할 수직 레이아웃
        left_layout = QVBoxLayout()
        # 오른쪽 열을 담당할 수직 레이아웃
        right_layout = QVBoxLayout()

        # 설정 파일에서 데이터 파일 경로와 요약 규칙 등을 불러옴
        config = load_config()
        data_file = config.get("data_file")
        summary_config = load_summary_config()

        # --- 왼쪽 열 구성 ---
        # FEG -> SemAlign -> SGIS -> MGIS -> IGP 순서로 위젯을 추가
        for title in ["FEG"]:
            if title in summary_config: # 설정에 해당 섹션이 정의되어 있으면
                # MultiLineSummaryBox 부품을 만들어 왼쪽 레이아웃에 추가
                left_layout.addWidget(MultiLineSummaryBox(data_file, summary_config[title].items(), title))

        # SemAlignStigSection 부품을 만들어 왼쪽 레이아웃에 추가
        left_layout.addWidget(SemAlignStigSection(data_file))

        for title in ["SGIS", "MGIS", "IGP"]:
            if title in summary_config:
                left_layout.addWidget(MultiLineSummaryBox(data_file, summary_config[title].items(), title))

        # --- 오른쪽 열 구성 ---
        # LMIS -> FIB_Aperture -> 메모 순서로 위젯을 추가
        for title in ["LMIS", "FIB_Aperture"]:
            if title in summary_config:
                right_layout.addWidget(MultiLineSummaryBox(data_file, summary_config[title].items(), title))

        # MemoBoardBox 부품을 만들어 오른쪽 레이아웃에 추가
        right_layout.addWidget(MemoBoardBox())

        # --- 최종 조립 ---
        # 전체 수평 레이아웃에 왼쪽과 오른쪽 레이아웃을 추가
        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        # addStretch(1): 남는 공간을 모두 차지하는 '신축성 있는 빈 공간'을 추가합니다.
        # 이로 인해 왼쪽과 오른쪽 내용이 창 크기를 늘려도 왼쪽으로 붙어있게 됩니다.
        layout.addStretch(1)
