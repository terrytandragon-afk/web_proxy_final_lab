# Web 代理服务器期末实验

项目名称建议：**基于 Socket 的 Web 代理服务器设计与实现**

本项目用于“计算机安全与保密”课程期末实验。目标是逐步实现一个 Web 代理服务器，而不是一次性复制完整代码。

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
  src/
    README.md
  tests/
    manual_test_commands.md
    webroot/
      index.html
      forbidden.html
      classroom.html
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
```

详细说明见：

```text
docs/08_backend_cli_rule_management.md
docs/09_powershell_and_backend_echo_fix.md
```

一键验证：

```powershell
python tests\run_all_smoke.py
```

## 重要边界

普通代理可以过滤 **HTTP 明文网页内容**。  
对于 **HTTPS**，普通代理只能看到 CONNECT 请求里的目标域名，不能直接看到网页正文，所以可以做 HTTPS 域名拦截，但不建议把 HTTPS 正文过滤作为基础要求。
