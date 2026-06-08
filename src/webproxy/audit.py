from datetime import datetime

from .config_rules import resolve_project_path


LOG_FILE_KEYS = {
    "proxy": "log_file",
    "blocked": "blocked_log_file",
    "error": "error_log_file",
}


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
