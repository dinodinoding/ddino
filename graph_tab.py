import os
import subprocess
import sys # QApplication import를 위해 추가
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QComboBox,
    QStackedLayout, QFrame, QApplication # QApplication 추가
)
from PySide6.QtCore import QTimer, Qt # Qt.AlignLeft 추가
import xml.etree.ElementTree as ET

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.ticker import LogLocator, FormatStrFormatter

# config_loader.py 파일이 같은 디렉터리 내 utils 폴더에 있다고 가정
# from utils.config_loader import load_config
# 임시 load_config 함수 (실제 환경에 맞게 교체 필요)
def load_config():
    return {
        "xml_log": "output.xml", # 예시 경로
        "batch_file": "run_log_generation.bat", # 예시 배치 파일
        "parameter_map": {
            "Param001": "IGP1", "Param002": "IGP2", "Param003": "IGP3",
            "Param004": "IGP4", "Param005": "HVG", "Param006": "ACC_V",
            "Param007": "EXT_v", "Param008": "LENS1_V", "Param009": "ACC_L",
            "Param010": "Emission", "Param011": "LENS1_L"
        }
    }


def strip_namespace(tree):
    # XML 네임스페이스 제거 (파싱 오류 방지)
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]


def parse_xml_data(xml_path, param_map):
    print(">> [parse_xml_data] XML 데이터 파싱 시작")
    if not os.path.exists(xml_path):
        raise FileNotFoundError(f"XML 로그 파일을 찾을 수 없습니다: {xml_path}")

    temp_points = []
    try:
        tree = ET.parse(xml_path)
        strip_namespace(tree)
        root = tree.getroot()
        for vd in root.findall('.//ValueData'):
            param_id = vd.attrib.get("ParameterID", "")
            if param_id not in param_map:
                # print(f">> [스킵] parameter_map에 없음 → 제외됨: {param_id}")
                continue

            param_name = param_map[param_id]
            param_values = []

            for child in vd:
                tag = child.tag.lower()
                if tag == "parametervalues":
                    param_values.extend(child.findall("ParameterValue"))
                elif tag == "parametervalue":
                    param_values.append(child)

            # print(f"ParameterID: {param_id} → {param_name}, 값 수: {len(param_values)}")

            for pv in param_values:
                try:
                    ts = pv.get("Timestamp")
                    val_node = pv.find("Value")
                    if ts is None or val_node is None or val_node.text is None:
                        continue
                    dt = datetime.fromisoformat(ts).replace(tzinfo=None)
                    val = float(val_node.text)
                    temp_points.append({'param': param_name, 'time': dt, 'value': val})
                except Exception as e:
                    print(f"   !! 파싱 예외: {e} (param={param_name})")
    except Exception as e:
        print(f">> [오류] XML 파싱 중 예외 발생: {e}")
        raise e

    if not temp_points:
        raise ValueError("XML 파일에 유효한 데이터를 찾을 수 없습니다.")
    return temp_points


class GraphTab(QWidget):
    TIME_OPTIONS = {
        "30분": timedelta(minutes=30), "1시간": timedelta(hours=1),
        "6시간": timedelta(hours=6), "12시간": timedelta(hours=12),
        "하루": timedelta(days=1),
    }

    GRAPH_DEFINITIONS = [
        {"y_label": "Pressure (Pa)", "y_scale": "log", "y_range": None,
         "series": ['IGP1', 'IGP2', 'IGP3', 'IGP4', 'HVG']},

        {"y_label": "Voltage (V)", "y_scale": "linear", "y_range": (0, 35000),
         "series": ['ACC_V', 'EXT_v', 'LENS1_V']},

        {"y_label": "Current (uA)", "y_scale": "linear", "y_range": (0, 50),
         "series": ['ACC_L', 'Emission', 'LENS1_L']}
    ]

    # --- 프로그레스 바 관련 상수 ---
    TOTAL_PROGRESS_STEPS = 100 # 전체 진행도 단위를 100으로 설정 (0-100%)
    BAT_EXEC_PROGRESS = 30     # 배치 파일 실행 (3초 대기)에 할당할 진행도 (0~30)
    XML_PARSE_PROGRESS = 50    # XML 파싱에 할당할 진행도 (30~80)
    GRAPH_PLOT_PROGRESS = 20   # 그래프 생성/업데이트에 할당할 진행도 (80~100)


    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self._setup_description(layout) # 설명 라벨 추가
        self._setup_controls(layout)
        self._setup_graph_area(layout)

        cfg = load_config()
        # 상대 경로 처리: 스크립트가 실행되는 디렉토리를 기준으로 경로를 구성
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        self.xml_log_path = os.path.join(current_script_dir, cfg.get("xml_log", "output.xml"))
        self.bat_path = os.path.join(current_script_dir, cfg.get("batch_file", "run_log_generation.bat"))
        
        self.param_map = cfg.get("parameter_map", {})

        self.all_series_names = list(set(sum([d["series"] for d in self.GRAPH_DEFINITIONS], [])))
        self.all_points = []
        
        # UI 초기 상태 설정 (버튼 비활성화 등)
        self._set_ui_enabled_state(True)


    def _setup_description(self, main_layout):
        self.description_label = QLabel(
            "이 탭은 `.bat` 파일을 실행하여 로그 XML 파일을 생성하고, "
            "해당 XML 파일을 파싱하여 실시간 데이터를 그래프로 시각화합니다. "
            "배치 파일 실행, XML 파싱, 그리고 그래프 업데이트의 진행 상황을 추적합니다."
        )
        self.description_label.setWordWrap(True)
        main_layout.addWidget(self.description_label)
        main_layout.addSpacing(10) # 설명과 컨트롤 사이 간격 추가


    def _setup_controls(self, main_layout):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("기간 선택:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(list(self.TIME_OPTIONS.keys()))
        self.time_combo.setCurrentText("30분")
        self.time_combo.currentTextChanged.connect(self.update_display)
        controls_layout.addWidget(self.time_combo)
        
        # 프로그레스 바와 스페이서 관리 (현재 스페이서 대신 텍스트 라벨 사용)
        self.progress_container_layout = QVBoxLayout()
        self.progress_container_layout.setAlignment(Qt.AlignTop) # 상단 정렬
        
        self.progress_text_label = QLabel("준비 완료.")
        self.progress_text_label.setFixedHeight(15) # 텍스트 라벨 높이 고정
        self.progress_container_layout.addWidget(self.progress_text_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.TOTAL_PROGRESS_STEPS) # 전체 진행도 범위 설정
        self.progress_bar.setTextVisible(True) # 텍스트 항상 보이게
        self.progress_bar.setFixedHeight(10)
        self.progress_container_layout.addWidget(self.progress_bar)
        
        controls_layout.addLayout(self.progress_container_layout, 1) # 프로그레스 바 컨테이너 추가
        
        self.refresh_button = QPushButton("로그 생성 및 새로고침")
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        controls_layout.addWidget(self.refresh_button)
        main_layout.addLayout(controls_layout)
        main_layout.addSpacing(10) # 컨트롤과 그래프 사이 간격 추가


    def _setup_graph_area(self, main_layout):
        self.figure = Figure(figsize=(10, 9), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.subplots(nrows=3, ncols=1, sharex=True)
        main_layout.addWidget(NavigationToolbar(self.canvas, self))
        main_layout.addWidget(self.canvas)
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

    def _set_ui_enabled_state(self, enabled):
        """UI 요소들의 활성화 상태를 설정합니다."""
        self.time_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        # 프로그레스 바와 텍스트 라벨은 항상 보이지만, 작업 중에는 버튼만 비활성화
        # self.progress_bar.setEnabled(enabled)
        # self.progress_text_label.setEnabled(enabled)

    def update_display(self):
        print(f">> [DEBUG] update_display called | all_points={len(self.all_points)}")

        if not self.all_points:
            self.status_label.setText("표시할 데이터가 없습니다.")
            for ax in self.axes:
                ax.clear()
            self.canvas.draw()
            return

        dmax = max(p['time'] for p in self.all_points)
        selected_delta = self.TIME_OPTIONS[self.time_combo.currentText()]
        cutoff_time = dmax - selected_delta

        for i, ax in enumerate(self.axes):
            definition = self.GRAPH_DEFINITIONS[i]
            data_for_this_graph = {name: [] for name in definition["series"]}
            for point in self.all_points:
                if point['time'] >= cutoff_time and point['param'] in definition["series"]:
                    data_for_this_graph[point['param']].append((point['time'], point['value']))
            self.plot_single_graph(ax, data_for_this_graph, definition)

        self.status_label.setText("그래프 업데이트 완료.")
        self.canvas.draw()

    def plot_single_graph(self, ax, series_data, definition):
        ax.clear()
        has_data = False
        for name in definition["series"]:
            display_name = name
            points = series_data.get(name, [])
            if points:
                points.sort(key=lambda x: x[0])
                times, values = zip(*points)

                if name == "Emission":
                    values = [v * 1e6 for v in values] # Emission 값은 1e6 곱하여 스케일링
                    display_name += " (scaled)"

                ax.plot(times, values, label=display_name, marker='.', linestyle='-', markersize=3)
                has_data = True
            else:
                ax.plot([], [], label=display_name) # 데이터가 없어도 범례 표시를 위해 빈 플롯 추가

        ax.set_ylabel(definition["y_label"])
        ax.set_yscale(definition["y_scale"])
        if definition["y_range"]:
            ax.set_ylim(definition["y_range"])
        if definition["y_scale"] == 'log':
            ax.yaxis.set_major_locator(LogLocator(base=10))
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.1e'))
        ax.grid(True, which="both", ls="--", alpha=0.6)
        ax.legend(loc='upper left', fontsize='small')

    def on_refresh_clicked(self):
        self._set_ui_enabled_state(False) # UI 비활성화
        self.progress_bar.setValue(0) # 프로그레스 바 초기화

        if not os.path.exists(self.bat_path):
            self.status_label.setText(f"오류: 배치 파일이 존재하지 않습니다: {self.bat_path}")
            self.progress_text_label.setText("오류 발생.")
            self._set_ui_enabled_state(True)
            return

        self.status_label.setText("배치 파일 실행 중...")
        self.progress_text_label.setText("단계 1/3: 배치 파일 실행 중...")
        self.progress_bar.setFormat("배치 파일 실행 중... %p%")
        QApplication.processEvents() # UI 업데이트 강제

        try:
            # 배치 파일 실행 (논블로킹)
            subprocess.Popen(self.bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print(f">> [DEBUG] Batch file executed: {self.bat_path}")
        except Exception as e:
            self.status_label.setText(f"오류: 배치 파일 실행 중 문제 발생: {e}")
            self.progress_text_label.setText("오류 발생.")
            self._set_ui_enabled_state(True)
            return

        # 배치 파일 실행 대기 및 진행도 업데이트 (3초 가정)
        self.elapsed_time_for_bat = 0
        self.bat_progress_timer = QTimer(self)
        self.bat_progress_timer.timeout.connect(self._update_bat_progress)
        self.bat_progress_timer.start(100) # 0.1초마다 업데이트

    def _update_bat_progress(self):
        self.elapsed_time_for_bat += 100
        # 배치 파일 실행은 3초를 가정하고, 전체 진행도의 BAT_EXEC_PROGRESS 비율을 차지
        current_val = int((self.elapsed_time_for_bat / 3000) * self.BAT_EXEC_PROGRESS)
        self.progress_bar.setValue(min(current_val, self.BAT_EXEC_PROGRESS)) # BAT_EXEC_PROGRESS를 넘지 않도록
        self.progress_bar.setFormat(f"배치 파일 실행 중... {min(current_val, self.BAT_EXEC_PROGRESS)}%")
        QApplication.processEvents()

        if self.elapsed_time_for_bat >= 3000:
            self.bat_progress_timer.stop()
            self._parse_xml_and_plot() # 다음 단계로 이동

    def _parse_xml_and_plot(self):
        self.status_label.setText("XML 데이터 파싱 중...")
        self.progress_text_label.setText("단계 2/3: XML 파싱 중...")
        # XML 파싱 진행도는 BAT_EXEC_PROGRESS부터 시작
        self.progress_bar.setFormat(f"XML 파싱 중... {self.BAT_EXEC_PROGRESS + 1}%")
        self.progress_bar.setValue(self.BAT_EXEC_PROGRESS + 1)
        QApplication.processEvents()

        try:
            # XML 데이터 로드
            self.all_points = parse_xml_data(self.xml_log_path, self.param_map)
            print(">> [DEBUG] XML data successfully loaded.")

            # XML 파싱 완료 후 진행도 업데이트
            self.progress_bar.setValue(self.BAT_EXEC_PROGRESS + self.XML_PARSE_PROGRESS)
            self.progress_bar.setFormat(f"XML 파싱 완료! {self.BAT_EXEC_PROGRESS + self.XML_PARSE_PROGRESS}%")
            QApplication.processEvents()

            # 그래프 업데이트 단계
            self.status_label.setText("그래프 업데이트 중...")
            self.progress_text_label.setText("단계 3/3: 그래프 업데이트 중...")
            self.progress_bar.setFormat(f"그래프 업데이트 중... {self.BAT_EXEC_PROGRESS + self.XML_PARSE_PROGRESS + 1}%")
            self.progress_bar.setValue(self.BAT_EXEC_PROGRESS + self.XML_PARSE_PROGRESS + 1)
            QApplication.processEvents()

            self.update_display() # 그래프 업데이트
            
            # 최종 완료
            self.progress_bar.setValue(self.TOTAL_PROGRESS_STEPS)
            self.progress_bar.setFormat("작업 완료!")
            self.status_label.setText("로그 생성 및 그래프 업데이트 완료.")
            self.progress_text_label.setText("작업 완료.")

        except FileNotFoundError as e:
            self.status_label.setText(f"오류: {e}")
            self.progress_text_label.setText("오류 발생: XML 파일 없음.")
            self.all_points = [] # 데이터 초기화
        except ValueError as e:
            self.status_label.setText(f"오류: {e}")
            self.progress_text_label.setText("오류 발생: 유효한 데이터 없음.")
            self.all_points = [] # 데이터 초기화
        except Exception as e:
            self.status_label.setText(f"예상치 못한 오류 발생: {e}")
            self.progress_text_label.setText("오류 발생.")
            self.all_points = [] # 데이터 초기화
        finally:
            self._set_ui_enabled_state(True) # UI 다시 활성화


# --- 메인 애플리케이션 실행 부분 (수정 없음) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    class MainWindow(QWidget): # QMainWindow 대신 QWidget으로 변경
        def __init__(self):
            super().__init__()
            self.setWindowTitle("로그 및 그래프 뷰어")
            self.setGeometry(100, 100, 1200, 900)

            main_layout = QVBoxLayout(self)
            self.graph_tab = GraphTab()
            main_layout.addWidget(self.graph_tab)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
