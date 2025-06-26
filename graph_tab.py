# graph_tab.py

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


import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# 🔧 [추가] 네임스페이스 제거 함수
def strip_namespace(tree):
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    return tree

def parse_xml_data(xml_path, series_names):
    print(">> [parse_xml_data] XML 데이터 파싱 시작")
    if not os.path.exists(xml_path):
        print(f">> [오류] XML 파일 경로 존재하지 않음: {xml_path}")
        raise FileNotFoundError(f"XML 로그 파일을 찾을 수 없습니다: {xml_path}")

    temp_points = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        strip_namespace(tree)  # 🔧 [추가됨] 네임스페이스 제거

        value_data_list = root.findall('.//ValueData')
        print(f">> 전체 ValueData 블록 수: {len(value_data_list)}")

        for idx, vd in enumerate(value_data_list, 1):
            full_param = vd.get('Parameter') or vd.get('Prameter') or ""
            print(f"\n-- [{idx}] ValueData Parameter: {full_param}")

            # 🔧 [수정됨] 정규표현식으로 정확히 I-Column.파라미터만 추출
            match = re.search(r'I-Column\.([A-Za-z0-9_]+)$', full_param)
            if not match:
                print("   ❌ 패턴 불일치 → 건너뜀")
                continue
            param_name = match.group(1)

            if param_name not in series_names:
                print(f"   ❌ 시리즈 대상 아님: {param_name}")
                continue

            print(f"   ✅ 대상 파라미터: {param_name}")

            # 내부 값 파싱
            param_values = vd.findall('ParameterValue')
            print(f"   ▶ 포함된 ParameterValue 수: {len(param_values)}")
            for pv in param_values:
                try:
                    ts = pv.get('Timestamp')
                    val_node = pv.find('Value')
                    val_text = val_node.text if val_node is not None else None

                    if ts is None or val_node is None or val_text is None:
                        print(f"      ⚠️ 스킵: Timestamp 또는 Value 없음")
                        continue

                    # 🔧 [보완] Z가 붙은 경우도 처리
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                    val = float(val_text)
                    temp_points.append({'param': param_name, 'time': dt, 'value': val})
                except Exception as e:
                    print(f"      ⚠️ 파싱 실패 → {e}")
                    continue

    except Exception as e:
        print(f">> [오류] XML 파싱 중 예외 발생: {e}")
        raise e

    if not temp_points:
        print(">> [경고] 유효한 데이터가 없음")
        raise ValueError("XML 파일에 유효한 데이터를 찾을 수 없습니다.")

    print(f">> [성공] 파싱된 포인트 수: {len(temp_points)}")
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
        print(">> [GraphTab] 그래프 탭 초기화 시작")

        layout = QVBoxLayout(self)
        self._setup_controls(layout)
        self._setup_graph_area(layout)

        try:
            cfg = load_config()
        except Exception as e:
            print(f"[에러] config 로드 실패: {e}")
            cfg = {}
        self.xml_log_path = cfg.get("xml_log", "")
        self.bat_path = cfg.get("batch_file", "")
        if not self.xml_log_path:
            print("[경고] xml_log 경로가 비어있음")
        if not self.bat_path:
            print("[경고] batch_file 경로가 비어있음")
        print(f">> 설정된 XML 경로: {self.xml_log_path}")
        print(f">> 설정된 배치 파일 경로: {self.bat_path}")

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
        stretchy_spacer = QFrame()
        stretchy_spacer.setFrameShape(QFrame.Shape.NoFrame)
        self.stretchy_layout.addWidget(stretchy_spacer)

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

        toolbar = NavigationToolbar(self.canvas, self)
        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.canvas)

        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)
        self.axes[0].callbacks.connect('xlim_changed', self.update_x_ticks)

    def update_x_ticks(self, ax_event):
        try:
            xmin, xmax = self.axes[0].get_xlim()
            duration_seconds = (xmax - xmin) * 24 * 3600
            if duration_seconds <= 15:
                formatter = mdates.DateFormatter('%H:%M:%S')
            elif duration_seconds <= 3600 * 12:
                formatter = mdates.DateFormatter('%H:%M')
            else:
                formatter = mdates.DateFormatter('%m-%d %H:%M')
            self.axes[-1].xaxis.set_major_formatter(formatter)
            self.canvas.draw_idle()
        except Exception as e:
            print(f">> [경고] x축 포맷 변경 중 예외 발생: {e}")

    def update_display(self, force_reload=False):
        print(">> [update_display] 그래프 업데이트 시작")
        if force_reload or not self.all_points:
            self.status_label.setText("XML 데이터 로딩 중...")
            if not self._load_data_from_xml():
                print(">> [경고] XML 로드 실패")
                for ax in self.axes:
                    ax.clear()
                self.canvas.draw()
                return

        if not self.all_points:
            self.status_label.setText("표시할 데이터가 없습니다.")
            print(">> [경고] 데이터 없음")
            return

        try:
            dmax = max(p['time'] for p in self.all_points)
            selected_delta = self.TIME_OPTIONS[self.time_combo.currentText()]
            cutoff_time = dmax - selected_delta
            print(f">> 시간 필터: {self.time_combo.currentText()}, cutoff={cutoff_time}")
        except ValueError:
            self.status_label.setText("데이터에서 유효한 시간을 찾을 수 없습니다.")
            print(">> [오류] 시간 파싱 실패")
            return

        for i, ax in enumerate(self.axes):
            definition = self.GRAPH_DEFINITIONS[i]
            print(f">> 그래프 {i} 그리기 시작")
            data_for_this_graph = {name: [] for name in definition["series"]}
            for point in self.all_points:
                if point['time'] >= cutoff_time and point['param'] in definition["series"]:
                    data_for_this_graph[point['param']].append((point['time'], point['value']))
            print(f"   >> {definition['y_label']} 데이터 수: {[len(data_for_this_graph[name]) for name in definition['series']]}")
            self.plot_single_graph(ax, data_for_this_graph, definition)

        self.status_label.setText("그래프 업데이트 완료.")
        self.canvas.draw()
        print(">> [update_display] 그래프 완료")

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
        print(f">> [refresh] 배치 실행 요청: {self.bat_path}")
        if not self.bat_path:
            print("[에러] batch_file 경로가 비어있음")
        if not os.path.exists(self.bat_path):
            msg = f"배치 파일이 존재하지 않습니다: {self.bat_path}"
            self.status_label.setText(msg)
            print(f">> [오류] {msg}")
            return

        self.status_label.setText("배치 파일 실행 중... 3초 대기합니다.")
        try:
            subprocess.Popen(self.bat_path, shell=True)
            print(f">> [refresh] 배치 파일 실행: {self.bat_path}")
        except Exception as e:
            msg = f"배치 파일 실행 실패: {e}"
            self.status_label.setText(msg)
            print(f">> [오류] {msg}")
            return

        self.stretchy_layout.setCurrentIndex(1)
        self.progress_bar.setValue(0)
        self.elapsed = 0
        self.refresh_button.setEnabled(False)
        print("[상태] refresh_button 비활성화, 진행바 시작")
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(100)

    def _update_progress(self):
        self.elapsed += 100
        self.progress_bar.setValue(self.elapsed)
        print(f"[진행] 진행바 값: {self.elapsed}")
        if self.elapsed >= 3000:
            print(">> [refresh] 진행바 완료 → XML 로드")
            self.progress_timer.stop()
            self.stretchy_layout.setCurrentIndex(0)
            self.refresh_button.setEnabled(True)
            print("[상태] refresh_button 활성화")
            self.update_display(force_reload=True)

    def _load_data_from_xml(self):
        print(">> [load_data] XML 로드 시도")
        try:
            self.all_points = parse_xml_data(self.xml_log_path, self.all_series_names)
            print(f">> [load_data] XML 로드 성공, 데이터 수: {len(self.all_points)}")
            return True
        except Exception as e:
            print(f">> [load_data] XML 로드 실패: {e}")
            self.status_label.setText(str(e))
            self.all_points = []
            return False
