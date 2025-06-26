import os
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QComboBox,
    QStackedLayout, QFrame
)
from PySide6.QtCore import QTimer
import xml.etree.ElementTree as ET

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.ticker import LogLocator, FormatStrFormatter
import matplotlib.dates as mdates

from utils.config_loader import load_config


def strip_namespace(tree):
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
                print(f">> [스킵] parameter_map에 없음 → 제외됨: {param_id}")
                continue

            param_name = param_map[param_id]
            param_values = []

            for child in vd:
                tag = child.tag.lower()
                if tag == "parametervalues":
                    param_values.extend(child.findall("ParameterValue"))
                elif tag == "parametervalue":
                    param_values.append(child)

            print(f"ParameterID: {param_id} → {param_name}, 값 수: {len(param_values)}")

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
        {"y_label": "Pressure (Pa)", "y_scale": "log", "y_range": None, "series": ['IGP1', 'IGP2', 'IGP3', 'IGP4', 'HVG']},
        {"y_label": "Voltage (V)", "y_scale": "linear", "y_range": (0, 35000), "series": ['ACC', 'EXT', 'LENS1', 'Supp']},
        {"y_label": "Current (uA)", "y_scale": "linear", "y_range": (0, 50), "series": ['ACC_Leakage', 'Emission_current', 'Lens1_Leakage', 'Supp_Leakage']}
    ]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self._setup_controls(layout)
        self._setup_graph_area(layout)

        cfg = load_config()
        self.xml_log_path = cfg.get("xml_log", "")
        self.bat_path = cfg.get("batch_file", "")
        self.param_map = cfg.get("parameter_map", {})

        self.all_series_names = list(set(sum([d["series"] for d in self.GRAPH_DEFINITIONS], [])))
        self.all_points = []
        self.update_display(force_reload=True)

    def _setup_controls(self, main_layout):
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("기간 선택:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(list(self.TIME_OPTIONS.keys()))
        self.time_combo.setCurrentText("30분")
        self.time_combo.currentTextChanged.connect(self.update_display)
        controls_layout.addWidget(self.time_combo)

        self.stretchy_layout = QStackedLayout()
        self.stretchy_layout.addWidget(QFrame())  # Spacer
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 3000)
        self.progress_bar.setTextVisible(False)
        self.stretchy_layout.addWidget(self.progress_bar)
        controls_layout.addLayout(self.stretchy_layout, 1)

        self.refresh_button = QPushButton("로그 생성 및 새로고침")
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        controls_layout.addWidget(self.refresh_button)
        main_layout.addLayout(controls_layout)

    def _setup_graph_area(self, main_layout):
        self.figure = Figure(figsize=(10, 9), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.subplots(nrows=3, ncols=1, sharex=True)
        main_layout.addWidget(NavigationToolbar(self.canvas, self))
        main_layout.addWidget(self.canvas)
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

    def update_display(self, force_reload=False):
        if force_reload or not self.all_points:
            self.status_label.setText("XML 데이터 로딩 중...")
            if not self._load_data_from_xml():
                for ax in self.axes:
                    ax.clear()
                self.canvas.draw()
                return

        if not self.all_points:
            self.status_label.setText("표시할 데이터가 없습니다.")
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
        for name, points in series_data.items():
            if points:
                points.sort(key=lambda x: x[0])
                times, values = zip(*points)
                ax.plot(times, values, label=name, marker='.', linestyle='-', markersize=3)
        ax.set_ylabel(definition["y_label"])
        ax.set_yscale(definition["y_scale"])
        if definition["y_range"]:
            ax.set_ylim(definition["y_range"])
        if definition["y_scale"] == 'log':
            ax.yaxis.set_major_locator(LogLocator(base=10))
            ax.yaxis.set_major_formatter(FormatStrFormatter('%.1e'))
        ax.grid(True, which="both", ls="--", alpha=0.6)
        if any(series_data.values()):
            ax.legend(loc='upper left', fontsize='small')

    def on_refresh_clicked(self):
        if not self.bat_path or not os.path.exists(self.bat_path):
            self.status_label.setText(f"배치 파일이 존재하지 않습니다: {self.bat_path}")
            return
        self.status_label.setText("배치 파일 실행 중... 3초 대기합니다.")
        subprocess.Popen(self.bat_path, shell=True)
        self.stretchy_layout.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.elapsed = 0
        self.refresh_button.setEnabled(False)
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(100)

    def _update_progress(self):
        self.elapsed += 100
        self.progress_bar.setValue(self.elapsed)
        if self.elapsed >= 3000:
            self.progress_timer.stop()
            self.stretchy_layout.setCurrentIndex(0)
            self.refresh_button.setEnabled(True)
            self.update_display(force_reload=True)

    def _load_data_from_xml(self):
        try:
            self.all_points = parse_xml_data(self.xml_log_path, self.param_map)
            return True
        except Exception as e:
            self.status_label.setText(str(e))
            self.all_points = []
            return False