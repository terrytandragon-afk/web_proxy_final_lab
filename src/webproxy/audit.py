from datetime import datetime
import re

from .config_rules import resolve_project_path


LOG_FILE_KEYS = {
    "proxy": "log_file",
    "blocked": "blocked_log_file",
    "error": "error_log_file",
}

LOG_LINE_PATTERN = re.compile(
    r"^\[(?P<time>[^\]]+)\]\s+(?P<event>[A-Z_]+)(?:\s+(?P<message>.*))?$"
)


def write_log_line(config, file_key, line):
    """Append one line to a configured log file when that log is enabled."""
    log_path_text = config.get(file_key)
    if not log_path_text:
        return
    log_path = resolve_project_path(log_path_text)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def log_event(state, event_type, message):
    """Print and persist one event, including specialized blocked/error logs."""
    config = state.get_config()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {event_type} {message}"
    print(line, flush=True)

    write_log_line(config, "log_file", line)
    # Authentication failures and rate-limit rejections are interception events too.
    if event_type.startswith(("BLOCK", "FILTER", "AUTH_REQUIRED", "RATE_LIMIT")):
        write_log_line(config, "blocked_log_file", line)
    if event_type.startswith("ERROR"):
        write_log_line(config, "error_log_file", line)


def read_log_tail(config, kind, limit):
    """Read the newest configured access, blocked, or error log lines."""
    file_key = LOG_FILE_KEYS.get(kind, "log_file")
    log_path_text = config.get(file_key)
    if not log_path_text:
        return []
    log_path = resolve_project_path(log_path_text)
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def parse_log_line(line):
    """Convert one text log line into fields suitable for a query result table."""
    match = LOG_LINE_PATTERN.match(line)
    if not match:
        return {"time": "", "event": "UNKNOWN", "message": line, "fields": {}, "raw": line}

    message = match.group("message") or ""
    fields = {}
    for token in message.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return {
        "time": match.group("time"),
        "event": match.group("event"),
        "message": message,
        "fields": fields,
        "raw": line,
    }


def query_log_entries(config, kind="proxy", events=None, search="", limit=200):
    """Filter logs like a small read-only database query and return structured rows."""
    normalized_kind = kind if kind in LOG_FILE_KEYS else "proxy"
    file_key = LOG_FILE_KEYS[normalized_kind]
    log_path_text = config.get(file_key)
    if not log_path_text:
        return {
            "kind": normalized_kind,
            "events": [],
            "search": search,
            "total": 0,
            "matched": 0,
            "entries": [],
        }

    log_path = resolve_project_path(log_path_text)
    lines = (
        log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if log_path.exists()
        else []
    )
    event_set = {event.strip().upper() for event in (events or []) if event.strip()}
    search_lower = str(search or "").strip().lower()

    matched_entries = []
    for line in lines:
        entry = parse_log_line(line)
        if event_set and entry["event"] not in event_set:
            continue
        if search_lower and search_lower not in line.lower():
            continue
        matched_entries.append(entry)

    bounded_limit = max(1, min(int(limit), 1000))
    return {
        "kind": normalized_kind,
        "events": sorted(event_set),
        "search": search,
        "total": len(lines),
        "matched": len(matched_entries),
        # Detail pages are easier to scan with the newest event first.
        "entries": list(reversed(matched_entries[-bounded_limit:])),
    }


def clear_log_files(config):
    """Clear all configured runtime log files for a fresh classroom demo."""
    cleared = []
    for file_key in LOG_FILE_KEYS.values():
        log_path_text = config.get(file_key)
        if not log_path_text:
            continue
        log_path = resolve_project_path(log_path_text)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        cleared.append(str(log_path))
    return cleared
