"""
Universal, reliable backend launcher for Leads Scraper.
Prevents WinError 10048 (port 8000 already in use) by cleanly freeing port 8000
before launching uvicorn with auto-reload.
"""
import os
import sys
import time
import subprocess

def free_port(port: int = 8000) -> None:
    """Terminates any orphan or lingering process holding the target port."""
    if sys.platform == "win32":
        try:
            cmd = f"netstat -ano | findstr :{port}"
            output = subprocess.check_output(cmd, shell=True).decode()
            current_pid = os.getpid()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    pid = int(parts[-1])
                    if pid != current_pid and pid != 0:
                        print(f"[Launcher] Found lingering process (PID {pid}) on port {port}. Terminating...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        time.sleep(1)
        except Exception:
            pass

def main() -> None:
    free_port(8000)
    print("[Launcher] Starting Leads Platform backend on http://127.0.0.1:8000 ...")
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
