import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18082


def main():
    config = {
        "mode": "blacklist",
        "blocked_domains": ["blocked.test"],
    }
    server_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, config),
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)

    request = (
        "GET http://blocked.test/ HTTP/1.1\r\n"
        "Host: blocked.test\r\n"
        "User-Agent: stage5-smoke-test\r\n"
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

    text = b"".join(chunks).decode("iso-8859-1", errors="replace")
    assert "403 Forbidden" in text
    assert "domain_blacklist" in text
    assert "<details open>" in text
    print("stage5 smoke test passed")


if __name__ == "__main__":
    main()
