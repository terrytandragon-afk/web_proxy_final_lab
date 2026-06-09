from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import socket
import sys
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18121
ADMIN_PORT = 18122
UPSTREAM_PORT = 19121
CONFIG_PATH = PROJECT_ROOT / "tests" / "stage18_client_ip_config.json"


class ClientPolicyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"client IP policy upstream page"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def proxy_get():
    """Send one request from the local client so runtime IP policy is exercised."""
    target = f"http://{HOST}:{UPSTREAM_PORT}/client-policy"
    request = (
        f"GET {target} HTTP/1.1\r\n"
        f"Host: {HOST}:{UPSTREAM_PORT}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(request)
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def admin_request(method, path, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"} if body else {}
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    response_body = response.read()
    connection.close()
    return response.status, json.loads(response_body.decode("utf-8"))


def post(path, payload):
    status, result = admin_request("POST", path, payload)
    assert status == 200 and result["ok"] is True
    return result


def main():
    # Every run owns fresh evidence so exact log-count assertions stay repeatable.
    for name in (
        "stage18_proxy.log",
        "stage18_blocked.log",
        "stage18_error.log",
        "stage18_changes.jsonl",
    ):
        path = PROJECT_ROOT / "tests" / name
        if path.exists():
            path.unlink()

    # Direct matcher checks cover addresses that cannot be used as the local test client.
    assert proxy.client_ip_matches("192.168.1.20", ["192.168.1.0/24"])
    assert not proxy.client_ip_matches("192.168.2.20", ["192.168.1.0/24"])
    assert proxy.client_ip_matches("2001:db8::1", ["2001:db8::/32"])
    assert proxy.check_client_access_policy(
        "10.0.0.8",
        {"blocked_client_ips": [], "allowed_client_ips": ["10.0.0.0/8"]},
    ) == (True, "allow")

    config = {
        "listen_host": HOST,
        "listen_port": PROXY_PORT,
        "admin_host": HOST,
        "admin_port": ADMIN_PORT,
        "mode": "blacklist",
        "blocked_domains": [],
        "allowed_domains": [],
        "blocked_client_ips": [],
        "allowed_client_ips": [],
        "blocked_url_keywords": [],
        "blocked_content_keywords": [],
        "blocked_methods": [],
        "cache_enabled": False,
        "timeout_seconds": 5,
        "log_file": "tests/stage18_proxy.log",
        "blocked_log_file": "tests/stage18_blocked.log",
        "error_log_file": "tests/stage18_error.log",
        "change_log_file": "tests/stage18_changes.jsonl",
    }
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), ClientPolicyHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    state = proxy.RuntimeState(proxy.load_config(str(CONFIG_PATH)), str(CONFIG_PATH))
    admin_server = proxy.start_admin_server(HOST, ADMIN_PORT, state)
    threading.Thread(target=proxy.start_server, args=(HOST, PROXY_PORT, state), daemon=True).start()
    time.sleep(0.5)

    assert "200 OK" in proxy_get()

    # CIDR normalization and blacklist enforcement take effect without a restart.
    result = post(
        "/api/rules/add",
        {"rule_type": "blocked_client_ips", "value": "127.0.0.99/24"},
    )
    assert result["value"] == "127.0.0.0/24"
    assert "client_ip_blacklist" in proxy_get()

    # Moving the blocked network away immediately restores this client.
    post(
        "/api/rules/update",
        {
            "rule_type": "blocked_client_ips",
            "old_value": "127.0.0.0/24",
            "new_value": "10.0.0.0/8",
        },
    )
    assert "200 OK" in proxy_get()
    post("/api/rules/delete", {"rule_type": "blocked_client_ips", "value": "10.0.0.0/8"})

    # A non-empty allowlist rejects unmatched clients, then permits a matching host.
    post("/api/rules/add", {"rule_type": "allowed_client_ips", "value": "10.0.0.0/8"})
    assert "client_ip_not_allowed" in proxy_get()
    post(
        "/api/rules/update",
        {
            "rule_type": "allowed_client_ips",
            "old_value": "10.0.0.0/8",
            "new_value": HOST,
        },
    )
    assert "200 OK" in proxy_get()
    post("/api/rules/delete", {"rule_type": "allowed_client_ips", "value": HOST})

    status, invalid = admin_request(
        "POST",
        "/api/rules/add",
        {"rule_type": "blocked_client_ips", "value": "not-an-ip"},
    )
    assert status == 400 and invalid["ok"] is False

    status, stats = admin_request("GET", "/api/stats")
    assert status == 200 and stats["stats"]["blocked_client"] == 2
    status, logs = admin_request(
        "GET",
        "/api/logs/query?kind=blocked&event=BLOCK&search=client_ip_&limit=20",
    )
    assert status == 200 and logs["matched"] == 2
    assert {entry["fields"]["reason"] for entry in logs["entries"]} == {
        "client_ip_blacklist",
        "client_ip_not_allowed",
    }

    saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved["blocked_client_ips"] == []
    assert saved["allowed_client_ips"] == []

    print("stage18 client IP policy smoke test passed")
    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
