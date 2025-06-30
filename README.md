# ddino

pyinstaller --noconfirm --onefile --windowed quick_log_viewer.py


Traceback (most recent call last):
  File "quickviewer.py", line 111, in <module>
    create_gui()
  File "quickviewer.py", line 91, in create_gui
    summary_lines = extract_summary_lines(filepath)
  File "quickviewer.py", line 51, in extract_summary_lines
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
PermissionError: [Errno 13] Permission denied: 'C:\\errorlogtool\\project6'
무슨 에러지 해결방법은?
