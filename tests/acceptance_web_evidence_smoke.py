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
from tests.acceptance_support import (
    BLOCKED_LOG,
    CHANGE_LOG,
    ERROR_LOG,
    EVIDENCE_CONFIG,
    PROXY_LOG,
    admin_request,
    assert_log_events,
    build_evidence_config,
    clear_evidence_files,
    proxy_request,
    write_evidence_config,
)


HOST = "127.0.0.1"
PROXY_PORT = 18201
ADMIN_PORT = 18202
UPSTREAM_PORT = 19201
TUNNEL_PORT = 19202


class EvidenceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/forbidden"):
            body = b"acceptance page contains evidence-forbidden keyword"
        else:
            body = f"acceptance upstream page path={self.path}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def tunnel_echo_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, TUNNEL_PORT))
    server.listen(1)
    try:
        connection, _ = server.accept()
        with connection:
            data = connection.recv(4096)
            connection.sendall(b"evidence-echo:" + data)
    finally:
        server.close()


def connect_request():
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                f"CONNECT {HOST}:{TUNNEL_PORT} HTTP/1.1\r\n"
                f"Host: {HOST}:{TUNNEL_PORT}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
        )
        response = client.recv(4096)
        assert b"200 Connection Established" in response
        client.sendall(b"hello")
        assert client.recv(4096) == b"evidence-echo:hello"


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def post_settings(settings):
    status, payload = admin_request(
        ADMIN_PORT,
        "POST",
        "/api/settings/update",
        {"settings": settings},
    )
    assert status == 200 and payload["ok"] is True
    return payload


def main():
    # Every run starts with empty evidence logs, so assertions never pass on stale data.
    clear_evidence_files(PROXY_LOG, BLOCKED_LOG, ERROR_LOG, CHANGE_LOG)
    config = build_evidence_config(PROXY_PORT, ADMIN_PORT)
    config.update(
        {
            "blocked_domains": ["blocked.evidence.test"],
            "blocked_url_keywords": ["evidence-private"],
            "blocked_content_keywords": ["evidence-forbidden"],
            "blocked_methods": ["DELETE"],
            "cache_enabled": True,
        }
    )
    write_evidence_config(config)

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), EvidenceHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    tunnel_thread = threading.Thread(target=tunnel_echo_server, daemon=True)
    tunnel_thread.start()

    state = proxy.RuntimeState(proxy.load_config(str(EVIDENCE_CONFIG)), str(EVIDENCE_CONFIG))
    admin_server = proxy.start_admin_server(HOST, ADMIN_PORT, state)
    threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    ).start()
    time.sleep(0.5)

    local_host = f"{HOST}:{UPSTREAM_PORT}"
    normal_url = f"http://{local_host}/normal"

    # Forwarding and cache: first request reaches upstream, second request is CACHE_HIT.
    assert "200 OK" in proxy_request(PROXY_PORT, "GET", normal_url, local_host)
    assert "200 OK" in proxy_request(PROXY_PORT, "GET", normal_url, local_host)

    assert "403 Forbidden" in proxy_request(
        PROXY_PORT,
        "GET",
        "http://blocked.evidence.test/",
        "blocked.evidence.test",
    )
    assert "url_keyword:evidence-private" in proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/evidence-private",
        local_host,
    )
    assert "method_blacklist" in proxy_request(
        PROXY_PORT,
        "DELETE",
        normal_url,
        local_host,
    )
    assert "blocked by keyword filter: evidence-forbidden" in proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/forbidden",
        local_host,
    )
    connect_request()

    # Authentication rejection must appear in the interception log.
    post_settings(
        {
            "proxy_auth_enabled": True,
            "proxy_auth_users": {"evidence": "pass"},
        }
    )
    assert "407 Proxy Authentication Required" in proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/auth",
        local_host,
    )
    assert "200 OK" in proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/auth-ok",
        local_host,
        {"Proxy-Authorization": basic_auth("evidence", "pass")},
    )

    # A limit of one means exactly the first authenticated request is allowed.
    post_settings(
        {
            "proxy_auth_enabled": False,
            "rate_limit_enabled": True,
            "rate_limit_per_minute": 1,
            "rate_limit_window_seconds": 60,
        }
    )
    status, payload = admin_request(ADMIN_PORT, "POST", "/api/rate/reset")
    assert status == 200 and payload["ok"] is True
    first_limited = proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/rate-first",
        local_host,
    )
    second_limited = proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/rate-second",
        local_host,
    )
    assert "200 OK" in first_limited
    assert "429 Too Many Requests" in second_limited
    post_settings({"rate_limit_enabled": False})

    # The frontend reads these exact APIs, so API assertions also prove UI-visible evidence.
    status, proxy_payload = admin_request(ADMIN_PORT, "GET", "/api/logs?kind=proxy&limit=200")
    assert status == 200
    assert_log_events(
        proxy_payload["logs"],
        [
            "ALLOW",
            "CACHE_MISS",
            "CACHE_HIT",
            "BLOCK",
            "FILTER",
            "CONNECT",
            "AUTH_REQUIRED",
            "RATE_ALLOW",
            "RATE_LIMIT",
        ],
    )
    status, blocked_payload = admin_request(ADMIN_PORT, "GET", "/api/logs?kind=blocked&limit=200")
    assert status == 200
    assert_log_events(blocked_payload["logs"], ["BLOCK", "FILTER", "AUTH_REQUIRED", "RATE_LIMIT"])
    status, query_payload = admin_request(
        ADMIN_PORT,
        "GET",
        "/api/logs/query?kind=blocked&event=BLOCK&search=domain_blacklist&limit=20",
    )
    assert status == 200 and query_payload["matched"] == 1
    assert query_payload["entries"][0]["fields"]["host"] == "blocked.evidence.test"
    status, tunnel_payload = admin_request(
        ADMIN_PORT,
        "GET",
        "/api/logs/query?kind=proxy&event=CONNECT&limit=20",
    )
    assert status == 200 and tunnel_payload["matched"] == 1
    # The ordinary dashboard uses this fixed profile query after the batch exits.
    status, evidence_query = admin_request(
        ADMIN_PORT,
        "GET",
        "/api/logs/query?profile=web&kind=blocked&event=BLOCK&limit=20",
    )
    assert status == 200 and evidence_query["profile"] == "web"
    assert evidence_query["matched"] >= 1
    status, profiles_payload = admin_request(ADMIN_PORT, "GET", "/api/evidence/profiles")
    web_profile = next(item for item in profiles_payload["profiles"] if item["name"] == "web")
    assert status == 200 and web_profile["blocked_log_count"] >= 1
    status, frontend = admin_request(ADMIN_PORT, "GET", "/")
    assert status == 200 and b"/logs.html?profile=web" in frontend

    print("acceptance web evidence smoke test passed")
    print(f"evidence config: {EVIDENCE_CONFIG}")
    print(f"proxy log events verified: {len(proxy_payload['logs'])}")
    print(f"blocked log events verified: {len(blocked_payload['logs'])}")

    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
