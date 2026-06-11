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
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
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
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

访问非白名单域名：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://not-allowed.test/
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
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

正确认证访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
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
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
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
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
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

## 阶段 23：普通管理台查看隔离的批量验收证据

### 实现内容

- 新增 `src/webproxy/evidence.py`，集中管理固定的 `web`、`rules` 两个只读证据档案。
- 普通管理端新增 `/api/evidence/profiles`，显示两类证据是否存在以及访问、拦截、错误、规则变更数量。
- 日志查询与 CSV 导出支持 `profile=web`，普通 `8088` 管理端可读取批量 Web 测试日志。
- 新增 `/api/evidence/changes/query`，支持规则变更总查询，以及按 `action`、`rule_type`、全文关键字独立查询。
- 新增 `frontend/changes.html` 规则变更详情页，显示按操作和规则组汇总结果。
- 管理台首页新增“批量验收证据”入口，明确区分当前运行数据与批量验收数据。
- 固定证据档案由后端映射，前端不能传入任意文件路径。

### 验证命令

```powershell
python tests\stage8_admin_smoke.py
python tests\acceptance_web_evidence_smoke.py
python tests\acceptance_rule_evidence_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `stage8_admin_smoke.py`：验证首页证据入口、日志详情页、规则变更详情页和证据档案 API。
- `acceptance_web_evidence_smoke.py`：生成完整 Web 日志，并确认 `profile=web` 可由前端 API 查询。
- `acceptance_rule_evidence_smoke.py`：生成规则操作记录，并验证总查询、操作分类查询和规则组分类查询。
- `run_all_smoke.py`：验证两批证据互不覆盖，并回归整个项目。

## 阶段 24：客户端 IP/CIDR 访问控制与自适应统计界面

### 实现内容

- 新增 `blocked_client_ips` 和 `allowed_client_ips` 两个可编辑规则组。
- 使用 Python 标准库 `ipaddress` 校验和标准化单个 IPv4/IPv6 地址与 CIDR 网段。
- 客户端黑名单优先；客户端白名单非空时，仅允许匹配的客户端。
- 客户端访问控制在代理认证、限流和目标域名过滤之前执行。
- 新增 `blocked_client` 统计项，以及 `client_ip_blacklist`、`client_ip_not_allowed` 审计原因。
- 前端新增客户端 IP 规则提示、“客户端拦截”指标和规则变更分类选项。
- 统计卡片由固定 12 列改为自适应网格，新增指标后仍能合理换行。
- 新增 `stage18_client_ip_policy_smoke.py`，验证 API 热更新、CIDR 标准化、黑白名单、统计与日志。
- CLI 和批量验收证据增加客户端 IP 规则验证。

### 验证命令

```powershell
python tests\stage18_client_ip_policy_smoke.py
python tests\stage16_rule_cli_smoke.py
python tests\acceptance_web_evidence_smoke.py
python tests\acceptance_rule_evidence_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `stage18_client_ip_policy_smoke.py`：专门验证客户端 IP/CIDR 黑白名单。
- `stage16_rule_cli_smoke.py`：验证命令行新增、修改、删除客户端网段规则后立即生效。
- `acceptance_web_evidence_smoke.py`：确认客户端 IP 拦截进入前端可查询的 Web 拦截证据。
- `acceptance_rule_evidence_smoke.py`：确认客户端 IP 规则操作进入规则变更证据。

## 阶段 25：首页完整显示最近验收结果

### 实现内容

- 新增 `/api/evidence/dashboard`，根据持久化 Web 验收日志重建首页统计、域名排行和关键字排行。
- 新增“总拦截”指标，统一汇总域名、客户端、URL、方法、正文、认证和限流拦截，并支持点击查询全部拦截日志。
- 首页新增“当前运行 / 最近验收”数据源切换，统一控制统计数字、排行、右侧日志、规则变更回显和统计详情链接。
- 存在验收证据时，普通管理端首页默认显示最近验收结果，解决新进程内存统计为零导致首页无内容的问题。
- 规则和运行设置修改仍只作用于当前运行配置；执行修改时首页自动切回当前运行数据。
- 新增 `frontend_script_syntax_smoke.py`，使用 Node.js 检查三个管理页面的内联 JavaScript 语法；未安装 Node.js 时明确跳过，不影响 Python 代理运行。
- 新增自动测试，复现“新启动普通管理端实时统计为零，但首页可以读取最近验收汇总”的现场验收流程。

### 验证命令

```powershell
python tests\frontend_script_syntax_smoke.py
python tests\acceptance_web_evidence_smoke.py
python tests\stage8_admin_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `frontend_script_syntax_smoke.py`：检查首页、日志详情页和规则变更详情页的 JavaScript 语法。
- `acceptance_web_evidence_smoke.py`：验证验收日志能够重建首页统计，并验证普通新进程可以读取该统计。
- `stage8_admin_smoke.py`：验证首页包含数据源切换和验收汇总 API。
- `run_all_smoke.py`：运行全部 Web、规则管理和证据隔离回归。

## 阶段 26：确定性手动验收环境与本机代理修复

### 实现内容

- 新增 `manual_demo_server.py`，统一提供 HTTP 测试站与 CONNECT TCP 回显目标，不再依赖启动目录或公网。
- 新增独立的 `/content-test.html` 与真实存在的 `/game/index.html`，避免 URL 过滤和正文过滤互相抢先命中，也避免把上游 `404` 误认为 URL 模块故障。
- 缓存测试页返回 `X-Upstream-Hit` 和正文命中计数，可直接证明第二次响应来自代理缓存。
- 新增 `manual_connect_tunnel.py`，在 CONNECT 建立后发送并接收回显数据，证明隧道不只是完成握手。
- 手动验收命令加入 `--noproxy no-host-bypass.invalid`，防止 Windows `curl.exe` 对本机地址绕过代理。
- 限流手动验收明确要求同时设置 `rate_limit_enabled=true`、窗口上限、窗口秒数并清空计数。
- 管理前端将“每分钟请求上限”改为“时间窗口内请求上限”，与实际固定窗口算法一致。
- 新增 `manual_acceptance_workflow_smoke.py`，使用现场命令语义回归 URL、正文、缓存、隧道和限流。

### 验证命令

```powershell
python tests\manual_acceptance_workflow_smoke.py
python tests\run_all_smoke.py
```

命令含义：

- `manual_acceptance_workflow_smoke.py`：自动复现修正后的完整手动验收流程。
- `run_all_smoke.py`：确认手动验收资源和说明更新没有影响其他功能。

## 阶段 27：浏览器强制代理与可展开 403 拦截页

### 实现内容

- 修复正文关键字过滤返回 `200 OK` 的语义问题；命中正文规则后现在返回 `403 Forbidden`。
- 域名、客户端、URL、方法和正文策略拦截统一使用浏览器可展示的 HTML 替代页，原网页不会返回。
- 拦截页显示状态码、原因摘要，并可点击“查看详细信息”查看命中规则、请求方法、目标地址和客户端地址。
- 新增 `tools/start_proxy_browser.ps1`，通过独立 Edge/Chrome 配置和 `--proxy-bypass-list=<-loopback>` 强制本机地址经过代理。
- 浏览器启动器默认打开 `127.0.0.1.nip.io:9000` 的 URL 与正文过滤测试页，并关闭无关后台网络请求，避免浏览器自身流量干扰验收。
- 管理前端顶部新增“验证 URL 拦截”和“验证正文过滤”入口，可直接打开两个稳定的浏览器验收地址。
- 管理前端规则说明明确：URL 关键字检查域名、路径/子文件和查询参数，不检查网页正文。
- 文档明确代理认证用于控制客户端使用代理的权限，不是目标网站登录；代理凭据不会转发给目标网站。
- 新增浏览器启动器烟测，并强化域名、URL、方法、正文过滤测试对 `403` 替代页和详细信息的断言。
- 新增真实 Edge/Chrome 端到端烟测；浏览器环境可用时，实际验证两个页面经过代理并分别命中 URL 与正文规则。

### 验证命令

```powershell
python tests\browser_proxy_launcher_smoke.py
python tests\stage5_smoke.py
python tests\stage6_smoke.py
python tests\stage7_policy_smoke.py
python tests\manual_acceptance_workflow_smoke.py
python tests\run_all_smoke.py
```

浏览器手工验收：

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1
```

## 阶段 28：公网 HTTP URL 与正文过滤验收边界

### 实现内容

- 明确记录 HTTPS CONNECT 可见性边界：普通代理只能看到目标域名和端口，看不到 TLS 内部路径和正文。
- 管理前端规则说明明确 URL 路径过滤和正文过滤只适用于明文 HTTP；HTTPS 只支持目标域名策略。
- 第 8 号验收文档新增两个真实公网 HTTP 示例：
  - `http://httpforever.com/url-filter-demo` 验证 URL 路径规则。
  - `http://neverssl.com/` 验证返回正文规则。
- 新增 `public_http_filter_examples_smoke.py`，验证文档中的公网示例规则与项目实现保持一致。
- `stage7_policy_smoke.py` 增加 HTTP 完整路径可见、HTTPS CONNECT 内部路径不可见的边界测试。

### 验证命令

```powershell
python tests\public_http_filter_examples_smoke.py
python tests\stage7_policy_smoke.py
python tests\stage8_admin_smoke.py
python tests\run_all_smoke.py
```

## 阶段 29：项目最终展示整理与期末实验报告

### 实现内容

- 新增根目录 `PROJECT_SHOWCASE.md`，集中展示题目要求完成情况、系统架构、全部功能、实现技术、运行方式、测试覆盖和主要文件入口。
- 在 README 和项目总览中增加最终展示入口，使验收人员能够快速定位展示总览、逐模块验收文档和期末报告。
- 完善客户端 IP/CIDR 黑名单与白名单手工验收指导，加入正常访问、规则新增、拒绝结果、日志查询、规则热更新恢复和验收清理步骤。
- 新增 `report/final_report.tex`，按照需求分析、总体设计、详细实现、测试验收、安全边界和总结的课程报告结构说明整个项目。
- 使用 XeLaTeX 生成 `report/final_report.pdf`，报告包含系统架构图、请求处理流程图、测试结果表和常用命令附录。
- 再次单独运行客户端 IP/CIDR 实测，并执行完整回归测试，确认展示文档与当前代码行为一致。

### 验证与生成命令

```powershell
python tests\stage18_client_ip_policy_smoke.py
python tests\run_all_smoke.py
cd report
latexmk -xelatex -interaction=nonstopmode final_report.tex
```

命令含义：

- `stage18_client_ip_policy_smoke.py`：实际验证客户端黑名单拒绝、白名单拒绝、规则热更新恢复、统计和日志。
- `run_all_smoke.py`：运行全部 Web/代理功能与规则/运行模式回归。
- `latexmk -xelatex`：使用 XeLaTeX 自动完成中文报告所需的多轮编译，并生成最终 PDF。
