from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
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


# 功能验证：代理运行中通过后端 API 热更新白名单、代理认证和访问频率设置。
HOST = "127.0.0.1"
PROXY_PORT = 18111
ADMIN_PORT = 18112
UPSTREAM_PORT = 19111
CONFIG_PATH = PROJECT_ROOT / "tests" / "stage17_runtime_settings_config.json"


class RuntimeDemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"runtime settings demo page"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def post_json(path, payload=None):
    body = json.dumps(payload or {}).encode("utf-8")
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request(
        "POST",
        path,
        body=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    response = connection.getresponse()
    response_body = response.read()
    connection.close()
    return response.status, json.loads(response_body.decode("utf-8"))


def proxy_request(url, host_header, extra_headers=None):
    headers = [
        f"GET {url} HTTP/1.1",
        f"Host: {host_header}",
        "Connection: close",
    ]
    for name, value in (extra_headers or {}).items():
        headers.append(f"{name}: {value}")
    request = ("\r\n".join(headers) + "\r\n\r\n").encode("ascii")

    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(request)
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def basic_auth(username, password):
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def main():
    config = {
        "listen_host": HOST,
        "listen_port": PROXY_PORT,
        "admin_host": HOST,
        "admin_port": ADMIN_PORT,
        "mode": "blacklist",
        "blocked_domains": [],
        "allowed_domains": [],
        "blocked_url_keywords": [],
        "blocked_content_keywords": [],
        "blocked_methods": [],
        "cache_enabled": False,
        "proxy_auth_enabled": False,
        "proxy_auth_users": {},
        "rate_limit_enabled": False,
        "rate_limit_per_minute": 60,
        "rate_limit_window_seconds": 60,
        "timeout_seconds": 5,
        "log_file": "tests/stage17_proxy.log",
        "blocked_log_file": "tests/stage17_blocked.log",
        "error_log_file": "tests/stage17_error.log",
    }
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), RuntimeDemoHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    state = proxy.RuntimeState(proxy.load_config(str(CONFIG_PATH)), str(CONFIG_PATH))
    admin_server = proxy.start_admin_server(HOST, ADMIN_PORT, state)
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    local_url = f"http://127.0.0.1:{UPSTREAM_PORT}/index.txt"
    local_host = f"127.0.0.1:{UPSTREAM_PORT}"

    baseline = proxy_request(local_url, local_host)
    assert "runtime settings demo page" in baseline

    # 白名单模式运行中生效：添加 allowed domain 后切换 whitelist，删除后立刻拦截。
    status, payload = post_json(
        "/api/rules/add",
        {"rule_type": "allowed_domains", "value": "127.0.0.1"},
    )
    assert status == 200 and payload["ok"] is True
    status, payload = post_json("/api/settings/update", {"settings": {"mode": "whitelist"}})
    assert status == 200 and payload["settings"]["mode"] == "whitelist"
    whitelist_allowed = proxy_request(local_url, local_host)
    assert "runtime settings demo page" in whitelist_allowed
    post_json("/api/rules/delete", {"rule_type": "allowed_domains", "value": "127.0.0.1"})
    whitelist_blocked = proxy_request(local_url, local_host)
    assert "domain_not_in_whitelist" in whitelist_blocked
    post_json("/api/settings/update", {"settings": {"mode": "blacklist"}})

    # 代理认证运行中生效：设置用户并启用后，无认证 407，有认证放行。
    status, payload = post_json(
        "/api/settings/update",
        {
            "settings": {
                "proxy_auth_enabled": True,
                "proxy_auth_users": {"alice": "pw123"},
            }
        },
    )
    assert status == 200 and payload["settings"]["proxy_auth_enabled"] is True
    no_auth = proxy_request(local_url, local_host)
    assert "407 Proxy Authentication Required" in no_auth
    with_auth = proxy_request(
        local_url,
        local_host,
        {"Proxy-Authorization": basic_auth("alice", "pw123")},
    )
    assert "runtime settings demo page" in with_auth
    post_json("/api/settings/update", {"settings": {"proxy_auth_enabled": False}})

    # 访问频率运行中生效：设置 1 次/分钟后第二次请求 429，调大后立刻放行。
    status, payload = post_json(
        "/api/settings/update",
        {
            "settings": {
                "rate_limit_enabled": True,
                "rate_limit_per_minute": 1,
                "rate_limit_window_seconds": 60,
            }
        },
    )
    assert status == 200 and payload["settings"]["rate_limit_enabled"] is True
    first = proxy_request(local_url, local_host)
    second = proxy_request(local_url, local_host)
    assert "runtime settings demo page" in first
    assert "429 Too Many Requests" in second
    status, payload = post_json(
        "/api/settings/update",
        {"settings": {"rate_limit_per_minute": 5}},
    )
    assert status == 200 and payload["settings"]["rate_limit_per_minute"] == 5
    status, payload = post_json("/api/rate/reset")
    assert status == 200 and payload["ok"] is True
    after_update = proxy_request(local_url, local_host)
    assert "runtime settings demo page" in after_update

    saved_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved_config["mode"] == "blacklist"
    assert saved_config["proxy_auth_users"] == {"alice": "pw123"}
    assert saved_config["rate_limit_enabled"] is True
    assert saved_config["rate_limit_per_minute"] == 5
    assert saved_config["rate_limit_window_seconds"] == 60

    print("stage17 runtime settings smoke test passed")

    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
