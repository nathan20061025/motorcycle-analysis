"""Desktop launcher: starts the server, opens the browser, prints the phone (LAN) URL.
Used by start.bat (from source) and by the packaged Windows build."""
import os, socket, sys, threading, time, urllib.request, webbrowser


def _lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return None


def _free_port(start=8080):
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def main():
    if getattr(sys, "frozen", False):   # packaged build: data in %APPDATA%, bundled weights
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        os.environ.setdefault("DATA_DIR", os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                                                       "TrafficAnalysis", "data"))
        os.environ.setdefault("TRAFFIC_MODEL", os.path.join(base, "yolov8n.pt"))
    else:
        os.environ.setdefault("TRAFFIC_MODEL", "yolov8n.pt")
        os.environ.setdefault("DATA_DIR", "data")
    import uvicorn
    from app.main import app
    port = int(os.environ.get("PORT", 0)) or _free_port()
    print("=" * 56, "\n Motorcycle Traffic Analysis\n", "=" * 56)
    print(f" Open on this PC : http://localhost:{port}")
    ip = _lan_ip()
    if ip:
        print(f" Open on phone   : http://{ip}:{port}   (same Wi-Fi; allow firewall access if asked)")
    print(f" Data folder     : {os.environ['DATA_DIR']}\n Close this window to stop the app.\n")

    def open_browser():
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); break
            except Exception:
                time.sleep(0.5)
        if not os.environ.get("NO_BROWSER"):
            webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
