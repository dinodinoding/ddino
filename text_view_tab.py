from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtGui import QFont
import os
import re
from utils.config_loader import load_config
from utils.summary_loader import load_summary_config

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# ─────────────────────────────────────────────────────────────
# 🔹 STIG 그래프 박스
class StigGraphBox(QWidget):
    def __init__(self, title, x_val, y_val):
        super().__init__()
        layout = QVBoxLayout(self)
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
        layout.addWidget(canvas)

# ─────────────────────────────────────────────────────────────
# 🔹 요약 텍스트 박스
class MultiLineSummaryBox(QWidget):
    def __init__(self, file_path, label_mapping, title=None):
        super().__init__()
        layout = QVBoxLayout(self)
        font = QFont("Arial", 10)

        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Arial", 12, QFont.Bold))
            layout.addWidget(title_label)

        results = []

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for keyword, label_prefix in label_mapping:
                matched = False
                for line in lines:
                    line = line.strip()
                    if line.startswith(keyword) and 'data' in line:
                        parts = re.split(r'\s+data\s+', line.strip())
                        if len(parts) == 2:
                            value = parts[1].strip()

                            # ✅ 특별 처리: apercurr → 줄바꿈
                            if keyword == "apercurr":
                                value = value.replace("/", "\n")
                                results.append(f"{label_prefix}\n{value}")
                            else:
                                results.append(f"{label_prefix} {value}")

                            matched = True
                            break
                if not matched:
                    results.append(f"{label_prefix} [값 없음]")
        else:
            results = ["[파일 없음]"]

        for line in results:
            lbl = QLabel(line)
            lbl.setFont(font)
            layout.addWidget(lbl)

        self.setLayout(layout)

# ─────────────────────────────────────────────────────────────
# 🔹 SEM Align + STIG 섹션
class SemAlignStigSection(QWidget):
    def __init__(self, data_file):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SEM Align&stig", font=QFont("Arial", 12, QFont.Bold)))

        semalign_text = ""
        stig_coords = {}

        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("sem_align") and 'data' in line:
                        value = re.split(r'\s+data\s+', line)[-1].strip()
                        semalign_text = f"Last SEM_Align Data {value}"
                    elif line.startswith("stig_"):
                        match = re.match(r"stig_(\w+?)_(x|y)\s+data\s+([-\d\.eE]+)", line)
                        if match:
                            level, axis, val_str = match.groups()
                            key = f"stig{level.lower()}"
                            try:
                                value = float(val_str)
                                if key not in stig_coords:
                                    stig_coords[key] = {}
                                stig_coords[key][axis] = value
                            except ValueError:
                                continue

        if semalign_text:
            layout.addWidget(QLabel(semalign_text, font=QFont("Courier", 10)))

        graph_layout = QHBoxLayout()
        for key in ['stig20k', 'stig10k', 'stig5k', 'stig2k', 'stig1k']:
            coords = stig_coords.get(key, {'x': 0, 'y': 0})
            graph_layout.addWidget(StigGraphBox(key.upper(), coords['x'], coords['y']))
        layout.addLayout(graph_layout)

# ─────────────────────────────────────────────────────────────
# 🔹 전체 탭 구성
class TextViewTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        config = load_config()
        data_file = config.get("data_file")
        summary_config = load_summary_config()

        # 왼쪽: FEG, SGIS, MIS
        for title in ["FEG", "SGIS", "MGIS"]:
            if title in summary_config:
                mapping = summary_config[title].items()
                left_layout.addWidget(MultiLineSummaryBox(data_file, mapping, title))

        left_layout.addWidget(SemAlignStigSection(data_file))

        # 오른쪽: IPG, LMIS, Aperture
        for title in ["IGP", "LMIS", "FIB_Aperture"]:
            if title in summary_config:
                mapping = summary_config[title].items()
                right_layout.addWidget(MultiLineSummaryBox(data_file, mapping, title))

        layout.addLayout(left_layout)
        layout.addLayout(right_layout)
        layout.addStretch(1)
