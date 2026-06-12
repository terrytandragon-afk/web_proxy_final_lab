import json
from collections import Counter
from datetime import datetime

from .audit import parse_log_line
from .config_rules import PROJECT_ROOT, load_config


# Evidence profiles are fixed server-side. The API never accepts an arbitrary path
# from the browser, so the read-only evidence viewer cannot expose unrelated files.
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
    """Return metadata for one trusted evidence profile or reject the name."""
    profile = EVIDENCE_PROFILES.get(str(profile_name or "").strip().lower())
    if not profile:
        raise ValueError(f"unsupported evidence profile: {profile_name}")
    return profile


def load_evidence_config(profile_name):
    """Load the isolated acceptance configuration selected by a fixed profile."""
    profile = get_evidence_profile(profile_name)
    config_path = profile["config_path"]
    if not config_path.exists():
        return {}
    return load_config(str(config_path))


def _read_jsonl(path):
    """Read valid JSON objects from a JSONL evidence file."""
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
    """Count persisted evidence lines without loading application state."""
    if not path or not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _config_path(config, key):
    """Resolve one path stored in an evidence configuration."""
    path_text = config.get(key)
    if not path_text:
        return None
    path = PROJECT_ROOT / path_text
    return path.resolve() if not path.is_absolute() else path


def list_evidence_profiles():
    """Describe evidence availability and counts for the main dashboard."""
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
    """Query one configured JSONL change log like a small read-only database."""
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
    """Query persisted acceptance changes from one fixed evidence profile."""
    return query_change_entries_from_config(
        load_evidence_config(profile_name),
        profile_name=profile_name,
        action=action,
        rule_type=rule_type,
        search=search,
        limit=limit,
    )


def build_evidence_dashboard():
    """Rebuild the main dashboard snapshot from the latest persisted Web evidence."""
    config = load_evidence_config("web")
    proxy_log_path = _config_path(config, "log_file")
    lines = (
        proxy_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if proxy_log_path and proxy_log_path.exists()
        else []
    )
    entries = [parse_log_line(line) for line in lines]

    # These events finish one proxy request. Intermediate events such as CACHE_MISS
    # and RATE_ALLOW are counted separately but must not inflate total_requests.
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
            # A miss followed by ALLOW is stored; a miss followed by FILTER is not.
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
