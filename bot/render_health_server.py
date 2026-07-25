import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class RenderHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "service": "linkedin-autoposter"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_render_health_server():
    port = os.getenv("PORT")
    if not port:
        return None

    server = ThreadingHTTPServer(("0.0.0.0", int(port)), RenderHealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Render health server listening on port {port}")
    return server
