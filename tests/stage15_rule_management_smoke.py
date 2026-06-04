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


# 功能验证：通过管理 API 增、删、改、查规则，并确认代理立即按新规则过滤。
HOST = "127.0.0.1"
PROXY_PORT = 18091
ADMIN_PORT = 18092
UPSTREAM_PORT = 19091
CONFIG_PATH = PROJECT_ROOT / "tests" / "stage15_rules_config.json"


class RuleDemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/lecture"):
            body = b"dynamic rule demo page contains lecture text"
        else:
            body = b"dynamic rule demo page contains classroom text"
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


def http_get(path):
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def post_json(path, payload):
    body = json.dumps(payload).encode("utf-8")
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


def request_line(method, url, host_header):
    return (
        f"{method} {url} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )


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
        "timeout_seconds": 5,
        "log_file": "tests/stage15_proxy.log",
        "blocked_log_file": "tests/stage15_blocked.log",
        "error_log_file": "tests/stage15_error.log",
    }
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), RuleDemoHandler)
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

    status, body = http_get("/api/rules")
    assert status == 200
    rules_payload = json.loads(body.decode("utf-8"))
    assert len(rules_payload["groups"]) >= 5

    # 正文关键词规则：新增后过滤，修改后新词生效，删除后恢复放行。
    baseline = proxy_request(request_line("GET", local_url, local_host))
    assert "dynamic rule demo page" in baseline

    status, payload = post_json(
        "/api/rules/add",
        {"rule_type": "blocked_content_keywords", "value": "classroom"},
    )
    assert status == 200 and payload["ok"] is True
    filtered = proxy_request(request_line("GET", local_url, local_host))
    assert "网页已被过滤" in filtered
    assert "blocked by keyword filter: classroom" in filtered

    status, payload = post_json(
        "/api/rules/update",
        {
            "rule_type": "blocked_content_keywords",
            "old_value": "classroom",
            "new_value": "lecture",
        },
    )
    assert status == 200 and payload["ok"] is True
    assert "lecture" in payload["values"]
    assert "classroom" not in payload["values"]

    classroom_allowed = proxy_request(request_line("GET", local_url, local_host))
    assert "dynamic rule demo page" in classroom_allowed
    lecture_filtered = proxy_request(
        request_line("GET", f"http://127.0.0.1:{UPSTREAM_PORT}/lecture.txt", local_host)
    )
    assert "网页已被过滤" in lecture_filtered
    assert "blocked by keyword filter: lecture" in lecture_filtered

    status, payload = post_json(
        "/api/rules/delete",
        {"rule_type": "blocked_content_keywords", "value": "lecture"},
    )
    assert status == 200 and payload["ok"] is True
    allowed_again = proxy_request(request_line("GET", local_url, local_host))
    assert "dynamic rule demo page" in allowed_again

    # URL 关键词规则：替换整组后按 URL 拦截，再替换为空后恢复访问。
    status, payload = post_json(
        "/api/rules/replace",
        {"rule_type": "blocked_url_keywords", "values": ["secret-path", "private"]},
    )
    assert status == 200 and payload["ok"] is True
    assert payload["values"] == ["secret-path", "private"]
    blocked_url = proxy_request(
        request_line("GET", f"http://127.0.0.1:{UPSTREAM_PORT}/secret-path", local_host)
    )
    assert "403 Forbidden" in blocked_url
    assert "url_keyword:secret-path" in blocked_url

    status, payload = post_json(
        "/api/rules/replace",
        {"rule_type": "blocked_url_keywords", "values": []},
    )
    assert status == 200 and payload["ok"] is True
    assert payload["values"] == []
    url_allowed = proxy_request(
        request_line("GET", f"http://127.0.0.1:{UPSTREAM_PORT}/secret-path", local_host)
    )
    assert "dynamic rule demo page" in url_allowed

    # 方法规则：新增 PATCH 后拦截，删除后不再由代理规则拦截。
    status, payload = post_json(
        "/api/rules/add",
        {"rule_type": "blocked_methods", "value": "patch"},
    )
    assert status == 200 and "PATCH" in payload["values"]
    blocked_method = proxy_request(request_line("PATCH", local_url, local_host))
    assert "403 Forbidden" in blocked_method
    assert "method_blacklist" in blocked_method

    status, payload = post_json(
        "/api/rules/delete",
        {"rule_type": "blocked_methods", "value": "PATCH"},
    )
    assert status == 200 and payload["ok"] is True
    method_allowed = proxy_request(request_line("PATCH", local_url, local_host))
    assert "method_blacklist" not in method_allowed

    # 域名黑名单规则：新增后无需真实解析域名，代理直接返回 403。
    status, payload = post_json(
        "/api/rules/add",
        {"rule_type": "blocked_domains", "value": "dynamic-block.test"},
    )
    assert status == 200 and payload["ok"] is True
    blocked_domain = proxy_request(
        request_line("GET", "http://dynamic-block.test/", "dynamic-block.test")
    )
    assert "403 Forbidden" in blocked_domain
    assert "domain_blacklist" in blocked_domain

    status, payload = post_json(
        "/api/rules/update",
        {
            "rule_type": "blocked_domains",
            "old_value": "dynamic-block.test",
            "new_value": "*dynamic*",
        },
    )
    assert status == 200 and payload["ok"] is True
    keyword_domain_blocked = proxy_request(
        request_line("GET", "http://www.dynamic-block.test/", "www.dynamic-block.test")
    )
    assert "403 Forbidden" in keyword_domain_blocked
    assert "domain_blacklist" in keyword_domain_blocked
    post_json(
        "/api/rules/delete",
        {"rule_type": "blocked_domains", "value": "*dynamic*"},
    )

    # 白名单规则：新增 allowed domain 后允许访问，删除后白名单模式会拦截。
    status, payload = post_json(
        "/api/rules/add",
        {"rule_type": "allowed_domains", "value": "127.0.0.1"},
    )
    assert status == 200 and payload["ok"] is True
    status, payload = post_json(
        "/api/settings/update",
        {"settings": {"mode": "whitelist"}},
    )
    assert status == 200 and payload["settings"]["mode"] == "whitelist"
    whitelist_allowed = proxy_request(request_line("GET", local_url, local_host))
    assert "dynamic rule demo page" in whitelist_allowed

    post_json(
        "/api/rules/delete",
        {"rule_type": "allowed_domains", "value": "127.0.0.1"},
    )
    whitelist_blocked = proxy_request(request_line("GET", local_url, local_host))
    assert "403 Forbidden" in whitelist_blocked
    assert "domain_not_in_whitelist" in whitelist_blocked

    # 最后确认规则和模式确实保存到了配置文件，重启后不会丢。
    post_json("/api/settings/update", {"settings": {"mode": "blacklist"}})
    saved_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert saved_config["mode"] == "blacklist"
    assert "classroom" not in saved_config["blocked_content_keywords"]
    assert "lecture" not in saved_config["blocked_content_keywords"]
    assert "secret-path" not in saved_config["blocked_url_keywords"]
    assert "PATCH" not in saved_config["blocked_methods"]
    assert "127.0.0.1" not in saved_config["allowed_domains"]

    print("stage15 rule management smoke test passed")

    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
