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


# 功能验证：管理前端和 API。产生代理流量后检查页面、配置、统计和日志接口。
HOST = "127.0.0.1"
PROXY_PORT = 18089
ADMIN_PORT = 18090
UPSTREAM_PORT = 19089


class FrontendDemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"frontend display demo page"
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
    return b"".join(chunks)


def admin_get(path):
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def main():
    for log_name in (
        "stage12_proxy.log",
        "stage12_blocked.log",
        "stage12_error.log",
    ):
        log_path = PROJECT_ROOT / "tests" / log_name
        if log_path.exists():
            log_path.unlink()

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), FrontendDemoHandler)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()

    config = {
        "listen_host": HOST,
        "listen_port": PROXY_PORT,
        "admin_host": HOST,
        "admin_port": ADMIN_PORT,
        "mode": "blacklist",
        "blocked_domains": ["blocked.test"],
        "blocked_url_keywords": ["game"],
        "blocked_methods": ["DELETE"],
        "blocked_content_keywords": [],
        "cache_enabled": True,
        "cache_ttl_seconds": 60,
        "cache_max_items": 10,
        "timeout_seconds": 5,
        "log_file": "tests/stage12_proxy.log",
        "blocked_log_file": "tests/stage12_blocked.log",
        "error_log_file": "tests/stage12_error.log",
    }
    state = proxy.RuntimeState(config)
    admin_server = proxy.start_admin_server(HOST, ADMIN_PORT, state)
    proxy_thread = threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    )
    proxy_thread.start()
    time.sleep(0.5)

    normal_request = (
        f"GET http://127.0.0.1:{UPSTREAM_PORT}/demo.txt HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{UPSTREAM_PORT}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    first = proxy_request(normal_request).decode("utf-8", errors="replace")
    second = proxy_request(normal_request).decode("utf-8", errors="replace")
    assert "frontend display demo page" in first
    assert "frontend display demo page" in second

    blocked = proxy_request(
        "GET http://blocked.test/ HTTP/1.1\r\n"
        "Host: blocked.test\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).decode("iso-8859-1", errors="replace")
    assert "403 Forbidden" in blocked

    status, html = admin_get("/")
    assert status == 200
    html_text = html.decode("utf-8", errors="replace")
    assert "Web 代理服务器管理台" in html_text
    assert "过滤规则管理" in html_text
    assert "保存设置" in html_text
    assert "添加" in html_text
    assert "修改" in html_text
    assert "删除" in html_text
    assert "替换整组" in html_text
    assert "规则变更回显" in html_text
    assert "缓存命中" in html_text
    assert "HTTPS 隧道" in html_text
    assert "认证拦截" in html_text
    assert "限流拦截" in html_text
    assert "客户端拦截" in html_text
    assert "清空缓存" in html_text
    assert "重置统计" in html_text
    assert "清空日志" in html_text
    assert "/logs.html?" in html_text

    status, body = admin_get("/api/config")
    assert status == 200
    config_payload = json.loads(body.decode("utf-8"))
    assert config_payload["config"]["cache_enabled"] is True
    assert config_payload["config"]["blocked_domains"] == ["blocked.test"]

    status, body = admin_get("/api/rules")
    assert status == 200
    rules_payload = json.loads(body.decode("utf-8"))
    assert any(group["type"] == "blocked_domains" for group in rules_payload["groups"])
    assert any(group["type"] == "blocked_client_ips" for group in rules_payload["groups"])
    assert any(group["type"] == "blocked_content_keywords" for group in rules_payload["groups"])

    status, body = admin_get("/api/stats")
    assert status == 200
    stats_payload = json.loads(body.decode("utf-8"))
    stats = stats_payload["stats"]
    assert stats["total_requests"] >= 3
    assert stats["allowed_requests"] >= 2
    assert stats["blocked_domain"] >= 1
    assert stats["cache_hits"] >= 1
    assert stats["cache_misses"] >= 1
    assert stats["cache_entries"] >= 1

    status, body = admin_get("/api/logs?kind=proxy&limit=20")
    assert status == 200
    logs_payload = json.loads(body.decode("utf-8"))
    assert any("CACHE_HIT" in line or "ALLOW" in line for line in logs_payload["logs"])

    status, body = admin_get("/api/logs/query?kind=proxy&event=CACHE_MISS&limit=20")
    assert status == 200
    query_payload = json.loads(body.decode("utf-8"))
    assert query_payload["matched"] >= 1
    assert all(entry["event"] == "CACHE_MISS" for entry in query_payload["entries"])

    status, body = admin_get(
        "/api/logs/query?kind=blocked&event=BLOCK&search=domain_blacklist&limit=20"
    )
    assert status == 200
    query_payload = json.loads(body.decode("utf-8"))
    assert query_payload["matched"] >= 1
    assert query_payload["entries"][0]["fields"]["host"] == "blocked.test"

    print("stage12 frontend display smoke test passed")

    admin_server.shutdown()
    admin_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
