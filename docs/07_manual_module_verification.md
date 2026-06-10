# 07 逐模块手工验证指南

本文件用于你自己熟悉项目，也用于现场逐个功能模块验收。

使用方式：

1. 先按“通用准备”启动测试网站和代理。
2. 再按每个模块的小节运行命令。
3. 每个命令后面都有参数解释和预期结果。
4. 如果要演示特殊模式，例如认证、限流、白名单，就使用对应的示例配置文件启动代理。

## 一、通用准备

### 1. 启动本地测试网站

打开第一个 PowerShell：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\manual_demo_server.py
```

命令解释：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python tests\manual_demo_server.py
```

启动专用手动验收目标：HTTP 测试站监听 `9000`，CONNECT 回显目标监听 `9001`。

作用：

```text
模拟真实 Web 服务器，供代理转发、过滤、缓存测试使用。
```

专用测试站提供互不干扰的地址：

```text
/content-test.html  正文包含 forbidden，但 URL 不包含 forbidden
/game/index.html    文件真实存在，用于证明 URL 规则返回 403，而不是上游 404
/cache.txt          返回 X-Upstream-Hit，方便证明第二次请求来自代理缓存
/rate-limit.txt     用于限流演示
127.0.0.1:9001      TCP 回显目标，用于证明 CONNECT 建立后确实转发数据
```

### 2. 启动代理和管理前端

打开第二个 PowerShell：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

命令解释：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python src\proxy.py
```

启动代理主程序。

```text
--config config.example.json
```

指定默认配置文件。

启动后：

```text
代理服务：http://127.0.0.1:8080
管理前端：http://127.0.0.1:8088/
```

### 3. PowerShell 本机代理验收的重要参数

所有访问 `127.0.0.1:9000` 的代理测试都必须包含：

```text
--noproxy no-host-bypass.invalid
```

Windows 的 `curl.exe` 经常从 `NO_PROXY` 环境变量读取 `127.0.0.1`，导致本机请求绕过 `-x` 指定的代理。使用一个不会匹配目标的 `--noproxy` 值，可以强制请求经过 `8080` 代理。

判断是否真的经过代理：

```text
代理终端必须打印本次请求，管理前端“当前运行”的总请求必须增加。
访问 /game/index.html 时，如果看到上游 404，说明请求绕过了代理或 URL 规则尚未添加。
```

验收前准备互不冲突的规则：

```powershell
python tools\rule_cli.py add blocked_url_keywords game
python tools\rule_cli.py add blocked_content_keywords forbidden
```

使用前端或 `rule_cli.py` 修改规则会立即生效。直接编辑 `config.example.json` 后，需要重启代理或执行：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/reload
```

### 4. 打开管理前端

浏览器打开：

```text
http://127.0.0.1:8088/
```

你应该能看到：

```text
过滤规则
过滤规则管理
添加
删除
总请求
缓存命中
HTTPS 隧道
认证拦截
限流拦截
访问日志
```

### 5. 演示前清空状态

可以在管理前端点击：

```text
清空缓存
重置统计
清空日志
```

也可以用命令行：

```powershell
curl -X POST http://127.0.0.1:8088/api/cache/clear
curl -X POST http://127.0.0.1:8088/api/stats/reset
curl -X POST http://127.0.0.1:8088/api/logs/clear
```

命令解释：

```text
curl
```

命令行 HTTP 客户端。

```text
-X POST
```

指定请求方法为 POST。

```text
/api/cache/clear
```

清空代理缓存。

```text
/api/stats/reset
```

重置运行统计。

```text
/api/logs/clear
```

清空日志文件。

## 二、模块 1：HTTP 代理转发

### 实现位置

```text
src/proxy.py
parse_http_request()
build_upstream_request()
forward_http()
handle_client()
```

### 验证命令

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

命令解释：

```text
-i
```

显示响应头和正文。

```text
-x http://127.0.0.1:8080
```

指定使用本项目代理服务器。

```text
http://127.0.0.1:9000/
```

目标 Web 服务器地址。

预期结果：

```text
HTTP/1.0 200 OK
Manual proxy demo home
```

前端观察：

```text
总请求 +1
放行 +1
访问日志出现 ALLOW
```

## 三、模块 2：域名黑名单拦截

### 实现位置

```text
src/proxy.py
domain_matches()
check_access_policy()
```

### 验证命令

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

命令解释：

```text
blocked.test
```

默认配置文件中的黑名单域名。

预期结果：

```text
HTTP/1.1 403 Forbidden
domain_blacklist
```

前端观察：

```text
域名拦截 +1
拦截日志出现 BLOCK
```

## 四、模块 3：网页正文关键字过滤

### 实现位置

```text
src/proxy.py
filter_response_content()
build_keyword_block_response()
```

### 验证命令

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/content-test.html
```

命令解释：

```text
content-test.html
```

测试页面的正文包含敏感词 `forbidden`，但 URL 本身不包含该词，因此可以明确证明命中的是正文过滤，不是 URL 过滤。

预期结果：

```text
网页已被过滤
This page is blocked by keyword filter
```

前端观察：

```text
正文过滤 +1
关键字命中排行出现 forbidden
拦截日志出现 FILTER
```

## 五、模块 4：URL 关键字拦截

### 实现位置

```text
src/proxy.py
check_access_policy()
```

### 验证命令

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

命令解释：

```text
game
```

验收前通过 `rule_cli.py` 加入的 URL 关键字。测试站中该文件真实存在，因此 `403` 能证明代理执行了 URL 拦截。

预期结果：

```text
HTTP/1.1 403 Forbidden
url_keyword:game
```

前端观察：

```text
URL 拦截 +1
拦截日志出现 BLOCK reason=url_keyword:game
```

## 六、模块 5：请求方法过滤

### 实现位置

```text
src/proxy.py
check_access_policy()
```

### 验证命令

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
```

命令解释：

```text
-X DELETE
```

将 HTTP 方法指定为 `DELETE`。

预期结果：

```text
HTTP/1.1 403 Forbidden
method_blacklist
```

前端观察：

```text
方法拦截 +1
```

## 七、模块 6：HTTP GET 缓存

### 实现位置

```text
src/proxy.py
RuntimeState.get_cache()
RuntimeState.set_cache()
is_cacheable_request()
build_cache_key()
```

### 验证命令

先启用缓存并清空已有缓存：

```powershell
python tools\rule_cli.py set cache_enabled true
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
```

连续执行两次：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
```

预期结果：

```text
两次响应都显示 X-Upstream-Hit: 1 和 upstream-hit=1。
第一次日志出现 CACHE_MISS 和 ALLOW。
第二次代理直接返回缓存，日志出现 CACHE_HIT。
```

前端观察：

```text
缓存未命中 +1
缓存命中 +1
缓存条目增加
```

## 八、模块 7：HTTPS CONNECT 隧道

### 实现位置

```text
src/proxy.py
parse_http_request()
forward_connect()
```

### 外网可用时验证

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

命令解释：

```text
-I
```

只请求响应头。

```text
https://example.com/
```

目标 HTTPS 网站。curl 会先向代理发送 CONNECT 请求。

预期结果：

```text
HTTPS 隧道建立成功，返回目标网站响应头。
```

### 本地确定性验证：证明隧道建立后转发数据

```powershell
python tests\manual_connect_tunnel.py
```

预期：

```text
HTTP/1.1 200 Connection Established
echo:hello-through-manual-tunnel
manual CONNECT tunnel data forwarding passed
```

前端观察：

```text
HTTPS 隧道 +1
```

## 九、模块 8：白名单模式

### 实现位置

```text
src/proxy.py
check_access_policy()
configs/whitelist.example.json
```

### 启动白名单配置

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\whitelist.example.json
```

### 验证允许域名

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.0 200 OK
```

### 验证非白名单域名

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://not-allowed.test/
```

预期：

```text
HTTP/1.1 403 Forbidden
domain_not_in_whitelist
```

## 十、模块 9：代理认证

### 实现位置

```text
src/proxy.py
check_proxy_auth()
send_auth_required_response()
configs/auth.example.json
```

### 启动认证配置

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\auth.example.json
```

### 未认证访问

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 407 Proxy Authentication Required
```

### 正确认证访问

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

命令解释：

```text
--proxy-user student:123456
```

向代理发送用户名和密码。

预期：

```text
HTTP/1.0 200 OK
```

前端观察：

```text
认证拦截增加
访问日志出现 AUTH_REQUIRED
```

## 十一、模块 10：访问频率限制

### 实现位置

```text
src/proxy.py
RuntimeState.check_rate_limit()
configs/rate_limit.example.json
```

### 运行中启用限流

默认配置中 `rate_limit_enabled=false`。只修改请求上限不会启用限流，必须同时打开限流并清空旧计数：

```powershell
python tools\rule_cli.py set rate_limit_enabled true
python tools\rule_cli.py set rate_limit_per_minute 1
python tools\rule_cli.py set rate_limit_window_seconds 60
python tools\rule_cli.py rate-reset
```

`rate_limit_per_minute` 是为兼容旧配置保留的字段名，实际含义是“一个 `rate_limit_window_seconds` 时间窗口内允许的请求数”。

### 连续请求

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
```

预期：

```text
第一次请求返回 200。
第二次请求返回 429 Too Many Requests。
```

前端观察：

```text
限流拦截 +1
访问日志出现 RATE_LIMIT
```

演示后关闭限流：

```powershell
python tools\rule_cli.py set rate_limit_enabled false
python tools\rule_cli.py rate-reset
```

## 十二、模块 11：管理 API 与前端

### 实现位置

```text
src/proxy.py
AdminHandler
frontend/index.html
```

### 查看配置

```powershell
curl http://127.0.0.1:8088/api/config
```

### 查看统计

```powershell
curl http://127.0.0.1:8088/api/stats
```

### 查看日志

```powershell
curl "http://127.0.0.1:8088/api/logs?kind=proxy&limit=20"
```

命令解释：

```text
kind=proxy
```

查看访问日志。

```text
limit=20
```

最多返回 20 行。

### 演示重置 API

```powershell
curl -X POST http://127.0.0.1:8088/api/cache/clear
curl -X POST http://127.0.0.1:8088/api/stats/reset
curl -X POST http://127.0.0.1:8088/api/logs/clear
```

预期：

```text
"ok": true
```

## 十三、模块 12：过滤规则增删改查管理

这个模块是现场展示时很重要的一部分：证明系统不是只能写死配置，而是可以在运行时新增、删除、修改、查询过滤条件，也可以替换整个规则组。

### 实现位置

```text
src/proxy.py
LIST_RULE_FIELDS
RuntimeState.get_rules()
RuntimeState.add_list_rule()
RuntimeState.delete_list_rule()
RuntimeState.update_list_rule()
RuntimeState.replace_list_rules()
RuntimeState.update_settings()
AdminHandler.do_GET()
AdminHandler.do_POST()
frontend/index.html
renderRuleGroups()
addRule()
deleteRule()
updateRule()
replaceRuleGroup()
renderChangeLog()
saveSettings()
```

### 方式 A：通过前端增删改查

打开：

```text
http://127.0.0.1:8088/
```

查询规则：

```text
页面中的“过滤规则管理”区域会列出当前所有规则。
```

新增正文关键字：

```text
在“正文关键字”输入框中输入 classroom，然后点击“添加”。
```

验证新增生效：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期：

```text
网页已被过滤
blocked by keyword filter: classroom
```

修改正文关键字：

```text
在“正文关键字”规则列表中找到 classroom，点击旁边的“修改”，输入 lecture。
```

前端回显：

```text
在“规则变更回显”区域，可以看到“修改 正文关键字：classroom -> lecture”。
```

删除正文关键字：

```text
在“正文关键字”规则列表中找到 lecture，点击旁边的“删除”。
```

替换整个规则组：

```text
点击某个规则组右侧的“替换整组”，输入多个规则值，用逗号分隔。
```

筛选回显：

```text
在“规则变更回显”区域，可以用下拉框筛选新增、修改、删除、替换整组等操作记录。
```

再次验证：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期：

```text
HTTP/1.0 200 OK
Classroom Rule Demo
```

### 方式 B：通过 curl.exe 命令行增删改查

查询当前规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

命令解释：

```text
curl.exe
```

Windows 下明确调用 curl 程序。

```text
/api/rules
```

规则查询接口，返回域名黑名单、域名白名单、URL 关键字、正文关键字、禁止方法等规则。

新增正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令解释：

```text
-X POST
```

指定 HTTP 方法为 POST。

```text
/api/rules/add
```

规则新增接口。

```text
-H "Content-Type: application/json"
```

说明请求体是 JSON。

```text
-d
```

发送请求体数据。

```text
rule_type
```

规则类型。

```text
blocked_content_keywords
```

表示网页正文关键字规则。

```text
value
```

规则值。

```text
classroom
```

本次新增的正文关键字。

删除正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

命令解释：

```text
/api/rules/delete
```

规则删除接口。

```text
value
```

要删除的规则值。

修改正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

命令解释：

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

替换整个 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":["private","exam"]}'
```

命令解释：

```text
/api/rules/replace
```

规则组替换接口。

```text
values
```

新的规则组列表。

### 方式 C：通过 Python 后端命令行工具

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

命令解释：

```text
tools\rule_cli.py
```

项目提供的后端规则命令行管理工具，内部调用管理后端 API。

```text
list / add / update / delete / replace
```

分别表示查询、新增、修改、删除、替换规则组。

### 域名黑名单增删

新增：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
```

验证：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://demo-block.test/
```

预期：

```text
HTTP/1.1 403 Forbidden
domain_blacklist
```

删除：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
```

### URL 关键字增删

新增：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","value":"private"}'
```

验证：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/private/page.html
```

预期：

```text
HTTP/1.1 403 Forbidden
url_keyword:private
```

删除：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","value":"private"}'
```

### 禁止方法增删

新增：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_methods","value":"PATCH"}'
```

验证：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 -X PATCH http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 403 Forbidden
method_blacklist
```

删除：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_methods","value":"PATCH"}'
```

### 白名单规则增删

新增白名单域名：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

切换到白名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"whitelist"}}'
```

验证白名单内域名：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.0 200 OK
```

删除白名单域名：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

再次访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 403 Forbidden
domain_not_in_whitelist
```

演示结束后切回黑名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"blacklist"}}'
```

### 自动验证命令

```powershell
python tests\stage15_rule_management_smoke.py
python tests\stage16_rule_cli_smoke.py
```

预期：

```text
stage15 rule management smoke test passed
stage16 rule cli smoke test passed
```

## 十四、自己一步步熟悉项目的建议顺序

建议按下面顺序练习：

1. HTTP 代理转发。
2. 域名黑名单。
3. 网页正文过滤。
4. URL 关键字和方法过滤。
5. 缓存。
6. 管理前端。
7. 过滤规则增删改查。
8. HTTPS CONNECT。
9. 白名单模式。
10. 代理认证。
11. 频率限制。
12. 一键全量测试。

最后运行：

```powershell
python tests\run_all_smoke.py
```

看到：

```text
all smoke tests passed
```

说明项目整体功能正常。
