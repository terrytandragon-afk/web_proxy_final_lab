# 项目结构与源码阅读指南

本文用于快速理解项目代码结构，重点说明 Web 代理是怎么形成的，以及各类过滤规则在源码中的位置。

## 一、总体目录

```text
web_proxy_final_lab/
  config.example.json              # 主配置文件：端口、规则组、日志路径、缓存/认证/限流设置
  README.md                        # 项目入口说明
  PROJECT_SHOWCASE.md              # 展示性总览文件
  src/
    proxy.py                       # 代理服务、管理后端、过滤链路的核心代码
    webproxy/
      config_rules.py              # 规则组定义、配置读取、规则值规范化
      audit.py                     # 运行日志、拦截日志、错误日志、CSV 导出
      evidence.py                  # 从批量验收日志重建前端大屏数据
      __init__.py
  frontend/
    index.html                     # 管理首页：规则、运行设置、统计大屏、日志入口
    logs.html                      # Web/拦截日志查询详情页
    changes.html                   # 规则变更记录查询详情页
  tools/
    rule_cli.py                    # 命令行规则管理工具，调用 8088 后端 API
    start_proxy_browser.ps1        # 以实验代理参数启动 Edge/Chrome
  tests/
    run_all_smoke.py               # 一键批量验收入口
    run_web_features_smoke.py      # Web 代理功能批量验收
    run_rule_management_smoke.py   # 规则组和运行模式批量验收
    manual_demo_server.py          # 本地确定性 HTTP 测试站点
    webroot/                       # 本地测试网页
  docs/
    07_manual_module_verification.md
    08_backend_cli_rule_management.md
    10_project_structure.md
  report/
    final_report.tex
    final_report_revised.pdf
```

## 二、运行后的两个服务

项目启动命令：

```powershell
python src\proxy.py --config config.example.json
```

启动后会同时运行两个端口：

```text
127.0.0.1:8080  Web 正向代理端口
127.0.0.1:8088  管理前端和后端 API 端口
```

浏览器或 curl 把 Web 请求交给 `8080`，代理服务负责转发和过滤。管理页面、命令行工具、验收脚本访问 `8088`，用于修改规则、读取日志、查看统计。

## 三、Web 代理请求处理流程

核心入口是 `src/proxy.py` 中的 `handle_client()`。它处理一次客户端连接，主要顺序如下：

```text
客户端连接代理 8080
  ↓
recv() 接收 HTTP 请求字节
  ↓
parse_http_request() 解析 method、host、port、path
  ↓
check_client_access_policy() 检查客户端 IP 黑/白名单
  ↓
check_proxy_auth() 检查代理认证
  ↓
check_rate_limit() 检查访问频率限制
  ↓
check_access_policy() 检查方法、域名、URL 关键字
  ↓
GET 请求尝试读取 RuntimeState.cache
  ↓
CONNECT 请求 → forward_connect() 建立 HTTPS 隧道
普通 HTTP 请求 → forward_http() 转发并接收响应
  ↓
filter_response_content() 对 HTTP 明文响应做正文关键字过滤
  ↓
返回原响应或代理生成的 403 拦截页
  ↓
log_event() 写入访问日志/拦截日志/错误日志
```

## 四、几个过滤模块在哪里实现

| 功能 | 主要函数 | 说明 |
| --- | --- | --- |
| 域名黑名单 | `domain_matches()`、`check_access_policy()` | 命中 `blocked_domains` 后直接返回 403 |
| 域名白名单 | `check_access_policy()` | `mode=whitelist` 时，只允许 `allowed_domains` |
| URL 关键字 | `check_access_policy()` | 检查 HTTP 请求的 host、path、query、target |
| 正文关键字 | `filter_response_content()` | 先拿到上游响应，再检查文本正文，命中后替换为 403 页面 |
| HTTP 方法限制 | `check_access_policy()` | 例如禁止 PUT、DELETE |
| 客户端 IP 黑/白名单 | `client_ip_matches()`、`check_client_access_policy()` | 支持单个 IP 与 CIDR |
| 代理认证 | `check_proxy_auth()` | 使用 HTTP Basic Proxy-Authorization |
| 访问频率限制 | `RuntimeState.check_rate_limit()` | 按客户端 IP 做固定窗口计数 |
| HTTP GET 缓存 | `RuntimeState.get_cache()`、`set_cache()` | 缓存上游原始响应，命中后仍按最新正文规则检查 |
| HTTPS CONNECT | `forward_connect()` | 只转发加密字节流，不解密正文 |

## 五、配置和规则流向

规则保存在 `config.example.json`。运行时修改规则有两条路径：

```text
前端 index.html
  → fetch("/api/rules/add")
  → AdminHandler.do_POST()
  → RuntimeState.add_list_rule()
  → 写回 config.example.json
  → 写入 change_log_file
```

```text
命令行 tools/rule_cli.py
  → http.client 请求 127.0.0.1:8088/api/rules/add
  → AdminHandler.do_POST()
  → RuntimeState.add_list_rule()
  → 写回 config.example.json
  → 写入 change_log_file
```

因此，前端和命令行不是两套规则系统，而是共用同一个后端 API 和同一个配置文件。

## 六、日志和前端显示

`src/webproxy/audit.py` 负责写日志和查询日志：

```text
log_event()
  → 写入 log_file
  → BLOCK/FILTER/AUTH_REQUIRED/RATE_LIMIT 同时写入 blocked_log_file
  → ERROR 写入 error_log_file
```

前端首页实时统计来自：

```text
GET /api/stats → RuntimeState.snapshot()
```

日志详情页来自：

```text
GET /api/logs/query → query_log_entries()
```

批量验收完成后的“最近验收”大屏来自：

```text
GET /api/evidence/dashboard → build_evidence_dashboard()
```

它会读取 `tests/evidence/` 中的持久化日志，重新计算总请求、总拦截、缓存命中、限流、认证等统计。

## 七、源码阅读建议

建议按下面顺序读：

1. `src/proxy.py` 的 `main()`、`start_server()`：看服务如何启动。
2. `handle_client()`：看单次请求的总流程。
3. `parse_http_request()`：看代理如何识别 HTTP 与 CONNECT。
4. `check_access_policy()`：看域名、URL、方法规则如何拦截。
5. `forward_http()`：看明文 HTTP 如何转发。
6. `filter_response_content()`：看正文关键字如何过滤。
7. `forward_connect()`：看 HTTPS 隧道为什么只能转发加密流量。
8. `AdminHandler`：看前端和命令行如何修改规则。
9. `src/webproxy/config_rules.py`：看规则组元数据和输入规范化。
10. `tools/rule_cli.py`：看后端命令行管理如何调用 API。

