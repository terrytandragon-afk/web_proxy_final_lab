import http.client
import json
import socket
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "tests" / "evidence"
EVIDENCE_CONFIG = EVIDENCE_DIR / "acceptance_config.json"
PROXY_LOG = EVIDENCE_DIR / "proxy.log"
BLOCKED_LOG = EVIDENCE_DIR / "blocked.log"
ERROR_LOG = EVIDENCE_DIR / "error.log"
CHANGE_LOG = EVIDENCE_DIR / "changes.jsonl"


def build_evidence_config(proxy_port, admin_port):
    """Return a deterministic baseline used only by acceptance tests."""
    return {
        "listen_host": "127.0.0.1",
        "listen_port": proxy_port,
        "admin_host": "127.0.0.1",
        "admin_port": admin_port,
        "mode": "blacklist",
        "blocked_domains": [],
        "allowed_domains": [],
        "blocked_url_keywords": [],
        "blocked_content_keywords": [],
        "blocked_methods": [],
        "cache_enabled": False,
        "cache_ttl_seconds": 60,
        "cache_max_items": 20,
        "proxy_auth_enabled": False,
        "proxy_auth_users": {},
        "rate_limit_enabled": False,
        "rate_limit_per_minute": 60,
        "rate_limit_window_seconds": 60,
        "timeout_seconds": 5,
        "log_file": "tests/evidence/proxy.log",
        "blocked_log_file": "tests/evidence/blocked.log",
        "error_log_file": "tests/evidence/error.log",
        "change_log_file": "tests/evidence/changes.jsonl",
    }


def write_evidence_config(config):
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_CONFIG.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_evidence_files(*paths):
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        path.write_text("", encoding="utf-8")


def admin_request(port, method, path, payload=None):
    """Call one admin API endpoint and return status, decoded JSON or raw bytes."""
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    response_body = response.read()
    connection.close()
    if response.headers.get_content_type() == "application/json":
        return response.status, json.loads(response_body.decode("utf-8"))
    return response.status, response_body


def proxy_request(proxy_port, method, url, host_header, extra_headers=None):
    """Send one raw HTTP proxy request so the test observes the actual wire response."""
    lines = [
        f"{method} {url} HTTP/1.1",
        f"Host: {host_header}",
        "Connection: close",
    ]
    for name, value in (extra_headers or {}).items():
        lines.append(f"{name}: {value}")
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")

    chunks = []
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=5) as client:
        client.sendall(request)
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def assert_log_events(lines, event_names):
    """Assert every expected event is visible through the same lines used by the UI."""
    missing = [name for name in event_names if not any(name in line for line in lines)]
    assert not missing, f"missing log events: {missing}"

