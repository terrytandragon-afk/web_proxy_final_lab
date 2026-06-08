from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


# 功能验证：通过 tools/rule_cli.py 命令行工具增、删、改、替换规则组。
HOST = "127.0.0.1"
PROXY_PORT = 18101
ADMIN_PORT = 18102
UPSTREAM_PORT = 19101
CONFIG_PATH = PROJECT_ROOT / "tests" / "stage16_cli_config.json"


class CliDemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/lecture"):
            body = b"command line rule demo contains lecture text"
        else:
            body = b"command line rule demo contains classroom text"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def proxy_request(raw_request):
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(raw_request.encode("ascii"))
        while True:
            response = client.recv(4096)
            if not response:
                break
            chunks.append(response)
    return b"".join(chunks).decode("utf-8", errors="replace")


def request_line(method, url, host_header):
    return (
        f"{method} {url} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )


def run_cli(*args):
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "rule_cli.py"),
        "--admin-host",
        HOST,
        "--admin-port",
        str(ADMIN_PORT),
        *args,
    ]
    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr)
        raise AssertionError(f"rule_cli failed: {' '.join(args)}")
    return json.loads(completed.stdout)


def main():
    for log_name in ("stage16_proxy.log", "stage16_blocked.log", "stage16_error.log"):
        (PROJECT_ROOT / "tests" / log_name).write_text("", encoding="utf-8")

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
        "timeout_seconds": 5,
        "log_file": "tests/stage16_proxy.log",
        "blocked_log_file": "tests/stage16_blocked.log",
        "error_log_file": "tests/stage16_error.log",
    }
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), CliDemoHandler)
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
    lecture_url = f"http://127.0.0.1:{UPSTREAM_PORT}/lecture.txt"
    private_url = f"http://127.0.0.1:{UPSTREAM_PORT}/private/page.html"
    local_host = f"127.0.0.1:{UPSTREAM_PORT}"

    listed = run_cli("list")
    assert any(group["type"] == "blocked_content_keywords" for group in listed["groups"])

    added = run_cli("add", "blocked_content_keywords", "classroom")
    assert "classroom" in added["values"]
    classroom_filtered = proxy_request(request_line("GET", local_url, local_host))
    assert "blocked by keyword filter: classroom" in classroom_filtered

    updated = run_cli("update", "blocked_content_keywords", "classroom", "lecture")
    assert "lecture" in updated["values"]
    classroom_allowed = proxy_request(request_line("GET", local_url, local_host))
    assert "command line rule demo contains classroom text" in classroom_allowed
    lecture_filtered = proxy_request(request_line("GET", lecture_url, local_host))
    assert "blocked by keyword filter: lecture" in lecture_filtered

    deleted = run_cli("delete", "blocked_content_keywords", "lecture")
    assert "lecture" not in deleted["values"]
    lecture_allowed = proxy_request(request_line("GET", lecture_url, local_host))
    assert "command line rule demo contains lecture text" in lecture_allowed

    replaced = run_cli("replace", "blocked_url_keywords", "private", "exam")
    assert replaced["values"] == ["private", "exam"]
    private_blocked = proxy_request(request_line("GET", private_url, local_host))
    assert "url_keyword:private" in private_blocked

    cleared = run_cli("replace", "blocked_url_keywords")
    assert cleared["values"] == []
    private_allowed = proxy_request(request_line("GET", private_url, local_host))
    assert "command line rule demo" in private_allowed

    domain_added = run_cli("add", "blocked_domains", "cli-block.test")
    assert "cli-block.test" in domain_added["values"]
    domain_blocked = proxy_request(
        request_line("GET", "http://cli-block.test/", "cli-block.test")
    )
    assert "domain_blacklist" in domain_blocked
    domain_updated = run_cli("update", "blocked_domains", "cli-block.test", "*cli*")
    assert "*cli*" in domain_updated["values"]
    domain_keyword_blocked = proxy_request(
        request_line("GET", "http://www.cli-block.test/", "www.cli-block.test")
    )
    assert "domain_blacklist" in domain_keyword_blocked
    run_cli("delete", "blocked_domains", "*cli*")

    run_cli("add", "allowed_domains", "127.0.0.1")
    mode_changed = run_cli("set", "mode", "whitelist")
    assert mode_changed["settings"]["mode"] == "whitelist"
    whitelist_allowed = proxy_request(request_line("GET", local_url, local_host))
    assert "command line rule demo" in whitelist_allowed
    run_cli("delete", "allowed_domains", "127.0.0.1")
    whitelist_blocked = proxy_request(request_line("GET", local_url, local_host))
    assert "domain_not_in_whitelist" in whitelist_blocked
    run_cli("set", "mode", "blacklist")

    changes = run_cli("changes", "--limit", "30")
    assert any(item["action"] == "add" for item in changes["changes"])
    assert any(item["action"] == "settings" for item in changes["changes"])

    current_config = run_cli("config")
    assert "config" in current_config

    auth_user = run_cli("auth-user", "cliuser", "clipass")
    assert auth_user["settings"]["proxy_auth_users"]["cliuser"] == "clipass"
    auth_deleted = run_cli("auth-delete", "cliuser")
    assert "cliuser" not in auth_deleted["settings"]["proxy_auth_users"]

    rate_enabled = run_cli("set", "rate_limit_enabled", "true")
    assert rate_enabled["settings"]["rate_limit_enabled"] is True
    rate_count = run_cli("set", "rate_limit_per_minute", "2")
    assert rate_count["settings"]["rate_limit_per_minute"] == 2
    rate_window = run_cli("set", "rate_limit_window_seconds", "60")
    assert rate_window["settings"]["rate_limit_window_seconds"] == 60
    rate_reset = run_cli("rate-reset")
    assert rate_reset["ok"] is True
    run_cli("set", "rate_limit_enabled", "false")

    queried_logs = run_cli(
        "log-query",
        "--kind",
        "blocked",
        "--event",
        "BLOCK",
        "--search",
        "domain_blacklist",
        "--limit",
        "20",
    )
    assert queried_logs["matched"] == 2
    assert all(entry["event"] == "BLOCK" for entry in queried_logs["entries"])

    saved_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved_config["mode"] == "blacklist"
    assert saved_config["blocked_content_keywords"] == []
    assert saved_config["blocked_url_keywords"] == []
    assert saved_config["blocked_domains"] == []

    print("stage16 rule cli smoke test passed")

    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
