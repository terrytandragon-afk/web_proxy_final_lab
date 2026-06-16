"""规则配置与命令行/前端输入规范化工具。

代理服务和管理后端都需要读写同一个 JSON 配置文件。这个模块集中处理：
- 项目根目录定位；
- 可编辑规则组的元数据；
- 规则值规范化和重复判断；
- Windows CMD/PowerShell 下 curl JSON 引号被处理后的兼容解析。

把这些逻辑从 proxy.py 中拆出来，是为了让“网络转发逻辑”和“规则配置逻辑”
保持分离，便于课程答辩时分别说明。
"""

import ipaddress
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 这些列表型规则可以通过三种方式修改：
# 1. 前端管理页面；
# 2. 后端 HTTP API，例如 /api/rules/add；
# 3. tools/rule_cli.py 命令行工具。
# 每个字段都带 title/description/value_label，前端会直接用这些元数据渲染规则卡片。
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
        "description": "明文 HTTP 请求地址中的域名、路径/子文件或查询参数包含该关键字时直接拦截；HTTPS 只能检查 CONNECT 目标域名。",
        "value_label": "URL 关键字",
    },
    "blocked_content_keywords": {
        "title": "正文关键字",
        "description": "HTTP 明文网页正文包含该关键字时，以 403 拦截提示页替代原网页；不解密 HTTPS 正文。",
        "value_label": "正文关键字",
    },
    "blocked_methods": {
        "title": "禁止 HTTP 方法",
        "description": "请求方法命中后直接拦截，例如 PUT、DELETE。",
        "value_label": "HTTP 方法",
    },
}

CONFIG_SETTING_FIELDS = {
    # 简单运行时设置的类型表。Admin API 收到 JSON 后会按这里的类型做校验和转换。
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
    """读取 JSON 配置文件；相对路径统一按项目根目录解析。"""
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        print(f"Config file not found, using defaults: {config_path}", flush=True)
        return {}
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def resolve_project_path(path_text):
    """把配置文件中的相对路径解析到项目根目录下，避免受当前命令行目录影响。"""
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def normalize_rule_value(rule_type, value):
    """规范化用户输入的规则值，使增删改查能稳定匹配。

    例如：
    - 域名统一转小写并去掉末尾点；
    - 客户端 IP/CIDR 用 ipaddress 校验，避免非法网段进入配置；
    - HTTP 方法统一转大写；
    - 其他关键字保留用户输入，便于做大小写不敏感匹配。
    """
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("rule value cannot be empty")
    if rule_type in ("blocked_domains", "allowed_domains"):
        return normalized.lower().strip(".")
    if rule_type in ("blocked_client_ips", "allowed_client_ips"):
        try:
            # 单个 IP 保持为标准地址；CIDR 网段允许用户写 192.168.1.1/24，
            # strict=False 会自动归一化为 192.168.1.0/24。
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
    """返回用于比较的规则身份；大小写差异不应造成重复规则。"""
    return normalize_rule_value(rule_type, value).lower()


def validate_rule_type(rule_type):
    """只允许修改 LIST_RULE_FIELDS 中声明的规则组，防止任意字段被写入配置。"""
    if rule_type not in LIST_RULE_FIELDS:
        raise ValueError(f"unsupported rule type: {rule_type}")


def build_rules_payload(config):
    """构造前端规则面板需要的响应结构：规则组元数据 + 当前规则值。"""
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
    """按顶层逗号拆分文本，并跳过引号、数组、对象内部的逗号。

    这个函数服务于宽松 JSON 解析。例如 `{settings:{a:1,b:2}}` 中，
    内层 `a:1,b:2` 不能被外层逗号拆散。
    """
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
    """解析课堂验收中常见的宽松 JSON 值。

    Windows PowerShell 和 CMD 对引号的处理不同，用户复制 curl 命令时可能把
    标准 JSON 变成 `{rule_type:blocked_domains,value:*.bing.com}` 这种形式。
    后端先尝试标准 json.loads，失败后再用这里的宽松解析兜底。
    """
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
    """兼容 PowerShell/curl 引号差异产生的简单 `{key:value}` 请求体。"""
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
