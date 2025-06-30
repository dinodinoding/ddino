import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import json
import winreg

# --- 설정 불러오기 ---
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "settings", "config.json")
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

# --- 로그 요약 추출 ---
def extract_summary_lines(filepath):
    if not os.path.exists(filepath):
        return ["[로그 파일을 찾을 수 없습니다]"]
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    summary = [line.strip() for line in lines if any(line.startswith(k) for k in KEYWORDS)]
    return summary if summary else ["[요약 가능한 로그 없음]"]

# --- 외부 파일 실행 ---
def launch_detail_view():
    target_path = "C:\\monitoring\\listlist.txt"
    try:
        subprocess.Popen(["start", "", target_path], shell=True)
    except Exception as e:
        messagebox.showerror("실행 오류", f"파일 실행 실패:\n{e}")

# --- GUI 생성 ---
def create_gui():
    config = load_config()
    filepath = config.get("data_file", "")
    filepath = os.path.abspath(filepath)

    root = tk.Tk()
    root.title("Quick Log Viewer")
    root.geometry("300x200")
    root.attributes("-alpha", 0.9)

    # 투명도 조절 핸들러
    def on_alpha_change(val):
        alpha = float(val)
        root.attributes("-alpha", alpha)

    # 상단 체크박스
    def on_autorun_toggle():
        set_autorun(var_autorun.get())

    var_autorun = tk.BooleanVar(value=is_autorun_enabled())
    check_autorun = tk.Checkbutton(root, text="Windows 재시작 시 자동 실행", variable=var_autorun, command=on_autorun_toggle)
    check_autorun.place(x=10, y=10)

    # 로그 출력
    text_area = tk.Text(root, wrap="word", font=("Courier", 9))
    text_area.place(x=10, y=40, width=280, height=80)
    summary_lines = extract_summary_lines(filepath)
    text_area.insert("1.0", "\n".join(summary_lines))
    text_area.config(state="disabled")

    # 투명도 슬라이더
    alpha_slider = tk.Scale(root, from_=0.3, to=1.0, resolution=0.01, orient="horizontal", label="투명도", command=on_alpha_change)
    alpha_slider.set(0.9)
    alpha_slider.place(x=10, y=130, width=140)

    # 하단 '더 자세히 ⚙' 버튼
    detail_frame = tk.Frame(root)
    label = tk.Label(detail_frame, text="더 자세히", font=("Arial", 9))
    label.pack(side="left", padx=4)
    gear_button = tk.Button(detail_frame, text="⚙", font=("Arial", 10), command=launch_detail_view)
    gear_button.pack(side="left")
    detail_frame.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()