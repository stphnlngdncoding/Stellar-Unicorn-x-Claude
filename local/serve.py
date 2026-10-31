#!/usr/bin/env python3
"""Serve the local Unicorn Remote at http://localhost:8765 (no Cloudflare needed).

The page is served from this folder, and anything under /board/ is passed
straight through to the board's built-in web API on your Wi-Fi, so the page
never has to talk across networks itself. Standard library only.

    UNICORN_HOST=192.168.0.154 python3 serve.py          # then open http://localhost:8765
    python3 serve.py --host 192.168.0.154 --port 8765
"""
import argparse
import http.server
import os
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def make_handler(host):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=HERE, **k)

        def log_message(self, fmt, *args):
            pass                                   # keep the terminal quiet

        def _proxy(self, method):
            path = self.path[len("/board"):] or "/"
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else (b"" if method == "POST" else None)
            req = urllib.request.Request("http://%s%s" % (host, path), data=body, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    status, data, ctype = r.status, r.read(), r.headers.get("Content-Type", "text/plain")
            except urllib.error.HTTPError as e:
                status, data, ctype = e.code, e.read(), "text/plain"
            except (urllib.error.URLError, OSError) as e:
                status, ctype = 502, "text/plain"
                data = ("Can't reach the board at %s (%s)." % (host, getattr(e, "reason", e))).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/board/"):
                return self._proxy("GET")
            if self.path in ("/", ""):
                self.path = "/remote.html"
            return super().do_GET()

        def do_POST(self):
            if self.path.startswith("/board/"):
                return self._proxy("POST")
            self.send_error(404)

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=os.environ.get("UNICORN_HOST", "unicorn.local"),
                    help="the board's IP address (it scrolls it at startup)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    args = ap.parse_args()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.host))
    print("Unicorn Remote: http://localhost:%d  (board at %s, Ctrl-C to stop)" % (args.port, args.host))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
