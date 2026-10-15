"""Start the auth server and the Streamlit app (plus the mock API in demo mode)."""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")  # child processes inherit these variables

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"


def main():
    procs = []
    if DEMO_MODE:
        os.environ["API_BASE_URL"] = "http://localhost:5001"
        procs.append(subprocess.Popen([sys.executable, HERE / "mock_api.py"]))

    procs.append(subprocess.Popen([sys.executable, HERE / "auth" / "app.py"]))
    procs.append(subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", HERE / "streamlit_app" / "main.py",
        "--server.headless", "true"
    ]))

    time.sleep(2)
    print(f"\nBirdTag running {'in demo mode ' if DEMO_MODE else ''}at http://localhost:8500/login\n")
    webbrowser.open("http://localhost:8500/login")

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
