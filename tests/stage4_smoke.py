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
PROXY_PORT = 18081
UPSTREAM_PORT = 19081


class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"upstream page through proxy"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), TestHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    server_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)

    request = (
        f"GET http://127.0.0.1:{UPSTREAM_PORT}/ HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
        "User-Agent: stage4-smoke-test\r\n"
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

    response = b"".join(chunks)
    text = response.decode("iso-8859-1", errors="replace")
    assert "200 OK" in text
    assert "upstream page through proxy" in text
    print("stage4 smoke test passed")

    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
