import json

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


def query_change_entries(profile_name, action="", rule_type="", search="", limit=200):
    """Query persisted rule/settings changes like a small read-only database."""
    config = load_evidence_config(profile_name)
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
