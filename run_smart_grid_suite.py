import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", message=r".*sklearn\.utils\.parallel.*")
import time
import subprocess
import threading
import re
import socket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

CLOUDFLARED_EXE = os.path.join(SCRIPT_DIR, "cloudflared.exe")

# Windows flag to suppress creating a new console window
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

def get_local_ip():
    """Finds local network IP of this PC."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def free_port(port: int = 8000):
    """Automatically terminates orphaned processes occupying the target port."""
    if os.name == 'nt':
        try:
            cmd = f"netstat -ano | findstr :{port}"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != os.getpid():
                        print(f"[Launcher] Port {port} in use by PID {pid}. Freeing port...")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        time.sleep(1)
        except Exception as e:
            print(f"[Launcher] Port cleanup notice: {e}")

def cleanup_old_tunnels():
    """Terminates any stale cloudflared processes from previous sessions."""
    if os.name == 'nt':
        try:
            subprocess.run("taskkill /F /IM cloudflared.exe", shell=True, capture_output=True)
        except Exception:
            pass

def run_web_server():
    """Runs Uvicorn web server in background thread without opening external windows."""
    try:
        import uvicorn
        try:
            from src.dashboard import grid_dashboard
        except ImportError:
            import grid_dashboard
        config = uvicorn.Config(
            grid_dashboard.app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"\n[Launcher Error] Web dashboard server failed to start: {e}\n")

def main():
    print("==================================================================")
    print("     ⚡ AUTONOMOUS SMART GRID: UNIFIED SYSTEM LAUNCHER ⚡         ")
    print("==================================================================")
    print("Initializing components silently (zero popup windows)...")

    # Step 1: Ensure port 8000 and old tunnels are clean
    free_port(8000)
    cleanup_old_tunnels()

    # Step 2: Start Web Dashboard in background thread
    print("[1/3] Starting SCADA Web Dashboard on port 8000 (thread)...")
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Active readiness poll: ensure web server is responding before launching tunnel
    for _ in range(30):
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:8000/api/status", timeout=0.5) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.2)

    # Step 3: Start Cloudflare Worldwide Tunnel in background (silent, no window)
    public_url = None
    log_file = os.path.join(SCRIPT_DIR, "cloudflared.log")
    link_file = os.path.join(SCRIPT_DIR, "public_link.txt")
    tunnel_proc = None

    if os.path.exists(log_file):
        try: os.remove(log_file)
        except Exception: pass

    if os.path.exists(CLOUDFLARED_EXE):
        print("[2/3] Provisioning Worldwide Public HTTPS Tunnel via Cloudflare...")
        try:
            tunnel_proc = subprocess.Popen(
                [CLOUDFLARED_EXE, "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", log_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )

            # Read log file for URL
            start_wait = time.time()
            while time.time() - start_wait < 15.0:
                if os.path.exists(log_file):
                    try:
                        with open(log_file, "r") as lf:
                            content = lf.read()
                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                            if match:
                                public_url = match.group(0)
                                with open(link_file, "w") as pf:
                                    pf.write(public_url)
                                break
                    except Exception:
                        pass
                time.sleep(0.5)
        except Exception as e:
            print(f"[Launcher] Cloudflare tunnel notice: {e}")
    else:
        print("[2/3] cloudflared.exe not found. Running in Local Wi-Fi mode.")

    local_ip = get_local_ip()

    # Print Access Banner
    print("\n==================================================================")
    print(" 🌐 SMART GRID SCADA DASHBOARD & AUTONOMOUS CONTROLLER ACTIVE     ")
    print("==================================================================")
    if public_url:
        print(f" 🌍 PUBLIC WORLDWIDE LINK:  {public_url}")
        print(f"    (Anyone anywhere can open this in any phone/PC browser)")
    else:
        print(" ℹ️  OFFLINE / LOCAL STANDBY: Cloudflare tunnel inactive (No Internet)")
        print("    Web SCADA is running locally on PC & Local Wi-Fi network.")
    print(f" 🏠 LOCAL WI-FI LINK:       http://{local_ip}:8000")
    print(f" 💻 PC LOCALHOST LINK:      http://localhost:8000")
    print("==================================================================")
    print(" Features Active:")
    print("  • Live Circular Capacity Gauge & 60s Rolling Multi-Load Charts")
    print("  • Open Remote Relay Actuation Deck (Hospital, Street, House, Industry)")
    print("  • Instant Smartphone Telegram Alerts & Simulator Fallback")
    print("  • 1-Click PDF Engineering & IEEE Reliability Report Download")
    print("==================================================================\n")

    # Step 3.5: If in simulation mode, start Virtual ESP32 Hardware
    is_simulated = ("--mock" in sys.argv or "--simulate" in sys.argv)
    sim = None
    if is_simulated:
        print("[MOCK MODE] Starting Virtual ESP32 Hardware Simulator in background...")
        try:
            from src.services.mock_esp32 import MockESP32Simulator
        except ImportError:
            from services.mock_esp32 import MockESP32Simulator
        sim = MockESP32Simulator()
        sim.start_simulation()

    # Step 4: Run AI Closed-Loop Controller in the foreground
    print("[3/3] Starting Autonomous Closed-Loop AI Controller...")
    try:
        import src.smart_grid_ai as smart_grid_ai
    except ImportError:
        import smart_grid_ai
    try:
        smart_grid_ai.start_ai_controller()
    except KeyboardInterrupt:
        print("\nExiting Smart Grid Suite. Clean shutdown complete.")
    finally:
        if sim:
            sim.stop_simulation()
        if tunnel_proc:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
