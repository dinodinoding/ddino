import subprocess

def stop_monitor_process():
    try:
        # 프로세스명은 빌드한 .exe 이름 기준
        subprocess.run('taskkill /f /im monitor_on.exe', shell=True, check=True)
        print(">> 모니터링 프로세스 종료 완료")
    except subprocess.CalledProcessError as e:
        print(">> 종료 실패 또는 실행 중이지 않음")

if __name__ == "__main__":
    stop_monitor_process()