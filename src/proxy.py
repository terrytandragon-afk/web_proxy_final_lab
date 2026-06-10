import argparse
import base64
import fnmatch
from html import escape
import ipaddress
import json
import select
import socket
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

try:
    from .webproxy.audit import (
        build_log_csv,
        clear_log_files,
        log_event,
        query_log_entries,
        read_log_tail,
    )
    from .webproxy.config_rules import (
        CONFIG_SETTING_FIELDS,
        LIST_RULE_FIELDS,
        PROJECT_ROOT,
        build_rules_payload,
        load_config,
        normalize_rule_value,
        parse_loose_json_object,
        resolve_project_path,
        rule_identity,
        validate_rule_type,
    )
    from .webproxy.evidence import (
        build_evidence_dashboard,
        list_evidence_profiles,
        load_evidence_config,
        query_change_entries,
    )
except ImportError:
    # Running `python src/proxy.py` adds `src` rather than the project root to sys.path.
    from webproxy.audit import (
        build_log_csv,
        clear_log_files,
        log_event,
        query_log_entries,
        read_log_tail,
    )
    from webproxy.config_rules import (
        CONFIG_SETTING_FIELDS,
        LIST_RULE_FIELDS,
        PROJECT_ROOT,
        build_rules_payload,
        load_config,
        normalize_rule_value,
        parse_loose_json_object,
        resolve_project_path,
        rule_identity,
        validate_rule_type,
    )
    from webproxy.evidence import (
        build_evidence_dashboard,
        list_evidence_profiles,
        load_evidence_config,
        query_change_entries,
    )

BUFFER_SIZE = 8192
DEFAULT_TIMEOUT = 10
FRONTEND_INDEX = PROJECT_ROOT / "frontend" / "index.html"
LOG_DETAILS_INDEX = PROJECT_ROOT / "frontend" / "logs.html"
CHANGE_DETAILS_INDEX = PROJECT_ROOT / "frontend" / "changes.html"


class RuntimeState:
    """保存代理运行期间的共享状态：配置、统计、缓存、限流桶和排行数据。"""

    def __init__(self, config, config_path=""):
        self.config = config
        self.config_path = config_path
        self.started_at = time.time()
        self.lock = threading.Lock()
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "blocked_domain": 0,
            "blocked_client": 0,
            "blocked_url": 0,
            "blocked_method": 0,
            "filtered_keyword": 0,
            "https_tunnels": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "auth_required": 0,
            "rate_limited": 0,
            "bad_requests": 0,
            "errors": 0,
            "bytes_from_clients": 0,
            "bytes_to_clients": 0,
        }
        self.host_hits = {}
        self.keyword_hits = {}
        self.cache = {}
        self.rate_limits = {}
        # Persisted JSONL history lets the frontend show CLI/API changes after a restart.
        self.change_history = self._load_change_history()

    def _load_change_history(self):
        """Load the newest persisted rule/settings changes for the admin frontend."""
        path_text = self.config.get("change_log_file")
        if not path_text:
            return []
        path = resolve_project_path(path_text)
        if not path.exists():
            return []

        entries = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return list(reversed(entries))

    def _append_change_history_locked(self, entry):
        """Append one JSONL change record. Caller must already hold self.lock."""
        path_text = self.config.get("change_log_file")
        if not path_text:
            return
        path = resolve_project_path(path_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as change_file:
            change_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_config(self):
        with self.lock:
            return dict(self.config)

    def reload_config(self):
        """从配置文件重新加载规则，用于管理前端的“重新加载配置”按钮。"""
        if not self.config_path:
            return self.get_config()
        config = load_config(self.config_path)
        with self.lock:
            self.config = config
        return config

    def _save_config_locked(self):
        """把当前内存配置写回 JSON 文件，调用方必须已经持有 self.lock。"""
        if not self.config_path:
            return False
        config_path = resolve_project_path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as config_file:
            json.dump(self.config, config_file, ensure_ascii=False, indent=2)
            config_file.write("\n")
        return True

    def get_rules(self):
        """返回当前可编辑规则，用于前端和 curl 查询。"""
        with self.lock:
            return build_rules_payload(self.config)

    def get_change_history(self, limit=80):
        """Return rule/settings changes so API/CLI edits can be shown by the web UI."""
        with self.lock:
            limit = max(1, min(int(limit), 200))
            return [dict(item) for item in self.change_history[:limit]]

    def _record_change_locked(self, action, result):
        """Store one admin change entry. Caller must already hold self.lock."""
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "changed": bool(result.get("changed", False)),
            "saved": bool(result.get("saved", False)),
        }
        for key in ("rule_type", "value", "old_value", "new_value", "values", "settings"):
            if key in result:
                entry[key] = result[key]
        self.change_history.insert(0, entry)
        self.change_history = self.change_history[:100]
        self._append_change_history_locked(entry)
        return entry

    def add_list_rule(self, rule_type, value):
        """向指定规则列表新增一条规则，并立即保存到配置文件。"""
        validate_rule_type(rule_type)
        normalized = normalize_rule_value(rule_type, value)
        new_identity = rule_identity(rule_type, normalized)
        with self.lock:
            current_values = list(self.config.get(rule_type, []))
            current_identities = {
                rule_identity(rule_type, item)
                for item in current_values
            }
            if new_identity in current_identities:
                changed = False
            else:
                current_values.append(normalized)
                self.config[rule_type] = current_values
                changed = True
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "rule_type": rule_type,
                "value": normalized,
                "values": list(self.config.get(rule_type, [])),
            }
            result["history_entry"] = self._record_change_locked("add", result)
            return result

    def delete_list_rule(self, rule_type, value):
        """从指定规则列表删除一条规则，并立即保存到配置文件。"""
        validate_rule_type(rule_type)
        target_identity = rule_identity(rule_type, value)
        with self.lock:
            current_values = list(self.config.get(rule_type, []))
            new_values = [
                item
                for item in current_values
                if rule_identity(rule_type, item) != target_identity
            ]
            changed = len(new_values) != len(current_values)
            self.config[rule_type] = new_values
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "rule_type": rule_type,
                "value": normalize_rule_value(rule_type, value),
                "values": list(new_values),
            }
            result["history_entry"] = self._record_change_locked("delete", result)
            return result

    def update_list_rule(self, rule_type, old_value, new_value):
        """修改指定规则列表中的一条规则，并立即保存到配置文件。"""
        validate_rule_type(rule_type)
        old_identity = rule_identity(rule_type, old_value)
        normalized_new = normalize_rule_value(rule_type, new_value)
        new_identity = rule_identity(rule_type, normalized_new)
        with self.lock:
            current_values = list(self.config.get(rule_type, []))
            found_old = False
            duplicate_new = False
            new_values = []

            for item in current_values:
                item_identity = rule_identity(rule_type, item)
                if item_identity == old_identity:
                    found_old = True
                    new_values.append(normalized_new)
                else:
                    if item_identity == new_identity:
                        duplicate_new = True
                    new_values.append(item)

            if not found_old:
                raise ValueError(f"rule value not found: {old_value}")
            if duplicate_new:
                raise ValueError(f"new rule value already exists: {normalized_new}")

            changed = new_values != current_values
            self.config[rule_type] = new_values
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "rule_type": rule_type,
                "old_value": normalize_rule_value(rule_type, old_value),
                "new_value": normalized_new,
                "values": list(new_values),
            }
            result["history_entry"] = self._record_change_locked("update", result)
            return result

    def replace_list_rules(self, rule_type, values):
        """替换某一个规则组，适合命令行一次性重设整组过滤条件。"""
        validate_rule_type(rule_type)
        if not isinstance(values, list):
            raise ValueError("values must be a list")

        normalized_values = []
        seen = set()
        for value in values:
            normalized = normalize_rule_value(rule_type, value)
            identity = rule_identity(rule_type, normalized)
            if identity in seen:
                continue
            seen.add(identity)
            normalized_values.append(normalized)

        with self.lock:
            current_values = list(self.config.get(rule_type, []))
            changed = current_values != normalized_values
            self.config[rule_type] = normalized_values
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "rule_type": rule_type,
                "values": list(normalized_values),
            }
            result["history_entry"] = self._record_change_locked("replace", result)
            return result

    def update_settings(self, updates):
        """更新模式、缓存、认证、限流等简单配置项，并保存到配置文件。"""
        if not isinstance(updates, dict):
            raise ValueError("settings payload must be an object")
        normalized_updates = {}
        for key, value in updates.items():
            if key not in CONFIG_SETTING_FIELDS:
                raise ValueError(f"unsupported setting: {key}")
            value_type = CONFIG_SETTING_FIELDS[key]
            if key == "mode":
                value = str(value).strip().lower()
                if value not in ("blacklist", "whitelist"):
                    raise ValueError("mode must be blacklist or whitelist")
            elif key == "proxy_auth_users":
                if not isinstance(value, dict):
                    raise ValueError("proxy_auth_users must be an object")
                # 认证用户表按 username -> password 保存，便于 API/CLI 在运行中热更新。
                normalized_users = {}
                for username, password in value.items():
                    username = str(username).strip()
                    if not username:
                        raise ValueError("proxy auth username cannot be empty")
                    normalized_users[username] = str(password)
                value = normalized_users
            elif value_type is bool:
                if isinstance(value, bool):
                    pass
                elif isinstance(value, str):
                    value = value.strip().lower() in ("1", "true", "yes", "on")
                else:
                    value = bool(value)
            elif value_type is int:
                value = int(value)
                if value < 0:
                    raise ValueError(f"{key} cannot be negative")
                if key in ("rate_limit_per_minute", "rate_limit_window_seconds") and value <= 0:
                    raise ValueError(f"{key} must be greater than 0")
            else:
                value = value_type(value)
            normalized_updates[key] = value

        with self.lock:
            changed = any(self.config.get(key) != value for key, value in normalized_updates.items())
            self.config.update(normalized_updates)
            if any(key.startswith("rate_limit_") for key in normalized_updates):
                self.rate_limits.clear()
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "settings": {
                    key: self.config.get(key)
                    for key in CONFIG_SETTING_FIELDS
                },
            }
            result["history_entry"] = self._record_change_locked("settings", result)
            return result

    def increment(self, key, amount=1):
        with self.lock:
            self.stats[key] = self.stats.get(key, 0) + amount

    def record_host(self, host):
        with self.lock:
            self.host_hits[host] = self.host_hits.get(host, 0) + 1

    def record_keyword(self, keyword):
        with self.lock:
            self.keyword_hits[keyword] = self.keyword_hits.get(keyword, 0) + 1

    def get_cache(self, key):
        """读取 HTTP GET 缓存；如果缓存过期，自动删除并返回 None。"""
        with self.lock:
            entry = self.cache.get(key)
            if not entry:
                return None
            if entry["expires_at"] < time.time():
                del self.cache[key]
                return None
            return dict(entry)

    def set_cache(self, key, response_bytes, status_code, ttl_seconds, max_items):
        """写入 HTTP GET 缓存，并在超过最大条目数时删除最早的缓存。"""
        if ttl_seconds <= 0:
            return
        with self.lock:
            while max_items > 0 and len(self.cache) >= max_items:
                oldest_key = min(
                    self.cache,
                    key=lambda item: self.cache[item]["created_at"],
                )
                del self.cache[oldest_key]
            self.cache[key] = {
                "response_bytes": response_bytes,
                "status_code": status_code,
                "created_at": time.time(),
                "expires_at": time.time() + ttl_seconds,
            }

    def check_rate_limit(self, client_ip, max_requests, window_seconds):
        """按客户端 IP 做固定时间窗口限流，返回是否允许和剩余/等待时间。"""
        if max_requests <= 0:
            return True, 0, 0
        now = time.time()
        with self.lock:
            bucket = self.rate_limits.get(client_ip)
            if not bucket or now >= bucket["reset_at"]:
                self.rate_limits[client_ip] = {
                    "count": 1,
                    "reset_at": now + window_seconds,
                }
                return True, 0, 1
            if bucket["count"] >= max_requests:
                retry_after = max(1, int(bucket["reset_at"] - now))
                return False, retry_after, bucket["count"]
            bucket["count"] += 1
            return True, 0, bucket["count"]

    def clear_cache(self):
        """清空缓存，方便验收时重新演示第一次 MISS、第二次 HIT。"""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            return count

    def clear_rate_limits(self):
        """清空限流计数桶，让访问频率设置修改后可以马上重新演示。"""
        with self.lock:
            count = len(self.rate_limits)
            self.rate_limits.clear()
            return count

    def clear_change_history(self):
        """Clear in-memory and persisted rule/settings change history."""
        with self.lock:
            count = len(self.change_history)
            self.change_history.clear()
            path_text = self.config.get("change_log_file")
            if path_text:
                path = resolve_project_path(path_text)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            return count

    def reset_stats(self):
        """重置统计、排行和限流桶，保留当前配置和缓存内容。"""
        with self.lock:
            for key in self.stats:
                self.stats[key] = 0
            self.host_hits.clear()
            self.keyword_hits.clear()
            self.rate_limits.clear()
            self.started_at = time.time()

    def snapshot(self):
        """返回管理首页使用的实时统计快照，并派生跨类别的总拦截数。"""
        with self.lock:
            uptime_seconds = int(time.time() - self.started_at)
            stats = dict(self.stats)
            stats["cache_entries"] = len(self.cache)
            # 总拦截用于首页总览，包含直接拒绝、正文过滤、认证和限流拒绝。
            stats["total_blocked"] = sum(
                stats[key]
                for key in (
                    "blocked_domain",
                    "blocked_client",
                    "blocked_url",
                    "blocked_method",
                    "filtered_keyword",
                    "auth_required",
                    "rate_limited",
                )
            )
            return {
                "started_at": datetime.fromtimestamp(self.started_at).isoformat(timespec="seconds"),
                "uptime_seconds": uptime_seconds,
                "stats": stats,
                "top_hosts": sorted(
                    self.host_hits.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10],
                "keyword_hits": sorted(
                    self.keyword_hits.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10],
            }


def parse_args():
    parser = argparse.ArgumentParser(description="Web proxy server with admin dashboard")
    parser.add_argument("--host", default=None, help="Proxy listen host")
    parser.add_argument("--port", type=int, default=None, help="Proxy listen port")
    parser.add_argument("--config", default="config.example.json", help="Config file path")
    parser.add_argument("--admin-host", default=None, help="Admin dashboard listen host")
    parser.add_argument("--admin-port", type=int, default=None, help="Admin dashboard listen port")
    parser.add_argument("--no-admin", action="store_true", help="Disable admin dashboard")
    return parser.parse_args()


def ensure_state(state_or_config=None):
    if isinstance(state_or_config, RuntimeState):
        return state_or_config
    return RuntimeState(state_or_config or {})


def find_header(headers, name):
    prefix = name.lower() + ":"
    for line in headers:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def parse_bounded_query_int(query, name, default, maximum):
    """Read one integer URL query parameter without allowing invalid or huge values."""
    try:
        value = int(query.get(name, [str(default)])[0])
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def parse_http_request(request_text):
    """解析客户端发来的 HTTP/代理请求，提取方法、目标主机、端口、路径和请求头。"""
    lines = request_text.splitlines()
    if not lines:
        raise ValueError("empty request")

    parts = lines[0].split()
    if len(parts) != 3:
        raise ValueError(f"invalid request line: {lines[0]}")

    method, target, version = parts
    host_header = find_header(lines[1:], "Host")

    if method.upper() == "CONNECT":
        host_part = target
        if not host_part and host_header:
            host_part = host_header
        if ":" in host_part:
            host, port_text = host_part.rsplit(":", 1)
            port = int(port_text)
        else:
            host = host_part
            port = 443
        path = target
    elif target.startswith("http://"):
        parsed = urlsplit(target)
        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
    else:
        if not host_header:
            raise ValueError("missing Host header")
        host_part = host_header
        if ":" in host_part:
            host, port_text = host_part.rsplit(":", 1)
            port = int(port_text)
        else:
            host = host_part
            port = 80
        path = target or "/"

    if not host:
        raise ValueError("missing target host")

    return {
        "method": method.upper(),
        "target": target,
        "version": version,
        "host": host,
        "port": port,
        "path": path,
        "host_header": host_header,
        "headers": {
            line.split(":", 1)[0].strip().lower(): line.split(":", 1)[1].strip()
            for line in lines[1:]
            if ":" in line
        },
    }


def send_simple_response(client_socket, status_code, reason, message):
    """向客户端返回简单文本响应，供 400/403/429/502/504 等错误场景使用。"""
    body = f"{status_code} {reason}: {message}\n".encode("utf-8")
    response = (
        f"HTTP/1.1 {status_code} {reason}\r\n".encode("ascii")
        + b"Content-Type: text/plain; charset=utf-8\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: close\r\n"
        + b"\r\n"
        + body
    )
    client_socket.sendall(response)
    return len(response)


def build_policy_block_response(reason, request_info=None, client_ip="", detail=""):
    """构造替代原网页的 403 拦截提示页，并提供可展开的具体命中信息。"""
    request_info = request_info or {}
    reason_labels = {
        "domain_blacklist": "目标域名命中黑名单",
        "domain_not_in_whitelist": "目标域名不在白名单",
        "client_ip_blacklist": "客户端地址命中黑名单",
        "client_ip_not_allowed": "客户端地址不在白名单",
        "method_blacklist": "HTTP 请求方法被禁止",
    }
    if reason.startswith("url_keyword:"):
        summary = "请求 URL 命中禁止关键词"
        matched_rule = reason.split(":", 1)[1]
        legacy_message = ""
    elif reason.startswith("content_keyword:"):
        summary = "网页正文命中禁止关键词"
        matched_rule = reason.split(":", 1)[1]
        # 保留清晰的英文证据文本，方便 curl、自动测试和课程截图共同识别。
        legacy_message = (
            "<p><strong>网页已被过滤</strong><br>"
            f"This page is blocked by keyword filter: {escape(matched_rule)}</p>"
        )
    else:
        summary = reason_labels.get(reason, "请求被代理访问策略拦截")
        matched_rule = detail or reason
        legacy_message = ""

    method = request_info.get("method", "")
    host = request_info.get("host", "")
    path = request_info.get("path", "")
    body = (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>403 请求已被代理拦截</title>"
        "<style>"
        "body{margin:0;background:#f4f7fb;color:#172033;font-family:Arial,'Microsoft YaHei',sans-serif}"
        "main{max-width:760px;margin:10vh auto;padding:0 24px}"
        ".code{font-size:64px;font-weight:800;color:#b42318}"
        "h1{margin:8px 0;font-size:30px}p{line-height:1.7;color:#475467}"
        "details{margin-top:24px;border:1px solid #d0d5dd;background:#fff;padding:16px}"
        "summary{cursor:pointer;font-weight:700}dl{display:grid;grid-template-columns:130px 1fr;gap:10px;margin-bottom:0}"
        "dt{color:#667085}dd{margin:0;overflow-wrap:anywhere;font-family:Consolas,monospace}"
        "</style></head><body><main>"
        "<div class=\"code\">403</div><h1>请求已被 Web 代理拦截</h1>"
        f"<p>{escape(summary)}。原网页未返回，当前页面由代理服务器生成。</p>"
        f"{legacy_message}"
        "<details open><summary>查看详细信息</summary><dl>"
        f"<dt>拦截原因</dt><dd>{escape(reason)}</dd>"
        f"<dt>命中规则</dt><dd>{escape(matched_rule)}</dd>"
        f"<dt>请求方法</dt><dd>{escape(method)}</dd>"
        f"<dt>目标地址</dt><dd>{escape(host + path)}</dd>"
        f"<dt>客户端地址</dt><dd>{escape(client_ip)}</dd>"
        "</dl></details></main></body></html>"
    ).encode("utf-8")
    return (
        b"HTTP/1.1 403 Forbidden\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Cache-Control: no-store\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: close\r\n"
        + b"\r\n"
        + body
    )


def send_policy_block_response(client_socket, reason, request_info=None, client_ip="", detail=""):
    """发送浏览器可直接展示的访问策略拦截页。"""
    response = build_policy_block_response(reason, request_info, client_ip, detail)
    client_socket.sendall(response)
    return len(response)


def send_auth_required_response(client_socket):
    """返回代理认证挑战响应，curl 或浏览器收到后会知道需要代理用户名密码。"""
    body = b"407 Proxy Authentication Required: valid proxy credentials required\n"
    response = (
        b"HTTP/1.1 407 Proxy Authentication Required\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Proxy-Authenticate: Basic realm=\"WebProxyLab\"\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: close\r\n"
        + b"\r\n"
        + body
    )
    client_socket.sendall(response)
    return len(response)


def domain_matches(host, patterns):
    """匹配域名规则，支持完整域名、后缀域名和显式通配符。"""
    host = host.lower().strip(".")
    for pattern in patterns:
        pattern = pattern.lower().strip(".")
        if not pattern:
            continue
        # 显式通配符由 * 表达，例如 *.baidu.com 或 *baidu*。
        # 不再把普通 baidu 当成“任意包含 baidu”，避免误拦其他域名。
        if fnmatch.fnmatch(host, pattern):
            return True
        if "*" not in pattern and (host == pattern or host.endswith("." + pattern)):
            return True
    return False


def client_ip_matches(client_ip, patterns):
    """Match a client address against normalized single-IP and CIDR rules."""
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for pattern in patterns:
        try:
            if address == ipaddress.ip_address(pattern):
                return True
            continue
        except ValueError:
            pass
        try:
            if address in ipaddress.ip_network(pattern, strict=False):
                return True
        except ValueError:
            # A manually edited invalid configuration entry is ignored safely.
            continue
    return False


def check_client_access_policy(client_ip, config):
    """Apply client allow/deny lists before authentication and target filtering."""
    blocked_clients = config.get("blocked_client_ips", [])
    if client_ip_matches(client_ip, blocked_clients):
        return False, "client_ip_blacklist"

    allowed_clients = config.get("allowed_client_ips", [])
    if allowed_clients and not client_ip_matches(client_ip, allowed_clients):
        return False, "client_ip_not_allowed"
    return True, "allow"


def check_access_policy(request_info, config):
    """执行访问控制：方法黑名单、白名单模式、域名黑名单和 URL 关键字拦截。"""
    host = request_info["host"]
    method = request_info["method"]
    path = request_info["path"]
    target = request_info["target"]
    mode = config.get("mode", "blacklist").lower()

    blocked_methods = [item.upper() for item in config.get("blocked_methods", [])]
    if method in blocked_methods:
        return False, "method_blacklist"

    if mode == "whitelist":
        allowed_domains = config.get("allowed_domains", [])
        if not domain_matches(host, allowed_domains):
            return False, "domain_not_in_whitelist"

    blocked_domains = config.get("blocked_domains", [])
    if domain_matches(host, blocked_domains):
        return False, "domain_blacklist"

    searchable_url = f"{host}{path} {target}".lower()
    for keyword in config.get("blocked_url_keywords", []):
        if keyword.lower() in searchable_url:
            return False, f"url_keyword:{keyword}"

    return True, "allow"


def check_proxy_auth(request_info, config):
    """检查 Proxy-Authorization Basic 认证头，认证关闭时直接放行。"""
    if not config.get("proxy_auth_enabled", False):
        return True

    users = config.get("proxy_auth_users", {})
    auth_header = request_info.get("headers", {}).get("proxy-authorization", "")
    if not auth_header.lower().startswith("basic "):
        return False

    token = auth_header.split(None, 1)[1].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return False

    if ":" not in decoded:
        return False
    username, password = decoded.split(":", 1)
    return users.get(username) == password


def is_cacheable_request(request_info, config):
    return bool(config.get("cache_enabled", False)) and request_info["method"] == "GET"


def build_cache_key(request_info):
    return f"{request_info['host']}:{request_info['port']}{request_info['path']}"


def is_text_content_type(content_type):
    text_types = (
        "text/html",
        "text/plain",
        "text/css",
        "application/javascript",
        "application/json",
    )
    content_type = content_type.lower()
    return any(content_type.startswith(item) for item in text_types)


def response_header_value(header_lines, name):
    return find_header(header_lines, name)


def parse_status_code(response_bytes):
    first_line = response_bytes.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    parts = first_line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def filter_response_content(response_bytes, config, request_info=None, client_ip=""):
    """对 HTTP 明文文本响应做正文关键字过滤，二进制或压缩内容直接放行。"""
    if b"\r\n\r\n" not in response_bytes:
        return response_bytes, None

    header_bytes, body = response_bytes.split(b"\r\n\r\n", 1)
    header_text = header_bytes.decode("iso-8859-1", errors="replace")
    header_lines = header_text.splitlines()

    content_type = response_header_value(header_lines, "Content-Type")
    content_encoding = response_header_value(header_lines, "Content-Encoding")

    if content_encoding and content_encoding.lower() not in ("identity", "none"):
        return response_bytes, None

    if not is_text_content_type(content_type):
        return response_bytes, None

    body_text = body.decode("utf-8", errors="replace")
    body_text_lower = body_text.lower()

    for keyword in config.get("blocked_content_keywords", []):
        if keyword.lower() in body_text_lower:
            return (
                build_policy_block_response(
                    f"content_keyword:{keyword}",
                    request_info,
                    client_ip,
                    detail=keyword,
                ),
                keyword,
            )

    return response_bytes, None


def split_request(request_text):
    if "\r\n\r\n" in request_text:
        header_text, body = request_text.split("\r\n\r\n", 1)
    elif "\n\n" in request_text:
        header_text, body = request_text.split("\n\n", 1)
    else:
        header_text, body = request_text, ""
    return header_text.splitlines(), body


def build_upstream_request(request_text, request_info):
    """把代理格式请求改写成真实服务器能接受的普通 HTTP 请求。"""
    header_lines, body = split_request(request_text)
    upstream_lines = [
        f"{request_info['method']} {request_info['path']} {request_info['version']}",
        f"Host: {request_info['host']}:{request_info['port']}"
        if request_info["port"] != 80
        else f"Host: {request_info['host']}",
    ]

    skipped_headers = {
        "host",
        "connection",
        "proxy-connection",
        # Proxy credentials are only for this proxy and must never reach a website.
        "proxy-authorization",
        "proxy-authenticate",
        "accept-encoding",
    }

    for line in header_lines[1:]:
        if ":" not in line:
            continue
        header_name = line.split(":", 1)[0].strip().lower()
        if header_name in skipped_headers:
            continue
        upstream_lines.append(line)

    upstream_lines.append("Connection: close")
    upstream_lines.append("Accept-Encoding: identity")

    upstream_text = "\r\n".join(upstream_lines) + "\r\n\r\n" + body
    return upstream_text.encode("iso-8859-1", errors="replace")


def forward_http(client_socket, request_text, request_info, config, client_ip=""):
    """处理普通 HTTP 请求：连接目标服务器、转发请求、接收响应、执行正文过滤。"""
    upstream_request = build_upstream_request(request_text, request_info)
    timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT))

    try:
        with socket.create_connection(
            (request_info["host"], request_info["port"]),
            timeout=timeout,
        ) as upstream_socket:
            upstream_socket.settimeout(timeout)
            upstream_socket.sendall(upstream_request)

            chunks = []
            while True:
                chunk = upstream_socket.recv(BUFFER_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)

            response_bytes = b"".join(chunks)
            status_code = parse_status_code(response_bytes)
            response_bytes, blocked_keyword = filter_response_content(
                response_bytes,
                config,
                request_info,
                client_ip,
            )
            if blocked_keyword:
                status_code = 403
            client_socket.sendall(response_bytes)
            return {
                "outcome": "filtered" if blocked_keyword else "allowed",
                "status_code": status_code,
                "bytes_sent": len(response_bytes),
                "keyword": blocked_keyword,
                "response_bytes": response_bytes,
            }
    except socket.timeout:
        bytes_sent = send_simple_response(
            client_socket,
            504,
            "Gateway Timeout",
            "target server timed out",
        )
        return {"outcome": "error", "status_code": 504, "bytes_sent": bytes_sent}
    except OSError as error:
        bytes_sent = send_simple_response(
            client_socket,
            502,
            "Bad Gateway",
            f"cannot connect to target server: {error}",
        )
        return {"outcome": "error", "status_code": 502, "bytes_sent": bytes_sent}


def forward_connect(client_socket, request_info, config):
    """处理 HTTPS CONNECT：建立 TCP 隧道，只转发加密字节流，不读取 HTTPS 正文。"""
    timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT))
    response = b"HTTP/1.1 200 Connection Established\r\nConnection: close\r\n\r\n"
    bytes_to_client = 0
    bytes_from_client = 0

    try:
        with socket.create_connection(
            (request_info["host"], request_info["port"]),
            timeout=timeout,
        ) as upstream_socket:
            client_socket.sendall(response)
            bytes_to_client += len(response)

            client_socket.setblocking(False)
            upstream_socket.setblocking(False)

            sockets = [client_socket, upstream_socket]
            last_activity = time.time()

            while True:
                if time.time() - last_activity > timeout:
                    break

                readable, _, exceptional = select.select(sockets, [], sockets, 1)
                if exceptional:
                    break

                for ready_socket in readable:
                    try:
                        data = ready_socket.recv(BUFFER_SIZE)
                    except BlockingIOError:
                        continue

                    if not data:
                        return {
                            "outcome": "tunnel",
                            "status_code": 200,
                            "bytes_sent": bytes_to_client,
                            "bytes_from_client": bytes_from_client,
                        }

                    last_activity = time.time()
                    if ready_socket is client_socket:
                        upstream_socket.sendall(data)
                        bytes_from_client += len(data)
                    else:
                        client_socket.sendall(data)
                        bytes_to_client += len(data)

        return {
            "outcome": "tunnel",
            "status_code": 200,
            "bytes_sent": bytes_to_client,
            "bytes_from_client": bytes_from_client,
        }
    except socket.timeout:
        bytes_sent = send_simple_response(
            client_socket,
            504,
            "Gateway Timeout",
            "target server timed out",
        )
        return {
            "outcome": "error",
            "status_code": 504,
            "bytes_sent": bytes_sent,
            "bytes_from_client": bytes_from_client,
        }
    except OSError as error:
        bytes_sent = send_simple_response(
            client_socket,
            502,
            "Bad Gateway",
            f"cannot connect to target server: {error}",
        )
        return {
            "outcome": "error",
            "status_code": 502,
            "bytes_sent": bytes_sent,
            "bytes_from_client": bytes_from_client,
        }


def update_block_stats(state, reason):
    """根据拦截原因更新对应统计项。"""
    if reason.startswith("client_ip_"):
        state.increment("blocked_client")
    elif reason.startswith("url_keyword:"):
        state.increment("blocked_url")
    elif reason == "method_blacklist":
        state.increment("blocked_method")
    else:
        state.increment("blocked_domain")


def handle_client(client_socket, client_address, state):
    """处理单个客户端连接，是认证、限流、规则过滤、缓存、转发的总入口。"""
    config = state.get_config()
    try:
        data = client_socket.recv(BUFFER_SIZE)
        if not data:
            return

        state.increment("total_requests")
        state.increment("bytes_from_clients", len(data))

        request_text = data.decode("iso-8859-1", errors="replace")
        request_info = parse_http_request(request_text)
        state.record_host(request_info["host"])

        print("=" * 60, flush=True)
        print(f"Client: {client_address[0]}:{client_address[1]}", flush=True)
        print(
            f"Request line: {request_info['method']} {request_info['target']} {request_info['version']}",
            flush=True,
        )
        print(f"Host: {request_info['host_header']}", flush=True)
        print(
            "Parsed: "
            f"method={request_info['method']} "
            f"host={request_info['host']} "
            f"port={request_info['port']} "
            f"path={request_info['path']}",
            flush=True,
        )
        print("=" * 60, flush=True)

        # Client network policy runs before authentication and rate limiting so a
        # denied machine cannot consume credentials or rate-limit capacity.
        client_allowed, client_reason = check_client_access_policy(client_address[0], config)
        if not client_allowed:
            update_block_stats(state, client_reason)
            bytes_sent = send_policy_block_response(
                client_socket,
                client_reason,
                request_info,
                client_address[0],
            )
            state.increment("bytes_to_clients", bytes_sent)
            log_event(
                state,
                "BLOCK",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} path={request_info['path']} reason={client_reason}",
            )
            return

        if not check_proxy_auth(request_info, config):
            state.increment("auth_required")
            bytes_sent = send_auth_required_response(client_socket)
            state.increment("bytes_to_clients", bytes_sent)
            log_event(
                state,
                "AUTH_REQUIRED",
                f"client={client_address[0]} method={request_info['method']} host={request_info['host']}",
            )
            return

        # Count authenticated proxy requests. This keeps a 407 authentication challenge
        # from consuming the only permitted request when the limit is set to one.
        rate_config_enabled = config.get("rate_limit_enabled", False)
        if rate_config_enabled:
            max_requests = int(config.get("rate_limit_per_minute", 60))
            window_seconds = int(config.get("rate_limit_window_seconds", 60))
            allowed_by_rate, retry_after, current_count = state.check_rate_limit(
                client_address[0],
                max_requests,
                window_seconds,
            )
            if not allowed_by_rate:
                state.increment("rate_limited")
                bytes_sent = send_simple_response(
                    client_socket,
                    429,
                    "Too Many Requests",
                    f"rate limit exceeded, retry after {retry_after} seconds",
                )
                state.increment("bytes_to_clients", bytes_sent)
                log_event(
                    state,
                    "RATE_LIMIT",
                    f"client={client_address[0]} method={request_info['method']} "
                    f"host={request_info['host']} count={current_count} "
                    f"limit={max_requests} retry_after={retry_after}",
                )
                return
            log_event(
                state,
                "RATE_ALLOW",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} count={current_count} limit={max_requests}",
            )

        allowed, reason = check_access_policy(request_info, config)
        if not allowed:
            update_block_stats(state, reason)
            bytes_sent = send_policy_block_response(
                client_socket,
                reason,
                request_info,
                client_address[0],
            )
            state.increment("bytes_to_clients", bytes_sent)
            log_event(
                state,
                "BLOCK",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} path={request_info['path']} reason={reason}",
            )
            return

        cache_key = None
        if is_cacheable_request(request_info, config):
            cache_key = build_cache_key(request_info)
            cached = state.get_cache(cache_key)
            if cached:
                response_bytes = cached["response_bytes"]
                client_socket.sendall(response_bytes)
                bytes_sent = len(response_bytes)
                state.increment("cache_hits")
                state.increment("allowed_requests")
                state.increment("bytes_to_clients", bytes_sent)
                log_event(
                    state,
                    "CACHE_HIT",
                    f"client={client_address[0]} method={request_info['method']} "
                    f"host={request_info['host']} path={request_info['path']} "
                    f"status={cached.get('status_code', 0)} bytes={bytes_sent}",
                )
                return
            state.increment("cache_misses")
            log_event(
                state,
                "CACHE_MISS",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} path={request_info['path']}",
            )

        if request_info["method"] == "CONNECT":
            result = forward_connect(client_socket, request_info, config)
        else:
            result = forward_http(
                client_socket,
                request_text,
                request_info,
                config,
                client_address[0],
            )

        state.increment("bytes_to_clients", result.get("bytes_sent", 0))
        state.increment("bytes_from_clients", result.get("bytes_from_client", 0))

        if result["outcome"] == "allowed":
            if cache_key and result.get("status_code") == 200 and result.get("response_bytes"):
                state.set_cache(
                    cache_key,
                    result["response_bytes"],
                    result.get("status_code", 0),
                    int(config.get("cache_ttl_seconds", 60)),
                    int(config.get("cache_max_items", 100)),
                )
            state.increment("allowed_requests")
            log_event(
                state,
                "ALLOW",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} path={request_info['path']} "
                f"status={result.get('status_code', 0)} bytes={result.get('bytes_sent', 0)}",
            )
        elif result["outcome"] == "filtered":
            state.increment("filtered_keyword")
            state.record_keyword(result["keyword"])
            log_event(
                state,
                "FILTER",
                f"client={client_address[0]} method={request_info['method']} "
                f"host={request_info['host']} path={request_info['path']} keyword={result['keyword']}",
            )
        elif result["outcome"] == "tunnel":
            state.increment("allowed_requests")
            state.increment("https_tunnels")
            log_event(
                state,
                "CONNECT",
                f"client={client_address[0]} host={request_info['host']} "
                f"port={request_info['port']} bytes={result.get('bytes_sent', 0)}",
            )
        else:
            state.increment("errors")
            log_event(
                state,
                "ERROR",
                f"client={client_address[0]} host={request_info['host']} "
                f"path={request_info['path']} status={result.get('status_code', 0)}",
            )
    except ValueError as error:
        state.increment("bad_requests")
        bytes_sent = send_simple_response(client_socket, 400, "Bad Request", str(error))
        state.increment("bytes_to_clients", bytes_sent)
        log_event(state, "ERROR", f"bad_request client={client_address[0]} error={error}")
    except Exception as error:
        state.increment("errors")
        log_event(state, "ERROR", f"client={client_address[0]} error={error}")
    finally:
        client_socket.close()


class AdminHandler(BaseHTTPRequestHandler):
    """管理后端：提供前端页面、配置/规则 API、统计 API、日志 API 和演示重置 API。"""

    state = None

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_frontend(FRONTEND_INDEX)
            return
        if parsed.path == "/logs.html":
            self.send_frontend(LOG_DETAILS_INDEX)
            return
        if parsed.path == "/changes.html":
            self.send_frontend(CHANGE_DETAILS_INDEX)
            return
        if parsed.path == "/api/config":
            self.send_json({"config": self.state.get_config()})
            return
        if parsed.path == "/api/rules":
            self.send_json(self.state.get_rules())
            return
        if parsed.path == "/api/changes":
            query = parse_qs(parsed.query)
            limit = parse_bounded_query_int(query, "limit", 80, 200)
            self.send_json({"changes": self.state.get_change_history(limit)})
            return
        if parsed.path == "/api/stats":
            self.send_json(self.state.snapshot())
            return
        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            kind = query.get("kind", ["proxy"])[0]
            profile = query.get("profile", [""])[0]
            limit = parse_bounded_query_int(query, "limit", 100, 500)
            config = load_evidence_config(profile) if profile else self.state.get_config()
            logs = read_log_tail(config, kind, limit)
            self.send_json({"kind": kind, "profile": profile, "logs": logs})
            return
        if parsed.path == "/api/logs/query":
            query = parse_qs(parsed.query)
            kind = query.get("kind", ["proxy"])[0]
            profile = query.get("profile", [""])[0]
            events = query.get("event", [""])[0].split(",")
            search = query.get("search", [""])[0]
            limit = parse_bounded_query_int(query, "limit", 200, 1000)
            config = load_evidence_config(profile) if profile else self.state.get_config()
            result = query_log_entries(
                config,
                kind=kind,
                events=events,
                search=search,
                limit=limit,
            )
            result["profile"] = profile
            self.send_json(result)
            return
        if parsed.path == "/api/logs/export.csv":
            query = parse_qs(parsed.query)
            kind = query.get("kind", ["proxy"])[0]
            profile = query.get("profile", [""])[0]
            events = query.get("event", [""])[0].split(",")
            search = query.get("search", [""])[0]
            limit = parse_bounded_query_int(query, "limit", 1000, 5000)
            config = load_evidence_config(profile) if profile else self.state.get_config()
            result = query_log_entries(
                config,
                kind=kind,
                events=events,
                search=search,
                limit=limit,
            )
            self.send_bytes(
                build_log_csv(result),
                "text/csv; charset=utf-8",
                filename=f"{result['kind']}_logs.csv",
            )
            return
        if parsed.path == "/api/evidence/profiles":
            self.send_json({"profiles": list_evidence_profiles()})
            return
        if parsed.path == "/api/evidence/dashboard":
            self.send_json(build_evidence_dashboard())
            return
        if parsed.path == "/api/evidence/changes/query":
            query = parse_qs(parsed.query)
            profile = query.get("profile", ["rules"])[0]
            action = query.get("action", [""])[0]
            rule_type = query.get("rule_type", [""])[0]
            search = query.get("search", [""])[0]
            limit = parse_bounded_query_int(query, "limit", 200, 1000)
            self.send_json(
                query_change_entries(
                    profile,
                    action=action,
                    rule_type=rule_type,
                    search=search,
                    limit=limit,
                )
            )
            return
        if parsed.path == "/api/health":
            self.send_json({"ok": True})
            return
        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlsplit(self.path)
        try:
            if parsed.path == "/api/reload":
                config = self.state.reload_config()
                self.send_json({"ok": True, "config": config})
                return
            if parsed.path == "/api/rules/add":
                payload = self.read_json_body()
                result = self.state.add_list_rule(
                    payload.get("rule_type"),
                    payload.get("value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/delete":
                payload = self.read_json_body()
                result = self.state.delete_list_rule(
                    payload.get("rule_type"),
                    payload.get("value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/update":
                payload = self.read_json_body()
                result = self.state.update_list_rule(
                    payload.get("rule_type"),
                    payload.get("old_value"),
                    payload.get("new_value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/replace":
                payload = self.read_json_body()
                result = self.state.replace_list_rules(
                    payload.get("rule_type"),
                    payload.get("values"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/settings/update":
                payload = self.read_json_body()
                updates = payload.get("settings", payload)
                result = self.state.update_settings(updates)
                self.send_json(result)
                return
            if parsed.path == "/api/cache/clear":
                cleared = self.state.clear_cache()
                self.send_json({"ok": True, "cleared": cleared})
                return
            if parsed.path == "/api/rate/reset":
                cleared = self.state.clear_rate_limits()
                self.send_json({"ok": True, "cleared": cleared})
                return
            if parsed.path == "/api/changes/clear":
                cleared = self.state.clear_change_history()
                self.send_json({"ok": True, "cleared": cleared})
                return
            if parsed.path == "/api/stats/reset":
                self.state.reset_stats()
                self.send_json({"ok": True})
                return
            if parsed.path == "/api/logs/clear":
                cleared = clear_log_files(self.state.get_config())
                self.send_json({"ok": True, "cleared": cleared})
                return
            self.send_error(404, "Not Found")
        except ValueError as error:
            self.send_json({"ok": False, "error": str(error)}, status_code=400)

    def send_frontend(self, page_path=FRONTEND_INDEX):
        """Serve one trusted static administration page from the project frontend."""
        if not page_path.exists():
            self.send_error(404, f"{page_path.name} not found")
            return
        body = page_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        """读取 POST JSON 请求体，兼容 PowerShell 和 CMD 常见 curl 写法。"""
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw_body = self.rfile.read(length).decode("utf-8")
        body_text = raw_body.strip()
        # CMD 中单引号不会被当作字符串边界，用户直接复制 PowerShell 写法时，
        # 后端会收到一整个被单引号包住的字符串；这里兼容这种课堂验收常见误用。
        if len(body_text) >= 2 and body_text[0] == "'" and body_text[-1] == "'":
            body_text = body_text[1:-1]
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError as error:
            try:
                payload = parse_loose_json_object(body_text)
            except ValueError as loose_error:
                raise ValueError(
                    f"invalid JSON body: {error}; loose parser: {loose_error}"
                ) from error
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def send_json(self, payload, status_code=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8", status_code=status_code)

    def send_bytes(self, body, content_type, status_code=200, filename=""):
        """Send a byte response; filename enables browser downloads for exported evidence."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_admin_server(host, port, state):
    """启动管理服务，默认监听 8088，前端和 API 都从这里提供。"""
    handler_class = type("BoundAdminHandler", (AdminHandler,), {"state": state})
    server = ThreadingHTTPServer((host, port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Admin dashboard started at http://{host}:{port}/", flush=True)
    return server


def start_server(host, port, state=None):
    """启动代理服务，默认监听 8080，为每个客户端连接创建处理线程。"""
    state = ensure_state(state)
    config = state.get_config()

    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_socket.bind((host, port))
    listen_socket.listen(int(config.get("max_clients", 50)))

    print(f"Proxy started at {host}:{port}", flush=True)
    print("Proxy features: forwarding, HTTPS CONNECT, domain blocking, URL/method blocking, keyword filtering.", flush=True)
    print(f"Mode: {config.get('mode', 'blacklist')}", flush=True)
    print(f"Blocked domains: {len(config.get('blocked_domains', []))}", flush=True)
    print(f"Blocked client IP rules: {len(config.get('blocked_client_ips', []))}", flush=True)
    print(f"Blocked URL keywords: {len(config.get('blocked_url_keywords', []))}", flush=True)
    print(f"Blocked content keywords: {len(config.get('blocked_content_keywords', []))}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            client_socket, client_address = listen_socket.accept()
            worker = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address, state),
                daemon=True,
            )
            worker.start()
    except KeyboardInterrupt:
        print("\nProxy stopped.", flush=True)
    finally:
        listen_socket.close()


def main():
    args = parse_args()
    config = load_config(args.config)
    state = RuntimeState(config, args.config)

    host = args.host or config.get("listen_host", "127.0.0.1")
    port = args.port or int(config.get("listen_port", 8080))
    admin_host = args.admin_host or config.get("admin_host", "127.0.0.1")
    admin_port = args.admin_port or int(config.get("admin_port", 8088))

    if not args.no_admin:
        start_admin_server(admin_host, admin_port, state)

    start_server(host, port, state)


if __name__ == "__main__":
    main()
