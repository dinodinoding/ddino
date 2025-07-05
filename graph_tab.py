import os
import subprocess
import sys
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QComboBox,
    QApplication
)
from PySide6.QtCore import QTimer, Qt
import xml.etree.ElementTree as ET

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.ticker import LogLocator, FormatStrFormatter

from utils.config_loader import load_config


def strip_namespace(tree):
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]


def parse_xml_data(xml_path, param_map):
    print(f">> [parse_xml_data] XML 데이터 파싱 시작: {xml_path}")
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
                continue
            param_name = param_map[param_id]
            param_values = []
            for child in vd:
                tag = child.tag.lower()
                if tag == "parametervalues":
                    param_values.extend(child.findall("ParameterValue"))
                elif tag == "parametervalue":
                    param_values.append(child)
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
        raise ValueError(f"XML 파일 '{xml_path}'에 유효한 데이터를 찾을 수 없습니다.")
    return temp_points


def find_latest_xml_file(directory_path):
    print(f">> [find_latest_xml_file] 디렉토리에서 최신 XML 파일 검색: {directory_path}")
    if not os.path.isdir(directory_path):
        raise FileNotFoundError(f"지정된 디렉토리를 찾을 수 없습니다: {directory_path}")

    xml_files = []
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".xml"):
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                xml_files.append((os.path.getmtime(file_path), file_path))

    if not xml_files:
        raise FileNotFoundError(f"'{directory_path}' 디렉토리에서 XML 파일을 찾을 수 없습니다.")

    xml_files.sort(key=lambda x: x[0], reverse=True)
    latest_file_path = xml_files[0][1]
    print(f">> [find_latest_xml_file] 최신 XML 파일 발견: {latest_file_path}")
    return latest_file_path


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

    TOTAL_PROGRESS_STEPS = 100
    BAT_EXEC_PROGRESS_RATIO = 0.30
    XML_FIND_PARSE_PROGRESS_RATIO = 0.50
    GRAPH_PLOT_PROGRESS_RATIO = 0.20

    BAT_EXEC_START = 0
    BAT_EXEC_END = int(TOTAL_PROGRESS_STEPS * BAT_EXEC_PROGRESS_RATIO)
    XML_FIND_PARSE_START = BAT_EXEC_END
    XML_FIND_PARSE_END = BAT_EXEC_END + int(TOTAL_PROGRESS_STEPS * XML_FIND_PARSE_PROGRESS_RATIO)
    GRAPH_PLOT_START = XML_FIND_PARSE_END
    GRAPH_PLOT_END = TOTAL_PROGRESS_STEPS

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._setup_description(layout)
        self._setup_controls(layout)
        self._setup_graph_area(layout)

        cfg = load_config()

        self.xml_output_directory = cfg.get("xml_output_directory", "C:/monitoring")
        self.bat_path = cfg.get("batch_file", "C:/monitoring/run_log_generation.bat")
        self.param_map = cfg.get("parameter_map", {})

        # ✅ 추가: 배치 실행 체크 간격 (기본값 200ms)
        self.bat_check_interval = cfg.get("bat_check_interval_ms", 200)

        self.all_series_names = list(set(sum([d["series"] for d in self.GRAPH_DEFINITIONS], [])))
        self.all_points = []
        self.bat_process = None

        self._set_ui_enabled_state(True)

    def _setup_description(self, main_layout):
        self.description_label = QLabel(
            "이 탭은 `.bat` 파일을 실행하여 로그 XML 파일을 생성하고, "
            "해당 XML 파일을 파싱하여 실시간 데이터를 그래프로 시각화합니다. "
            "배치 파일 실행, XML 파싱, 그리고 그래프 업데이트의 진행 상황을 추적합니다."
        )
        self.description_label.setWordWrap(True)
        main_layout.addWidget(self.description_label)
        main_layout.addSpacing(10)

    def _setup_controls(self, main_layout):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("기간 선택:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(list(self.TIME_OPTIONS.keys()))
        self.time_combo.setCurrentText("30분")
        self.time_combo.currentTextChanged.connect(self.update_display)
        controls_layout.addWidget(self.time_combo)

        self.progress_container_layout = QVBoxLayout()
        self.progress_container_layout.setAlignment(Qt.AlignTop)

        self.progress_text_label = QLabel("준비 완료.")
        self.progress_text_label.setFixedHeight(15)
        self.progress_container_layout.addWidget(self.progress_text_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.TOTAL_PROGRESS_STEPS)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(10)
        self.progress_container_layout.addWidget(self.progress_bar)

        controls_layout.addLayout(self.progress_container_layout, 1)

        self.refresh_button = QPushButton("로그 생성 및 새로고침")
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        controls_layout.addWidget(self.refresh_button)

        main_layout.addLayout(controls_layout)
        main_layout.addSpacing(10)

    def _setup_graph_area(self, main_layout):
        self.figure = Figure(figsize=(10, 9), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.subplots(nrows=3, ncols=1, sharex=True)
        main_layout.addWidget(NavigationToolbar(self.canvas, self))
        main_layout.addWidget(self.canvas)
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

    def _set_ui_enabled_state(self, enabled):
        self.time_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def update_display(self):
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
            points = series_data.get(name, [])
            if points:
                points.sort(key=lambda x: x[0])
                times, values = zip(*points)
                if name == "Emission":
                    values = [v * 1e6 for v in values]
                ax.plot(times, values, label=name, marker='.', linestyle='-', markersize=3)
                has_data = True
            else:
                ax.plot([], [], label=name)

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
        self._set_ui_enabled_state(False)
        self.progress_bar.setValue(self.BAT_EXEC_START)

        if not os.path.exists(self.bat_path):
            self.status_label.setText(f"오류: 배치 파일이 존재하지 않습니다: {self.bat_path}")
            self.progress_text_label.setText("오류 발생.")
            self._set_ui_enabled_state(True)
            return

        self.status_label.setText("배치 파일 실행 중...")
        self.progress_text_label.setText("단계 1/3: 배치 파일 실행 중...")
        self.progress_bar.setFormat("배치 파일 실행 중... %p%")
        QApplication.processEvents()

        try:
            self.bat_process = subprocess.Popen(self.bat_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.status_label.setText(f"오류: 배치 파일 실행 중 문제 발생: {e}")
            self.progress_text_label.setText("오류 발생.")
            self._set_ui_enabled_state(True)
            return

        self.bat_check_timer = QTimer(self)
        self.bat_check_timer.timeout.connect(self._check_bat_completion)
        self.bat_check_timer.start(self.bat_check_interval)  # ✅ 적용 완료

    def _check_bat_completion(self):
        return_code = self.bat_process.poll()

        if return_code is not None:
            self.bat_check_timer.stop()
            if return_code != 0:
                self.status_label.setText(f"오류: 배치 파일이 오류 코드 {return_code}로 종료되었습니다.")
                self.progress_text_label.setText(f"오류: 배치 파일 실패 ({return_code}).")
                self.progress_bar.setValue(0)
                self._set_ui_enabled_state(True)
                return

            self.progress_bar.setValue(self.BAT_EXEC_END)
            self._find_and_parse_xml_and_plot()
        else:
            current_value = self.BAT_EXEC_START + int((self.BAT_EXEC_END - self.BAT_EXEC_START) * 0.5)
            self.progress_bar.setValue(current_value)
            QApplication.processEvents()

    def _find_and_parse_xml_and_plot(self):
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

            self.update_display()

            self.progress_bar.setValue(self.TOTAL_PROGRESS_STEPS)
            self.progress_bar.setFormat("작업 완료!")
            self.status_label.setText("로그 생성 및 그래프 업데이트 완료.")
            self.progress_text_label.setText("작업 완료.")

        except Exception as e:
            self.status_label.setText(f"오류: {e}")
            self.progress_text_label.setText("오류 발생.")
            self.all_points = []
        finally:
            self._set_ui_enabled_state(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    class MainWindow(QWidget):
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