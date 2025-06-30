import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import json
import winreg

# --- 기본 실행 파일 여부 확인 & 경로 설정 ---
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

# --- 설정 불러오기 ---
def load_config():
    config_path = os.path.join(base_path, "settings", "config.json")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- 자동 실행 설정 ---
APP_NAME = "QuickLogViewer"
def set_autorun(enable):
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    exe_path = sys.executable
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass

def is_autorun_enabled():
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return os.path.normcase(value) == os.path.normcase(sys.executable)
    except FileNotFoundError:
        return False

# --- 필터 키워드 ---
KEYWORDS = [
    "feg_lifetime", "feg_change", "lmis_lifetime",
    "gis1", "gis2",
    "mis1", "mis2", "mis3", "mis4", "mis5", "mis6"
]

# --- 요약 로그 추출 (폴더→파일 자동 처리 포함) ---
def extract_summary_lines(filepath):
    if os.path.isdir(filepath):
        # 디렉토리면 그 안에서 첫 .txt 파일 찾기
        txts = [f for f in os.listdir(filepath) if f.endswith(".txt")]
        if txts:
            filepath = os.path.join(filepath, txts[0])
        else:
            return [f"[No .txt files in directory: {filepath}]"]

    if not os.path.isfile(filepath):
        return [f"[Invalid log path: {filepath}]"]

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except PermissionError:
        return [f"[Permission denied opening file: {filepath}]"]

    summary = [line.strip() for line in lines if any(line.startswith(k) for k in KEYWORDS)]
    return summary if summary else ["[No matching keywords in log]"]

# --- '더 자세히' 버튼 동작: txt든 exe든 실행 됨 ---
def launch_detail_view():
    target = os.path.join("C:\\monitoring", "listlist.txt")
    try:
        subprocess.Popen(["start", "", target], shell=True)
    except Exception as e:
        messagebox.showerror("Launch error", f"Failed to open: {e}")

# --- GUI 생성 ---
def create_gui():
    config = load_config()
    filepath = config.get("data_file", "")
    filepath = os.path.abspath(os.path.join(base_path, filepath)) if not os.path.isabs(filepath) else filepath

    print("CONFIG:", config)
    print("FILEPATH:", filepath)

    root = tk.Tk()
    root.title("Quick Log Viewer")
    root.geometry("300x283")
    root.attributes("-alpha", 0.9)

    def on_alpha_change(val):
        root.attributes("-alpha", float(val))

    def on_autorun_toggle():
        set_autorun(var_autorun.get())

    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    check_autorun = tk.Checkbutton(root, text="Auto-run on Startup", variable=var_autorun, command=on_autorun_toggle)
    check_autorun.place(x=10, y=10)

    text_area = tk.Text(root, wrap="word", font=("Courier", 9))
    text_area.place(x=10, y=30, width=280, height=180)
    summary = extract_summary_lines(filepath)
    text_area.insert("1.0", "\n".join(summary))
    text_area.config(state="disabled")

    alpha_slider = tk.Scale(root, from_=0.3, to=1.0, resolution=0.01, orient="horizontal", label="Opacity", command=on_alpha_change)
    alpha_slider.set(0.9)
    alpha_slider.place(x=10, y=230, width=140)

    detail_frame = tk.Frame(root)
    tk.Label(detail_frame, text="Details", font=("Arial", 9)).pack(side="left", padx=4)
    tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view).pack(side="left")
    detail_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()