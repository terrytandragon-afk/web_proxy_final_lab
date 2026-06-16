"""批量验收证据读取与大屏统计重建。

实时运行时，管理首页从 RuntimeState 读取统计；批量验收脚本结束后，代理进程
可能已经退出，内存统计也不存在了。为了解决“脚本跑完但前端首页看不到数据”
的问题，测试脚本会把日志写入 tests/evidence 目录，本模块再从这些持久化日志
中重建统计数据和规则变更记录。
"""

import json
from collections import Counter
from datetime import datetime

from .audit import parse_log_line
from .config_rules import PROJECT_ROOT, load_config


# 证据 profile 在后端写死，浏览器不能传任意文件路径。
# 这样前端只能查看项目约定的验收日志，不能借 API 读取系统上的其他文件。
EVIDENCE_PROFILES = {
    "web": {
        "title": "Web/代理功能验收证据",
        "description": "转发、拦截、正文过滤、HTTPS、缓存、认证和限流日志。",
        "config_path": PROJECT_ROOT / "tests" / "evidence" / "web" / "acceptance_config.json",
    },
    "rules": {
        "title": "规则与运行模式验收证据",
        "description": "规则组增删改查、白名单模式和运行时设置变更记录。",
        "config_path": PROJECT_ROOT / "tests" / "evidence" / "rules" / "acceptance_config.json",
    },
}


def get_evidence_profile(profile_name):
    """返回可信证据 profile 的元数据；未知名称直接拒绝。"""
    profile = EVIDENCE_PROFILES.get(str(profile_name or "").strip().lower())
    if not profile:
        raise ValueError(f"unsupported evidence profile: {profile_name}")
    return profile


def load_evidence_config(profile_name):
    """读取某个验收 profile 对应的独立配置文件。"""
    profile = get_evidence_profile(profile_name)
    config_path = profile["config_path"]
    if not config_path.exists():
        return {}
    return load_config(str(config_path))


def _read_jsonl(path):
    """从 JSONL 证据文件中读取合法 JSON 对象，坏行会被跳过。"""
    if not path or not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _count_lines(path):
    """统计证据日志行数，用于首页判断批量验收证据是否存在。"""
    if not path or not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _config_path(config, key):
    """解析证据配置中的日志路径。"""
    path_text = config.get(key)
    if not path_text:
        return None
    path = PROJECT_ROOT / path_text
    return path.resolve() if not path.is_absolute() else path


def list_evidence_profiles():
    """列出 Web 功能验收和规则验收两类证据的可用状态与日志数量。"""
    results = []
    for name, profile in EVIDENCE_PROFILES.items():
        config_path = profile["config_path"]
        config = load_config(str(config_path)) if config_path.exists() else {}
        results.append(
            {
                "name": name,
                "title": profile["title"],
                "description": profile["description"],
                "available": config_path.exists(),
                "config_path": str(config_path.relative_to(PROJECT_ROOT)),
                "proxy_log_count": _count_lines(_config_path(config, "log_file")),
                "blocked_log_count": _count_lines(_config_path(config, "blocked_log_file")),
                "error_log_count": _count_lines(_config_path(config, "error_log_file")),
                "change_count": _count_lines(_config_path(config, "change_log_file")),
            }
        )
    return results


def query_change_entries_from_config(
    config,
    profile_name="current",
    action="",
    rule_type="",
    search="",
    limit=200,
):
    """像只读小数据库一样查询 JSONL 规则变更日志。"""
    change_path = _config_path(config, "change_log_file")
    entries = _read_jsonl(change_path)
    normalized_action = str(action or "").strip().lower()
    normalized_rule_type = str(rule_type or "").strip()
    search_lower = str(search or "").strip().lower()

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

    bounded_limit = max(1, min(int(limit), 1000))
    return {
        "profile": profile_name,
        "action": normalized_action,
        "rule_type": normalized_rule_type,
        "search": search,
        "total": len(entries),
        "matched": len(matched_entries),
        "action_counts": action_counts,
        "rule_type_counts": rule_type_counts,
        # Persisted files are chronological; detail pages show newest records first.
        "entries": list(reversed(matched_entries[-bounded_limit:])),
    }


def query_change_entries(profile_name, action="", rule_type="", search="", limit=200):
    """查询某个固定验收 profile 中持久化的规则变更证据。"""
    return query_change_entries_from_config(
        load_evidence_config(profile_name),
        profile_name=profile_name,
        action=action,
        rule_type=rule_type,
        search=search,
        limit=limit,
    )


def build_evidence_dashboard():
    """从最新 Web 验收日志重建首页统计快照。

    这里不会读取代理进程内存，而是逐行解析日志，把 ALLOW、BLOCK、FILTER、
    CONNECT、CACHE_HIT 等事件重新累计成和实时首页一致的统计结构。
    """
    config = load_evidence_config("web")
    proxy_log_path = _config_path(config, "log_file")
    lines = (
        proxy_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if proxy_log_path and proxy_log_path.exists()
        else []
    )
    entries = [parse_log_line(line) for line in lines]

    # 这些事件代表一次请求已经完成。CACHE_MISS、RATE_ALLOW 属于中间过程，
    # 可以单独统计，但不能重复增加 total_requests。
    terminal_events = {
        "ALLOW",
        "CACHE_HIT",
        "BLOCK",
        "FILTER",
        "CONNECT",
        "AUTH_REQUIRED",
        "RATE_LIMIT",
        "ERROR",
    }
    stats = {
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
        "cache_entries": 0,
        "auth_required": 0,
        "rate_limited": 0,
        "bad_requests": 0,
        "errors": 0,
        "bytes_from_clients": 0,
        "bytes_to_clients": 0,
    }
    host_hits = Counter()
    keyword_hits = Counter()
    cache_keys = set()
    pending_cache_misses = set()
    event_times = []

    for entry in entries:
        event = entry["event"]
        fields = entry.get("fields", {})
        host = fields.get("host", "")
        path = fields.get("path", "")
        reason = fields.get("reason", "")

        if entry.get("time"):
            try:
                event_times.append(datetime.fromisoformat(entry["time"]))
            except ValueError:
                pass
        if event in terminal_events:
            stats["total_requests"] += 1
            if host:
                host_hits[host] += 1
        if event in {"ALLOW", "CACHE_HIT", "CONNECT"}:
            stats["allowed_requests"] += 1
        if event == "BLOCK":
            if reason.startswith("domain_"):
                stats["blocked_domain"] += 1
            elif reason.startswith("client_ip_"):
                stats["blocked_client"] += 1
            elif reason.startswith("url_keyword:"):
                stats["blocked_url"] += 1
            elif reason == "method_blacklist":
                stats["blocked_method"] += 1
        elif event == "FILTER":
            stats["filtered_keyword"] += 1
            keyword = fields.get("keyword", "")
            if keyword:
                keyword_hits[keyword] += 1
        elif event == "CONNECT":
            stats["https_tunnels"] += 1
        elif event in {"CACHE_HIT", "CACHE_HIT_FILTERED"}:
            stats["cache_hits"] += 1
        elif event == "CACHE_MISS":
            stats["cache_misses"] += 1
        elif event == "AUTH_REQUIRED":
            stats["auth_required"] += 1
        elif event == "RATE_LIMIT":
            stats["rate_limited"] += 1
        elif event == "ERROR":
            stats["errors"] += 1
            if "bad_request" in entry.get("message", ""):
                stats["bad_requests"] += 1

        cache_key = (host, path)
        if event == "CACHE_MISS" and host:
            pending_cache_misses.add(cache_key)
        elif event == "CACHE_HIT" and host:
            cache_keys.add(cache_key)
        elif event == "ALLOW" and cache_key in pending_cache_misses:
            # MISS 后如果最终 ALLOW，说明该响应可被缓存；MISS 后 FILTER 不缓存。
            cache_keys.add(cache_key)

    stats["cache_entries"] = len(cache_keys)
    # 与实时首页口径一致，汇总所有会阻止客户端获得原始目标响应的事件。
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
    first_time = min(event_times).isoformat(sep=" ", timespec="seconds") if event_times else ""
    last_time = max(event_times).isoformat(sep=" ", timespec="seconds") if event_times else ""
    elapsed = int((max(event_times) - min(event_times)).total_seconds()) if event_times else 0
    return {
        "source": "evidence",
        "started_at": first_time,
        "finished_at": last_time,
        "uptime_seconds": elapsed,
        "stats": stats,
        "top_hosts": host_hits.most_common(10),
        "keyword_hits": keyword_hits.most_common(10),
    }
