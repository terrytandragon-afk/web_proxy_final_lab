import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18084


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
    config = {
        "mode": "blacklist",
        "blocked_domains": [],
        "blocked_url_keywords": ["game"],
        "blocked_methods": ["DELETE"],
    }
    server_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, config),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)

    url_response = request_through_proxy(
        "GET http://127.0.0.1:19084/game/index.html HTTP/1.1\r\n"
        "Host: 127.0.0.1:19084\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    assert "403 Forbidden" in url_response
    assert "url_keyword:game" in url_response
    assert "<details open>" in url_response

    method_response = request_through_proxy(
        "DELETE http://127.0.0.1:19084/ HTTP/1.1\r\n"
        "Host: 127.0.0.1:19084\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    assert "403 Forbidden" in method_response
    assert "method_blacklist" in method_response
    assert "<details open>" in method_response

    print("stage7 policy smoke test passed")


if __name__ == "__main__":
    main()
