from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18083
UPSTREAM_PORT = 19083


class KeywordHandler(BaseHTTPRequestHandler):
    # 模拟 NeverSSL 一类发送完整响应后仍保持 TCP 连接的 HTTP/1.1 网站。
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        body = b"<html><body>This page contains forbidden content.</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        time.sleep(2)

    def log_message(self, format, *args):
        return


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), KeywordHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "blacklist",
        "blocked_domains": [],
        "blocked_content_keywords": ["forbidden"],
        "timeout_seconds": 1,
    }
    server_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, config),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)

    request = (
        f"GET http://127.0.0.1:{UPSTREAM_PORT}/forbidden.html HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
        "User-Agent: stage6-smoke-test\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")

    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(request)
        while True:
            response = client.recv(4096)
            if not response:
                break
            chunks.append(response)

    text = b"".join(chunks).decode("utf-8", errors="replace")
    assert "403 Forbidden" in text
    assert "网页已被过滤" in text
    assert "blocked by keyword filter: forbidden" in text
    assert "content_keyword:forbidden" in text
    assert "请求已被 Web 代理拦截" in text
    assert "<details open>" in text
    assert "This page contains forbidden content" not in text
    print("stage6 smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
