from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


# 功能验证：代理认证。未认证/错误认证返回 407，正确认证后允许访问。
HOST = "127.0.0.1"
PROXY_PORT = 18091
UPSTREAM_PORT = 19091


class AuthTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"auth allowed page"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def request_through_proxy(extra_header=""):
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                f"GET http://127.0.0.1:{UPSTREAM_PORT}/ HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
                f"{extra_header}"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
        )
        while True:
            data = client.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("iso-8859-1", errors="replace")


def basic_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Proxy-Authorization: Basic {token}\r\n"


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), AuthTestHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "blacklist",
        "blocked_domains": [],
        "blocked_content_keywords": [],
        "cache_enabled": False,
        "proxy_auth_enabled": True,
        "proxy_auth_users": {"student": "123456"},
    }
    state = proxy.RuntimeState(config)
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    no_auth = request_through_proxy()
    assert "407 Proxy Authentication Required" in no_auth

    wrong_auth = request_through_proxy(basic_header("student", "wrong"))
    assert "407 Proxy Authentication Required" in wrong_auth

    correct_auth = request_through_proxy(basic_header("student", "123456"))
    assert "200 OK" in correct_auth
    assert "auth allowed page" in correct_auth

    stats = state.snapshot()["stats"]
    assert stats["auth_required"] == 2
    assert stats["allowed_requests"] == 1

    print("stage13 auth smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
