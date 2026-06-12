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
PROXY_PORT = 18086
UPSTREAM_PORT = 19086
UPSTREAM_HITS = 0


class CacheTestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global UPSTREAM_HITS
        UPSTREAM_HITS += 1
        body = f"cacheable response hit={UPSTREAM_HITS}".encode("utf-8")
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
                f"GET http://127.0.0.1:{UPSTREAM_PORT}/cache.txt HTTP/1.1\r\n"
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
    return b"".join(chunks).decode("utf-8", errors="replace")


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), CacheTestHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "blacklist",
        "blocked_domains": [],
        "blocked_content_keywords": [],
        "cache_enabled": True,
        "cache_ttl_seconds": 60,
        "cache_max_items": 10,
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

    assert "cacheable response hit=1" in first
    assert "cacheable response hit=1" in second
    assert UPSTREAM_HITS == 1

    stats = state.snapshot()["stats"]
    assert stats["cache_misses"] == 1
    assert stats["cache_hits"] == 1
    assert stats["cache_entries"] == 1

    # 新增正文规则必须清理旧缓存，否则浏览器会继续看到规则添加前的页面。
    result = state.add_list_rule("blocked_content_keywords", "cacheable response")
    assert result["changed"] is True
    assert result["cache_cleared"] == 1
    filtered = request_once()
    assert "content_keyword:cacheable response" in filtered
    assert "cacheable response hit=2" not in filtered
    assert UPSTREAM_HITS == 2

    print("stage10 cache smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
