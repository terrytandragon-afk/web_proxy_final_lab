import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18085
UPSTREAM_PORT = 19085


def echo_once_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, UPSTREAM_PORT))
    server.listen(1)
    try:
        connection, _ = server.accept()
        with connection:
            data = connection.recv(4096)
            connection.sendall(b"echo:" + data)
    finally:
        server.close()


def recv_until(sock, marker):
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def main():
    upstream_thread = threading.Thread(target=echo_once_server, daemon=True)
    upstream_thread.start()

    config = {
        "mode": "blacklist",
        "blocked_domains": ["blocked.test"],
        "timeout_seconds": 5,
    }
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, config),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                f"CONNECT 127.0.0.1:{UPSTREAM_PORT} HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
        )
        response = recv_until(client, b"\r\n\r\n")
        assert b"200 Connection Established" in response
        client.sendall(b"hello-through-tunnel")
        echoed = client.recv(4096)
        assert echoed == b"echo:hello-through-tunnel"

    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                "CONNECT blocked.test:443 HTTP/1.1\r\n"
                "Host: blocked.test:443\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
        )
        response = client.recv(4096).decode("iso-8859-1", errors="replace")
        assert "403 Forbidden" in response
        assert "domain_blacklist" in response

    print("stage9 connect smoke test passed")


if __name__ == "__main__":
    main()
