# 手工测试命令

## 1. 启动本地测试网站

终端 1：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\manual_demo_server.py
```

该脚本同时启动 `9000` HTTP 测试站和 `9001` CONNECT 回显目标，并提供存在的 `/game/index.html`、独立正文测试页、缓存页和限流页。

PowerShell 访问本机测试站时，代理命令必须加入：

```text
--noproxy no-host-bypass.invalid
```

否则 Windows `curl.exe` 可能根据 `NO_PROXY` 绕过代理，使过滤、缓存和限流看起来全部失效。

浏览器访问本机测试站时，Edge/Chrome 也会默认绕过代理。使用项目启动器打开专用验收浏览器：

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1
```

该窗口会强制 `127.0.0.1` 经过 `8080`。在其中访问：

```text
http://127.0.0.1:9000/content-test.html
http://127.0.0.1:9000/game/index.html
```

预期显示代理生成的 `403` 拦截页，并可点击“查看详细信息”。若显示原网页且代理终端无新请求，说明所用浏览器窗口绕过了代理。

## 1.1 快速烟测

基础 Web/代理功能批量测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_web_features_smoke.py
```

规则组更改、模式切换和运行时设置批量测试：

```powershell
python tests\run_rule_management_smoke.py
```

运行全部测试批次：

```powershell
python tests\run_all_smoke.py
```

批量测试结束后，日志证据、规则变更证据和使用前端查看证据的方法见：

```text
docs/08_backend_cli_rule_management.md
```

预期：

```text
PASSED batch: web/proxy features
PASSED batch: rule groups and runtime modes
all test batches passed
```

也可以逐个运行：

```powershell
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
python tests\stage17_runtime_settings_smoke.py
python tests\browser_proxy_launcher_smoke.py
```

预期：

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
browser proxy launcher smoke test passed
```

## 2. 启动代理服务器

终端 2：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

代理端口：

```text
127.0.0.1:8080
```

管理前端：

```text
http://127.0.0.1:8088/
```

## 3. 不经过代理访问

终端 3：

```powershell
curl -i http://127.0.0.1:9000/
```

访问敏感词页面：

```powershell
curl.exe -i http://127.0.0.1:9000/content-test.html
```

## 4. 经过代理访问普通页面

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.0 200 OK
```

## 5. 经过代理访问敏感词页面

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/content-test.html
```

预期：

```text
HTTP/1.1 403 Forbidden
网页已被过滤
content_keyword:forbidden
```

## 6. 域名黑名单测试

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

预期：

```text
HTTP/1.1 403 Forbidden
url_keyword:game
```

URL 关键字检查域名、路径/子文件和查询参数，不检查网页正文，因此 `game` 会命中 `/game/index.html`。

## 7. URL 关键字拦截测试

先确保 URL 规则存在：

```powershell
python tools\rule_cli.py add blocked_url_keywords game
```

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

预期：

```text
HTTP/1.1 403 Forbidden
```

## 8. 请求方法过滤测试

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 403 Forbidden
```

## 9. 日志查看

```powershell
Get-Content E:\eve_jump\web_proxy_final_lab\logs\proxy.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\blocked.log
Get-Content E:\eve_jump\web_proxy_final_lab\logs\error.log
```

实时查看：

```powershell
Get-Content E:\eve_jump\web_proxy_final_lab\logs\proxy.log -Wait
```

## 10. 管理后端 API 测试

查看当前规则：

```powershell
curl.exe http://127.0.0.1:8088/api/config
```

查看可编辑规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

新增正文关键字 classroom：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

验证新增生效：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

修改正文关键字 classroom 为 lecture：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

删除正文关键字 lecture：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"lecture"}'
```

替换 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":["private","exam"]}'
```

清空 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":[]}'
```

使用 Python 后端命令行工具：

```powershell
python tools\rule_cli.py list
python tools\rule_cli.py add blocked_content_keywords classroom
python tools\rule_cli.py update blocked_content_keywords classroom lecture
python tools\rule_cli.py delete blocked_content_keywords lecture
python tools\rule_cli.py replace blocked_url_keywords private exam
```

新增域名黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
```

删除域名黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_domains","value":"demo-block.test"}'
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

命令含义：

```text
curl.exe
```

Windows 下明确调用 curl 程序。

```text
-X POST
```

指定使用 POST 方法。

```text
-H "Content-Type: application/json"
```

说明请求体是 JSON。

```text
-d
```

发送 JSON 请求体。

```text
rule_type
```

规则类型。

```text
value
```

要新增或删除的规则值。

```text
old_value / new_value
```

修改规则时的旧值和新值。

```text
values
```

替换规则组时的新规则列表。

## 客户端 IP/CIDR 访问控制

新增客户端网段黑名单：

```powershell
python tools\rule_cli.py add blocked_client_ips 127.0.0.0/24
```

通过代理访问，预期返回 `403` 和 `client_ip_blacklist`：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

删除规则并恢复访问：

```powershell
python tools\rule_cli.py delete blocked_client_ips 127.0.0.0/24
```

查询客户端拦截日志：

```powershell
python tools\rule_cli.py log-query --kind blocked --event BLOCK --search client_ip_ --limit 20
```

自动验证：

```powershell
python tests\stage18_client_ip_policy_smoke.py
```

查看统计：

```powershell
curl.exe http://127.0.0.1:8088/api/stats
```

查看访问日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=proxy&limit=50"
```

查看拦截日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=blocked&limit=50"
```

重新加载配置：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/reload
```

清空缓存、重置统计、清空日志：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
curl.exe -X POST http://127.0.0.1:8088/api/stats/reset
curl.exe -X POST http://127.0.0.1:8088/api/logs/clear
```

## 11. HTTPS CONNECT 测试

自动测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage9_connect_smoke.py
```

手动证明 CONNECT 建立后确实转发了数据：

```powershell
python tests\manual_connect_tunnel.py
```

预期出现 `echo:hello-through-manual-tunnel` 和 `manual CONNECT tunnel data forwarding passed`。

如果网络环境允许，可以测试外部 HTTPS 网站：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

命令含义：

```text
-I
```

只请求响应头，便于快速验证。

```text
-x http://127.0.0.1:8080
```

指定使用本项目代理服务器。

```text
https://example.com/
```

目标 HTTPS 网站。curl 会先向代理发送 CONNECT 请求。

## 12. HTTP GET 缓存测试

自动测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage10_cache_smoke.py
```

手动测试：

```powershell
python tools\rule_cli.py set cache_enabled true
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
```

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
```

命令含义：

```text
-i
```

显示响应头和正文。

```text
-x http://127.0.0.1:8080
```

指定代理服务器。

展示重点：

```text
第一次请求缓存未命中，第二次请求缓存命中。
两次响应中的 X-Upstream-Hit 和 upstream-hit 都应为 1。
管理前端的“缓存命中”“缓存未命中”“缓存条目”会变化。
```

## 13. 代理认证测试

自动测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage13_auth_smoke.py
```

手动测试认证通过：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

命令含义：

```text
--proxy-user student:123456
```

向代理发送用户名和密码。

## 14. 访问频率限制测试

自动测试：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage14_rate_limit_smoke.py
```

手动测试时，启用限流后连续请求：

```powershell
python tools\rule_cli.py set rate_limit_enabled true
python tools\rule_cli.py set rate_limit_per_minute 1
python tools\rule_cli.py set rate_limit_window_seconds 60
python tools\rule_cli.py rate-reset
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
```

预期：

```text
HTTP/1.1 429 Too Many Requests
```

只修改 `rate_limit_per_minute` 不会启用限流；必须令 `rate_limit_enabled=true`。演示后运行：

```powershell
python tools\rule_cli.py set rate_limit_enabled false
python tools\rule_cli.py rate-reset
```

## 15. 过滤规则增删改查自动测试

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage15_rule_management_smoke.py
```

预期：

```text
stage15 rule management smoke test passed
```

## 16. 后端命令行规则管理自动测试

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage16_rule_cli_smoke.py
```

预期：

```text
stage16 rule cli smoke test passed
```

## 17. 首页最近验收汇总测试

完整验收后启动普通管理端：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
python src\proxy.py --config config.example.json
```

如果启动命令提示 `8088` 端口被占用，请先在旧代理终端按 `Ctrl+C`，再重新启动。网页刷新不会重新加载 Python 后端代码。

浏览器打开 `http://127.0.0.1:8088/`，首页应默认选择“最近验收”，总请求、总拦截、右侧日志和规则变更回显均应有数据。

命令行对比实时数据和验收证据：

```powershell
curl.exe http://127.0.0.1:8088/api/stats
curl.exe http://127.0.0.1:8088/api/evidence/dashboard
```

- `/api/stats`：当前新进程实时统计，尚未发送代理请求时可以为 `0`。
- `/api/evidence/dashboard`：最近一次验收产生的首页汇总，应包含请求和拦截计数。

检查前端 JavaScript 语法：

```powershell
python tests\frontend_script_syntax_smoke.py
```

该测试使用 `node --check` 验证首页、日志详情页和规则变更详情页；没有安装 Node.js 时会明确提示跳过。
