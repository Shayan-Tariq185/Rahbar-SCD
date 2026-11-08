"""Lightweight local proxy to view the RAHBAR UI connected to the Kubernetes API without CORS issues."""

import http.server
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = str(ROOT / "ui")


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/"):
            url = f"http://127.0.0.1:8000{self.path}"
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)


if __name__ == "__main__":
    port = 8088
    server = http.server.HTTPServer(("127.0.0.1", port), ProxyHandler)
    print(f"RAHBAR UI is live at: http://127.0.0.1:{port}")
    print("Proxying /api/ask directly to your live Kubernetes cluster on port 8000...")
    server.serve_forever()

