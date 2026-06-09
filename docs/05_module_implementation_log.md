# 05 模块实现清单与命令说明

本文件用于课程展示和验收。每完成一个功能模块，都在这里记录：

- 实现了什么功能。
- 涉及哪些文件。
- 用什么命令启动或验证。
- 命令中每个参数是什么意思。
- 展示时应该观察什么结果。

## 模块 1：HTTP 代理转发

### 已实现功能

- 代理服务器监听 `127.0.0.1:8080`。
- 接收客户端 HTTP 请求。
- 解析请求方法、目标域名、端口和路径。
- 将请求转发给真实 Web 服务器。
- 将服务器响应返回给客户端。

### 涉及文件

```text
src/proxy.py
tests/stage4_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage4_smoke.py
```

### 命令含义

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python tests\stage4_smoke.py
```

运行 HTTP 转发自动测试。测试脚本会临时启动一个本地 Web 服务器，再通过代理访问它。

### 预期输出

```text
stage4 smoke test passed
```

## 模块 2：域名黑名单拦截

### 已实现功能

- 从配置文件读取 `blocked_domains`。
- 命中黑名单域名时，代理直接返回 `403 Forbidden`。
- 被拦截请求不会连接真实服务器。
- 支持 `*.example.com` 形式的通配符规则。

### 涉及文件

```text
src/proxy.py
config.example.json
tests/stage5_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage5_smoke.py
```

### 命令含义

```text
python tests\stage5_smoke.py
```

运行域名黑名单测试。测试会访问 `blocked.test`，验证代理返回 403。

### 预期输出

```text
stage5 smoke test passed
```

## 模块 3：网页正文关键字过滤

### 已实现功能

- 从配置文件读取 `blocked_content_keywords`。
- 只对文本类响应做关键字检测。
- 支持 HTML、普通文本、CSS、JavaScript、JSON 等类型。
- 命中关键字时返回过滤提示页。
- 图片、压缩包等二进制内容不做正文扫描。

### 涉及文件

```text
src/proxy.py
config.example.json
tests/stage6_smoke.py
tests/webroot/forbidden.html
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage6_smoke.py
```

### 命令含义

```text
python tests\stage6_smoke.py
```

运行网页正文关键字过滤测试。测试页面包含 `forbidden`，代理应返回“网页已被过滤”。

### 预期输出

```text
stage6 smoke test passed
```

## 模块 4：URL 关键字拦截与请求方法过滤

### 已实现功能

- 从配置文件读取 `blocked_url_keywords`。
- 如果 URL 中包含 `game`、`download`、`admin` 等关键字，直接返回 403。
- 从配置文件读取 `blocked_methods`。
- 如果请求方法是 `DELETE`、`PUT` 等禁止方法，直接返回 403。

### 涉及文件

```text
src/proxy.py
config.example.json
tests/stage7_policy_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage7_policy_smoke.py
```

### 命令含义

```text
python tests\stage7_policy_smoke.py
```

运行访问控制策略测试。测试会分别验证 URL 关键字拦截和 HTTP 方法拦截。

### 预期输出

```text
stage7 policy smoke test passed
```

## 模块 5：日志审计与运行统计

### 已实现功能

- 记录访问日志。
- 记录拦截日志。
- 记录错误日志。
- 统计总请求数、放行数、域名拦截数、URL 拦截数、方法拦截数、正文过滤数。
- 统计域名访问排行。
- 统计关键字命中排行。
- 统计代理收发字节数。

### 涉及文件

```text
src/proxy.py
config.example.json
logs/proxy.log
logs/blocked.log
logs/error.log
```

### 手动查看命令

```powershell
Get-Content E:\eve_jump\web_proxy_final_lab\logs\proxy.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\blocked.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\error.log
```

### 命令含义

```text
Get-Content
```

读取文本文件内容。

```text
logs/proxy.log
```

访问日志，记录允许访问和普通请求结果。

```text
logs/blocked.log
```

拦截日志，记录域名拦截、URL 拦截、方法拦截和正文过滤。

```text
logs/error.log
```

错误日志，记录请求格式错误、连接失败、超时等情况。

### 实时查看命令

```powershell
Get-Content E:\eve_jump\web_proxy_final_lab\logs\proxy.log -Wait
```

### 命令含义

```text
-Wait
```

持续监听文件变化，日志新增时会自动显示，适合课堂展示。

## 模块 6：管理前端与后端 API

### 已实现功能

- 代理端口和管理端口分离。
- `8080` 负责代理转发。
- `8088` 负责管理前端和 API。
- 前端显示规则、统计、日志、域名排行和关键字排行。
- 支持点击按钮重新加载配置。

### 涉及文件

```text
src/proxy.py
frontend/index.html
docs/04_frontend_backend.md
tests/stage8_admin_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage8_admin_smoke.py
```

### 预期输出

```text
stage8 admin smoke test passed
```

### 启动命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

### 命令参数含义

```text
python
```

使用 Python 解释器运行程序。

```text
src\proxy.py
```

代理服务器主程序。

```text
--config config.example.json
```

指定配置文件。程序会从该文件读取代理端口、管理端口、黑名单、关键字和日志路径。

### 前端打开地址

```text
http://127.0.0.1:8088/
```

## 模块 7：HTTPS CONNECT 隧道

### 已实现功能

- 支持 `CONNECT host:443 HTTP/1.1` 请求。
- 代理连接目标服务器后返回 `200 Connection Established`。
- 在客户端和目标服务器之间转发加密字节流。
- 支持对 HTTPS 目标域名做黑名单拦截。
- HTTPS 正文不做关键字过滤，因为正文经过 TLS 加密。
- 管理前端统计 `HTTPS 隧道` 次数。

### 涉及文件

```text
src/proxy.py
frontend/index.html
tests/stage9_connect_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage9_connect_smoke.py
```

### 命令含义

```text
python tests\stage9_connect_smoke.py
```

运行 HTTPS CONNECT 隧道测试。测试脚本会启动一个本地 TCP 服务，通过代理发送 `CONNECT` 请求，验证隧道建立后字节可以正常转发。

### 预期输出

```text
stage9 connect smoke test passed
```

### 外部 HTTPS 验证命令

如果网络环境允许，可以执行：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

### 命令参数含义

```text
curl
```

命令行 HTTP 客户端。

```text
-I
```

只请求响应头，不下载完整网页正文。

```text
-x http://127.0.0.1:8080
```

指定代理服务器地址和端口。

```text
https://example.com/
```

目标 HTTPS 网站。curl 会先向代理发送 CONNECT 请求，再进行 TLS 访问。

### 展示时说明

```text
HTTPS CONNECT 模块只能看到目标域名，不能看到 HTTPS 网页正文。因此本系统对 HTTPS 支持域名拦截，但不做正文关键字过滤。HTTP 明文网页可以做正文关键字过滤。
```

## 模块 8：HTTP GET 缓存

### 已实现功能

- 支持缓存 HTTP `GET` 请求的响应。
- 缓存命中时，代理直接返回缓存内容，不再连接目标服务器。
- 支持配置缓存开关、缓存有效时间和最大缓存条目数。
- 管理前端显示缓存命中、缓存未命中和缓存条目数。
- 日志中记录 `CACHE_HIT` 事件。

### 涉及文件

```text
src/proxy.py
frontend/index.html
config.example.json
tests/stage10_cache_smoke.py
```

### 配置项

```json
{
  "cache_enabled": true,
  "cache_ttl_seconds": 60,
  "cache_max_items": 100
}
```

配置含义：

```text
cache_enabled
```

是否启用缓存。

```text
cache_ttl_seconds
```

缓存有效时间，单位是秒。

```text
cache_max_items
```

最多缓存多少个 URL 响应，超过后删除最早缓存的条目。

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage10_cache_smoke.py
```

### 命令含义

```text
python tests\stage10_cache_smoke.py
```

运行缓存测试。测试脚本会连续两次请求同一个 URL。第一次访问目标服务器并写入缓存，第二次由代理直接返回缓存。

### 预期输出

```text
stage10 cache smoke test passed
```

### 手动展示命令

先启动本地测试网站：

```powershell
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

再启动代理：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

连续访问同一页面两次：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

命令参数含义：

```text
curl
```

命令行 HTTP 客户端。

```text
-i
```

显示响应头和正文。

```text
-x http://127.0.0.1:8080
```

指定代理服务器。

```text
http://127.0.0.1:9000/
```

目标测试网站地址。

展示现象：

```text
第一次请求：缓存未命中，访问目标服务器。
第二次请求：缓存命中，代理直接返回缓存。
```

管理前端中应看到：

```text
缓存命中
缓存未命中
缓存条目
```

## 一键自动验证当前全部模块

推荐命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
```

预期输出：

```text
all smoke tests passed
```

逐个运行命令：

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
```

预期输出：

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
```

## 模块 9：白名单模式

### 已实现功能

- 支持配置 `mode: whitelist`。
- 只有 `allowed_domains` 中的域名可以访问。
- 不在白名单中的域名返回 `403 Forbidden`。
- 拦截原因显示为 `domain_not_in_whitelist`。

### 涉及文件

```text
src/proxy.py
config.example.json
tests/stage11_whitelist_smoke.py
```

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage11_whitelist_smoke.py
```

### 命令含义

```text
python tests\stage11_whitelist_smoke.py
```

运行白名单模式测试。测试脚本会允许 `127.0.0.1` 访问，同时拦截 `not-allowed.test`。

### 预期输出

```text
stage11 whitelist smoke test passed
```

### 手动展示命令

将配置文件中的模式改为：

```json
{
  "mode": "whitelist",
  "allowed_domains": ["127.0.0.1", "localhost"]
}
```

启动代理：

```powershell
python src\proxy.py --config config.example.json
```

访问允许域名：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

访问非白名单域名：

```powershell
curl -i -x http://127.0.0.1:8080 http://not-allowed.test/
```

命令参数含义：

```text
-x http://127.0.0.1:8080
```

指定使用本项目代理服务器。

展示现象：

```text
白名单内域名可以访问。
白名单外域名返回 403 Forbidden。
```

## 模块 10：一键验收与前端展示验证

### 已实现功能

- 提供一键运行全部自动测试的脚本。
- 验证前端 HTML 能正常返回。
- 验证前端展示项包含缓存、HTTPS、规则、统计等关键内容。
- 验证管理 API 可以返回配置、统计和日志。

### 涉及文件

```text
tests/run_all_smoke.py
tests/stage12_frontend_display_smoke.py
frontend/index.html
src/proxy.py
```

### 一键验收命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
```

### 命令含义

```text
python tests\run_all_smoke.py
```

依次运行所有功能模块的自动测试。任意模块失败时，脚本会停止并显示失败的测试文件。

### 预期输出

```text
all smoke tests passed
```

### 前端展示验证命令

```powershell
python tests\stage12_frontend_display_smoke.py
```

### 命令含义

```text
stage12_frontend_display_smoke.py
```

启动临时代理服务、管理服务和测试 Web 服务，产生访问流量，然后验证前端页面和 API 中是否能展示规则、日志、统计、缓存指标。

### 预期输出

```text
stage12 frontend display smoke test passed
```

## 模块 11：代理认证

### 已实现功能

- 支持 `Proxy-Authorization: Basic ...` 认证。
- 未提供认证或认证错误时返回 `407 Proxy Authentication Required`。
- 认证成功后才继续执行访问控制和代理转发。
- 管理前端显示认证开关和认证拦截次数。

### 涉及文件

```text
src/proxy.py
frontend/index.html
config.example.json
tests/stage13_auth_smoke.py
```

### 配置项

```json
{
  "proxy_auth_enabled": false,
  "proxy_auth_users": {
    "student": "123456"
  }
}
```

配置含义：

```text
proxy_auth_enabled
```

是否启用代理认证。

```text
proxy_auth_users
```

允许使用代理的用户名和密码。

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage13_auth_smoke.py
```

### 手动展示命令

启用认证后，未认证访问：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

正确认证访问：

```powershell
curl -i -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

命令参数含义：

```text
--proxy-user student:123456
```

向代理服务器发送用户名和密码。curl 会自动生成 `Proxy-Authorization` 请求头。

预期现象：

```text
未认证返回 407。
正确认证返回 200。
```

## 模块 12：访问频率限制

### 已实现功能

- 支持按客户端 IP 限制每分钟请求次数。
- 超过限制时返回 `429 Too Many Requests`。
- 管理前端显示限流拦截次数。

### 涉及文件

```text
src/proxy.py
frontend/index.html
config.example.json
tests/stage14_rate_limit_smoke.py
```

### 配置项

```json
{
  "rate_limit_enabled": false,
  "rate_limit_per_minute": 60
}
```

配置含义：

```text
rate_limit_enabled
```

是否启用访问频率限制。

```text
rate_limit_per_minute
```

同一个客户端 IP 每分钟最多允许多少次请求。

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage14_rate_limit_smoke.py
```

### 手动展示命令

启用限流后，连续快速访问：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期现象：

```text
超过每分钟限制后返回 429 Too Many Requests。
管理前端中的“限流拦截”数字增加。
```

## 模块 13：演示重置 API

### 已实现功能

- 清空缓存。
- 重置统计。
- 清空日志。
- 前端提供对应按钮。
- 命令行可通过 POST 请求调用。

### 涉及文件

```text
src/proxy.py
frontend/index.html
tests/stage8_admin_smoke.py
```

### 命令行验证

```powershell
curl -X POST http://127.0.0.1:8088/api/cache/clear
curl -X POST http://127.0.0.1:8088/api/stats/reset
curl -X POST http://127.0.0.1:8088/api/logs/clear
```

命令参数含义：

```text
-X POST
```

指定使用 POST 方法调用管理 API。

```text
/api/cache/clear
```

清空代理缓存。

```text
/api/stats/reset
```

重置统计数字和排行。

```text
/api/logs/clear
```

清空访问日志、拦截日志和错误日志。

预期结果：

```text
"ok": true
```

前端展示：

```text
点击“清空缓存”“重置统计”“清空日志”按钮后，对应数据归零或清空。
```

## 模块 14：过滤规则增删改查管理

### 已实现功能

- 查询当前所有可编辑过滤规则。
- 新增域名黑名单规则。
- 删除域名黑名单规则。
- 新增域名白名单规则。
- 删除域名白名单规则。
- 新增 URL 关键字规则。
- 删除 URL 关键字规则。
- 新增网页正文关键字规则。
- 删除网页正文关键字规则。
- 新增禁止 HTTP 方法规则。
- 删除禁止 HTTP 方法规则。
- 修改单条过滤规则。
- 替换整个规则组。
- 支持保存模式、缓存、认证、限流等运行设置。
- 规则新增、删除、修改或替换后立即影响代理运行。
- 规则会保存回当前 `--config` 指定的 JSON 配置文件，重启后不会丢。
- 支持 `curl.exe` 直接调用后端 API。
- 支持 `python tools\rule_cli.py` 后端命令行管理工具。

### 涉及文件

```text
src/proxy.py
frontend/index.html
config.example.json
tools/rule_cli.py
tests/stage15_rule_management_smoke.py
tests/stage16_rule_cli_smoke.py
```

### Python 实现位置

```text
src/proxy.py
LIST_RULE_FIELDS
normalize_rule_value()
build_rules_payload()
RuntimeState.get_rules()
RuntimeState.add_list_rule()
RuntimeState.delete_list_rule()
RuntimeState.update_list_rule()
RuntimeState.replace_list_rules()
RuntimeState.update_settings()
AdminHandler.do_GET()
AdminHandler.do_POST()
AdminHandler.read_json_body()
```

实现说明：

```text
LIST_RULE_FIELDS
```

定义哪些配置项可以通过前端、API 和命令行工具增删改查。

```text
normalize_rule_value()
```

整理用户输入，例如域名转小写、HTTP 方法转大写、空值不允许保存。

```text
RuntimeState.add_list_rule()
```

向当前运行配置中添加规则，并写回配置文件。

```text
RuntimeState.delete_list_rule()
```

从当前运行配置中删除规则，并写回配置文件。

```text
RuntimeState.update_list_rule()
```

修改当前运行配置中的一条规则，并写回配置文件。

```text
RuntimeState.replace_list_rules()
```

一次性替换某个规则组，并写回配置文件。

```text
AdminHandler.do_POST()
```

接收 `/api/rules/add`、`/api/rules/delete`、`/api/rules/update`、`/api/rules/replace`、`/api/settings/update` 等管理请求。

### 前端实现位置

```text
frontend/index.html
renderRuleGroups()
addRule()
deleteRule()
updateRule()
replaceRuleGroup()
renderChangeLog()
saveSettings()
```

实现说明：

```text
renderRuleGroups()
```

把 `/api/rules` 返回的规则分组渲染成输入框、添加按钮、修改按钮、删除按钮和替换整组按钮。

```text
addRule()
```

点击“添加”时调用 `/api/rules/add`。

```text
deleteRule()
```

点击“删除”时调用 `/api/rules/delete`。

```text
updateRule()
```

点击“修改”时调用 `/api/rules/update`。

```text
replaceRuleGroup()
```

点击“替换整组”时调用 `/api/rules/replace`。

```text
renderChangeLog()
```

渲染“规则变更回显”，显示本次新增、删除、修改或替换的规则组和值。

```text
saveSettings()
```

点击“保存设置”时调用 `/api/settings/update`。

### 自动验证命令

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage15_rule_management_smoke.py
python tests\stage16_rule_cli_smoke.py
```

命令含义：

```text
python tests\stage15_rule_management_smoke.py
```

运行规则管理自动测试。`stage15` 通过 API 新增、删除、修改、替换规则并检查代理行为；`stage16` 通过命令行工具 `tools/rule_cli.py` 完成同样的底层操作验证。

预期输出：

```text
stage15 rule management smoke test passed
stage16 rule cli smoke test passed
```

### 查询规则命令

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

命令含义：

```text
curl.exe
```

Windows 下明确调用 curl 程序，避免 PowerShell 把 `curl` 当成别名。

```text
http://127.0.0.1:8088/api/rules
```

管理后端的规则查询接口，返回所有可编辑规则分组。

### 新增正文关键字

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令参数含义：

```text
-X POST
```

使用 POST 方法，因为这是新增规则操作。

```text
/api/rules/add
```

规则新增接口。

```text
-H "Content-Type: application/json"
```

声明请求体是 JSON。

```text
rule_type
```

规则类型。`blocked_content_keywords` 表示网页正文关键字。

```text
value
```

规则值。这里新增的正文关键字是 `classroom`。

### 验证新增正文关键字生效

新增后访问正文包含该关键字的页面：

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

如果页面正文包含新关键字，预期结果：

```text
网页已被过滤
This page is blocked by keyword filter
```

### 删除正文关键字

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令参数含义：

```text
/api/rules/delete
```

规则删除接口。

```text
blocked_content_keywords
```

表示删除的是正文关键字规则。

```text
classroom
```

要删除的规则值。

### 修改正文关键字

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

命令参数含义：

```text
/api/rules/update
```

规则修改接口。

```text
old_value
```

原规则值。

```text
new_value
```

修改后的新规则值。

### 替换整个规则组

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":["private","exam"]}'
```

命令参数含义：

```text
/api/rules/replace
```

规则组替换接口。

```text
values
```

新的规则组列表。执行后原有同类型规则会被这一组值替换。

清空 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":[]}'
```

### 后端命令行工具

查询规则：

```powershell
python tools\rule_cli.py list
```

新增规则：

```powershell
python tools\rule_cli.py add blocked_content_keywords classroom
```

修改规则：

```powershell
python tools\rule_cli.py update blocked_content_keywords classroom lecture
```

删除规则：

```powershell
python tools\rule_cli.py delete blocked_content_keywords lecture
```

替换规则组：

```powershell
python tools\rule_cli.py replace blocked_url_keywords private exam
```

清空规则组：

```powershell
python tools\rule_cli.py replace blocked_url_keywords
```

命令参数含义：

```text
tools\rule_cli.py
```

项目提供的后端规则管理命令行工具，内部调用管理 API。

```text
list / add / update / delete / replace
```

分别表示查询、新增、修改、删除、替换规则组。

### 其他规则增删命令

新增域名黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
```

删除域名黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
```

新增域名白名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

删除域名白名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

新增 URL 关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","value":"private"}'
```

删除 URL 关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","value":"private"}'
```

新增禁止方法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_methods","value":"PATCH"}'
```

删除禁止方法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_methods","value":"PATCH"}'
```

### 切换黑名单/白名单模式

切换白名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"whitelist"}}'
```

切换回黑名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"blacklist"}}'
```

命令参数含义：

```text
/api/settings/update
```

运行设置更新接口。

```text
settings
```

需要更新的设置对象。

```text
mode
```

访问控制模式，支持 `blacklist` 和 `whitelist`。

### 前端展示

打开：

```text
http://127.0.0.1:8088/
```

页面中可以看到：

```text
过滤规则管理
运行设置
域名黑名单
域名白名单
URL 关键字
正文关键字
禁止 HTTP 方法
添加
修改
删除
替换整组
规则变更回显
保存设置
```

展示说明：

```text
前端中的每个规则组都可以直接输入规则值并点击“添加”，也可以点击现有规则旁边的“删除”。这些操作会调用后端 API，后端更新运行时配置，并写回配置文件。
```

## 阶段 18：后端配置与规则模块拆分

### 实现内容

- 保留 `src/proxy.py` 作为稳定的命令行启动入口。
- 新建 `src/webproxy/config_rules.py`，集中管理配置读取、路径解析、规则类型、规则值标准化和宽松 JSON 解析。
- 同时支持 `python src\proxy.py` 直接启动，以及测试代码使用 `from src import proxy` 导入。
- 不改变配置文件格式、管理 API、前端页面或命令行规则管理方式。

### 验证命令

检查启动参数：

```powershell
python src\proxy.py --help
```

运行与规则模块直接相关的测试：

```powershell
python tests\stage8_admin_smoke.py
python tests\stage15_rule_management_smoke.py
python tests\stage16_rule_cli_smoke.py
```

运行完整项目回归：

```powershell
python tests\run_all_smoke.py
```

命令含义：

- `python`：使用当前环境中的 Python 解释器。
- `src\proxy.py`：启动后端主程序。
- `--help`：只显示支持的命令行参数，不启动服务器。
- `tests\stage8_admin_smoke.py`：验证管理前端与管理 API。
- `tests\stage15_rule_management_smoke.py`：验证规则增删改查和模式切换。
- `tests\stage16_rule_cli_smoke.py`：验证后端命令行规则管理工具。
- `tests\run_all_smoke.py`：按批次验证整个项目。

## 阶段 19：日志审计模块拆分

### 实现内容

- 新建 `src/webproxy/audit.py`，统一负责访问日志、拦截日志和错误日志。
- 日志模块提供写入事件、读取末尾日志、清空演示日志三个职责。
- `src/proxy.py` 继续兼容直接启动和测试模块导入，管理前端 API 地址保持不变。
- 认证失败与限流拒绝仍会同时记录到拦截日志，方便验收展示。

### 验证命令

验证管理 API：

```powershell
python tests\stage8_admin_smoke.py
```

验证前端统计和日志读取：

```powershell
python tests\stage12_frontend_display_smoke.py
```

验证日志证据包含放行、缓存、拦截、过滤、HTTPS、认证和限流事件：

```powershell
python tests\acceptance_web_evidence_smoke.py
```

运行完整项目回归：

```powershell
python tests\run_all_smoke.py
```

命令含义：

- `stage8_admin_smoke.py`：验证管理页面、配置、统计和日志 API。
- `stage12_frontend_display_smoke.py`：验证前端所需统计与日志数据可以正常读取。
- `acceptance_web_evidence_smoke.py`：生成并检查课程验收所需的完整日志证据。
- `run_all_smoke.py`：验证拆分后整个项目的所有功能。

## 阶段 20：代理认证凭据隔离

### 实现内容

- 代理仍然使用 `Proxy-Authorization` 验证客户端身份。
- 验证成功后，转发请求时删除 `Proxy-Authorization` 和 `Proxy-Authenticate`。
- 防止代理用户名和密码泄露给目标网站。
- 扩展认证自动测试，由目标测试网站确认没有收到代理认证请求头。

### 验证命令

```powershell
python tests\stage13_auth_smoke.py
```

命令含义：

- `stage13_auth_smoke.py`：验证无认证和错误认证返回 `407`，正确认证可以访问，并验证目标网站收不到代理认证凭据。

完整回归：

```powershell
python tests\run_all_smoke.py
```

## 阶段 21：结构化日志查询与测试证据隔离

### 实现内容

- 新增 `frontend/logs.html` 日志详情页。
- 管理台中的总请求、放行、域名/URL/方法拦截、正文过滤、HTTPS 隧道、缓存、认证和限流统计均可点击。
- 新增 `/api/logs/query`，支持按日志类型、事件类型、全文关键字和最大返回数量查询。
- 日志文本会解析为时间、事件、客户端、目标与详细信息，效果类似对日志数据库执行只读查询。
- 新增 `CACHE_MISS` 事件，使“缓存未命中”统计也有可查询日志。
- Web/代理测试证据保存到 `tests/evidence/web`，规则与运行模式证据保存到 `tests/evidence/rules`。
- `run_all_smoke.py` 会对 Web 证据文件计算摘要，确认后续规则测试没有修改这些文件。

### 验证命令

```powershell
python tests\stage8_admin_smoke.py
python tests\stage12_frontend_display_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `stage8_admin_smoke.py`：验证日志详情页和结构化查询 API。
- `stage12_frontend_display_smoke.py`：生成代理流量，并验证统计链接、`CACHE_MISS` 与拦截日志查询。
- `run_all_smoke.py`：验证全部功能，并确认两批测试的证据文件互不影响。

## 阶段 22：日志 CSV 证据导出

### 实现内容

- 新增 `/api/logs/export.csv`，使用与结构化日志查询相同的筛选条件。
- CSV 包含时间、事件、客户端、方法、主机、路径、状态、原因、关键字、消息和原始日志。
- CSV 使用 UTF-8 BOM，便于 Windows Excel 正确识别中文。
- 日志详情页新增“导出 CSV”按钮，导出当前页面的查询条件。
- Python CLI 新增 `log-export` 子命令，可指定导出文件路径。
- 后端、CLI 和测试代码均补充了职责注释。

### 验证命令

```powershell
python tests\stage8_admin_smoke.py
python tests\stage16_rule_cli_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `stage8_admin_smoke.py`：验证 CSV API 的文件头、字段名和筛选结果。
- `stage16_rule_cli_smoke.py`：验证命令行导出 CSV 并读取其中的域名拦截证据。
- `run_all_smoke.py`：验证新增导出功能没有影响代理、规则、运行模式与前端功能。
