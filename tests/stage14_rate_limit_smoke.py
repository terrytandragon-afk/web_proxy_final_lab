from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


# 功能验证：访问频率限制。超过每分钟请求次数后返回 429。
HOST = "127.0.0.1"
PROXY_PORT = 18092
UPSTREAM_PORT = 19092


class RateLimitHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"rate limit allowed page"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def request_once():
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                f"GET http://127.0.0.1:{UPSTREAM_PORT}/ HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
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


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), RateLimitHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "blacklist",
        "blocked_domains": [],
        "blocked_content_keywords": [],
        "cache_enabled": False,
        "rate_limit_enabled": True,
        "rate_limit_per_minute": 1,
    }
    state = proxy.RuntimeState(config)
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    first = request_once()
    second = request_once()

    assert "200 OK" in first
    assert "rate limit allowed page" in first
    assert "429 Too Many Requests" in second

    stats = state.snapshot()["stats"]
    assert stats["allowed_requests"] == 1
    assert stats["rate_limited"] == 1

    print("stage14 rate limit smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
