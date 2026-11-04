"""给本地工作台提供两个 H05 版本，只开放样本页面。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
ROUTES = {"/v1/": ROOT / "A/打开界面.html", "/v2/": ROOT / "B/打开界面.html"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        file = ROUTES.get(urlsplit(self.path).path)
        if file is None:
            self.send_error(404)
            return
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4315)
    port = parser.parse_args().port
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        for path in ROUTES:
            print(f"http://127.0.0.1:{server.server_port}{path}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
