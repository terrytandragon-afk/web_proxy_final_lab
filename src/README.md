# src 目录说明

这里放代理服务器后端源码。当前命令行入口仍然是：

```text
proxy.py
```

为便于课程验收、阅读和继续扩展，后端开始按职责逐步拆分。当前目录结构：

```text
src/
  proxy.py
  webproxy/
    __init__.py
    audit.py
    config_rules.py
```

- `proxy.py`：程序入口、运行状态、代理协议处理、转发、过滤、日志、管理 API 和服务器启动。
- `webproxy/audit.py`：运行日志、拦截日志、错误日志的写入、结构化查询、CSV 导出和清空。
- `webproxy/config_rules.py`：配置文件读取、项目路径解析、规则类型定义、规则值标准化和 Windows curl 宽松 JSON 解析。
- `webproxy/__init__.py`：标记可复用的后端模块包。

此次拆分不改变启动命令、API 地址和配置格式。直接运行脚本与测试代码导入模块两种方式都受支持。

## 已实现核心函数

1. `main()`：读取命令行参数。
2. `webproxy.config_rules.load_config()`：读取 JSON 配置。
3. `start_server()`：监听代理端口。
4. `handle_client()`：处理单个客户端连接。
5. `parse_http_request()`：解析 method、host、port、path。
6. `check_access_policy()`：执行域名、URL、方法、白名单策略。
7. `forward_http()`：转发 HTTP 请求并返回响应。
8. `filter_response_content()`：检查网页正文关键字。
9. `forward_connect()`：处理 HTTPS CONNECT 隧道。
10. `RuntimeState.add_list_rule()`：新增过滤规则并保存配置。
11. `RuntimeState.delete_list_rule()`：删除过滤规则并保存配置。
12. `AdminHandler`：提供前端页面和管理 API。

## 模块拆分验证命令

检查命令行入口：

```powershell
python src\proxy.py --help
```

检查全部 Python 文件语法：

```powershell
python -m compileall src tools tests
```

运行完整回归测试：

```powershell
python tests\run_all_smoke.py
```

## 项目边界

```text
HTTPS MITM
数据库
多用户分组策略
```

这些内容可以写进报告展望。当前项目已经实现 HTTP 代理转发、过滤、缓存、HTTPS CONNECT、日志统计、规则增删改查和管理前端。

## 客户端访问控制函数

- `client_ip_matches()`：判断客户端 IPv4/IPv6 地址是否命中单个地址或 CIDR 网段。
- `check_client_access_policy()`：执行客户端 IP 黑名单和白名单策略。
- `handle_client()`：在认证、限流和目标规则之前调用客户端访问控制。

客户端 IP/CIDR 规则的输入校验和标准化由 `webproxy/config_rules.py` 负责。
