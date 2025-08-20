# ## 필요한 도구들 가져오기 (라이브러리 임포트) ##

import os  # 운영체제 관련 기능 (파일 경로, 파일 존재 여부 확인 등)
import subprocess  # 다른 외부 프로그램 (예: .bat 파일)을 실행하기 위한 도구
import sys  # 파이썬 인터프리터 관련 기능
from datetime import datetime, timedelta  # 날짜와 시간을 다루기 위한 도구

# PySide6 라이브러리에서 GUI를 구성하는 데 필요한 부품들을 가져옵니다.
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QComboBox,
    QApplication
)
# PySide6의 타이머 기능과 정렬 옵션 등을 가져옵니다.
from PySide6.QtCore import QTimer, Qt
# 파이썬 표준 라이브러리에서 XML 파일을 분석(파싱)하기 위한 도구를 가져옵니다.
import xml.etree.ElementTree as ET

# Matplotlib 라이브러리에서 그래프를 그리기 위한 핵심 도구들을 가져옵니다.
from matplotlib.figure import Figure  # 그래프를 그릴 도화지(Figure)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # Matplotlib 그래프를 PySide 창에 표시하기 위한 연결 다리
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar  # 그래프 확대/축소/이동을 위한 툴바
from matplotlib.ticker import LogLocator, FormatStrFormatter  # 로그 스케일 눈금 및 형식 지정을 위한 도구

# 다른 파일에 정의된 설정 로딩 함수를 가져옵니다.
from utils.config_loader import load_config


# ## XML 데이터 처리 관련 헬퍼 함수 ##

def strip_namespace(tree):
    """XML 태그에서 {..} 와 같은 네임스페이스(namespace)를 제거하는 함수"""
    # XML 파일은 종종 태그 이름 앞에 중괄호로 묶인 주소같은 것을 붙이는데,
    # 이 때문에 태그를 찾기 어려워져서 미리 제거해주는 것이 편리합니다.
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]


def parse_xml_data(xml_path, param_map):
    """XML 파일을 열어 필요한 데이터를 추출하고 파싱하는 함수"""
    print(f">> [parse_xml_data] XML 데이터 파싱 시작: {xml_path}")
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f"XML 로그 파일을 찾을 수 없습니다: {xml_path}")

    temp_points = [] # 추출한 데이터 포인트들을 임시로 저장할 리스트
    try:
        tree = ET.parse(xml_path) # XML 파일을 파싱하여 트리 구조로 읽어들임
        strip_namespace(tree) # 태그 이름 정리
        root = tree.getroot() # XML의 최상위 노드를 가져옴
        
        # 'ValueData' 라는 모든 태그를 찾아서 반복
        for vd in root.findall('.//ValueData'):
            param_id = vd.attrib.get("ParameterID", "") # 태그의 속성에서 ParameterID를 가져옴
            if param_id not in param_map: continue # 우리가 찾는 ID가 아니면 건너뜀
            
            param_name = param_map[param_id] # ID에 해당하는 파라미터 이름 (예: 'IGP1')을 찾음
            param_values = []
            # ValueData 태그의 자식들을 확인하여 실제 값들을 찾음
            for child in vd:
                tag = child.tag.lower()
                if tag == "parametervalues":
                    param_values.extend(child.findall("ParameterValue"))
                elif tag == "parametervalue":
                    param_values.append(child)

            # 찾은 값들을 하나씩 처리
            for pv in param_values:
                try:
                    ts = pv.get("Timestamp") # 시간 정보
                    val_node = pv.find("Value") # 값 정보
                    if ts is None or val_node is None or val_node.text is None: continue # 정보가 없으면 건너뜀
                    
                    # 시간 문자열을 datetime 객체로 변환하고, 값 문자열을 실수(float)로 변환
                    dt = datetime.fromisoformat(ts).replace(tzinfo=None)
                    val = float(val_node.text)
                    # 최종적으로 추출한 데이터를 딕셔너리 형태로 리스트에 추가
                    temp_points.append({'param': param_name, 'time': dt, 'value': val})
                except Exception as e:
                    print(f"   !! 파싱 예외: {e} (param={param_name})")
    except Exception as e:
        print(f">> [오류] XML 파싱 중 예외 발생: {e}")
        raise e

    if not temp_points:
        raise ValueError(f"XML 파일 '{xml_path}'에 유효한 데이터를 찾을 수 없습니다.")
    return temp_points


def find_latest_xml_file(directory_path):
    """주어진 디렉토리에서 가장 최근에 수정된 XML 파일을 찾는 함수"""
    print(f">> [find_latest_xml_file] 디렉토리에서 최신 XML 파일 검색: {directory_path}")
    if not os.path.isdir(directory_path):
        raise FileNotFoundError(f"지정된 디렉토리를 찾을 수 없습니다: {directory_path}")

    xml_files = []
    # 디렉토리 내의 모든 파일을 확인
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".xml"): # 파일 이름이 .xml로 끝나면
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                # (수정 시간, 파일 경로) 튜플을 리스트에 추가
                xml_files.append((os.path.getmtime(file_path), file_path))

    if not xml_files:
        raise FileNotFoundError(f"'{directory_path}' 디렉토리에서 XML 파일을 찾을 수 없습니다.")

    # 수정 시간을 기준으로 내림차순 정렬 (가장 최신 파일이 맨 앞으로 옴)
    xml_files.sort(key=lambda x: x[0], reverse=True)
    latest_file_path = xml_files[0][1] # 가장 첫 번째 파일의 경로를 반환
    print(f">> [find_latest_xml_file] 최신 XML 파일 발견: {latest_file_path}")
    return latest_file_path


# ## 메인 GUI 클래스 정의 ##
class GraphTab(QWidget):
    # 시간 선택 옵션을 텍스트와 실제 시간 간격(timedelta)으로 매핑
    TIME_OPTIONS = {
        "30분": timedelta(minutes=30), "1시간": timedelta(hours=1),
        "6시간": timedelta(hours=6), "12시간": timedelta(hours=12),
        "하루": timedelta(days=1),
    }

    # 3개의 그래프 각각에 대한 정의를 리스트로 관리 (재사용 및 유지보수 용이)
    GRAPH_DEFINITIONS = [
        {"y_label": "Pressure (Pa)", "y_scale": "log", "y_range": None, "series": ['IGP1', 'IGP2', 'IGP3', 'IGP4', 'HVG']},
        {"y_label": "Voltage (V)", "y_scale": "linear", "y_range": (0, 35000), "series": ['ACC_V', 'EXT_v', 'LENS1_V']},
        {"y_label": "Current (uA)", "y_scale": "linear", "y_range": (0, 50), "series": ['ACC_L', 'Emission', 'LENS1_L']}
    ]

    # --- 진행률 표시줄(Progress Bar)의 단계별 비율 정의 ---
    TOTAL_PROGRESS_STEPS = 100 # 전체 진행률은 100
    # 각 단계가 전체 진행률에서 차지하는 비율
    BAT_EXEC_PROGRESS_RATIO = 0.30     # 배치 파일 실행: 30%
    XML_FIND_PARSE_PROGRESS_RATIO = 0.50 # XML 검색 및 파싱: 50%
    GRAPH_PLOT_PROGRESS_RATIO = 0.20     # 그래프 그리기: 20%
    
    # 각 단계의 시작점과 끝점을 미리 계산
    BAT_EXEC_START = 0
    BAT_EXEC_END = int(TOTAL_PROGRESS_STEPS * BAT_EXEC_PROGRESS_RATIO)
    XML_FIND_PARSE_START = BAT_EXEC_END
    XML_FIND_PARSE_END = BAT_EXEC_END + int(TOTAL_PROGRESS_STEPS * XML_FIND_PARSE_PROGRESS_RATIO)
    GRAPH_PLOT_START = XML_FIND_PARSE_END
    GRAPH_PLOT_END = TOTAL_PROGRESS_STEPS

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self) # 메인 레이아웃은 수직(위->아래) 배치

        # UI를 기능별로 나누어 생성하는 헬퍼 함수 호출
        self._setup_description(layout) # 설명 라벨 생성
        self._setup_controls(layout)    # 컨트롤 패널(콤보박스, 버튼 등) 생성
        self._setup_graph_area(layout)  # 그래프가 그려질 영역 생성

        # 설정 파일 로드
        cfg = load_config()
        self.xml_output_directory = cfg.get("xml_output_directory", "C:/monitoring")
        self.bat_path = cfg.get("batch_file", "C:/monitoring/run_log_generation.bat")
        self.param_map = cfg.get("parameter_map", {})
        self.bat_check_interval = cfg.get("bat_check_interval_ms", 200) # 배치 파일 완료 체크 간격 (ms)

        # 모든 그래프에 사용될 파라미터 이름들을 모아서 중복 제거
        self.all_series_names = list(set(sum([d["series"] for d in self.GRAPH_DEFINITIONS], [])))
        self.all_points = [] # 파싱된 모든 데이터 포인트를 저장할 리스트
        self.bat_process = None # 배치 파일 실행 프로세스를 저장할 변수

        self._set_ui_enabled_state(True) # 처음에는 모든 UI 컨트롤을 활성화

    def _setup_description(self, main_layout):
        """탭 상단의 설명 라벨을 생성하고 추가하는 함수"""
        self.description_label = QLabel(
            "이 탭은 `.bat` 파일을 실행하여 로그 XML 파일을 생성하고, "
            "해당 XML 파일을 파싱하여 실시간 데이터를 그래프로 시각화합니다. "
            "배치 파일 실행, XML 파싱, 그리고 그래프 업데이트의 진행 상황을 추적합니다."
        )
        self.description_label.setWordWrap(True) # 텍스트가 길어지면 자동 줄바꿈
        main_layout.addWidget(self.description_label)
        main_layout.addSpacing(10) # 위젯 아래에 약간의 여백 추가

    def _setup_controls(self, main_layout):
        """컨트롤 패널(기간 선택, 진행률 표시줄, 새로고침 버튼)을 생성하고 추가하는 함수"""
        controls_layout = QHBoxLayout() # 컨트롤들은 수평(왼쪽->오른쪽)으로 배치
        controls_layout.addWidget(QLabel("기간 선택:"))
        
        self.time_combo = QComboBox() # 드롭다운 메뉴(콤보박스) 생성
        self.time_combo.addItems(list(self.TIME_OPTIONS.keys())) # 옵션 추가
        self.time_combo.setCurrentText("30분") # 기본 선택값 설정
        self.time_combo.currentTextChanged.connect(self.update_display) # 선택이 바뀌면 update_display 함수 호출
        controls_layout.addWidget(self.time_combo)

        # 진행률 텍스트와 바를 묶는 수직 레이아웃
        self.progress_container_layout = QVBoxLayout()
        self.progress_container_layout.setAlignment(Qt.AlignTop)

        self.progress_text_label = QLabel("준비 완료.") # 진행 상황 텍스트 라벨
        self.progress_text_label.setFixedHeight(15)
        self.progress_container_layout.addWidget(self.progress_text_label)

        self.progress_bar = QProgressBar() # 진행률 표시줄 생성
        self.progress_bar.setRange(0, self.TOTAL_PROGRESS_STEPS) # 범위는 0~100
        self.progress_bar.setTextVisible(True) # 진행률 숫자 표시
        self.progress_bar.setFixedHeight(10)
        self.progress_container_layout.addWidget(self.progress_bar)

        controls_layout.addLayout(self.progress_container_layout, 1) # 남는 공간을 모두 차지하도록 추가

        self.refresh_button = QPushButton("로그 생성 및 새로고침")
        self.refresh_button.clicked.connect(self.on_refresh_clicked) # 버튼 클릭 시 on_refresh_clicked 함수 호출
        controls_layout.addWidget(self.refresh_button)

        main_layout.addLayout(controls_layout)
        main_layout.addSpacing(10)

    def _setup_graph_area(self, main_layout):
        """그래프가 그려질 도화지와 툴바를 생성하고 추가하는 함수"""
        self.figure = Figure(figsize=(10, 9), constrained_layout=True) # Matplotlib 도화지 생성
        self.canvas = FigureCanvas(self.figure) # 도화지를 Qt 위젯으로 변환
        # 3행 1열의 서브플롯(그래프 영역)을 만들고 x축을 공유
        self.axes = self.figure.subplots(nrows=3, ncols=1, sharex=True)
        main_layout.addWidget(NavigationToolbar(self.canvas, self)) # 그래프 툴바 추가
        main_layout.addWidget(self.canvas) # 그래프 캔버스 추가
        self.status_label = QLabel("") # 하단 상태 표시 라벨
        main_layout.addWidget(self.status_label)

    def _set_ui_enabled_state(self, enabled):
        """UI 컨트롤들의 활성화/비활성화 상태를 한번에 제어하는 함수"""
        self.time_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def update_display(self):
        """현재 선택된 기간에 맞춰 그래프를 다시 그리는 함수"""
        if not self.all_points: # 표시할 데이터가 없으면
            self.status_label.setText("표시할 데이터가 없습니다.")
            for ax in self.axes: ax.clear() # 모든 그래프 영역을 지움
            self.canvas.draw() # 변경 사항을 캔버스에 반영
            return

        # 데이터 중 가장 최신 시간을 기준으로, 선택된 기간만큼 과거 시간(cutoff_time)을 계산
        dmax = max(p['time'] for p in self.all_points)
        selected_delta = self.TIME_OPTIONS[self.time_combo.currentText()]
        cutoff_time = dmax - selected_delta

        # 3개의 그래프 영역을 순회하며 각각 다시 그림
        for i, ax in enumerate(self.axes):
            definition = self.GRAPH_DEFINITIONS[i]
            # 해당 그래프에 필요한 데이터만 필터링
            data_for_this_graph = {name: [] for name in definition["series"]}
            for point in self.all_points:
                if point['time'] >= cutoff_time and point['param'] in definition["series"]:
                    data_for_this_graph[point['param']].append((point['time'], point['value']))
            # 필터링된 데이터로 그래프 하나를 그림
            self.plot_single_graph(ax, data_for_this_graph, definition)

        self.status_label.setText("그래프 업데이트 완료.")
        self.canvas.draw() # 최종적으로 변경된 내용을 캔버스에 반영

    def plot_single_graph(self, ax, series_data, definition):
        """하나의 그래프 영역(ax)에 데이터를 그리는 헬퍼 함수"""
        ax.clear() # 그리기 전에 이전 내용을 모두 지움
        
        # 그래프 정의에 포함된 모든 시리즈(데이터 계열)에 대해 반복
        for name in definition["series"]:
            points = series_data.get(name, [])
            if points:
                points.sort(key=lambda x: x[0]) # 시간 순으로 정렬
                times, values = zip(*points) # 시간과 값을 분리
                if name == "Emission": # Emission 데이터는 단위 변환
                    values = [v * 1e6 for v in values]
                ax.plot(times, values, label=name, marker='.', linestyle='-', markersize=3)
            else: # 데이터가 없어도 범례(legend)에 표시되도록 빈 플롯을 추가
                ax.plot([], [], label=name)

        # 그래프의 Y축 라벨, 스케일(선형/로그), 범위 등을 설정
        ax.set_ylabel(definition["y_label"])
        ax.set_yscale(definition["y_scale"])
        if definition["y_range"]: ax.set_ylim(definition["y_range"])
        if definition["y_scale"] == 'log':
            ax.yaxis.set_major_locator(LogLocator(base=10))
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.1e'))
        ax.grid(True, which="both", ls="--", alpha=0.6) # 배경 그리드 추가
        ax.legend(loc='upper left', fontsize='small') # 범례 표시

    def on_refresh_clicked(self):
        """'새로고침' 버튼 클릭 시 실행되는 메인 로직"""
        self._set_ui_enabled_state(False) # 작업 중에는 UI 컨트롤을 비활성화
        self.progress_bar.setValue(self.BAT_EXEC_START)

        if not os.path.exists(self.bat_path):
            self.status_label.setText(f"오류: 배치 파일이 존재하지 않습니다: {self.bat_path}")
            self._set_ui_enabled_state(True)
            return

        self.status_label.setText("배치 파일 실행 중...")
        self.progress_text_label.setText("단계 1/3: 배치 파일 실행 중...")
        self.progress_bar.setFormat("배치 파일 실행 중... %p%")
        QApplication.processEvents() # UI가 멈추지 않도록 이벤트 처리

        try:
            # Popen을 사용해 배치 파일을 '비동기적'으로 실행 (GUI가 멈추지 않음)
            # CREATE_NO_WINDOW: 실행 시 검은색 콘솔 창이 나타나지 않도록 함
            self.bat_process = subprocess.Popen(self.bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.status_label.setText(f"오류: 배치 파일 실행 중 문제 발생: {e}")
            self._set_ui_enabled_state(True)
            return

        # QTimer를 사용하여 배치 파일이 끝났는지 주기적으로 확인
        self.bat_check_timer = QTimer(self)
        self.bat_check_timer.timeout.connect(self._check_bat_completion)
        self.bat_check_timer.start(self.bat_check_interval)

    def _check_bat_completion(self):
        """타이머에 의해 주기적으로 호출되어 배치 파일의 종료 여부를 확인하는 함수"""
        # poll()은 프로세스가 종료되었으면 종료 코드를, 실행 중이면 None을 반환
        return_code = self.bat_process.poll()

        if return_code is not None: # 프로세스가 종료되었다면
            self.bat_check_timer.stop() # 타이머 중지
            if return_code != 0: # 종료 코드가 0이 아니면 오류
                self.status_label.setText(f"오류: 배치 파일이 오류 코드 {return_code}로 종료되었습니다.")
                self.progress_bar.setValue(0)
                self._set_ui_enabled_state(True)
                return

            # 성공적으로 종료되었으면 진행률을 업데이트하고 다음 단계로 진행
            self.progress_bar.setValue(self.BAT_EXEC_END)
            self._find_and_parse_xml_and_plot()
        else: # 아직 실행 중이라면
            # 진행률 바를 약간 움직여서 프로그램이 멈추지 않았음을 보여줌
            current_value = self.BAT_EXEC_START + int((self.BAT_EXEC_END - self.BAT_EXEC_START) * 0.5)
            self.progress_bar.setValue(current_value)
            QApplication.processEvents()

    def _find_and_parse_xml_and_plot(self):
        """배치 파일 실행 완료 후, XML 검색, 파싱, 그래프 그리기를 수행하는 함수"""
        self.progress_text_label.setText("단계 2/3: XML 파일 검색 및 파싱 중...")
        QApplication.processEvents()

        try:
            latest_xml_path = find_latest_xml_file(self.xml_output_directory)
            self.all_points = parse_xml_data(latest_xml_path, self.param_map)

            self.progress_bar.setValue(self.XML_FIND_PARSE_END)
            self.progress_bar.setFormat("XML 검색/파싱 완료! %p%")

            self.status_label.setText("그래프 업데이트 중...")
            self.progress_text_label.setText("단계 3/3: 그래프 업데이트 중...")
            QApplication.processEvents()

            self.update_display() # 파싱된 데이터로 그래프 업데이트

            self.progress_bar.setValue(self.TOTAL_PROGRESS_STEPS)
            self.progress_bar.setFormat("작업 완료!")
            self.status_label.setText("로그 생성 및 그래프 업데이트 완료.")
            self.progress_text_label.setText("작업 완료.")

        except Exception as e:
            self.status_label.setText(f"오류: {e}")
            self.progress_text_label.setText("오류 발생.")
            self.all_points = []
        finally:
            # 작업이 성공하든 실패하든 마지막에는 UI 컨트롤을 다시 활성화
            self._set_ui_enabled_state(True)


# ## 이 스크립트가 직접 실행될 때 실행되는 부분 ##
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 이 GraphTab 위젯을 담을 간단한 메인 윈도우를 정의
    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("로그 및 그래프 뷰어")
            self.setGeometry(100, 100, 1200, 900)

            main_layout = QVBoxLayout(self)
            self.graph_tab = GraphTab() # 우리가 만든 GraphTab을 생성
            main_layout.addWidget(self.graph_tab) # 메인 윈도우에 추가

    window = MainWindow()
    window.show() # 창을 화면에 표시
    sys.exit(app.exec()) # 애플리케이션 실행
