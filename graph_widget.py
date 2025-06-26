# widgets/graph_widget.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import LogLocator, FormatStrFormatter, FuncFormatter
import matplotlib.dates as mdates

class GraphWidget(QWidget):
    """
    단일 Matplotlib 그래프를 표시하고 관리하는, 재사용 가능한 위젯.
    Y축 스케일, 범위, 레이블 등을 커스터마이징할 수 있음.
    """
    def __init__(self, y_label, y_scale='linear', y_range=None, parent=None):
        super().__init__(parent)
        self.y_label = y_label
        self.y_scale = y_scale
        self.y_range = y_range
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)

        self.canvas = FigureCanvas(Figure(figsize=(10, 3)))
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.canvas.figure.add_subplot(111)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.ax.callbacks.connect('xlim_changed', self.update_x_ticks)
    
    def update_x_ticks(self, ax_event):
        """현재 보이는 x축 범위에 맞춰 동적으로 틱과 포맷을 '완전 수동으로' 업데이트하는 최종 함수."""
        try:
            xmin, xmax = self.ax.get_xlim()
            duration_seconds = (xmax - xmin) * 24 * 3600

            # --- 최종 해결책: FuncFormatter를 사용하여 포맷을 강제 ---
            if duration_seconds <= 2:
                locator = mdates.MicrosecondLocator(interval=200000)
                # %f는 마이크로초(6자리), 슬라이싱으로 밀리초(3자리)로 만듦
                formatter = FuncFormatter(lambda x, pos: f"{mdates.num2date(x).strftime('%S.%f')[:-3]}")
            elif duration_seconds <= 15:
                locator = mdates.SecondLocator(interval=1)
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%H:%M:%S'))
            elif duration_seconds <= 60 * 2:
                locator = mdates.SecondLocator(interval=10)
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%H:%M:%S'))
            elif duration_seconds <= 60 * 30:
                locator = mdates.MinuteLocator(interval=1)
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%H:%M'))
            elif duration_seconds <= 3600 * 2:
                locator = mdates.MinuteLocator(interval=10)
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%H:%M'))
            elif duration_seconds <= 3600 * 12: # 12시간 이하 (6시간, 12시간 옵션)
                locator = mdates.HourLocator(interval=1)
                # '11:00' 형식 강제
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%H:%M'))
            else: # 그 이상 (하루 옵션)
                locator = mdates.HourLocator(interval=3)
                # '06-23 11:00' 형식 강제
                formatter = FuncFormatter(lambda x, pos: mdates.num2date(x).strftime('%m-%d %H:%M'))
            
            self.ax.xaxis.set_major_locator(locator)
            self.ax.xaxis.set_major_formatter(formatter)
            
            for label in self.ax.get_xticklabels():
                label.set_rotation(30)
                label.set_ha('right')
            
            self.canvas.draw_idle()
        except Exception:
            pass

    def plot_data(self, series_data, start_time, end_time):
        self.ax.clear()
        
        for name, points in series_data.items():
            if points:
                points.sort(key=lambda x: x[0]) 
                times = [p[0] for p in points]
                values = [p[1] for p in points]
                self.ax.plot(times, values, label=name, marker='.', linestyle='-', markersize=3)
        
        if start_time and end_time:
            self.ax.set_xlim(start_time, end_time)
        
        self.ax.set_ylabel(self.y_label)
        self.ax.set_yscale(self.y_scale)
        if self.y_range:
            self.ax.set_ylim(self.y_range)
        
        if self.y_scale == 'log':
            self.ax.yaxis.set_major_locator(LogLocator(base=10))
            self.ax.yaxis.set_major_formatter(FormatStrFormatter('%.1e'))
        
        self.ax.grid(True, which="both", ls="--", alpha=0.6)
        
        if any(series_data.values()):
            self.ax.legend(loc='upper left', fontsize='small')
        
        self.canvas.figure.tight_layout()
        self.canvas.draw()