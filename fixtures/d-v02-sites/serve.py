"""在本机启动四个独立的校园服务样本，只提供页面运行所需的公开文件。"""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CASES = ('w01', 'w02', 'w03', 'w04')
ASSETS = {
    '/shared/common.js': ('common.js', 'text/javascript'),
    '/shared/style.css': ('style.css', 'text/css'),
}
for case in CASES:
    ASSETS[f'/{case}/'] = ('index.html', 'text/html')
    ASSETS[f'/{case}/app.js'] = (f'{case}/app.js', 'text/javascript')


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, quiet=False, **kwargs):
        self.quiet = quiet
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        if not self.quiet:
            super().log_message(fmt, *args)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path not in ASSETS:
            self.send_error(404)
            return
        name, mime = ASSETS[path]
        data = (ROOT / 'public' / name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', f'{mime}; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)


def make_server(port=0, quiet=False):
    return ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, quiet=quiet))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4311)
    args = parser.parse_args()
    with make_server(args.port) as server:
        for case in CASES:
            print(f'http://127.0.0.1:{server.server_port}/{case}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
