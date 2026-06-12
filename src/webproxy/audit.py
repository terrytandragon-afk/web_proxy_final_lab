import csv
from datetime import datetime
import io
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

CSV_FIELD_NAMES = [
    "time",
    "event",
    "client",
    "method",
    "host",
    "path",
    "status",
    "reason",
    "keyword",
    "message",
    "raw",
]


def write_log_line(config, file_key, line):
    """日志启用时向配置指定的文件追加一行。"""
    log_path_text = config.get(file_key)
    if not log_path_text:
        return
    log_path = resolve_project_path(log_path_text)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def log_event(state, event_type, message):
    """打印并持久化事件，同时写入专用拦截或错误日志。"""
    config = state.get_config()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {event_type} {message}"
    print(line, flush=True)

    write_log_line(config, "log_file", line)
    # 认证失败和限流拒绝同样属于拦截事件。
    if event_type.startswith(("BLOCK", "FILTER", "AUTH_REQUIRED", "RATE_LIMIT")):
        write_log_line(config, "blocked_log_file", line)
    if event_type.startswith("ERROR"):
        write_log_line(config, "error_log_file", line)


def read_log_tail(config, kind, limit):
    """读取最新的访问、拦截或错误日志行。"""
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
    """把文本日志解析成适合查询结果表格展示的结构化字段。"""
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
    """像只读小型数据库一样筛选日志，并返回结构化记录。"""
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
        # 详情页按时间倒序展示，便于先查看最新事件。
        "entries": list(reversed(matched_entries[-bounded_limit:])),
    }


def build_log_csv(query_result):
    """把结构化查询结果序列化为适合 Excel 打开的 UTF-8 CSV。"""
    text_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(text_buffer, fieldnames=CSV_FIELD_NAMES)
    writer.writeheader()
    for entry in query_result.get("entries", []):
        fields = entry.get("fields", {})
        # 常用审计字段单独成列，同时保留完整原始证据。
        writer.writerow(
            {
                "time": entry.get("time", ""),
                "event": entry.get("event", ""),
                "client": fields.get("client", ""),
                "method": fields.get("method", ""),
                "host": fields.get("host", ""),
                "path": fields.get("path", ""),
                "status": fields.get("status", ""),
                "reason": fields.get("reason", ""),
                "keyword": fields.get("keyword", ""),
                "message": entry.get("message", ""),
                "raw": entry.get("raw", ""),
            }
        )
    # utf-8-sig 添加 BOM，使 Windows Excel 能直接识别中文。
    return text_buffer.getvalue().encode("utf-8-sig")


def clear_log_files(config):
    """清空当前配置的运行日志，便于重新进行课堂演示。"""
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
