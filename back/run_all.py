import subprocess
import sys
import time


def run_services():
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ocr.main:app",
            "--port",
            "8000",
            "--reload",
        ],
        [
            sys.executable,
            "-m",
            "uvicorn",
            "translate.main:app",
            "--port",
            +"8001",
            "--reload",
        ],
        [
            sys.executable,
            "-m",
            "uvicorn",
            "manager.main:app",
            "--port",
            "8002",
            "--reload",
        ],
    ]

    processes = []
    try:
        for cmd in commands:
            p = subprocess.Popen(cmd)
            processes.append(p)
            time.sleep(1)  # Krótka pauza między startem kolejnych usług

        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        for p in processes:
            p.terminate()


if __name__ == "__main__":
    run_services()
