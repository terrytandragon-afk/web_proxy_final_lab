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
PROXY_PORT = 18087
UPSTREAM_PORT = 19087


class WhitelistHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"whitelist allowed page"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def request_through_proxy(raw_request):
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(raw_request.encode("ascii"))
        while True:
            response = client.recv(4096)
            if not response:
                break
            chunks.append(response)
    return b"".join(chunks).decode("iso-8859-1", errors="replace")


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), WhitelistHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "whitelist",
        "allowed_domains": ["127.0.0.1"],
        "blocked_domains": [],
        "blocked_content_keywords": [],
        "cache_enabled": False,
    }
    state = proxy.RuntimeState(config)
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    allowed_response = request_through_proxy(
        f"GET http://127.0.0.1:{UPSTREAM_PORT}/ HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    assert "200 OK" in allowed_response
    assert "whitelist allowed page" in allowed_response

    blocked_response = request_through_proxy(
        "GET http://not-allowed.test/ HTTP/1.1\r\n"
        "Host: not-allowed.test\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    assert "403 Forbidden" in blocked_response
    assert "domain_not_in_whitelist" in blocked_response

    stats = state.snapshot()["stats"]
    assert stats["allowed_requests"] == 1
    assert stats["blocked_domain"] == 1

    print("stage11 whitelist smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()

