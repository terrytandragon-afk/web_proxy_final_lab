from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy
from tests.acceptance_support import (
    RULE_BLOCKED_LOG,
    RULE_CHANGE_LOG,
    RULE_ERROR_LOG,
    RULE_EVIDENCE_CONFIG,
    RULE_PROXY_LOG,
    admin_request,
    build_evidence_config,
    clear_evidence_files,
    proxy_request,
    write_evidence_config,
)


HOST = "127.0.0.1"
PROXY_PORT = 18211
ADMIN_PORT = 18212
UPSTREAM_PORT = 19211


class RuleEvidenceHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"rule evidence page contains classroom and lecture"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def post(path, payload):
    status, result = admin_request(ADMIN_PORT, "POST", path, payload)
    assert status == 200 and result["ok"] is True
    return result


def run_cli(*arguments):
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "tools" / "rule_cli.py"),
            "--admin-host",
            HOST,
            "--admin-port",
            str(ADMIN_PORT),
            *arguments,
        ],
        cwd=str(PROJECT_ROOT),
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def main():
    # Rule/mode evidence is isolated from Web-feature evidence and starts empty.
    clear_evidence_files(RULE_PROXY_LOG, RULE_BLOCKED_LOG, RULE_ERROR_LOG, RULE_CHANGE_LOG)
    baseline_config = build_evidence_config(PROXY_PORT, ADMIN_PORT, scope="rules")
    write_evidence_config(baseline_config, RULE_EVIDENCE_CONFIG)

    upstream = ThreadingHTTPServer((HOST, UPSTREAM_PORT), RuleEvidenceHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    state = proxy.RuntimeState(
        proxy.load_config(str(RULE_EVIDENCE_CONFIG)),
        str(RULE_EVIDENCE_CONFIG),
    )
    admin_server = proxy.start_admin_server(HOST, ADMIN_PORT, state)
    threading.Thread(
        target=proxy.start_server,
        args=(HOST, PROXY_PORT, state),
        daemon=True,
    ).start()
    time.sleep(0.5)

    local_host = f"{HOST}:{UPSTREAM_PORT}"
    local_url = f"http://{local_host}/rules"

    # API CRUD: add, update, delete and replace all leave visible change records.
    post("/api/rules/add", {"rule_type": "blocked_content_keywords", "value": "classroom"})
    assert "blocked by keyword filter: classroom" in proxy_request(
        PROXY_PORT, "GET", local_url, local_host
    )
    post(
        "/api/rules/update",
        {
            "rule_type": "blocked_content_keywords",
            "old_value": "classroom",
            "new_value": "lecture",
        },
    )
    post("/api/rules/delete", {"rule_type": "blocked_content_keywords", "value": "lecture"})
    post(
        "/api/rules/replace",
        {"rule_type": "blocked_url_keywords", "values": ["rule-private"]},
    )
    assert "url_keyword:rule-private" in proxy_request(
        PROXY_PORT,
        "GET",
        f"http://{local_host}/rule-private",
        local_host,
    )
    post("/api/rules/replace", {"rule_type": "blocked_url_keywords", "values": []})

    # Whitelist mode changes immediately and is also recorded as a settings change.
    post("/api/rules/add", {"rule_type": "allowed_domains", "value": HOST})
    post("/api/settings/update", {"settings": {"mode": "whitelist"}})
    assert "200 OK" in proxy_request(PROXY_PORT, "GET", local_url, local_host)
    post("/api/rules/delete", {"rule_type": "allowed_domains", "value": HOST})
    assert "domain_not_in_whitelist" in proxy_request(PROXY_PORT, "GET", local_url, local_host)
    post("/api/settings/update", {"settings": {"mode": "blacklist"}})

    # CLI changes use the same backend and must appear in the same frontend history.
    run_cli("add", "blocked_domains", "cli-evidence.test")
    run_cli("update", "blocked_domains", "cli-evidence.test", "*cli-evidence*")
    assert "domain_blacklist" in proxy_request(
        PROXY_PORT,
        "GET",
        "http://www.cli-evidence.test/",
        "www.cli-evidence.test",
    )
    run_cli("delete", "blocked_domains", "*cli-evidence*")
    run_cli("add", "blocked_client_ips", "10.20.30.99/24")
    run_cli("delete", "blocked_client_ips", "10.20.30.0/24")
    run_cli("set", "rate_limit_per_minute", "3")
    run_cli("set", "rate_limit_enabled", "true")
    run_cli("rate-reset")
    run_cli("set", "rate_limit_enabled", "false")

    status, changes_payload = admin_request(ADMIN_PORT, "GET", "/api/changes?limit=100")
    assert status == 200
    actions = {entry["action"] for entry in changes_payload["changes"]}
    assert {"add", "update", "delete", "replace", "settings"} <= actions
    assert any(entry.get("rule_type") == "blocked_domains" for entry in changes_payload["changes"])
    assert any(entry.get("rule_type") == "blocked_client_ips" for entry in changes_payload["changes"])
    assert any(entry.get("settings", {}).get("mode") == "whitelist" for entry in changes_payload["changes"])

    # Leave a safe empty baseline for the optional evidence dashboard, while retaining history.
    write_evidence_config(
        build_evidence_config(PROXY_PORT, ADMIN_PORT, scope="rules"),
        RULE_EVIDENCE_CONFIG,
    )
    admin_server.shutdown()
    admin_server.server_close()

    # Restart the admin server from disk and verify the UI APIs still expose all evidence.
    dashboard_state = proxy.RuntimeState(
        proxy.load_config(str(RULE_EVIDENCE_CONFIG)),
        str(RULE_EVIDENCE_CONFIG),
    )
    dashboard_server = proxy.start_admin_server(HOST, ADMIN_PORT, dashboard_state)
    status, reloaded_changes = admin_request(ADMIN_PORT, "GET", "/api/changes?limit=100")
    assert status == 200
    assert len(reloaded_changes["changes"]) == len(changes_payload["changes"])
    status, blocked_logs = admin_request(ADMIN_PORT, "GET", "/api/logs?kind=blocked&limit=200")
    assert status == 200 and any("BLOCK" in line for line in blocked_logs["logs"])
    # The evidence page supports both a total view and independent operation/group queries.
    status, all_change_evidence = admin_request(
        ADMIN_PORT,
        "GET",
        "/api/evidence/changes/query?profile=rules&limit=100",
    )
    assert status == 200
    assert all_change_evidence["total"] == len(changes_payload["changes"])
    assert {"add", "update", "delete", "replace", "settings"} <= set(
        all_change_evidence["action_counts"]
    )
    status, domain_add_evidence = admin_request(
        ADMIN_PORT,
        "GET",
        "/api/evidence/changes/query?profile=rules&action=add&rule_type=blocked_domains&limit=100",
    )
    assert status == 200 and domain_add_evidence["matched"] == 1
    assert domain_add_evidence["entries"][0]["value"] == "cli-evidence.test"
    status, frontend = admin_request(ADMIN_PORT, "GET", "/")
    assert status == 200 and b"/changes.html?profile=rules" in frontend
    status, changes_frontend = admin_request(ADMIN_PORT, "GET", "/changes.html")
    assert status == 200 and b"/api/evidence/changes/query" in changes_frontend

    print("acceptance rule evidence smoke test passed")
    print(f"persistent change entries verified: {len(changes_payload['changes'])}")
    print(f"evidence config: {RULE_EVIDENCE_CONFIG}")

    dashboard_server.shutdown()
    dashboard_server.server_close()
    upstream.shutdown()
    upstream.server_close()


if __name__ == "__main__":
    main()
