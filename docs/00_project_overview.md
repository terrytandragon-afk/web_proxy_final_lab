# 00 项目总览

项目名称：**基于 Socket 的 Web 代理服务器设计与实现**

本项目是一个完整的课程实验项目，包含代理服务、规则过滤、规则增删改查管理、日志审计、统计展示、管理前端、HTTPS CONNECT 隧道和 HTTP 缓存等模块。

## 一、系统总体架构

```text
curl / 浏览器
    |
    | 代理请求
    v
代理服务 127.0.0.1:8080
    |
    | 访问控制、内容过滤、缓存判断
    v
目标 Web 服务器

管理前端 127.0.0.1:8088
    |
    | JSON API
    v
规则增删改查、日志、统计、缓存状态
```

## 二、目录结构

```text
web_proxy_final_lab/
  src/proxy.py                         代理服务和管理 API 主程序
  frontend/index.html                  可编辑规则管理前端页面
  config.example.json                  规则和运行参数配置文件
  configs/*.example.json               认证、限流、白名单等专项演示配置
  docs/00_project_overview.md          项目总览
  docs/05_module_implementation_log.md 模块实现与命令说明
  docs/06_acceptance_and_self_check.md 验收和自测流程
  docs/07_manual_module_verification.md逐模块手工验证
  docs/08_backend_cli_rule_management.md后端命令行规则管理验收
  docs/09_powershell_and_backend_echo_fix.md PowerShell/CMD 引号兼容与后端回显
  tests/stage*_smoke.py                自动验证脚本
```

## 三、启动命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

命令含义：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python
```

使用 Python 解释器运行程序。

```text
src\proxy.py
```

项目主程序，同时启动代理服务和管理服务。

```text
--config config.example.json
```

指定配置文件，程序从中读取端口、过滤规则、缓存设置和日志路径。

启动后：

```text
代理服务：http://127.0.0.1:8080
管理前端：http://127.0.0.1:8088/
```

## 四、功能优先级划分

### P0：课程基础必做功能

这些功能对应题目最低要求，必须完成。

#### P0.1 HTTP 代理转发

已实现：

- 接收客户端 HTTP 请求。
- 转发给目标 Web 服务器。
- 将响应返回客户端。

验证命令：

```powershell
python tests\stage4_smoke.py
```

#### P0.2 指定域名拦截

已实现：

- 配置域名黑名单。
- 命中黑名单时返回 `403 Forbidden`。

验证命令：

```powershell
python tests\stage5_smoke.py
```

#### P0.3 网页正文关键字过滤

已实现：

- 对 HTTP 明文网页正文做关键字检测。
- 命中关键字时返回过滤提示页。

验证命令：

```powershell
python tests\stage6_smoke.py
```

### P1：推荐完善功能

这些功能能让项目更像完整系统，建议重点展示。

#### P1.1 URL 关键字拦截与请求方法过滤

已实现：

- URL 中包含指定关键字时拦截。
- 禁止 `PUT`、`DELETE` 等 HTTP 方法。

验证命令：

```powershell
python tests\stage7_policy_smoke.py
```

#### P1.2 日志审计与运行统计

已实现：

- 访问日志。
- 拦截日志。
- 错误日志。
- 请求数、放行数、拦截数、过滤数统计。

查看命令：

```powershell
Get-Content E:\eve_jump\web_proxy_final_lab\logs\proxy.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\blocked.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\error.log
```

#### P1.3 管理前端与后端 API

已实现：

- 前端显示规则、日志、统计、缓存状态。
- 前端支持新增、删除、查询过滤规则。
- 后端提供 JSON API。
- 支持重新加载配置。

验证命令：

```powershell
python tests\stage8_admin_smoke.py
```

打开前端：

```text
http://127.0.0.1:8088/
```

#### P1.4 过滤规则增删改查与命令行管理

已实现：

- 查询当前过滤规则。
- 新增域名黑名单、域名白名单、URL 关键字、正文关键字、禁止方法。
- 删除上述过滤规则。
- 修改单条过滤规则。
- 替换整个规则组。
- 新增和删除后立即影响代理运行。
- 规则会保存回当前 `--config` 指定的 JSON 配置文件。
- 支持 `curl.exe` 调后端 API，也支持 `python tools\rule_cli.py` 命令行工具。

自动验证命令：

```powershell
python tests\stage15_rule_management_smoke.py
python tests\stage16_rule_cli_smoke.py
python tests\stage17_runtime_settings_smoke.py
```

命令行新增正文关键字示例：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令行删除正文关键字示例：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令行工具示例：

```powershell
python tools\rule_cli.py add blocked_content_keywords classroom
python tools\rule_cli.py update blocked_content_keywords classroom lecture
python tools\rule_cli.py delete blocked_content_keywords lecture
python tools\rule_cli.py replace blocked_url_keywords private exam
```

查询规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

#### P1.5 HTTPS CONNECT 隧道

已实现：

- 支持 HTTPS CONNECT 隧道。
- 支持 HTTPS 目标域名拦截。
- 明确不对 HTTPS 正文做关键字过滤。

验证命令：

```powershell
python tests\stage9_connect_smoke.py
```

#### P1.6 HTTP GET 缓存

已实现：

- 缓存 HTTP GET 响应。
- 第二次访问同一 URL 时直接返回缓存。
- 前端展示缓存命中、未命中、缓存条目数。

验证命令：

```powershell
python tests\stage10_cache_smoke.py
```

### P2：加分扩展功能

这些功能可以根据时间继续做。

#### P2.1 白名单模式

已实现：

- 配置文件支持 `mode: whitelist`。
- 只有 `allowed_domains` 中的域名可以访问。

验证命令：

```powershell
python tests\stage11_whitelist_smoke.py
```

#### P2.2 配置热加载

已实现：

- 修改配置文件后，可以通过 API 重新加载。

命令：

```powershell
curl -X POST http://127.0.0.1:8088/api/reload
```

#### P2.3 演示重置 API

已实现：

- 清空缓存。
- 重置统计。
- 清空日志。
- 前端提供按钮。

命令：

```powershell
curl -X POST http://127.0.0.1:8088/api/cache/clear
curl -X POST http://127.0.0.1:8088/api/stats/reset
curl -X POST http://127.0.0.1:8088/api/logs/clear
```

#### P2.4 Docker 运行

已提供 Docker 命令说明：

```text
docker/README.md
```

### P3：后续展望功能

这些功能中，代理认证和访问频率限制已经实现；HTTPS 中间人过滤不建议作为基础目标。

#### P3.1 代理认证

已实现：

- 用户名密码认证。
- 未认证返回 `407 Proxy Authentication Required`。

验证命令：

```powershell
python tests\stage13_auth_smoke.py
```

#### P3.2 访问频率限制

已实现：

- 限制单个客户端每分钟请求次数。
- 超过限制返回 `429 Too Many Requests`。

验证命令：

```powershell
python tests\stage14_rate_limit_smoke.py
```

#### P3.3 HTTPS 中间人过滤

不建议实现为基础功能：

- 需要生成 CA 证书。
- 需要客户端信任证书。
- 涉及 HTTPS 解密和重新加密。
- 课程报告中可作为安全边界说明。

## 五、一键自动验证

推荐使用一条命令运行全部自动测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
```

预期结果：

```text
all smoke tests passed
```

也可以逐个运行：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage4_smoke.py
python tests\stage5_smoke.py
python tests\stage6_smoke.py
python tests\stage7_policy_smoke.py
python tests\stage8_admin_smoke.py
python tests\stage9_connect_smoke.py
python tests\stage10_cache_smoke.py
python tests\stage11_whitelist_smoke.py
python tests\stage12_frontend_display_smoke.py
python tests\stage13_auth_smoke.py
python tests\stage14_rate_limit_smoke.py
python tests\stage15_rule_management_smoke.py
python tests\stage16_rule_cli_smoke.py
```

预期结果：

```text
stage4 smoke test passed
stage5 smoke test passed
stage6 smoke test passed
stage7 policy smoke test passed
stage8 admin smoke test passed
stage9 connect smoke test passed
stage10 cache smoke test passed
stage11 whitelist smoke test passed
stage12 frontend display smoke test passed
stage13 auth smoke test passed
stage14 rate limit smoke test passed
stage15 rule management smoke test passed
stage16 rule cli smoke test passed
stage17 runtime settings smoke test passed
```

## 六、最新完善：客户端 IP/CIDR 访问控制

系统现在不仅能控制客户端访问哪些网站，还能控制哪些客户端可以使用代理：

- `blocked_client_ips`：客户端 IP 黑名单，命中后返回 `403 Forbidden`。
- `allowed_client_ips`：客户端 IP 白名单；列表非空时，未命中的客户端被拒绝。
- 支持单个 IPv4/IPv6 地址和 CIDR 网段。
- 规则可通过前端、管理 API 和 Python CLI 实时增删改查，无需重启代理。
- 拦截原因记录为 `client_ip_blacklist` 或 `client_ip_not_allowed`。
- 前端提供独立的“客户端拦截”统计和日志详情入口。

验证命令：

```powershell
python tests\stage18_client_ip_policy_smoke.py
```

后续扩展建议按价值排序：

1. `P1` 规则配置导入、导出与版本回滚，适合课堂展示配置备份。
2. `P1` 管理端登录认证，避免局域网内其他用户修改代理规则。
3. `P2` 定时规则，例如仅在指定时间段启用某组拦截规则。
4. `P2` SQLite 持久化审计，用于更大规模的分页、聚合和趋势查询。
5. `P3` HTTPS MITM 正文过滤，仅适合受控实验环境，不建议作为基础功能。

## 六、前端展示验收

前端管理台地址：

```text
http://127.0.0.1:8088/
```

自动验证前端页面和 API：

```powershell
python tests\stage12_frontend_display_smoke.py
```

该测试会验证：

- 前端 HTML 能正常返回。
- 页面包含“缓存命中”“HTTPS 隧道”等统计项。
- `/api/config` 能返回当前过滤规则。
- `/api/rules` 能返回当前可编辑规则分组。
- `/api/stats` 能返回请求统计、缓存统计、拦截统计。
- `/api/logs` 能返回访问日志。
