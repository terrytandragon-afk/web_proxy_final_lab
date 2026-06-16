"""Web 代理规则命令行管理工具。

这个脚本不是直接改内存变量，而是像前端一样调用 8088 管理后端 API。
好处是：
- 代理服务器运行中即可增删改查规则；
- 命令行修改和前端修改走同一套后端校验逻辑；
- 每次修改都会写入配置文件和规则变更日志，前端也能回显。
"""

import argparse
import http.client
import json
from pathlib import Path
import sys
from urllib.parse import urlencode


# 后端规则管理命令行工具：
# 通过管理 API 操作正在运行的代理规则，适合网络安全课程现场做底层命令行验收。
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def parse_args():
    """定义命令行参数和子命令。

    常用示例：
    - list：查看所有规则组；
    - add/delete/update/replace：修改列表型规则；
    - set：修改缓存、认证、限流、黑白名单模式等运行时设置；
    - logs/log-query/log-export：读取或导出日志证据。
    """
    parser = argparse.ArgumentParser(description="Manage web proxy filter rules from command line")
    parser.add_argument("--admin-host", default="127.0.0.1", help="Admin API host")
    parser.add_argument("--admin-port", type=int, default=8088, help="Admin API port")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List editable rule groups")
    subparsers.add_parser("config", help="Show current runtime config")

    add_parser = subparsers.add_parser("add", help="Add one rule value")
    add_parser.add_argument("rule_type", help="Rule group name")
    add_parser.add_argument("value", help="Rule value to add")

    delete_parser = subparsers.add_parser("delete", help="Delete one rule value")
    delete_parser.add_argument("rule_type", help="Rule group name")
    delete_parser.add_argument("value", help="Rule value to delete")

    update_parser = subparsers.add_parser("update", help="Update one rule value")
    update_parser.add_argument("rule_type", help="Rule group name")
    update_parser.add_argument("old_value", help="Old rule value")
    update_parser.add_argument("new_value", help="New rule value")

    replace_parser = subparsers.add_parser("replace", help="Replace a whole rule group")
    replace_parser.add_argument("rule_type", help="Rule group name")
    replace_parser.add_argument("values", nargs="*", help="New values for this rule group")

    set_parser = subparsers.add_parser("set", help="Update one runtime setting")
    set_parser.add_argument("key", help="Setting name, for example mode")
    set_parser.add_argument("value", help="Setting value")

    auth_user_parser = subparsers.add_parser("auth-user", help="Add or update one proxy auth user")
    auth_user_parser.add_argument("username", help="Proxy auth username")
    auth_user_parser.add_argument("password", help="Proxy auth password")

    auth_delete_parser = subparsers.add_parser("auth-delete", help="Delete one proxy auth user")
    auth_delete_parser.add_argument("username", help="Proxy auth username to delete")

    subparsers.add_parser("rate-reset", help="Clear current rate-limit counters")
    subparsers.add_parser("cache-clear", help="Clear current HTTP response cache")

    logs_parser = subparsers.add_parser("logs", help="Read logs from admin API")
    logs_parser.add_argument("--kind", choices=["proxy", "blocked", "error"], default="proxy")
    logs_parser.add_argument("--limit", type=int, default=20)

    log_query_parser = subparsers.add_parser(
        "log-query",
        help="Query structured log entries by event and text",
    )
    log_query_parser.add_argument(
        "--kind",
        choices=["proxy", "blocked", "error"],
        default="proxy",
    )
    log_query_parser.add_argument("--event", default="", help="Comma-separated event names")
    log_query_parser.add_argument("--search", default="", help="Case-insensitive full-line search")
    log_query_parser.add_argument("--limit", type=int, default=20)

    log_export_parser = subparsers.add_parser(
        "log-export",
        help="Export queried logs to a CSV file",
    )
    log_export_parser.add_argument("--kind", choices=["proxy", "blocked", "error"], default="proxy")
    log_export_parser.add_argument("--event", default="", help="Comma-separated event names")
    log_export_parser.add_argument("--search", default="", help="Case-insensitive full-line search")
    log_export_parser.add_argument("--limit", type=int, default=1000)
    log_export_parser.add_argument("--output", required=True, help="CSV output file path")

    changes_parser = subparsers.add_parser("changes", help="Read rule/settings change history")
    changes_parser.add_argument("--action", default="", help="Filter by add/update/delete/replace/settings")
    changes_parser.add_argument("--rule-type", default="", help="Filter by one rule group")
    changes_parser.add_argument("--search", default="", help="Case-insensitive full-record search")
    changes_parser.add_argument("--limit", type=int, default=20)

    return parser.parse_args()


def request_json(args, method, path, payload=None):
    """发送 JSON 管理请求并返回解析后的 JSON。

    这里直接使用 http.client，避免依赖 requests 等第三方库。
    method/path/payload 对应管理后端 AdminHandler 中的接口，例如：
    POST /api/rules/add 负责新增规则。
    """
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    connection = http.client.HTTPConnection(args.admin_host, args.admin_port, timeout=10)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    response_body = response.read().decode("utf-8", errors="replace")
    connection.close()

    try:
        data = json.loads(response_body)
    except json.JSONDecodeError:
        data = {"raw": response_body}

    if response.status >= 400:
        print_json({"ok": False, "status": response.status, "response": data})
        raise SystemExit(1)
    return data


def request_bytes(args, method, path):
    """下载非 JSON 响应，目前用于把日志查询结果导出为 CSV 文件。"""
    connection = http.client.HTTPConnection(args.admin_host, args.admin_port, timeout=10)
    connection.request(method, path)
    response = connection.getresponse()
    response_body = response.read()
    connection.close()
    if response.status >= 400:
        raise SystemExit(f"admin request failed: {response.status}")
    return response_body


def print_json(payload):
    """用 UTF-8 JSON 格式打印结果，便于在 PowerShell/CMD 中复制留证。"""
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_setting_value(value):
    """把命令行中的字符串转换为后端设置能识别的布尔值、整数或 JSON 对象。"""
    lowered = value.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if value.isdigit():
        return int(value)
    if value.startswith("{") or value.startswith("["):
        return json.loads(value)
    return value


def fetch_config(args):
    """读取当前运行配置，供命令行增删认证用户时保留已有用户。"""
    result = request_json(args, "GET", "/api/config")
    return result.get("config", {})


def main():
    """根据子命令组装 API 请求，并把后端返回结果原样打印出来。"""
    args = parse_args()

    if args.command == "list":
        # GET /api/rules：查询所有可编辑规则组。
        result = request_json(args, "GET", "/api/rules")
    elif args.command == "config":
        # GET /api/config：查看当前运行配置。
        result = request_json(args, "GET", "/api/config")
    elif args.command == "add":
        # POST /api/rules/add：新增一条规则，例如 blocked_domains *.bing.com。
        result = request_json(
            args,
            "POST",
            "/api/rules/add",
            {"rule_type": args.rule_type, "value": args.value},
        )
    elif args.command == "delete":
        # POST /api/rules/delete：删除一条规则。
        result = request_json(
            args,
            "POST",
            "/api/rules/delete",
            {"rule_type": args.rule_type, "value": args.value},
        )
    elif args.command == "update":
        # POST /api/rules/update：把旧规则值替换成新规则值。
        result = request_json(
            args,
            "POST",
            "/api/rules/update",
            {
                "rule_type": args.rule_type,
                "old_value": args.old_value,
                "new_value": args.new_value,
            },
        )
    elif args.command == "replace":
        # POST /api/rules/replace：一次性替换整个规则组，适合恢复验收环境。
        result = request_json(
            args,
            "POST",
            "/api/rules/replace",
            {"rule_type": args.rule_type, "values": args.values},
        )
    elif args.command == "set":
        # POST /api/settings/update：修改运行时设置，例如限流开关、缓存 TTL。
        result = request_json(
            args,
            "POST",
            "/api/settings/update",
            {"settings": {args.key: parse_setting_value(args.value)}},
        )
    elif args.command == "auth-user":
        # 认证用户表是一个整体设置，所以先读出现有用户，再追加/覆盖指定用户。
        config = fetch_config(args)
        users = dict(config.get("proxy_auth_users", {}))
        users[args.username] = args.password
        result = request_json(
            args,
            "POST",
            "/api/settings/update",
            {"settings": {"proxy_auth_users": users}},
        )
    elif args.command == "auth-delete":
        # 删除认证用户同样需要先取出现有用户表，再移除目标用户名后写回。
        config = fetch_config(args)
        users = dict(config.get("proxy_auth_users", {}))
        users.pop(args.username, None)
        result = request_json(
            args,
            "POST",
            "/api/settings/update",
            {"settings": {"proxy_auth_users": users}},
        )
    elif args.command == "rate-reset":
        result = request_json(args, "POST", "/api/rate/reset")
    elif args.command == "cache-clear":
        result = request_json(args, "POST", "/api/cache/clear")
    elif args.command == "logs":
        query = urlencode({"kind": args.kind, "limit": args.limit})
        result = request_json(args, "GET", f"/api/logs?{query}")
    elif args.command == "log-query":
        query = urlencode(
            {
                "kind": args.kind,
                "event": args.event,
                "search": args.search,
                "limit": args.limit,
            }
        )
        result = request_json(args, "GET", f"/api/logs/query?{query}")
    elif args.command == "log-export":
        query = urlencode(
            {
                "kind": args.kind,
                "event": args.event,
                "search": args.search,
                "limit": args.limit,
            }
        )
        csv_bytes = request_bytes(args, "GET", f"/api/logs/export.csv?{query}")
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(csv_bytes)
        result = {"ok": True, "output": str(output_path), "bytes": len(csv_bytes)}
    elif args.command == "changes":
        query = urlencode(
            {
                "action": args.action,
                "rule_type": args.rule_type,
                "search": args.search,
                "limit": args.limit,
            }
        )
        result = request_json(args, "GET", f"/api/changes/query?{query}")
    else:
        raise SystemExit(f"unsupported command: {args.command}")

    print_json(result)


if __name__ == "__main__":
    main()
