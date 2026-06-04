import http.client
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
ADMIN_PORT = 18088


def get(path):
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, body


def post(path):
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request("POST", path)
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
    return response.status, response_body


def post_raw_json(path, body_text):
    connection = http.client.HTTPConnection(HOST, ADMIN_PORT, timeout=5)
    connection.request(
        "POST",
        path,
        body=body_text.encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    response = connection.getresponse()
    response_body = response.read()
    connection.close()
    return response.status, response_body


def main():
    assert proxy.domain_matches("www.baidu.com", ["www.baidu.com"])
    assert proxy.domain_matches("www.baidu.com", ["baidu.com"])
    assert proxy.domain_matches("www.baidu.com", ["*.baidu.com"])
    assert proxy.domain_matches("www.baidu.com", ["*baidu*"])
    assert not proxy.domain_matches("www.baidu.com", ["baidu"])

    config = {
        "listen_host": "127.0.0.1",
        "listen_port": 8080,
        "admin_host": HOST,
        "admin_port": ADMIN_PORT,
        "mode": "blacklist",
        "blocked_domains": ["blocked.test"],
        "blocked_content_keywords": ["forbidden"],
        "log_file": "tests/stage8_proxy.log",
        "blocked_log_file": "tests/stage8_blocked.log",
        "error_log_file": "tests/stage8_error.log",
    }
    state = proxy.RuntimeState(config)
    server = proxy.start_admin_server(HOST, ADMIN_PORT, state)

    try:
        status, body = get("/api/config")
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["config"]["blocked_domains"] == ["blocked.test"]

        status, body = get("/api/rules")
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert any(group["type"] == "blocked_content_keywords" for group in payload["groups"])

        status, body = post_json(
            "/api/rules/add",
            {"rule_type": "blocked_content_keywords", "value": "malware"},
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert "malware" in payload["values"]

        status, body = post_raw_json(
            "/api/rules/add",
            '\'{"rule_type":"blocked_content_keywords","value":"cmdquote"}\'',
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert "cmdquote" in payload["values"]

        status, body = post_raw_json(
            "/api/rules/add",
            "{rule_type:blocked_content_keywords,value:psquote}",
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert "psquote" in payload["values"]

        status, body = post_json(
            "/api/rules/delete",
            {"rule_type": "blocked_content_keywords", "value": "cmdquote"},
        )
        assert status == 200

        status, body = post_json(
            "/api/rules/delete",
            {"rule_type": "blocked_content_keywords", "value": "psquote"},
        )
        assert status == 200

        status, body = post_json(
            "/api/rules/update",
            {
                "rule_type": "blocked_content_keywords",
                "old_value": "malware",
                "new_value": "trojan",
            },
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert "trojan" in payload["values"]
        assert "malware" not in payload["values"]

        status, body = post_json(
            "/api/rules/replace",
            {
                "rule_type": "blocked_url_keywords",
                "values": ["private", "exam"],
            },
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert payload["values"] == ["private", "exam"]

        status, body = post_json(
            "/api/rules/delete",
            {"rule_type": "blocked_content_keywords", "value": "trojan"},
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["ok"] is True
        assert "trojan" not in payload["values"]

        status, body = post_json(
            "/api/settings/update",
            {"settings": {"mode": "whitelist", "cache_enabled": False}},
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["settings"]["mode"] == "whitelist"
        assert payload["settings"]["cache_enabled"] is False

        status, body = get("/api/changes?limit=20")
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert any(item["action"] == "add" for item in payload["changes"])
        assert any(item["action"] == "settings" for item in payload["changes"])

        status, body = get("/api/stats")
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert "stats" in payload

        status, body = get("/")
        assert status == 200
        assert "Web 代理服务器管理台".encode("utf-8") in body
        assert "过滤规则管理".encode("utf-8") in body
        assert "添加".encode("utf-8") in body
        assert "修改".encode("utf-8") in body
        assert "删除".encode("utf-8") in body
        assert "替换整组".encode("utf-8") in body
        assert "规则变更回显".encode("utf-8") in body
        assert "保存设置".encode("utf-8") in body
        assert "清空缓存".encode("utf-8") in body
        assert "重置统计".encode("utf-8") in body
        assert "清空日志".encode("utf-8") in body

        status, body = post("/api/cache/clear")
        assert status == 200
        assert json.loads(body.decode("utf-8"))["ok"] is True

        status, body = post("/api/stats/reset")
        assert status == 200
        assert json.loads(body.decode("utf-8"))["ok"] is True

        status, body = post("/api/logs/clear")
        assert status == 200
        assert json.loads(body.decode("utf-8"))["ok"] is True

        print("stage8 admin smoke test passed")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
