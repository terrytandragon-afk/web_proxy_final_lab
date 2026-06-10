import ipaddress
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# These list fields are editable through the frontend, admin API, and CLI.
LIST_RULE_FIELDS = {
    "blocked_domains": {
        "title": "域名黑名单",
        "description": "命中后直接返回 403 Forbidden，支持完整域名、父域名和通配符。示例：baidu.com、www.baidu.com、*.baidu.com、*baidu*。",
        "value_label": "域名或通配符",
    },
    "allowed_domains": {
        "title": "域名白名单",
        "description": "白名单模式下只有这些域名允许访问，匹配方式与域名黑名单一致。",
        "value_label": "允许访问的域名或通配符",
    },
    "blocked_client_ips": {
        "title": "客户端 IP 黑名单",
        "description": "拒绝指定客户端使用代理，支持单个 IPv4/IPv6 地址和 CIDR 网段，例如 192.168.1.20、10.0.0.0/8。",
        "value_label": "客户端 IP 或 CIDR 网段",
    },
    "allowed_client_ips": {
        "title": "客户端 IP 白名单",
        "description": "列表非空时，仅允许匹配的客户端使用代理；客户端 IP 黑名单仍具有更高优先级。",
        "value_label": "允许的客户端 IP 或 CIDR 网段",
    },
    "blocked_url_keywords": {
        "title": "URL 关键字",
        "description": "请求地址中的域名、路径/子文件或查询参数包含该关键字时直接拦截；不检查网页正文。",
        "value_label": "URL 关键字",
    },
    "blocked_content_keywords": {
        "title": "正文关键字",
        "description": "HTTP 明文网页正文包含该关键字时，以 403 拦截提示页替代原网页。",
        "value_label": "正文关键字",
    },
    "blocked_methods": {
        "title": "禁止 HTTP 方法",
        "description": "请求方法命中后直接拦截，例如 PUT、DELETE。",
        "value_label": "HTTP 方法",
    },
}

CONFIG_SETTING_FIELDS = {
    "mode": str,
    "cache_enabled": bool,
    "cache_ttl_seconds": int,
    "cache_max_items": int,
    "proxy_auth_enabled": bool,
    "proxy_auth_users": dict,
    "rate_limit_enabled": bool,
    "rate_limit_per_minute": int,
    "rate_limit_window_seconds": int,
}


def load_config(config_path):
    """Load one JSON configuration file relative to the project root."""
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        print(f"Config file not found, using defaults: {config_path}", flush=True)
        return {}
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def resolve_project_path(path_text):
    """Resolve configured relative paths consistently from the project root."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def normalize_rule_value(rule_type, value):
    """Normalize user-entered values so duplicate and delete checks are stable."""
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("rule value cannot be empty")
    if rule_type in ("blocked_domains", "allowed_domains"):
        return normalized.lower().strip(".")
    if rule_type in ("blocked_client_ips", "allowed_client_ips"):
        try:
            # Keep a single host readable; normalize CIDR host bits with strict=False.
            return str(ipaddress.ip_address(normalized))
        except ValueError:
            try:
                return str(ipaddress.ip_network(normalized, strict=False))
            except ValueError as error:
                raise ValueError(f"invalid client IP or CIDR: {normalized}") from error
    if rule_type == "blocked_methods":
        return normalized.upper()
    return normalized


def rule_identity(rule_type, value):
    """Return the case-insensitive identity used for rule comparisons."""
    return normalize_rule_value(rule_type, value).lower()


def validate_rule_type(rule_type):
    """Reject fields that are not editable list-rule groups."""
    if rule_type not in LIST_RULE_FIELDS:
        raise ValueError(f"unsupported rule type: {rule_type}")


def build_rules_payload(config):
    """Build the rule-group response consumed by the admin frontend."""
    groups = []
    for rule_type, metadata in LIST_RULE_FIELDS.items():
        groups.append(
            {
                "type": rule_type,
                "title": metadata["title"],
                "description": metadata["description"],
                "value_label": metadata["value_label"],
                "values": list(config.get(rule_type, [])),
            }
        )
    return {
        "mode": config.get("mode", "blacklist"),
        "groups": groups,
    }


def split_top_level_csv(text):
    """Split comma-separated values while respecting nested []/{} and quotes."""
    items = []
    current = []
    depth = 0
    quote = ""
    escaped = False
    for char in text:
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
        elif char in ("{", "["):
            depth += 1
            current.append(char)
        elif char in ("}", "]"):
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or text.strip():
        items.append("".join(current).strip())
    return [item for item in items if item]


def parse_loose_json_value(text):
    """Parse classroom-friendly curl bodies where PowerShell stripped JSON quotes."""
    value = text.strip()
    if value.startswith("{") and value.endswith("}"):
        return parse_loose_json_object(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_loose_json_value(item) for item in split_top_level_csv(inner)]
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        return value[1:-1].replace('\\"', '"').replace("\\'", "'")
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        return value


def parse_loose_json_object(text):
    """Accept simple {key:value} bodies produced by Windows PowerShell/curl quoting."""
    body = text.strip()
    if not (body.startswith("{") and body.endswith("}")):
        raise ValueError("loose JSON body must be an object")
    inner = body[1:-1].strip()
    if not inner:
        return {}
    payload = {}
    for item in split_top_level_csv(inner):
        if ":" not in item:
            raise ValueError(f"invalid loose JSON item: {item}")
        key_text, value_text = item.split(":", 1)
        key = parse_loose_json_value(key_text)
        if not isinstance(key, str) or not key:
            raise ValueError(f"invalid loose JSON key: {key_text}")
        payload[key] = parse_loose_json_value(value_text)
    return payload
