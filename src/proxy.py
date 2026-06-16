"""课程实验的 Web 正向代理主程序。

这个文件同时包含两个服务：
1. 代理服务，默认监听 127.0.0.1:8080。浏览器或 curl 把请求交给它后，
   它负责解析请求、检查过滤规则、连接真实目标服务器，再把响应返回给客户端。
2. 管理服务，默认监听 127.0.0.1:8088。它给前端页面和命令行工具提供
   规则增删改查、运行设置、日志查询、缓存清理等 HTTP API。

实现上没有使用现成代理框架，而是直接使用 Python socket 处理 TCP 连接。
这样更适合课程展示：可以清楚看到 HTTP 请求行如何被解析、代理请求如何被
改写成普通服务器请求，以及域名/URL/正文关键字过滤分别发生在哪个阶段。
"""

import argparse
import base64
import fnmatch
import gzip
from html import escape
import ipaddress
import json
import select
import socket
import threading
import time
import zlib
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
    # 直接运行 `python src/proxy.py` 时，Python 会把 src 而非项目根目录加入模块路径。
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


# =============================================================================
# 1. 运行状态区：保存配置、统计、缓存、限流和规则变更历史
# =============================================================================


class RuntimeState:
    """保存代理运行期间的共享状态：配置、统计、缓存、限流桶和排行数据。"""

    def __init__(self, config, config_path=""):
        """
        初始化代理运行期间的共享状态。

        Args:
            config: 从 JSON 文件读入的当前规则和运行参数，支持热更新。
            config_path: 配置文件路径，用于热更新时写回磁盘。

        Attributes:
            config: 规则和运行参数的内存副本。
            config_path: 配置文件路径。
            started_at: 代理启动时间戳。
            lock: 线程锁，保护统计、缓存、限流桶等共享数据。
            stats: 请求统计计数器（按结果类型分类）。
            host_hits: 按主机名的请求命中次数排行。
            keyword_hits: 按关键词的过滤命中次数排行。
            cache: 上游响应的原始字节缓存（支持规则热更新）。
            rate_limits: 按客户端 IP 的访问频率计数。
            change_history: 规则变更历史记录（JSONL 持久化）。
        """
        # config 是从 JSON 文件读入的当前规则和运行参数；管理 API 修改规则时，
        # 会同时更新这里的内存副本并写回配置文件，所以代理无需重启即可生效。
        self.config = config
        self.config_path = config_path
        self.started_at = time.time()
        # 代理服务是多线程模型：每个客户端连接一个线程。
        # 统计、缓存、限流桶等共享数据必须用锁保护，避免并发读写时数据错乱。
        self.lock = threading.Lock()
        # 首页统计卡片的数据来源。每处理一个请求，handle_client 会按结果更新对应字段。
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
        # cache 保存的是“上游服务器返回的原始 HTTP 响应字节”，不是过滤后的页面。
        # 这样命中缓存时仍然可以按最新正文规则重新检查，保证规则热更新有效。
        self.cache = {}
        # rate_limits 按客户端 IP 存固定窗口计数，用于访问频率限制模块。
        self.rate_limits = {}
        # JSONL 持久化历史使前端在代理重启后仍能显示 CLI/API 变更。
        self.change_history = self._load_change_history()

    def _load_change_history(self):
        """加载最近的规则和运行设置变更，供管理前端回显。

        Returns:
            list[dict]: 按时间倒序排列的最近变更记录。配置未启用
            `change_log_file` 或文件不存在时返回空列表。
        """
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
        """追加一条 JSONL 变更记录，调用方必须已经持有 self.lock。

        Args:
            entry: 已构造好的规则或运行设置变更记录。
        """
        path_text = self.config.get("change_log_file")
        if not path_text:
            return
        path = resolve_project_path(path_text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as change_file:
            change_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_config(self):
        """读取当前运行配置的浅拷贝。

        Returns:
            dict: 当前内存配置副本。调用方修改返回值不会直接影响运行状态。
        """
        with self.lock:
            return dict(self.config)

    def reload_config(self):
        """从配置文件重新加载规则，用于管理前端的“重新加载配置”按钮。

        Returns:
            dict: 重新加载后的完整配置。
        """
        if not self.config_path:
            return self.get_config()
        config = load_config(self.config_path)
        with self.lock:
            old_content_rules = list(self.config.get("blocked_content_keywords", []))
            self.config = config
            if old_content_rules != list(config.get("blocked_content_keywords", [])):
                # 缓存保存的是上游原始响应；正文规则变化后不能继续直接复用旧结果。
                self.cache.clear()
        return config

    def _save_config_locked(self):
        """把当前内存配置写回 JSON 文件，调用方必须已经持有 self.lock。

        Returns:
            bool: 成功写回配置文件返回 True；没有配置路径时返回 False。
        """
        if not self.config_path:
            return False
        config_path = resolve_project_path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as config_file:
            json.dump(self.config, config_file, ensure_ascii=False, indent=2)
            config_file.write("\n")
        return True

    def get_rules(self):
        """返回当前可编辑规则，用于前端和 curl 查询。

        Returns:
            dict: 包含规则模式和规则组列表的响应结构。
        """
        with self.lock:
            return build_rules_payload(self.config)

    def get_change_history(self, limit=80):
        """返回最近变更，使 API/CLI 修改能够在管理前端回显。

        Args:
            limit: 最多返回多少条记录，后端会限制在 1 到 200 之间。

        Returns:
            list[dict]: 最近的规则或运行设置变更记录。
        """
        with self.lock:
            limit = max(1, min(int(limit), 200))
            return [dict(item) for item in self.change_history[:limit]]

    def query_changes(self, action="", rule_type="", search="", limit=200):
        """查询当前运行期间的变更历史，供规则变更总览页面筛选展示。

        Args:
            action: 可选操作类型，例如 add、delete、update、replace、settings。
            rule_type: 可选规则组名称，例如 blocked_domains。
            search: 可选全文搜索关键字。
            limit: 最多返回多少条匹配记录。

        Returns:
            dict: 包含总数、匹配数、分类统计和记录列表的查询结果。
        """
        normalized_action = str(action or "").strip().lower()
        normalized_rule_type = str(rule_type or "").strip()
        search_lower = str(search or "").strip().lower()
        bounded_limit = max(1, min(int(limit), 1000))
        with self.lock:
            entries = [dict(item) for item in self.change_history]

        action_counts = {}
        rule_type_counts = {}
        matched_entries = []
        for entry in entries:
            entry_action = str(entry.get("action", "unknown"))
            entry_rule_type = str(entry.get("rule_type", "settings"))
            action_counts[entry_action] = action_counts.get(entry_action, 0) + 1
            rule_type_counts[entry_rule_type] = rule_type_counts.get(entry_rule_type, 0) + 1
            if normalized_action and entry_action != normalized_action:
                continue
            if normalized_rule_type and entry_rule_type != normalized_rule_type:
                continue
            if search_lower:
                serialized = json.dumps(entry, ensure_ascii=False).lower()
                if search_lower not in serialized:
                    continue
            matched_entries.append(entry)

        return {
            "profile": "current",
            "action": normalized_action,
            "rule_type": normalized_rule_type,
            "search": search,
            "total": len(entries),
            "matched": len(matched_entries),
            "action_counts": action_counts,
            "rule_type_counts": rule_type_counts,
            "entries": matched_entries[:bounded_limit],
        }

    def _record_change_locked(self, action, result):
        """保存一条管理操作记录，调用方必须已经持有 self.lock。

        Args:
            action: 操作类型，例如 add、delete、settings。
            result: 规则修改或设置修改的执行结果。

        Returns:
            dict: 写入内存和 JSONL 文件的变更记录。
        """
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "changed": bool(result.get("changed", False)),
            "saved": bool(result.get("saved", False)),
        }
        for key in (
            "rule_type",
            "value",
            "old_value",
            "new_value",
            "values",
            "settings",
            "cache_cleared",
        ):
            if key in result:
                entry[key] = result[key]
        self.change_history.insert(0, entry)
        self.change_history = self.change_history[:100]
        self._append_change_history_locked(entry)
        return entry

    def _clear_cache_for_rule_change_locked(self, rule_type, changed):
        """正文过滤规则变化后清空旧响应缓存，调用方必须持有 self.lock。

        Args:
            rule_type: 被修改的规则组名称。
            changed: 规则组内容是否真的发生变化。

        Returns:
            int: 被清理的缓存条目数量。
        """
        if changed and rule_type == "blocked_content_keywords":
            cleared = len(self.cache)
            self.cache.clear()
            return cleared
        return 0

    def add_list_rule(self, rule_type, value):
        """向指定规则列表新增一条规则，并立即保存到配置文件。

        Args:
            rule_type: 规则组名称，例如 `blocked_domains`。
            value: 要新增的规则值，例如 `*.bing.com`。

        Returns:
            dict: 包含 ok、changed、saved、values、history_entry 等字段的结果。

        Raises:
            ValueError: 规则组不存在或规则值为空/非法。
        """
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
                "cache_cleared": self._clear_cache_for_rule_change_locked(rule_type, changed),
            }
            result["history_entry"] = self._record_change_locked("add", result)
            return result

    def delete_list_rule(self, rule_type, value):
        """从指定规则列表删除一条规则，并立即保存到配置文件。

        Args:
            rule_type: 规则组名称。
            value: 要删除的规则值。

        Returns:
            dict: 删除结果。即使目标不存在，也会返回 ok=True 和 changed=False。

        Raises:
            ValueError: 规则组不存在或规则值非法。
        """
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
                "cache_cleared": self._clear_cache_for_rule_change_locked(rule_type, changed),
            }
            result["history_entry"] = self._record_change_locked("delete", result)
            return result

    def update_list_rule(self, rule_type, old_value, new_value):
        """修改指定规则列表中的一条规则，并立即保存到配置文件。

        Args:
            rule_type: 规则组名称。
            old_value: 要被替换的旧规则值。
            new_value: 替换后的新规则值。

        Returns:
            dict: 修改结果和最新规则组。

        Raises:
            ValueError: 旧规则不存在、新规则重复、规则组非法或规则值非法。
        """
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
                "cache_cleared": self._clear_cache_for_rule_change_locked(rule_type, changed),
            }
            result["history_entry"] = self._record_change_locked("update", result)
            return result

    def replace_list_rules(self, rule_type, values):
        """替换某一个规则组，适合命令行一次性重设整组过滤条件。

        Args:
            rule_type: 规则组名称。
            values: 新规则值列表。

        Returns:
            dict: 替换结果和替换后的完整规则组。

        Raises:
            ValueError: 规则组非法，或 values 不是列表。
        """
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
                "cache_cleared": self._clear_cache_for_rule_change_locked(rule_type, changed),
            }
            result["history_entry"] = self._record_change_locked("replace", result)
            return result

    def update_settings(self, updates):
        """更新模式、缓存、认证、限流等简单配置项，并保存到配置文件。

        Args:
            updates: 设置项字典，例如 `{"rate_limit_enabled": True}`。

        Returns:
            dict: 设置修改结果、最新设置和变更历史记录。

        Raises:
            ValueError: 设置项不支持、类型不合法或数值越界。
        """
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
            cache_setting_changed = changed and any(
                key in {"cache_enabled", "cache_ttl_seconds", "cache_max_items"}
                for key in normalized_updates
            )
            self.config.update(normalized_updates)
            if any(key.startswith("rate_limit_") for key in normalized_updates):
                self.rate_limits.clear()
            cache_cleared = len(self.cache) if cache_setting_changed else 0
            if cache_setting_changed:
                # 缓存参数改变后清空旧条目，防止继续使用旧 TTL 或旧启用状态的数据。
                self.cache.clear()
            saved = self._save_config_locked()
            result = {
                "ok": True,
                "changed": changed,
                "saved": saved,
                "cache_cleared": cache_cleared,
                "settings": {
                    key: self.config.get(key)
                    for key in CONFIG_SETTING_FIELDS
                },
            }
            result["history_entry"] = self._record_change_locked("settings", result)
            return result

    def increment(self, key, amount=1):
        """增加一个统计计数器。

        Args:
            key: 统计字段名称。
            amount: 增加的数量，默认加 1。
        """
        with self.lock:
            self.stats[key] = self.stats.get(key, 0) + amount

    def record_host(self, host):
        """记录目标主机访问次数，用于首页 Top Hosts 排行。

        Args:
            host: 目标服务器主机名。
        """
        with self.lock:
            self.host_hits[host] = self.host_hits.get(host, 0) + 1

    def record_keyword(self, keyword):
        """记录正文过滤关键词命中次数。

        Args:
            keyword: 命中的正文过滤关键词。
        """
        with self.lock:
            self.keyword_hits[keyword] = self.keyword_hits.get(keyword, 0) + 1

    def get_cache(self, key):
        """读取 HTTP GET 缓存；如果缓存过期，自动删除并返回 None。

        Args:
            key: 由 host、port、path 组成的缓存键。

        Returns:
            dict | None: 未过期缓存条目；不存在或过期时返回 None。
        """
        with self.lock:
            entry = self.cache.get(key)
            if not entry:
                return None
            if entry["expires_at"] < time.time():
                del self.cache[key]
                return None
            return dict(entry)

    def set_cache(self, key, response_bytes, status_code, ttl_seconds, max_items):
        """写入 HTTP GET 缓存，并在超过最大条目数时删除最早的缓存。

        Args:
            key: 缓存键。
            response_bytes: 上游服务器返回的原始 HTTP 响应字节。
            status_code: 上游响应状态码。
            ttl_seconds: 缓存有效期。
            max_items: 最多缓存条目数。
        """
        if ttl_seconds <= 0 or max_items <= 0:
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
        """按客户端 IP 做固定时间窗口限流。

        Args:
            client_ip: 客户端 IP 地址。
            max_requests: 一个窗口内允许的最大请求数。
            window_seconds: 时间窗口长度。

        Returns:
            tuple[bool, int, int]: 是否允许、被拒绝时建议等待秒数、当前窗口计数。
        """
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
        """清空缓存，方便验收时重新演示第一次 MISS、第二次 HIT。

        Returns:
            int: 被清空的缓存条目数。
        """
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            return count

    def clear_rate_limits(self):
        """清空限流计数桶，让访问频率设置修改后可以马上重新演示。

        Returns:
            int: 被清空的限流客户端数量。
        """
        with self.lock:
            count = len(self.rate_limits)
            self.rate_limits.clear()
            return count

    def clear_change_history(self):
        """清空内存与 JSONL 文件中的规则和运行设置变更历史。

        Returns:
            int: 清空前的变更记录数量。
        """
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
        """返回管理首页使用的实时统计快照，并派生跨类别的总拦截数。

        Returns:
            dict: 包含 started_at、uptime_seconds、stats、top_hosts、
            keyword_hits 的首页统计数据。
        """
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


# =============================================================================
# 2. 参数解析与 HTTP 报文解析区
# =============================================================================


def parse_args():
    """解析代理进程启动参数。

    Returns:
        argparse.Namespace: 包含代理端口、管理端口、配置文件路径等参数。
    """
    parser = argparse.ArgumentParser(description="Web proxy server with admin dashboard")
    parser.add_argument("--host", default=None, help="Proxy listen host")
    parser.add_argument("--port", type=int, default=None, help="Proxy listen port")
    parser.add_argument("--config", default="config.example.json", help="Config file path")
    parser.add_argument("--admin-host", default=None, help="Admin dashboard listen host")
    parser.add_argument("--admin-port", type=int, default=None, help="Admin dashboard listen port")
    parser.add_argument("--no-admin", action="store_true", help="Disable admin dashboard")
    return parser.parse_args()


def ensure_state(state_or_config=None):
    """确保传入对象是 RuntimeState。

    Args:
        state_or_config: 已有 RuntimeState，或测试代码直接传入的配置 dict。

    Returns:
        RuntimeState: 可供代理处理流程使用的运行状态对象。
    """
    if isinstance(state_or_config, RuntimeState):
        return state_or_config
    return RuntimeState(state_or_config or {})


def find_header(headers, name):
    """在原始请求头/响应头行中查找一个头字段，大小写不敏感。

    Args:
        headers: 原始 HTTP 头部行列表。
        name: 要查找的头字段名称，例如 `Host`。

    Returns:
        str: 头字段值；不存在时返回空字符串。
    """
    prefix = name.lower() + ":"
    for line in headers:
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def parse_bounded_query_int(query, name, default, maximum):
    """读取整数查询参数，并限制异常值和过大结果集。

    Args:
        query: `parse_qs()` 解析后的查询参数字典。
        name: 参数名称。
        default: 缺省值或解析失败时使用的值。
        maximum: 允许的最大值。

    Returns:
        int: 限制在 1 到 maximum 之间的整数。
    """
    try:
        value = int(query.get(name, [str(default)])[0])
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def parse_http_request(request_text):
    """解析客户端发来的 HTTP/代理请求，提取方法、目标主机、端口、路径和请求头。

    浏览器使用正向代理时，请求格式与普通 Web 服务器看到的格式略有不同：
    - 明文 HTTP：请求行通常是 `GET http://example.com/a.html HTTP/1.1`，
      代理需要从完整 URL 中拆出 host、port、path。
    - HTTPS：浏览器先发送 `CONNECT example.com:443 HTTP/1.1`，
      代理只知道目标主机和端口，后续正文是 TLS 加密字节流。
    - 本地测试或部分工具也可能发送普通格式 `GET /a.html HTTP/1.1`，
      此时要从 Host 头补出目标主机。
    Args:
        request_text: 从客户端 socket 收到并按 iso-8859-1 解码后的 HTTP 请求文本。

    Returns:
        dict: 包含 method、target、version、host、port、path、host_header、
        headers 的请求信息字典。

    Raises:
        ValueError: 请求为空、请求行格式错误、Host 缺失或目标主机缺失。
    """
    lines = request_text.splitlines()
    if not lines:
        raise ValueError("empty request")

    parts = lines[0].split()
    if len(parts) != 3:
        raise ValueError(f"invalid request line: {lines[0]}")

    method, target, version = parts
    host_header = find_header(lines[1:], "Host")

    if method.upper() == "CONNECT":
        # CONNECT 只建立 TCP 隧道，不会出现 URL 路径；默认端口按 HTTPS 使用 443。
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
        # 代理格式的明文 HTTP 请求：请求行里带完整 URL，需要改写后再发给真实服务器。
        parsed = urlsplit(target)
        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
    else:
        # 普通源服务器格式请求，主要用于本地测试；目标主机来自 Host 请求头。
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


# =============================================================================
# 3. 本代理生成响应区：错误页、403 拦截页、407 认证挑战
# =============================================================================


def send_simple_response(client_socket, status_code, reason, message):
    """向客户端返回简单文本响应，供 400/403/429/502/504 等错误场景使用。

    Args:
        client_socket: 客户端连接 socket。
        status_code: HTTP 状态码。
        reason: HTTP 原因短语，例如 `Bad Gateway`。
        message: 响应正文中的说明文本。

    Returns:
        int: 发送给客户端的响应字节数。
    """
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
    """构造替代原网页的 403 拦截提示页，并提供可展开的具体命中信息。

    Args:
        reason: 拦截原因，例如 `domain_blacklist` 或 `url_keyword:game`。
        request_info: 当前请求信息字典，用于在提示页中展示目标地址。
        client_ip: 客户端 IP 地址。
        detail: 额外命中信息；为空时使用 reason。

    Returns:
        bytes: 完整 HTTP/1.1 403 响应字节，可直接发送给浏览器。
    """
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
    """发送浏览器可直接展示的访问策略拦截页。

    Args:
        client_socket: 客户端连接 socket。
        reason: 拦截原因。
        request_info: 当前请求信息。
        client_ip: 客户端 IP 地址。
        detail: 额外命中信息。

    Returns:
        int: 发送给客户端的字节数。
    """
    response = build_policy_block_response(reason, request_info, client_ip, detail)
    client_socket.sendall(response)
    return len(response)


def send_auth_required_response(client_socket):
    """返回代理认证挑战响应，curl 或浏览器收到后会知道需要代理用户名密码。

    Args:
        client_socket: 客户端连接 socket。

    Returns:
        int: 发送给客户端的响应字节数。
    """
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


# =============================================================================
# 4. 请求阶段访问控制区：客户端 IP、域名、URL、方法、代理认证
# =============================================================================


def domain_matches(host, patterns):
    """匹配域名规则，支持完整域名、后缀域名和显式通配符。

    设计约定：
    - `www.baidu.com` 只匹配这个完整主机；
    - `baidu.com` 匹配 `baidu.com` 及其子域名，例如 `www.baidu.com`；
    - `*.baidu.com`、`*baidu*` 使用 fnmatch 通配符匹配；
    - 普通短词 `baidu` 不自动当作包含匹配，避免误伤其他无关域名。
    Args:
        host: 当前请求的目标主机名。
        patterns: 配置中的域名规则列表。

    Returns:
        bool: 目标主机命中任意规则时返回 True。
    """
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
    """判断客户端地址是否命中单个 IP 或 CIDR 网段规则。

    Args:
        client_ip: 客户端 IP 地址。
        patterns: 配置中的 IP 或 CIDR 规则列表。

    Returns:
        bool: 命中任意 IP/CIDR 规则时返回 True。
    """
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
            # 手工修改配置时出现的非法条目会被安全忽略。
            continue
    return False


def check_client_access_policy(client_ip, config):
    """在认证和目标过滤前执行客户端 IP 黑白名单策略。

    Args:
        client_ip: 客户端 IP 地址。
        config: 当前运行配置。

    Returns:
        tuple[bool, str]: 是否允许访问代理，以及 `allow` 或具体拦截原因。
    """
    blocked_clients = config.get("blocked_client_ips", [])
    if client_ip_matches(client_ip, blocked_clients):
        return False, "client_ip_blacklist"

    allowed_clients = config.get("allowed_client_ips", [])
    if allowed_clients and not client_ip_matches(client_ip, allowed_clients):
        return False, "client_ip_not_allowed"
    return True, "allow"


def check_access_policy(request_info, config):
    """执行访问控制：方法黑名单、白名单模式、域名黑名单和 URL 关键字拦截。

    这里处理的是“请求到达上游服务器之前”就能判断的规则：
    - HTTP 方法：例如禁止 DELETE/PUT；
    - 域名黑白名单：只看目标 host；
    - URL 关键字：看 host、path、query 和原始 target。

    正文关键字过滤不在这里做，因为正文需要先向目标服务器取回响应，
    再在 filter_response_content 中检查。
    Args:
        request_info: `parse_http_request()` 返回的请求信息。
        config: 当前运行配置。

    Returns:
        tuple[bool, str]: 是否允许继续转发，以及 `allow` 或具体拦截原因。
    """
    host = request_info["host"]
    method = request_info["method"]
    path = request_info["path"]
    target = request_info["target"]
    mode = config.get("mode", "blacklist").lower()

    blocked_methods = [item.upper() for item in config.get("blocked_methods", [])]
    if method in blocked_methods:
        return False, "method_blacklist"

    if mode == "whitelist":
        # 白名单模式下，不在 allowed_domains 中的目标一律拒绝。
        allowed_domains = config.get("allowed_domains", [])
        if not domain_matches(host, allowed_domains):
            return False, "domain_not_in_whitelist"

    # 黑名单检查在白名单之后执行；如果二者都配置，黑名单仍可进一步收紧访问范围。
    blocked_domains = config.get("blocked_domains", [])
    if domain_matches(host, blocked_domains):
        return False, "domain_blacklist"

    # 明文 HTTP 可以看到完整路径和查询参数，因此能拦 /game/index.html 这类 URL 片段。
    # HTTPS 的具体路径在 TLS 内部，代理不解密，只能看到 CONNECT 目标域名。
    searchable_url = f"{host}{path} {target}".lower()
    for keyword in config.get("blocked_url_keywords", []):
        if keyword.lower() in searchable_url:
            return False, f"url_keyword:{keyword}"

    return True, "allow"


def check_proxy_auth(request_info, config):
    """检查 Proxy-Authorization Basic 认证头，认证关闭时直接放行。

    代理认证与普通网站登录不同：浏览器会把用户名密码放在
    Proxy-Authorization 头里发给代理，代理验证通过后才继续访问目标网站。
    这个头不会转发给上游服务器，避免把代理密码泄露给外部网站。
    Args:
        request_info: 当前请求信息，主要读取 headers 中的 Proxy-Authorization。
        config: 当前运行配置，包含 proxy_auth_enabled 和 proxy_auth_users。

    Returns:
        bool: 认证关闭或用户名密码正确时返回 True，否则返回 False。
    """
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


# =============================================================================
# 5. 缓存与 HTTP 响应解析区：判断缓存、解析状态码、接收完整响应
# =============================================================================


def is_cacheable_request(request_info, config):
    """判断当前请求是否可以进入 HTTP GET 缓存。

    Args:
        request_info: 当前请求信息。
        config: 当前运行配置。

    Returns:
        bool: 缓存开启且请求方法为 GET 时返回 True。
    """
    return bool(config.get("cache_enabled", False)) and request_info["method"] == "GET"


def build_cache_key(request_info):
    """构造缓存键。

    Args:
        request_info: 当前请求信息。

    Returns:
        str: 由 host、port、path 组成的缓存键。
    """
    return f"{request_info['host']}:{request_info['port']}{request_info['path']}"


def is_text_content_type(content_type):
    """判断响应类型是否适合做正文关键字扫描。

    Args:
        content_type: HTTP Content-Type 头字段值。

    Returns:
        bool: 文本、HTML、CSS、JS、JSON 等内容返回 True。
    """
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
    """在响应头行中查找一个头字段。

    Args:
        header_lines: 响应头行列表。
        name: 要查找的头字段名。

    Returns:
        str: 头字段值；不存在时返回空字符串。
    """
    return find_header(header_lines, name)


def parse_status_code(response_bytes):
    """从 HTTP 响应状态行中取出状态码，例如 200、403、404。

    Args:
        response_bytes: 完整或部分 HTTP 响应字节。

    Returns:
        int: 解析到的状态码；失败时返回 0。
    """
    first_line = response_bytes.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    parts = first_line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def decode_chunked_body(body):
    """解析 HTTP chunked 正文，仅用于关键词检查；解析失败时保留原始正文。

    Args:
        body: 响应体字节，可能是 chunked 编码。

    Returns:
        bytes: 解码后的连续正文；解析失败时返回原始 body。
    """
    chunks = []
    position = 0
    try:
        while True:
            line_end = body.find(b"\r\n", position)
            if line_end < 0:
                return body
            size_text = body[position:line_end].split(b";", 1)[0].strip()
            size = int(size_text, 16)
            position = line_end + 2
            if size == 0:
                return b"".join(chunks)
            chunk_end = position + size
            if chunk_end + 2 > len(body) or body[chunk_end:chunk_end + 2] != b"\r\n":
                return body
            chunks.append(body[position:chunk_end])
            position = chunk_end + 2
    except ValueError:
        return body


def chunked_body_is_complete(body):
    """判断 chunked 响应是否已经收到 0 长度结束块及可选尾部字段。

    Args:
        body: chunked 响应体字节。

    Returns:
        bool: 收到完整结束块时返回 True。
    """
    position = 0
    try:
        while True:
            line_end = body.find(b"\r\n", position)
            if line_end < 0:
                return False
            size_text = body[position:line_end].split(b";", 1)[0].strip()
            size = int(size_text, 16)
            position = line_end + 2
            if size == 0:
                # 无尾部字段时紧跟一个 CRLF；有尾部字段时以空行结束。
                return body[position:position + 2] == b"\r\n" or b"\r\n\r\n" in body[position:]
            chunk_end = position + size
            if chunk_end + 2 > len(body) or body[chunk_end:chunk_end + 2] != b"\r\n":
                return False
            position = chunk_end + 2
    except ValueError:
        return False


def http_response_is_complete(response_bytes, request_method="GET"):
    """按 HTTP 响应头判断报文是否完整，避免依赖目标服务器主动关闭连接。

    Args:
        response_bytes: 已接收的 HTTP 响应字节。
        request_method: 原请求方法，HEAD/204/304 没有普通正文。

    Returns:
        bool: 响应已经完整时返回 True。
    """
    if b"\r\n\r\n" not in response_bytes:
        return False

    header_bytes, body = response_bytes.split(b"\r\n\r\n", 1)
    header_lines = header_bytes.decode("iso-8859-1", errors="replace").splitlines()
    status_code = parse_status_code(response_bytes)

    if request_method.upper() == "HEAD" or status_code in {204, 304}:
        return True

    transfer_encoding = response_header_value(header_lines, "Transfer-Encoding").lower()
    if "chunked" in transfer_encoding:
        return chunked_body_is_complete(body)

    content_length = response_header_value(header_lines, "Content-Length").strip()
    if content_length:
        try:
            return len(body) >= int(content_length)
        except ValueError:
            return False

    # 没有长度信息的 HTTP/1.x 响应只能由连接关闭标记结束。
    return False


def response_has_explicit_length(response_bytes):
    """判断响应是否声明了必须完整接收的 Content-Length 或 chunked 边界。

    Args:
        response_bytes: HTTP 响应字节。

    Returns:
        bool: 响应头存在 Content-Length 或 Transfer-Encoding: chunked。
    """
    if b"\r\n\r\n" not in response_bytes:
        return False
    header_bytes = response_bytes.split(b"\r\n\r\n", 1)[0]
    header_lines = header_bytes.decode("iso-8859-1", errors="replace").splitlines()
    return bool(
        response_header_value(header_lines, "Content-Length").strip()
        or "chunked" in response_header_value(header_lines, "Transfer-Encoding").lower()
    )


def receive_http_response(upstream_socket, request_method="GET"):
    """接收一个完整 HTTP 响应；有报文边界时收到正文后立即返回。

    代理必须先尽量收完整上游响应，才能做正文关键词过滤和缓存。
    对 Content-Length 或 chunked 响应，本函数按 HTTP 协议边界判断结束；
    对没有长度信息的旧式响应，只能等待服务器关闭连接或超时。
    Args:
        upstream_socket: 与目标 Web 服务器建立的 socket。
        request_method: 原请求方法，用于判断 HEAD/204/304 等无正文场景。

    Returns:
        bytes: 从目标服务器接收到的 HTTP 响应字节。

    Raises:
        socket.timeout: 目标服务器长时间未返回完整响应。
    """
    response = bytearray()
    while True:
        try:
            chunk = upstream_socket.recv(BUFFER_SIZE)
        except socket.timeout:
            # 少数旧式服务器没有长度头且保持连接；已收到正文时保留可用响应。
            if response and b"\r\n\r\n" in response and not response_has_explicit_length(response):
                return bytes(response)
            raise
        if not chunk:
            return bytes(response)
        response.extend(chunk)
        if http_response_is_complete(response, request_method):
            return bytes(response)


# =============================================================================
# 6. 响应阶段正文过滤区：只处理 HTTP 明文文本响应
# =============================================================================


def decode_text_body(body, content_type):
    """按响应声明字符集解码正文，并兼容常见 UTF-8、GB18030 页面。

    关键词匹配必须在字符串层面完成，所以需要把字节正文转换成文本。
    如果页面没有声明 charset，就按常见顺序尝试，保证国内网页和英文网页
    都有较高概率被正确识别。
    Args:
        body: 已解压、已去 chunked 的响应体字节。
        content_type: Content-Type 头字段，用于读取 charset。

    Returns:
        str: 解码后的正文文本。
    """
    declared_charset = ""
    for parameter in content_type.split(";")[1:]:
        name, separator, value = parameter.partition("=")
        if separator and name.strip().lower() == "charset":
            declared_charset = value.strip().strip("\"'")
            break

    encodings = [declared_charset, "utf-8", "gb18030", "iso-8859-1"]
    tried = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if not normalized or normalized in tried:
            continue
        tried.add(normalized)
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def filter_response_content(response_bytes, config, request_info=None, client_ip=""):
    """对 HTTP 明文文本响应做正文关键字过滤，二进制内容直接放行。

    工作流程：
    1. 拆分响应头和响应体；
    2. 只检查 text/html、text/plain、json、javascript 等文本响应；
    3. 如果正文使用 chunked、gzip、deflate，先解码成可检查的原始文本；
    4. 命中 blocked_content_keywords 后，不把原网页发给浏览器，
       而是构造一个代理生成的 403 HTML 提示页。

    注意：HTTPS 正文经过 TLS 加密，本代理没有做中间人解密，因此无法检查
    HTTPS 页面正文，只能检查 CONNECT 目标域名。
    Args:
        response_bytes: 上游服务器返回的完整 HTTP 响应字节。
        config: 当前运行配置，读取 blocked_content_keywords。
        request_info: 当前请求信息，用于生成拦截提示页。
        client_ip: 客户端 IP 地址，用于生成拦截提示页。

    Returns:
        tuple[bytes, str | None]: 处理后的响应字节，以及命中的正文关键词。
        未命中时返回原响应和 None。
    """
    if b"\r\n\r\n" not in response_bytes:
        return response_bytes, None

    header_bytes, body = response_bytes.split(b"\r\n\r\n", 1)
    header_text = header_bytes.decode("iso-8859-1", errors="replace")
    header_lines = header_text.splitlines()

    content_type = response_header_value(header_lines, "Content-Type")
    content_encoding = response_header_value(header_lines, "Content-Encoding")
    transfer_encoding = response_header_value(header_lines, "Transfer-Encoding")

    if not is_text_content_type(content_type):
        return response_bytes, None

    # chunked 是 HTTP 分块传输编码；关键词检查时需要把多个 chunk 还原成连续正文。
    inspection_body = decode_chunked_body(body) if "chunked" in transfer_encoding.lower() else body
    encoding = content_encoding.strip().lower()
    try:
        # 很多网站会 gzip 压缩文本响应。若不先解压，关键字在压缩字节中无法匹配。
        if encoding == "gzip":
            inspection_body = gzip.decompress(inspection_body)
        elif encoding == "deflate":
            inspection_body = zlib.decompress(inspection_body)
        elif encoding not in ("", "identity", "none"):
            # 未支持的压缩格式保持原响应，避免破坏客户端可用内容。
            return response_bytes, None
    except (OSError, zlib.error):
        return response_bytes, None

    body_text = decode_text_body(inspection_body, content_type)
    body_text_lower = body_text.lower()

    for keyword in config.get("blocked_content_keywords", []):
        if keyword.lower() in body_text_lower:
            # 返回的不是原服务器响应，而是本代理生成的 403 拦截页；
            # 浏览器中看到的“详细信息”也来自这里。
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


# =============================================================================
# 7. 代理转发区：请求改写、HTTP 转发、HTTPS CONNECT 隧道
# =============================================================================


def split_request(request_text):
    """把客户端请求分为头部行和可选请求体，用于改写上游请求。

    Args:
        request_text: 客户端发来的原始请求文本。

    Returns:
        tuple[list[str], str]: 请求头行列表和请求体文本。
    """
    if "\r\n\r\n" in request_text:
        header_text, body = request_text.split("\r\n\r\n", 1)
    elif "\n\n" in request_text:
        header_text, body = request_text.split("\n\n", 1)
    else:
        header_text, body = request_text, ""
    return header_text.splitlines(), body


def build_upstream_request(request_text, request_info):
    """把代理格式请求改写成真实服务器能接受的普通 HTTP 请求。

    浏览器发给代理的请求行可能是：
        GET http://example.com/index.html HTTP/1.1
    真实 Web 服务器通常期望：
        GET /index.html HTTP/1.1
        Host: example.com

    因此代理在这里完成“请求报文改写”：保留必要请求头，去掉代理专用头，
    并强制使用 identity 编码，方便后续正文关键字检查。
    Args:
        request_text: 客户端发来的原始请求文本。
        request_info: `parse_http_request()` 解析出的请求信息。

    Returns:
        bytes: 可直接发给目标 Web 服务器的普通 HTTP 请求字节。
    """
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
        # 代理认证凭据只能由本代理读取，不能转发给目标网站。
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
    # 告诉上游尽量不要压缩响应，降低正文过滤复杂度；若服务器仍返回 gzip，
    # filter_response_content 中仍会尝试解压检查。
    upstream_lines.append("Accept-Encoding: identity")

    upstream_text = "\r\n".join(upstream_lines) + "\r\n\r\n" + body
    return upstream_text.encode("iso-8859-1", errors="replace")


def forward_http(client_socket, request_text, request_info, config, client_ip=""):
    """处理普通 HTTP 请求：连接目标服务器、转发请求、接收响应、执行正文过滤。

    这是明文 Web 代理的核心路径：
    客户端浏览器 -> 本代理 -> 目标 Web 服务器 -> 本代理 -> 客户端浏览器。
    域名/URL 规则已经在 handle_client 中提前判断；这里主要负责真正转发
    和收到响应后的正文关键字过滤。
    Args:
        client_socket: 客户端连接 socket。
        request_text: 客户端原始 HTTP 请求文本。
        request_info: 解析后的请求信息。
        config: 当前运行配置。
        client_ip: 客户端 IP 地址。

    Returns:
        dict: 转发结果，包含 outcome、status_code、bytes_sent，
        成功时还可能包含 response_bytes，正文过滤时包含 keyword。
    """
    upstream_request = build_upstream_request(request_text, request_info)
    timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT))

    try:
        with socket.create_connection(
            (request_info["host"], request_info["port"]),
            timeout=timeout,
        ) as upstream_socket:
            upstream_socket.settimeout(timeout)
            upstream_socket.sendall(upstream_request)

            # 按 Content-Length/chunked 等 HTTP 边界接收；不能只等待 TCP 关闭，
            # 否则 NeverSSL 等保持连接的网站会在正文已到齐后仍被误判为 504。
            response_bytes = receive_http_response(upstream_socket, request_info["method"])
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
    """处理 HTTPS CONNECT：建立 TCP 隧道，只转发加密字节流，不读取 HTTPS 正文。

    HTTPS 代理的标准做法是：
    1. 浏览器向代理发送 CONNECT host:443；
    2. 代理连接目标服务器成功后返回 200 Connection Established；
    3. 浏览器和目标服务器开始 TLS 握手，代理只搬运双方加密字节。

    因为没有解密 TLS，本项目可以记录 CONNECT、限制域名、统计流量，
    但不能检查 HTTPS 页面路径和正文关键字。
    Args:
        client_socket: 客户端连接 socket。
        request_info: CONNECT 请求的解析结果，包含 host 和 port。
        config: 当前运行配置。

    Returns:
        dict: 隧道处理结果，包含 outcome、status_code、bytes_sent、
        bytes_from_client。
    """
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
                        # 客户端发来的 TLS 字节转给真实服务器。
                        upstream_socket.sendall(data)
                        bytes_from_client += len(data)
                    else:
                        # 真实服务器返回的 TLS 字节转回浏览器。
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


# =============================================================================
# 8. 客户端连接处理区：把认证、限流、过滤、缓存、转发串起来
# =============================================================================


def update_block_stats(state, reason):
    """根据拦截原因更新对应统计项。

    Args:
        state: 当前 RuntimeState。
        reason: 拦截原因字符串，例如 `domain_blacklist` 或 `url_keyword:game`。
    """
    if reason.startswith("client_ip_"):
        state.increment("blocked_client")
    elif reason.startswith("url_keyword:"):
        state.increment("blocked_url")
    elif reason == "method_blacklist":
        state.increment("blocked_method")
    else:
        state.increment("blocked_domain")


def handle_client(client_socket, client_address, state):
    """处理单个客户端连接，是认证、限流、规则过滤、缓存、转发的总入口。

    单次请求的处理顺序固定如下：
    1. 接收并解析 HTTP/CONNECT 请求；
    2. 检查客户端 IP 黑白名单；
    3. 检查代理认证；
    4. 检查访问频率限制；
    5. 检查方法、域名、URL 关键字等请求阶段规则；
    6. GET 请求尝试读取缓存；
    7. 按 CONNECT 或普通 HTTP 分支转发；
    8. 记录统计和日志，供前端大屏和日志详情页展示。
    Args:
        client_socket: 与客户端浏览器或 curl 建立的 socket。
        client_address: 客户端地址元组，格式通常是 `(ip, port)`。
        state: 当前 RuntimeState，保存配置、统计、缓存和日志相关状态。

    Returns:
        None: 本函数直接向 client_socket 写响应，处理结束后关闭连接。
    """
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

        # 客户端地址策略先于认证和限流执行，拒绝的主机不会消耗认证与限流资源。
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

        # 仅对通过认证的请求计数，避免 407 认证挑战消耗限流额度。
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
                # 缓存中保存的是上游原始响应。每次命中仍需按当前正文规则检查，
                # 否则先访问页面、再新增正文规则时，浏览器会一直拿到旧缓存页面。
                response_bytes, blocked_keyword = filter_response_content(
                    cached["response_bytes"],
                    config,
                    request_info,
                    client_address[0],
                )
                client_socket.sendall(response_bytes)
                bytes_sent = len(response_bytes)
                state.increment("cache_hits")
                state.increment("bytes_to_clients", bytes_sent)
                if blocked_keyword:
                    state.increment("filtered_keyword")
                    state.record_keyword(blocked_keyword)
                    log_event(
                        state,
                        "CACHE_HIT_FILTERED",
                        f"client={client_address[0]} method={request_info['method']} "
                        f"host={request_info['host']} path={request_info['path']} "
                        f"keyword={blocked_keyword}",
                    )
                    log_event(
                        state,
                        "FILTER",
                        f"client={client_address[0]} method={request_info['method']} "
                        f"host={request_info['host']} path={request_info['path']} "
                        f"keyword={blocked_keyword}",
                    )
                    return
                state.increment("allowed_requests")
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
            # HTTPS 请求进入隧道转发分支。
            result = forward_connect(client_socket, request_info, config)
        else:
            # 明文 HTTP 请求进入普通转发分支，可在响应阶段做正文过滤。
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


# =============================================================================
# 9. 管理后端区：前端页面、规则 API、统计 API、日志 API
# =============================================================================


class AdminHandler(BaseHTTPRequestHandler):
    """管理后端：提供前端页面、配置/规则 API、统计 API、日志 API 和演示重置 API。

    这个类相当于项目的“后端控制面”：
    - 浏览器访问 8088 时，会拿到 frontend 目录中的管理页面；
    - 前端按钮和 rule_cli.py 都调用这里的 /api/rules/* 与 /api/settings/update；
    - 代理线程写入 RuntimeState 和日志文件后，前端通过 /api/stats、/api/logs/query
      读取最新统计和拦截证据。
    Attributes:
        state: 由 start_admin_server 动态绑定的 RuntimeState。所有 HTTP API
        都通过它读取或修改当前代理状态。
    """

    state = None

    def do_GET(self):
        """处理只读接口：前端页面、当前配置、统计、日志查询、CSV 导出。

        Returns:
            None: 直接通过 `self.wfile` 写 HTTP 响应。
        """
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
            # 返回完整运行配置，命令行工具更新认证用户时会先读取它。
            self.send_json({"config": self.state.get_config()})
            return
        if parsed.path == "/api/rules":
            # 返回可编辑规则组，前端用它渲染规则卡片。
            self.send_json(self.state.get_rules())
            return
        if parsed.path == "/api/changes":
            query = parse_qs(parsed.query)
            limit = parse_bounded_query_int(query, "limit", 80, 200)
            self.send_json({"changes": self.state.get_change_history(limit)})
            return
        if parsed.path == "/api/changes/query":
            query = parse_qs(parsed.query)
            action = query.get("action", [""])[0]
            rule_type = query.get("rule_type", [""])[0]
            search = query.get("search", [""])[0]
            limit = parse_bounded_query_int(query, "limit", 200, 1000)
            self.send_json(self.state.query_changes(action, rule_type, search, limit))
            return
        if parsed.path == "/api/stats":
            # 首页实时统计卡片的数据来源。
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
            # 日志详情页把普通文本日志解析成结构化结果，再按事件/关键词筛选。
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
            # 导出当前查询结果，便于验收时留存 CSV 证据。
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
        """处理会改变运行状态的接口：规则增删改、设置切换、缓存/日志清理。

        Returns:
            None: 直接通过 `self.wfile` 写 HTTP 响应。
        """
        parsed = urlsplit(self.path)
        try:
            if parsed.path == "/api/reload":
                config = self.state.reload_config()
                self.send_json({"ok": True, "config": config})
                return
            if parsed.path == "/api/rules/add":
                # 新增单条规则。前端“添加”按钮和 rule_cli.py add 都走这个入口。
                payload = self.read_json_body()
                result = self.state.add_list_rule(
                    payload.get("rule_type"),
                    payload.get("value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/delete":
                # 删除单条规则，按规范化后的规则身份匹配。
                payload = self.read_json_body()
                result = self.state.delete_list_rule(
                    payload.get("rule_type"),
                    payload.get("value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/update":
                # 修改单条规则，用于把一个旧值替换成新值。
                payload = self.read_json_body()
                result = self.state.update_list_rule(
                    payload.get("rule_type"),
                    payload.get("old_value"),
                    payload.get("new_value"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/rules/replace":
                # 替换整个规则组，适合验收脚本恢复一组稳定规则。
                payload = self.read_json_body()
                result = self.state.replace_list_rules(
                    payload.get("rule_type"),
                    payload.get("values"),
                )
                self.send_json(result)
                return
            if parsed.path == "/api/settings/update":
                # 热更新缓存、认证、限流、黑/白名单模式等运行时设置。
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
        """从固定前端目录发送可信管理页面。

        Args:
            page_path: 要发送的 HTML 页面路径。
        """
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
        """读取 POST JSON 请求体，兼容 PowerShell 和 CMD 常见 curl 写法。

        Returns:
            dict: 解析后的 JSON 对象。

        Raises:
            ValueError: 请求体不是合法 JSON/宽松 JSON 对象。
        """
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
        """发送 JSON 响应。

        Args:
            payload: 可 JSON 序列化的响应对象。
            status_code: HTTP 状态码。
        """
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8", status_code=status_code)

    def send_bytes(self, body, content_type, status_code=200, filename=""):
        """发送字节响应；提供文件名时触发浏览器下载验收证据。

        Args:
            body: 响应体字节。
            content_type: Content-Type 响应头。
            status_code: HTTP 状态码。
            filename: 可选下载文件名，传入后添加 Content-Disposition。
        """
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """关闭 BaseHTTPRequestHandler 默认访问日志，避免终端输出过于嘈杂。"""
        return


# =============================================================================
# 10. 服务启动区：启动管理端口和代理端口
# =============================================================================


def start_admin_server(host, port, state):
    """启动管理服务，默认监听 8088，前端和 API 都从这里提供。

    Args:
        host: 管理后端监听地址。
        port: 管理后端监听端口。
        state: 当前 RuntimeState，绑定到 AdminHandler。

    Returns:
        ThreadingHTTPServer: 已启动并在后台线程运行的管理服务对象。
    """
    handler_class = type("BoundAdminHandler", (AdminHandler,), {"state": state})
    server = ThreadingHTTPServer((host, port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Admin dashboard started at http://{host}:{port}/", flush=True)
    return server


def start_server(host, port, state=None):
    """启动代理服务，默认监听 8080，为每个客户端连接创建处理线程。

    Args:
        host: 代理监听地址。
        port: 代理监听端口。
        state: 可选 RuntimeState；为空时会用默认配置创建。
    """
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
    """程序入口：读取配置，启动管理后端，然后启动代理服务。"""
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
