# Web 代理服务器期末实验

项目名称建议：**基于 Socket 的 Web 代理服务器设计与实现**

本项目用于“计算机安全与保密”课程期末实验。目标是逐步实现一个 Web 代理服务器，而不是一次性复制完整代码。

## 最终展示入口

项目功能、系统架构、实现技术、验收入口和重要边界汇总在：

```text
PROJECT_SHOWCASE.md
```

课程期末实验报告及其 LaTeX 源文件位于：

```text
report/final_report.pdf
report/final_report.tex
```

现场逐模块验收命令、参数解释和预期结果位于：

```text
docs/08_backend_cli_rule_management.md
```

源码结构、核心函数和代理过滤流程阅读指南位于：

```text
docs/10_project_structure.md
```

## 课程最低要求

1. 能够接收客户端的 Web 访问请求。
2. 能够把请求转发给真实 Web 服务器。
3. 能够把服务器返回的网页返回给客户端。
4. 能够拦截指定域名。
5. 能够过滤包含指定关键字的网页内容。
6. 能够通过前端或命令行新增、删除、查询过滤条件。

## 推荐实现路线

推荐使用 **Python + socket + threading**。

原因：

- Windows 本机可以运行。
- Docker 容器里也可以运行。
- 不依赖图形界面。
- 便于说明代理服务器的底层原理。
- 课程报告里容易解释“监听、解析、转发、过滤、返回”的过程。

## 项目结构

```text
web_proxy_final_lab/
  README.md
  config.example.json
  frontend/
    index.html
    logs.html
  docs/
    00_project_overview.md
    00_environment.md
    01_minimum_project_steps.md
    02_feature_roadmap.md
    03_report_checklist.md
    04_frontend_backend.md
    05_module_implementation_log.md
    06_acceptance_and_self_check.md
    07_manual_module_verification.md
    08_backend_cli_rule_management.md
    09_powershell_and_backend_echo_fix.md
    10_project_structure.md
  src/
    README.md
    proxy.py
    webproxy/
      __init__.py
      audit.py
      config_rules.py
      evidence.py
  tests/
    manual_test_commands.md
    manual_acceptance_workflow_smoke.py
    manual_demo_server.py
    manual_connect_tunnel.py
    webroot/
      index.html
      forbidden.html
      content-test.html
      classroom.html
      game/index.html
  tools/
    start_proxy_browser.ps1
  docker/
    README.md
```

## 建议完成顺序

1. 普通 HTTP 代理转发。已完成。
2. 域名黑名单拦截。已完成。
3. HTTP 网页正文关键字过滤。已完成。
4. URL 关键字拦截、请求方法过滤、日志、统计。已完成。
5. 管理前端和后端 API。已完成。
6. 过滤规则增删改查和命令行管理。已完成。
7. HTTPS CONNECT 隧道。已完成。
8. HTTP GET 缓存。已完成。
9. 代理认证、频率限制等加分功能。已完成。

## 当前运行方式

启动代理和管理前端：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

代理端口：

```text
http://127.0.0.1:8080
```

管理前端：

```text
http://127.0.0.1:8088/
```

手动验收建议在另一个 PowerShell 启动确定性测试目标：

```powershell
python tests\manual_demo_server.py
```

访问本机测试站时，代理命令应包含 `--noproxy no-host-bypass.invalid`，否则 Windows `curl.exe` 可能根据 `NO_PROXY` 绕过代理，使 URL/正文过滤、缓存和限流看起来失效。完整逐模块命令见 `docs/07_manual_module_verification.md`。

Edge/Chrome 还会默认绕过本机地址。浏览器验收请运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1
```

该命令启动独立浏览器配置并强制 `127.0.0.1` 经过代理。命中域名、URL、方法或正文规则时，代理会用带“查看详细信息”的 `403` 页面替代原网页。

启动器会自动打开以下两个浏览器验收地址：

```text
http://127.0.0.1.nip.io:9000/game/index.html
http://127.0.0.1.nip.io:9000/content-test.html
```

`127.0.0.1.nip.io` 解析到本机，但不会触发 Chromium 对 `127.0.0.1` 字面地址的默认代理绕过，因此比在普通浏览器中直接输入 `127.0.0.1:9000` 更适合现场验收。

前端支持规则变更回显：添加、修改、删除、替换规则组后，页面会显示操作类型、规则组、旧值/新值以及是否保存成功。

查询、添加、删除过滤规则的命令示例：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"value`":`"classroom`"}"
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"old_value`":`"classroom`",`"new_value`":`"lecture`"}"
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"value`":`"lecture`"}"
curl.exe "http://127.0.0.1:8088/api/changes?limit=20"
```

也可以使用后端命令行工具：

```powershell
python tools\rule_cli.py list
python tools\rule_cli.py add blocked_content_keywords classroom
python tools\rule_cli.py update blocked_content_keywords classroom lecture
python tools\rule_cli.py delete blocked_content_keywords lecture
python tools\rule_cli.py replace blocked_url_keywords private exam
python tools\rule_cli.py config
python tools\rule_cli.py set mode whitelist
python tools\rule_cli.py auth-user student 123456
python tools\rule_cli.py set proxy_auth_enabled true
python tools\rule_cli.py set rate_limit_enabled true
python tools\rule_cli.py set rate_limit_per_minute 1
python tools\rule_cli.py set rate_limit_window_seconds 60
python tools\rule_cli.py rate-reset
python tools\rule_cli.py changes --limit 20
python tools\rule_cli.py log-query --kind blocked --event BLOCK --search domain_blacklist --limit 20
python tools\rule_cli.py log-export --kind blocked --event BLOCK --output exports\blocked.csv
```

详细说明见：

```text
docs/08_backend_cli_rule_management.md
docs/09_powershell_and_backend_echo_fix.md
```

分批验证：

```powershell
python tests\run_web_features_smoke.py
python tests\run_rule_management_smoke.py
```

第一条验证基础 Web/代理功能；第二条验证规则组增删改查、模式切换和运行时设置。

一键验证全部批次：

```powershell
python tests\run_all_smoke.py
```

批量测试会生成可由管理前端读取的访问日志、拦截日志和持久化规则变更记录。Web 功能证据与规则管理证据使用不同目录，互不覆盖。管理台统计数字可以点击进入日志查询详情页。重复运行、证据位置、前端查看方式和限流值为 `1` 时的准确行为见：

```text
docs/08_backend_cli_rule_management.md
```

运行批量测试后，仍然只需启动普通管理端：

```powershell
python src\proxy.py --config config.example.json
```

打开 `http://127.0.0.1:8088/` 后，首页会在存在验收证据时默认显示“最近验收”。总请求、总拦截、排行、右侧日志和规则变更回显会一起显示最近一次一键验收结果；也可以点击“当前运行”切回本次代理进程的实时数据。证据读取是只读操作，不会改变当前运行规则。

代码更新后需要在旧代理终端按 `Ctrl+C` 停止进程，再重新执行启动命令；仅刷新网页不会让已经运行的 Python 后端加载新接口。

## 重要边界

普通代理可以过滤 **HTTP 明文网页内容**。  
对于 **HTTPS**，普通代理只能看到 CONNECT 请求里的目标域名，不能直接看到网页正文，所以可以做 HTTPS 域名拦截，但不建议把 HTTPS 正文过滤作为基础要求。

## 客户端 IP/CIDR 访问控制

代理支持动态管理客户端 IP 黑名单和白名单，规则支持单个 IPv4/IPv6 地址与 CIDR 网段：

```powershell
python tools\rule_cli.py add blocked_client_ips 192.168.1.0/24
python tools\rule_cli.py delete blocked_client_ips 192.168.1.0/24
python tools\rule_cli.py add allowed_client_ips 127.0.0.1
python tools\rule_cli.py delete allowed_client_ips 127.0.0.1
python tests\stage18_client_ip_policy_smoke.py
```

客户端黑名单优先于白名单；白名单非空时，仅匹配白名单的客户端可以使用代理。管理前端统计区使用自适应布局，并提供可点击的“客户端拦截”日志查询。
