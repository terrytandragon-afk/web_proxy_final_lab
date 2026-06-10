# 08 后端命令行与逐模块验收总表

本文件用于现场验收。它按下面顺序组织：

1. 前半部分：规则组支持的两种后端修改方式。
2. 后半部分：原有各功能模块的逐项验证命令。
3. 最后部分：批量测试、日志证据、前端回显和重复运行验收。

重点说明：

```text
PowerShell 和 Windows CMD 对引号的处理不一样。
```

如果你看到下面这种错误：

```text
invalid JSON body: Expecting value: line 1 column 1 (char 0)
```

通常是因为在 CMD 中直接用了 PowerShell 的单引号 JSON 写法。更新后的后端已经兼容这种情况，但现场展示时仍建议按本文件区分 PowerShell / CMD 命令。

修改代码后需要重新启动代理服务：

```text
先按 Ctrl+C 停止旧的 python src\proxy.py 进程，再重新执行启动命令。
```

## 一、通用准备

### 1. 启动测试 Web 服务器

终端 1：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\manual_demo_server.py
```

命令解释：

```text
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
```

进入项目根目录。

```text
python tests\manual_demo_server.py
```

启动专用手动验收目标：HTTP 测试站监听 `9000`，CONNECT TCP 回显目标监听 `9001`。脚本提供 `/content-test.html`、`/game/index.html`、`/cache.txt` 和 `/rate-limit.txt`，避免测试路径缺失或不同模块互相抢先拦截。

### 2. 启动代理和管理后端

终端 2：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

命令解释：

```text
python src\proxy.py
```

启动代理服务器主程序。

```text
--config config.example.json
```

指定配置文件。程序从这里读取代理端口、管理端口、过滤规则、缓存、认证、限流和日志路径。

启动后：

```text
代理服务：http://127.0.0.1:8080
管理后端：http://127.0.0.1:8088
管理前端：http://127.0.0.1:8088/
```

PowerShell 验收本机目标时，代理命令必须包含：

```text
--noproxy no-host-bypass.invalid
```

该参数防止 Windows `curl.exe` 根据 `NO_PROXY` 绕过 `127.0.0.1:8080` 代理。若代理终端没有打印请求，或者 `/game/index.html` 返回上游 `404`，说明请求没有经过代理或尚未添加 `game` URL 规则。

准备 URL 与正文验收规则：

```powershell
python tools\rule_cli.py add blocked_url_keywords game
python tools\rule_cli.py add blocked_content_keywords forbidden
```

## 二、规则组说明

```text
blocked_domains
```

域名黑名单。命中后返回 `403 Forbidden`。

域名匹配方式补充说明：

```text
www.baidu.com
```

完整域名匹配，只匹配 `www.baidu.com`。

```text
baidu.com
```

父域名/后缀匹配，可以匹配 `baidu.com` 和 `www.baidu.com`。

```text
*.baidu.com
```

通配符匹配，可以匹配 `www.baidu.com`、`map.baidu.com` 等子域名。

```text
*baidu*
```

显式通配符包含匹配，可以匹配 `www.baidu.com`，但范围较宽，可能也匹配其他包含 `baidu` 的域名。

```text
baidu
```

普通短词不会自动当成包含匹配。这样做是为了避免误拦其他域名。需要包含匹配时，请显式写成 `*baidu*`。

```text
allowed_domains
```

域名白名单。`mode=whitelist` 时只有这些域名允许访问。

```text
blocked_url_keywords
```

URL 关键字。请求 URL 中包含关键字时返回 `403 Forbidden`。

```text
blocked_content_keywords
```

网页正文关键字。HTTP 明文网页正文命中后返回过滤提示页。

```text
blocked_methods
```

禁止的 HTTP 方法，例如 `PUT`、`DELETE`、`PATCH`。

## 三、规则组修改方式 1：curl.exe 调后端 API

### 1. 查询规则组

PowerShell / CMD 都可用：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

命令解释：

```text
curl.exe
```

Windows 下明确调用 curl 程序。

```text
http://127.0.0.1:8088/api/rules
```

管理后端的规则查询接口。

### 2. 新增正文关键字

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"value`":`"classroom`"}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_content_keywords\",\"value\":\"classroom\"}"
```

命令解释：

```text
-X POST
```

指定 HTTP 请求方法为 `POST`。新增、删除、修改、替换规则都属于改变后端状态的操作。

```text
http://127.0.0.1:8088/api/rules/add
```

规则新增接口。

```text
-H "Content-Type: application/json"
```

设置 HTTP 请求头，告诉后端请求体是 JSON 格式。

```text
-d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

发送请求体数据。

```text
rule_type
```

规则组类型。

```text
blocked_content_keywords
```

正文关键字规则组。

```text
value
```

要新增的单条规则值。

```text
classroom
```

本次新增的正文关键字。

验证新增生效：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期：

```text
HTTP/1.1 403 Forbidden
网页已被过滤
blocked by keyword filter: classroom
```

### 3. 修改正文关键字

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"old_value`":`"classroom`",`"new_value`":`"lecture`"}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_content_keywords\",\"old_value\":\"classroom\",\"new_value\":\"lecture\"}"
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

### 4. 删除正文关键字

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_content_keywords`",`"value`":`"lecture`"}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_content_keywords\",\"value\":\"lecture\"}"
```

命令解释：

```text
/api/rules/delete
```

规则删除接口。

```text
value
```

要删除的单条规则值。

### 5. 替换整个 URL 关键字规则组

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_url_keywords`",`"values`":[`"private`",`"exam`"]}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_url_keywords\",\"values\":[\"private\",\"exam\"]}"
```

命令解释：

```text
/api/rules/replace
```

替换整个规则组。

```text
values
```

新的规则组列表。执行后原有同类型规则会被这一组值替换。

验证：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/private/page.html
```

预期：

```text
HTTP/1.1 403 Forbidden
url_keyword:private
```

清空 URL 关键字规则组：

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_url_keywords`",`"values`":[]}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_url_keywords\",\"values\":[]}"
```

### 6. 切换黑名单/白名单模式

切换到白名单模式：

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{`"settings`":{`"mode`":`"whitelist`"}}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{\"settings\":{\"mode\":\"whitelist\"}}"
```

切换回黑名单模式：

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{`"settings`":{`"mode`":`"blacklist`"}}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{\"settings\":{\"mode\":\"blacklist\"}}"
```

## 四、规则组修改方式 2：Python 后端命令行工具

命令行工具文件：

```text
tools/rule_cli.py
```

查询规则组：

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

切换模式：

```powershell
python tools\rule_cli.py set mode whitelist
python tools\rule_cli.py set mode blacklist
```

命令解释：

```text
python
```

使用 Python 解释器运行脚本。

```text
tools\rule_cli.py
```

项目提供的后端规则管理命令行工具。

```text
list
```

查询规则组。

```text
add
```

新增单条规则。

```text
update
```

修改单条规则。

```text
delete
```

删除单条规则。

```text
replace
```

替换整个规则组。

```text
set
```

修改运行设置。

指定管理后端地址：

```powershell
python tools\rule_cli.py --admin-host 127.0.0.1 --admin-port 8088 list
```

```text
--admin-host
```

管理后端监听地址。

```text
--admin-port
```

管理后端监听端口。

## 五、前端回显观察

打开：

```text
http://127.0.0.1:8088/
```

前端中可以看到：

```text
规则变更回显
全部操作
新增
修改
删除
替换整组
运行设置
```

说明：

```text
通过前端按钮操作规则时，页面会显示本次操作改变了哪个规则组、旧值是什么、新值是什么、是否写入配置文件。回显下拉框可以按操作类型筛选。
```

注意：

```text
通过 curl.exe 或 tools/rule_cli.py 修改规则后，前端点击“刷新”即可看到最新规则组。
```

## 六、curl 常用参数解释

```text
-i
```

显示响应头和响应正文。适合验证状态码，例如 `200 OK`、`403 Forbidden`。

```text
-I
```

只请求响应头，不下载完整正文。适合快速验证 HTTPS CONNECT。

```text
-x http://127.0.0.1:8080
```

指定使用代理服务器。这里的 `8080` 是本项目代理端口。

注意：小写 `-x` 表示“使用哪个代理服务器”，大写 `-X` 表示“使用哪种 HTTP 请求方法”，两者含义完全不同。

```text
-X DELETE
```

指定 HTTP 请求方法为 `DELETE`。

```text
-X POST
```

指定 HTTP 请求方法为 `POST`。

```text
-H "Content-Type: application/json"
```

指定 HTTP 请求头，说明请求体是 JSON。

```text
-d
```

发送请求体数据。

```text
--proxy-user student:123456
```

向代理服务器发送用户名和密码。

### 浏览器访问本机测试站时强制经过代理

Edge/Chrome 默认绕过 `localhost` 和 `127.0.0.1`。即使 Windows 代理设置指向 `8080`，普通浏览器窗口访问本机测试站仍可能直接连接 `9000`。

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1
```

该脚本启动独立 Edge/Chrome 配置，通过 `--proxy-bypass-list=<-loopback>` 取消本机地址绕过，并自动打开 `127.0.0.1.nip.io:9000` 的 URL 与正文过滤测试页。该域名解析到本机，但不会触发 Chromium 对 `127.0.0.1` 字面地址的默认代理绕过。判断浏览器是否真的经过代理：代理终端必须打印请求，管理前端“当前运行”的总请求必须增加。

启动前只验证脚本，不打开浏览器：

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1 -ValidateOnly
```

规则新增命令返回 `changed=false` 时，表示规则已经存在，因此没有重复写入；只要 `ok=true`、`saved=true` 就不是报错。

## 七、逐模块验收命令

### 模块 1：HTTP 代理转发

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

目标测试网站。

预期：

```text
HTTP/1.0 200 OK
```

### 模块 2：域名黑名单拦截

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

预期：

```text
HTTP/1.1 403 Forbidden
domain_blacklist
```

命令解释：

```text
blocked.test
```

默认配置文件中的黑名单域名。

### 模块 3：网页正文关键字过滤

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/content-test.html
```

预期：

```text
HTTP/1.1 403 Forbidden
网页已被过滤
blocked by keyword filter: forbidden
content_keyword:forbidden
```

命令解释：

```text
content-test.html
```

测试页面正文包含 `forbidden`，但 URL 不包含该词，因此可以明确验证正文过滤，而不会先命中 URL 过滤。

### 模块 4：URL 关键字拦截

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

预期：

```text
HTTP/1.1 403 Forbidden
url_keyword:game
```

命令解释：

```text
game
```

验收前通过命令行加入的 URL 关键字。URL 关键字检查域名、路径/子文件和查询参数，不检查网页正文；因此 `game` 会命中 `/game/index.html`。测试站中该文件真实存在，因此返回 `403` 而不是 `404` 可以证明 URL 拦截生效。

### 模块 5：请求方法过滤

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 403 Forbidden
method_blacklist
```

命令解释：

```text
-X DELETE
```

指定请求方法为 `DELETE`，默认配置中禁止该方法。

### 模块 6：HTTP GET 缓存

启用缓存并清空旧缓存：

```powershell
python tools\rule_cli.py set cache_enabled true
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
```

连续执行两次：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
```

预期：

```text
第一次：缓存未命中。
第二次：日志出现 CACHE_HIT。
两次响应均显示 X-Upstream-Hit: 1 和 upstream-hit=1。
前端“缓存命中”“缓存条目”增加。
```

### 模块 7：HTTPS CONNECT 隧道

外网可用时：

```powershell
curl.exe -I -x http://127.0.0.1:8080 https://example.com/
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

本地确定性验收，证明 CONNECT 建立后还能双向转发数据：

```powershell
python tests\manual_connect_tunnel.py
```

预期包含：

```text
HTTP/1.1 200 Connection Established
echo:hello-through-manual-tunnel
manual CONNECT tunnel data forwarding passed
```

### 模块 8：白名单模式

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\whitelist.example.json
```

命令解释：

```text
--config configs\whitelist.example.json
```

使用白名单模式演示配置。

允许域名：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

非白名单域名：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://not-allowed.test/
```

预期：

```text
domain_not_in_whitelist
```

### 模块 9：代理认证

代理认证控制“谁有权使用代理”，不是目标网站登录。启用后未认证客户端收到 `407`，认证成功后才会转发请求；代理会在转发前删除 `Proxy-Authorization`，目标网站不会收到代理账号密码。

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\auth.example.json
```

未认证访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

正确认证访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

命令解释：

```text
--proxy-user student:123456
```

向代理服务器发送用户名 `student` 和密码 `123456`。

### 模块 10：访问频率限制

默认配置关闭限流。只修改次数不会自动启用限流，按以下命令热更新：

```powershell
python tools\rule_cli.py set rate_limit_enabled true
python tools\rule_cli.py set rate_limit_per_minute 1
python tools\rule_cli.py set rate_limit_window_seconds 60
python tools\rule_cli.py rate-reset
```

连续访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
```

预期：

```text
429 Too Many Requests
```

`rate_limit_per_minute` 是兼容旧配置的字段名，实际表示一个 `rate_limit_window_seconds` 时间窗口内的请求上限。演示后可关闭：

```powershell
python tools\rule_cli.py set rate_limit_enabled false
python tools\rule_cli.py rate-reset
```

### 模块 11：管理 API 与日志

查看配置：

```powershell
curl.exe http://127.0.0.1:8088/api/config
```

查看统计：

```powershell
curl.exe http://127.0.0.1:8088/api/stats
```

查看访问日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=proxy&limit=20"
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

清空缓存、统计、日志：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
curl.exe -X POST http://127.0.0.1:8088/api/stats/reset
curl.exe -X POST http://127.0.0.1:8088/api/logs/clear
```

## 八、自动验收命令

验证规则 API：

```powershell
python tests\stage15_rule_management_smoke.py
```

验证后端命令行工具：

```powershell
python tests\stage16_rule_cli_smoke.py
```

批量验证规则组更改、模式切换和运行时设置：

```powershell
python tests\run_rule_management_smoke.py
```

批量验证基础 Web/代理功能：

```powershell
python tests\run_web_features_smoke.py
```

一键验证全部模块：

```powershell
python tests\run_all_smoke.py
```

规则修改记录现在会写入配置项 `change_log_file` 指定的 JSONL 文件，代理重启后管理前端仍能回显。批量测试的重复运行机制、日志证据和前端查看方法见本文“十一、批量测试、日志证据与重复运行验收”。

预期：

```text
stage15 rule management smoke test passed
stage16 rule cli smoke test passed
stage17 runtime settings smoke test passed
PASSED batch: rule groups and runtime modes
PASSED batch: web/proxy features
all test batches passed
```

## 九、运行时设置热更新：白名单、代理认证、访问频率

本节回答一个验收重点：

```text
白名单模式、代理认证、访问频率限制不需要重启代理服务器。
```

只要代理已经启动：

```powershell
python src\proxy.py --config config.example.json
```

下面这些命令会直接修改正在运行的后端配置，下一次代理请求马上按新规则处理。

需要重启的通常是监听地址和监听端口，例如：

```text
listen_host
listen_port
admin_host
admin_port
```

这些参数是在服务器启动时绑定 socket 的，修改后要重启才能换端口。

### 1. 查询当前运行配置

API 查询：

```powershell
curl.exe http://127.0.0.1:8088/api/config
```

CLI 查询：

```powershell
python tools\rule_cli.py config
```

命令解释：

```text
/api/config
```

返回当前代理进程正在使用的配置。

```text
config
```

命令行工具里的配置查询子命令。

### 2. 热更新白名单模式

先添加允许访问的域名：

```powershell
python tools\rule_cli.py add allowed_domains 127.0.0.1
```

切换到白名单模式：

```powershell
python tools\rule_cli.py set mode whitelist
```

切回黑名单模式：

```powershell
python tools\rule_cli.py set mode blacklist
```

对应 API 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{`"settings`":{`"mode`":`"whitelist`"}}"
```

命令解释：

```text
mode
```

访问控制模式。

```text
whitelist
```

白名单模式。只有 `allowed_domains` 中匹配的域名允许访问。

```text
blacklist
```

黑名单模式。默认放行，只拦截黑名单规则命中的请求。

### 3. 热更新代理认证

添加或修改认证用户：

```powershell
python tools\rule_cli.py auth-user student 123456
```

启用代理认证：

```powershell
python tools\rule_cli.py set proxy_auth_enabled true
```

停用代理认证：

```powershell
python tools\rule_cli.py set proxy_auth_enabled false
```

删除认证用户：

```powershell
python tools\rule_cli.py auth-delete student
```

对应 API 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{`"settings`":{`"proxy_auth_enabled`":true,`"proxy_auth_users`":{`"student`":`"123456`"}}}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{\"settings\":{\"proxy_auth_enabled\":true,\"proxy_auth_users\":{\"student\":\"123456\"}}}"
```

命令解释：

```text
proxy_auth_enabled
```

是否启用代理认证。

```text
proxy_auth_users
```

代理认证用户表，格式是 `用户名 -> 密码`。

验证无认证会被拦截：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
407 Proxy Authentication Required
```

验证带认证可以访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

```text
--proxy-user student:123456
```

向代理服务器发送用户名 `student` 和密码 `123456`。

代理认证安全说明：

```text
Proxy-Authorization 只用于客户端向代理服务器证明身份。代理验证成功后会删除该请求头，不会把用户名和密码转发给目标网站。
```

自动验证认证结果和凭据隔离：

```powershell
python tests\stage13_auth_smoke.py
```

该脚本依次验证：

```text
未提供认证信息时返回 407
密码错误时返回 407
密码正确时成功转发
目标网站没有收到 Proxy-Authorization 请求头
```

### 4. 热更新访问频率限制

启用访问频率限制：

```powershell
python tools\rule_cli.py set rate_limit_enabled true
```

设置每个客户端在时间窗口内最多访问 1 次：

```powershell
python tools\rule_cli.py set rate_limit_per_minute 1
```

设置限流时间窗口为 60 秒：

```powershell
python tools\rule_cli.py set rate_limit_window_seconds 60
```

清空当前限流计数桶：

```powershell
python tools\rule_cli.py rate-reset
```

对应 API 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d "{`"settings`":{`"rate_limit_enabled`":true,`"rate_limit_per_minute`":1,`"rate_limit_window_seconds`":60}}"
```

清空限流计数桶 API：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rate/reset
```

命令解释：

```text
rate_limit_enabled
```

是否启用访问频率限制。

```text
rate_limit_per_minute
```

每个客户端 IP 在一个窗口内最多允许的请求次数。

```text
rate_limit_window_seconds
```

限流统计窗口秒数。默认是 60 秒。

```text
/api/rate/reset
```

清空当前限流计数，方便现场重新演示。

验证访问频率限制：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
```

如果 `rate_limit_per_minute=1`，第二次请求预期：

```text
429 Too Many Requests
```

把访问频率调大：

```powershell
python tools\rule_cli.py set rate_limit_per_minute 10
python tools\rule_cli.py rate-reset
```

再次访问会按新的 10 次窗口限制执行，不需要重启代理。

关闭访问频率限制：

```powershell
python tools\rule_cli.py set rate_limit_enabled false
```

### 5. 自动验证运行时热更新

```powershell
python tests\stage17_runtime_settings_smoke.py
```

预期：

```text
stage17 runtime settings smoke test passed
```

## 十、最新修正：PowerShell 引号和命令行回显

### 1. PowerShell 推荐写法

Windows PowerShell 调用外部程序 `curl.exe` 时，普通单引号 JSON 有时会把 JSON 内部的双引号吞掉。验收时推荐使用下面这种反引号转义写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_domains`",`"value`":`"*.baidu.com`"}"
```

参数解释：

```text
curl.exe
```

调用 Windows 自带的 curl 程序。

```text
-X POST
```

指定 HTTP 请求方法为 POST。新增、删除、修改、替换规则都属于改变后端状态的操作，所以用 POST。

```text
http://127.0.0.1:8088/api/rules/add
```

管理后端的新增规则接口。

```text
-H "Content-Type: application/json"
```

设置请求头，告诉后端 `-d` 发送的是 JSON 请求体。

```text
-d "{`"rule_type`":`"blocked_domains`",`"value`":`"*.baidu.com`"}"
```

发送 JSON 请求体。PowerShell 里反引号加双引号 `` `" `` 表示把真实的双引号传给 `curl.exe`。

```text
rule_type
```

要修改的规则组名称。

```text
blocked_domains
```

域名黑名单规则组。

```text
value
```

要新增的单条规则值。

```text
*.baidu.com
```

本次新增的域名黑名单值。`*` 是通配符，`*.baidu.com` 表示拦截 `www.baidu.com`、`map.baidu.com` 等百度子域名。

### 2. CMD 推荐写法

Windows CMD 里推荐使用反斜杠转义双引号：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_domains\",\"value\":\"*.baidu.com\"}"
```

通配符规则也可以修改：

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_domains`",`"old_value`":`"*.baidu.com`",`"new_value`":`"*baidu*`"}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_domains\",\"old_value\":\"*.baidu.com\",\"new_value\":\"*baidu*\"}"
```

通配符规则也可以删除：

PowerShell 写法：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_domains`",`"value`":`"*baidu*`"}"
```

CMD 写法：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_domains\",\"value\":\"*baidu*\"}"
```

### 3. 后端兼容写法

当前后端已经兼容下面两类常见误传请求体：

```text
'{"rule_type":"blocked_domains","value":"*.baidu.com"}'
```

这是 CMD 把外层单引号原样传给后端时的情况。

```text
{rule_type:blocked_domains,value:*.baidu.com}
```

这是 PowerShell 把 JSON 内部双引号吞掉时的情况。

### 4. 查询后端规则变更历史

用 `curl.exe` 查询：

```powershell
curl.exe "http://127.0.0.1:8088/api/changes?limit=20"
```

命令解释：

```text
/api/changes
```

查询后端保存的规则和运行设置变更历史。

```text
limit=20
```

最多返回 20 条记录。

用 Python 命令行工具查询：

```powershell
python tools\rule_cli.py changes --limit 20
```

命令解释：

```text
changes
```

查询规则变更历史。

```text
--limit 20
```

最多返回 20 条记录。

### 5. 前端回显验证

打开：

```text
http://127.0.0.1:8088/
```

用 `curl.exe` 或 `python tools\rule_cli.py` 修改规则后，在网页管理端点击“刷新”。页面里的“规则变更回显”会显示本次变更的操作类型、规则组、旧值、新值、是否 changed、是否 saved。

## 十一、批量测试、日志证据与重复运行验收

本节附在规则操作说明之后，用于最终验收时证明：

1. 两组批量测试能够反复运行，不依赖正式配置中当前规则组是否为空。
2. Web 功能测试会产生访问日志和拦截日志，管理前端可以读取并按事件查询这些记录。
3. API 与 Python CLI 产生的规则变更会写入持久化记录，代理重启后前端仍可回显。
4. Web 功能证据与规则/运行模式证据分别保存，后一个测试批次不会污染前一个批次。

### 1. 批量测试 Web 代理功能与日志

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_web_features_smoke.py
```

命令解释：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录，保证测试脚本能够找到 `src`、`frontend`、`tests` 等目录。

```text
python
```

使用当前环境中的 Python 解释器运行脚本。

```text
tests\run_web_features_smoke.py
```

运行 Web/代理功能批次。该批次验证：

- 普通 HTTP 代理转发。
- 域名黑名单拦截。
- URL 关键字和 HTTP 方法拦截。
- HTTP 明文正文关键字过滤。
- HTTPS CONNECT 隧道。
- HTTP GET 缓存。
- 管理前端及日志 API。
- 代理认证。
- 访问频率限制。
- 访问日志和拦截日志是否包含对应测试数据。

预期结果：

```text
PASSED batch: web/proxy features
Passed tests: 14/14
Web evidence: tests/evidence/web/proxy.log and tests/evidence/web/blocked.log
```

### 2. 批量测试规则组修改与运行模式

```powershell
python tests\run_rule_management_smoke.py
```

命令解释：

```text
tests\run_rule_management_smoke.py
```

运行规则管理批次。该批次从专用空规则组基线开始，验证：

- 管理 API 新增、查询、修改、删除和替换整组规则。
- `tools\rule_cli.py` 后端命令行规则管理。
- 黑名单与白名单模式切换。
- 代理认证、访问频率等运行时设置热更新。
- 规则变更记录持久化。
- 重启管理后端后，前端 API 仍能读取规则变更记录。

预期结果：

```text
PASSED batch: rule groups and runtime modes
Passed tests: 7/7
Rule evidence: tests/evidence/rules/changes.jsonl
```

### 3. 一键运行全部测试

```powershell
python tests\run_all_smoke.py
```

命令解释：

```text
tests\run_all_smoke.py
```

依次运行 `run_web_features_smoke.py` 和 `run_rule_management_smoke.py`。任意子测试失败时，脚本会返回失败状态并显示失败脚本名称。

最终预期：

```text
PASSED batch: web/proxy features
Passed tests: 14/14
PASSED batch: rule groups and runtime modes
Passed tests: 7/7
Web/proxy evidence isolation verified
all test batches passed
```

### 4. 为什么批量测试可以重复运行

- 测试只使用 `tests` 下的专用配置，不读取或修改正式 `config.example.json` 中当前存在的规则。
- 综合 Web 测试每次先清空旧验收日志，防止旧日志让测试误通过。
- 综合规则测试每次先重建空规则组基线，再执行增删改查，结束时恢复为空规则组。
- Web 证据写入 `tests\evidence\web`，规则证据写入 `tests\evidence\rules`，两个批次不会覆盖彼此文件。
- 一键测试会记录 Web 证据文件摘要，并在规则测试结束后再次比较；文件发生变化时测试直接失败。
- 因此正式规则组原来为空、被修改过，或者连续运行多次，都不会影响测试结果。

### 5. 使用 PowerShell 查看批量测试证据

查看访问日志：

```powershell
Get-Content tests\evidence\web\proxy.log
```

查看拦截日志：

```powershell
Get-Content tests\evidence\web\blocked.log
```

查看规则与设置变更记录：

```powershell
Get-Content tests\evidence\rules\changes.jsonl
```

命令解释：

```text
Get-Content
```

PowerShell 用于读取文本文件内容的命令。

```text
tests\evidence\web\proxy.log
```

访问总日志。应能看到 `ALLOW`、`CACHE_MISS`、`CACHE_HIT`、`CONNECT`、`RATE_ALLOW` 等事件。

```text
tests\evidence\web\blocked.log
```

拦截日志。应能看到 `BLOCK`、`FILTER`、`AUTH_REQUIRED`、`RATE_LIMIT` 等事件。

```text
tests\evidence\rules\changes.jsonl
```

规则与运行设置变更历史。每行是一个 JSON 对象，应能看到 `add`、`update`、`delete`、`replace`、`settings` 等操作。

### 6. 使用管理前端查看批量测试证据

完成全部批量测试后，启动专用证据管理端：

```powershell
python src\proxy.py --config tests\evidence\rules\acceptance_config.json
```

命令解释：

```text
src\proxy.py
```

启动代理服务与管理后端。

```text
--config tests\evidence\rules\acceptance_config.json
```

指定规则管理批量测试生成的证据配置。该配置使用管理端口 `18212`，并指向 `tests\evidence\rules` 中的日志与规则变更记录。

浏览器打开：

```text
http://127.0.0.1:18212/
```

前端观察点：

- “访问”日志页签显示转发、缓存、HTTPS CONNECT 和限流首次放行记录。
- “拦截”日志页签显示域名/URL/方法拦截、正文过滤、认证失败和限流拒绝。
- “规则变更回显”显示 API 与 Python CLI 产生的规则修改记录。

### 7. 使用 curl.exe 查询与前端相同的证据 API

查询访问日志：

```powershell
curl.exe "http://127.0.0.1:18212/api/logs?kind=proxy&limit=200"
```

查询拦截日志：

```powershell
curl.exe "http://127.0.0.1:18212/api/logs?kind=blocked&limit=200"
```

查询规则变更记录：

```powershell
curl.exe "http://127.0.0.1:18212/api/changes?limit=100"
```

命令解释：

```text
curl.exe
```

向管理后端发送 HTTP 请求。此处没有写 `-X`，因此默认使用 `GET` 查询数据。

```text
kind=proxy
```

查询访问总日志。

```text
kind=blocked
```

查询拦截日志。

```text
limit=200
```

最多返回 200 行日志。

```text
/api/changes?limit=100
```

查询规则与运行设置变更历史，最多返回 100 条。

这些 API 就是管理前端读取日志和规则变更回显时使用的接口。因此命令行能够查询到记录，也说明前端刷新后能够显示记录。

### 8. 按事件和关键字查询日志

查询域名黑名单拦截：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?kind=blocked&event=BLOCK&search=domain_blacklist&limit=100"
```

查询 HTTPS 隧道：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?kind=proxy&event=CONNECT&limit=100"
```

查询正文过滤和限流拦截两种事件：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?kind=blocked&event=FILTER,RATE_LIMIT&limit=100"
```

使用项目自带 Python CLI 查询域名拦截：

```powershell
python tools\rule_cli.py log-query --kind blocked --event BLOCK --search domain_blacklist --limit 100
```

命令解释：

- `/api/logs/query`：结构化日志查询接口。
- `?`：开始 URL 查询参数。
- `&`：连接多个查询参数。
- `kind=proxy`：查询访问总日志。
- `kind=blocked`：查询拦截日志。
- `event=BLOCK`：只返回事件类型为 `BLOCK` 的记录；多个事件使用英文逗号分隔。
- `search=domain_blacklist`：对整行日志执行不区分大小写的包含查询。
- `limit=100`：最多返回最新的 100 条匹配记录。
- `log-query`：调用相同结构化日志查询 API 的 Python CLI 子命令。
- `--kind blocked`：CLI 参数，指定查询拦截日志。
- `--event BLOCK`：CLI 参数，指定事件类型。
- `--search domain_blacklist`：CLI 参数，指定全文包含条件。
- `--limit 100`：CLI 参数，指定最大结果数。

返回结果中的主要字段：

- `total`：该日志文件原始记录总数。
- `matched`：符合查询条件的记录总数。
- `entries`：结构化结果列表。
- `entries[].time`：事件时间。
- `entries[].event`：事件类型。
- `entries[].fields`：从日志中解析出的 `client`、`host`、`path`、`reason` 等字段。

前端操作：

```text
打开 http://127.0.0.1:8088/，点击“域名拦截”“正文过滤”“HTTPS 隧道”等统计数字，即可进入日志详情页。详情页会自动带入对应查询条件，也可以手动修改后重新查询。
```

### 9. 导出日志查询结果为 CSV

使用 `curl.exe` 导出域名拦截日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/export.csv?kind=blocked&event=BLOCK&search=domain_blacklist&limit=1000" -o exports\domain_blocked.csv
```

使用项目自带 Python CLI 导出：

```powershell
python tools\rule_cli.py log-export --kind blocked --event BLOCK --search domain_blacklist --limit 1000 --output exports\domain_blocked.csv
```

导出 HTTPS 隧道记录：

```powershell
python tools\rule_cli.py log-export --kind proxy --event CONNECT --output exports\https_tunnels.csv
```

命令解释：

- `/api/logs/export.csv`：CSV 日志导出接口，查询参数与 `/api/logs/query` 一致。
- `-o exports\domain_blocked.csv`：`curl.exe` 把服务器返回内容写入指定文件，而不是输出到终端。
- `log-export`：Python CLI 的日志导出子命令。
- `--output exports\domain_blocked.csv`：指定 CSV 文件保存路径；目录不存在时 CLI 会自动创建。
- `--kind blocked`：选择拦截日志。
- `--event BLOCK`：只导出 `BLOCK` 事件。
- `--search domain_blacklist`：只导出包含域名黑名单原因的记录。
- `--limit 1000`：最多导出最新的 1000 条匹配记录。

CSV 字段说明：

- `time`：日志产生时间。
- `event`：事件类型，例如 `BLOCK`、`FILTER`、`CONNECT`。
- `client`：客户端 IP。
- `method`：HTTP 请求方法。
- `host`：目标主机。
- `path`：请求路径。
- `status`：响应状态码。
- `reason`：拦截原因。
- `keyword`：命中的正文关键字。
- `message`：日志详细消息。
- `raw`：原始日志行，便于保留完整验收证据。

## 十二、在普通管理前端查看批量验收证据

### 1. 为什么以前刷新普通前端看不到批量测试结果

批量测试为了能够反复运行，并防止规则测试覆盖 Web 功能测试日志，会把两批证据分别保存到：

```text
tests\evidence\web
tests\evidence\rules
```

普通管理台原来只读取 `config.example.json` 指向的当前运行日志和当前规则变更，因此刷新页面不会自动读取上述隔离目录。现在普通管理台新增了固定、只读的证据档案入口，既保留测试隔离，又能从同一个前端查看。

### 2. 一步步生成并查看证据

第一步，运行整个自动验收项目：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
```

- `cd`：切换到项目根目录。
- `python`：使用当前 Python 解释器。
- `tests\run_all_smoke.py`：依次运行 Web/代理功能批次和规则/运行模式批次。

第二步，启动普通代理服务器和管理前端：

```powershell
python src\proxy.py --config config.example.json
```

- `src\proxy.py`：启动代理后端和管理后端。
- `--config`：指定配置文件参数。
- `config.example.json`：当前日常运行配置；不会替换批量证据配置。

第三步，浏览器打开：

```text
http://127.0.0.1:8088/
```

首页“批量验收证据”区域会显示 Web 访问日志数、Web 拦截日志数和规则变更数，并提供：

- `Web 访问日志`：查看转发、缓存、HTTPS 隧道等记录。
- `Web 拦截日志`：查看域名、URL、HTTP 方法、正文、认证和限流拦截。
- `规则变更总览`：查看全部规则变更，并按操作类型、规则组或全文关键字筛选。

首页提供“当前运行 / 最近验收”数据源切换。选择“最近验收”后，总请求、总拦截、各类拦截次数、排行、右侧日志和规则变更回显会统一显示最近一次自动验收结果；选择“当前运行”后会统一显示本次代理进程数据。两类数据不会互相覆盖。

### 3. 用命令行查询与前端相同的 Web 验收日志

查看全部批量 Web 拦截记录：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?profile=web&kind=blocked&limit=100"
```

只查看域名黑名单拦截：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?profile=web&kind=blocked&event=BLOCK&search=domain_blacklist&limit=100"
```

只查看 HTTPS 隧道：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?profile=web&kind=proxy&event=CONNECT&limit=100"
```

命令和参数含义：

- `curl.exe`：Windows 自带的命令行 HTTP 客户端。
- 双引号：保护 URL 中的 `&`，避免 PowerShell 把它解释成其他语法。
- `?`：开始 URL 查询参数。
- `&`：分隔多个查询参数。
- `profile=web`：读取批量 Web/代理功能证据，不读取当前运行日志。
- `kind=proxy`：查询访问日志。
- `kind=blocked`：查询拦截日志。
- `event=BLOCK`：只保留事件类型为 `BLOCK` 的记录。
- `event=CONNECT`：只保留 HTTPS 隧道记录。
- `search=domain_blacklist`：在整条日志中搜索域名黑名单拦截原因。
- `limit=100`：最多返回 100 条匹配记录。

### 4. 用命令行总查和独立查询规则变更证据

查询全部规则变更：

```powershell
curl.exe "http://127.0.0.1:8088/api/evidence/changes/query?profile=rules&limit=100"
```

只查询新增操作：

```powershell
curl.exe "http://127.0.0.1:8088/api/evidence/changes/query?profile=rules&action=add&limit=100"
```

只查询域名黑名单的新增操作：

```powershell
curl.exe "http://127.0.0.1:8088/api/evidence/changes/query?profile=rules&action=add&rule_type=blocked_domains&limit=100"
```

只查询运行模式相关变更：

```powershell
curl.exe "http://127.0.0.1:8088/api/evidence/changes/query?profile=rules&action=settings&search=mode&limit=100"
```

参数含义：

- `profile=rules`：读取规则管理批量测试的持久化变更证据。
- `action=add`：只查询新增操作。
- `action=update`：只查询修改操作。
- `action=delete`：只查询删除操作。
- `action=replace`：只查询替换整组操作。
- `action=settings`：只查询白名单模式、认证、限流等运行设置变更。
- `rule_type=blocked_domains`：只查询域名黑名单规则组。
- `rule_type=allowed_domains`：只查询域名白名单规则组。
- `rule_type=blocked_url_keywords`：只查询 URL 关键词规则组。
- `rule_type=blocked_content_keywords`：只查询正文关键词规则组。
- `rule_type=blocked_methods`：只查询禁止 HTTP 方法规则组。
- `search=mode`：在变更记录的所有字段中搜索 `mode`。

返回结果中的 `total` 表示证据文件中的全部记录数，`matched` 表示符合当前查询条件的记录数；`action_counts` 和 `rule_type_counts` 对应规则变更详情页中的两个汇总区域。

### 5. 验收时建议展示顺序

1. 运行 `python tests\run_all_smoke.py`，展示两批测试全部通过。
2. 启动 `python src\proxy.py --config config.example.json`。
3. 打开普通管理台，展示“批量验收证据”数量。
4. 点击 `Web 拦截日志`，分别筛选 `BLOCK`、`FILTER`、`AUTH_REQUIRED`、`RATE_LIMIT`。
5. 点击 `Web 访问日志`，筛选 `ALLOW`、`CACHE_HIT`、`CONNECT`。
6. 点击 `规则变更总览`，先展示全部记录，再按新增、修改、删除、替换整组、运行设置筛选。
7. 使用本节 curl 命令展示前端与后端命令行查询结果一致。

前端导出：

```text
进入日志详情页，设置日志类型、事件和全文查询条件，点击“导出 CSV”。导出的内容与当前查询条件一致。
```

### 10. 限流值为 1 的准确验收行为

设置 `rate_limit_per_minute=1` 表示在配置的时间窗口内：

1. 第一个通过代理认证的请求放行，访问日志记录 `RATE_ALLOW count=1 limit=1`。
2. 第二个请求返回 `429 Too Many Requests`，拦截日志记录 `RATE_LIMIT`。
3. `407 Proxy Authentication Required` 不会消耗正常访问额度。

自动验证：

```powershell
python tests\stage14_rate_limit_smoke.py
```

浏览器通常会额外请求图标、脚本或样式，因此设置为 `1` 时，主页面请求成功后，附加请求可能立即收到 `429`。现场演示“请求多次后才拦截”时建议设置为 `3`：

```powershell
python tools\rule_cli.py set rate_limit_per_minute 3
python tools\rule_cli.py rate-reset
```

命令解释：

```text
set rate_limit_per_minute 3
```

把每个客户端在一个时间窗口内允许的请求次数修改为 3。

```text
rate-reset
```

清空当前限流计数桶，让新的限流演示从第一个请求重新开始。

## 十三、客户端 IP/CIDR 访问控制验收

### 1. 功能和优先级

客户端访问控制用于决定“谁能使用代理”，与域名规则决定“能访问什么网站”不同：

- `blocked_client_ips`：客户端黑名单，命中后返回 `403 Forbidden`。
- `allowed_client_ips`：客户端白名单；列表非空时，未命中的客户端返回 `403 Forbidden`。
- 黑名单优先于白名单。
- 支持单个 IPv4、IPv6 地址和 CIDR 网段。
- 命中原因分别记录为 `client_ip_blacklist` 和 `client_ip_not_allowed`。
- 客户端规则只作用于代理端口 `8080`，管理端口 `8088` 仍可用于恢复规则。

### 2. 使用 Python CLI 增删改查

查询全部规则组：

```powershell
python tools\rule_cli.py list
```

新增客户端网段黑名单：

```powershell
python tools\rule_cli.py add blocked_client_ips 192.168.1.0/24
```

修改客户端网段黑名单：

```powershell
python tools\rule_cli.py update blocked_client_ips 192.168.1.0/24 192.168.2.0/24
```

删除客户端网段黑名单：

```powershell
python tools\rule_cli.py delete blocked_client_ips 192.168.2.0/24
```

新增和删除客户端白名单：

```powershell
python tools\rule_cli.py add allowed_client_ips 127.0.0.1
python tools\rule_cli.py delete allowed_client_ips 127.0.0.1
```

命令含义：

- `python`：使用当前环境的 Python 解释器。
- `tools\rule_cli.py`：调用正在运行的 `8088` 管理 API。
- `list`：查询所有可编辑规则组。
- `add`：向指定规则组新增一条规则。
- `update`：把旧规则修改为新规则。
- `delete`：从指定规则组删除规则。
- `blocked_client_ips`：客户端 IP/CIDR 黑名单规则组。
- `allowed_client_ips`：客户端 IP/CIDR 白名单规则组。
- `192.168.1.0/24`：CIDR 网段，表示 `192.168.1.0` 到 `192.168.1.255`。
- `127.0.0.1`：单个 IPv4 地址。

输入 `127.0.0.99/24` 时，后端会标准化保存为 `127.0.0.0/24`。输入 `not-an-ip` 等非法值时，后端返回 `400`，不会写入配置。

### 3. 使用 PowerShell curl.exe 增删规则

新增本机网段黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_client_ips`",`"value`":`"127.0.0.0/24`"}"
```

删除本机网段黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_client_ips`",`"value`":`"127.0.0.0/24`"}"
```

参数含义：

- `curl.exe`：Windows 命令行 HTTP 客户端。
- `-X POST`：明确使用 HTTP `POST` 方法修改后端状态。
- `/api/rules/add`：新增规则 API。
- `/api/rules/delete`：删除规则 API。
- `-H "Content-Type: application/json"`：声明请求体为 JSON。
- `-d`：发送后面的 JSON 请求体。
- PowerShell 中的 `` ` ``：转义 JSON 内部双引号。
- `rule_type`：要修改的规则组。
- `value`：新增或删除的 IP/CIDR 规则值。

新增黑名单后，通过代理端口访问会被拒绝：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

- `-i`：同时显示 HTTP 响应头。
- `-x http://127.0.0.1:8080`：指定 Web 代理地址。
- 最后的 URL：客户端希望通过代理访问的目标网站。

预期响应中包含：

```text
HTTP/1.1 403 Forbidden
client_ip_blacklist
```

### 4. 查询客户端拦截日志和导出 CSV

查询当前运行的客户端拦截：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?kind=blocked&event=BLOCK&search=client_ip_&limit=100"
```

查询批量验收生成的客户端拦截证据：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs/query?profile=web&kind=blocked&event=BLOCK&search=client_ip_&limit=100"
```

导出客户端拦截 CSV：

```powershell
python tools\rule_cli.py log-export --kind blocked --event BLOCK --search client_ip_ --limit 1000 --output exports\client_ip_blocked.csv
```

关键参数：

- `kind=blocked`：查询拦截日志。
- `event=BLOCK`：只保留直接拒绝请求的记录。
- `search=client_ip_`：同时匹配黑名单和白名单拒绝原因。
- `profile=web`：读取批量 Web 验收证据，而不是当前运行日志。
- `--output exports\client_ip_blocked.csv`：指定 CSV 输出文件。

前端操作：打开 `http://127.0.0.1:8088/`，点击统计区的“客户端拦截”，即可进入带有相同筛选条件的日志详情页。

### 5. 自动验收

单独验证客户端 IP/CIDR 规则：

```powershell
python tests\stage18_client_ip_policy_smoke.py
```

验证命令行规则管理：

```powershell
python tests\stage16_rule_cli_smoke.py
```

完整回归：

```powershell
python tests\run_all_smoke.py
```

`stage18_client_ip_policy_smoke.py` 会逐步验证 CIDR 标准化、黑名单拦截、黑名单修改后恢复、白名单拒绝、白名单修改后放行、非法规则拒绝、统计值和结构化日志。

## 十四、后续可继续完善的模块

按照课程展示价值和实现风险，建议后续优先级如下：

1. 管理端认证：为 `8088` 管理 API 和前端增加登录，避免未授权修改规则。
2. 规则配置导入、导出和版本回滚：可在演示前保存规则快照，并一键恢复。
3. 定时规则：支持指定星期和时间段启用规则组。
4. SQLite 审计存储：支持大量日志分页、趋势统计和按字段聚合。
5. HTTPS MITM 正文过滤：实现复杂且有证书信任风险，只建议写入展望。

## 十五、验收后检查首页汇总

一键验收并启动普通代理：

```powershell
python tests\run_all_smoke.py
python src\proxy.py --config config.example.json
```

如果 `8088` 已被之前启动的代理占用，先在旧代理终端按 `Ctrl+C` 停止它，再执行第二条启动命令。刷新网页只能重新加载前端文件，不能让旧 Python 进程自动加载新后端 API。

打开 `http://127.0.0.1:8088/`。存在验收证据时，首页默认选中“最近验收”，因此新启动代理进程即使实时请求数为 `0`，首页仍会显示刚才验收得到的总请求、拦截、排行、日志和规则变更。

通过命令行对比两类首页数据：

```powershell
curl.exe http://127.0.0.1:8088/api/stats
curl.exe http://127.0.0.1:8088/api/evidence/dashboard
curl.exe "http://127.0.0.1:8088/api/logs?profile=web&kind=blocked&limit=100"
curl.exe "http://127.0.0.1:8088/api/evidence/changes/query?profile=rules&limit=100"
```

命令和参数含义：

- `curl.exe`：使用 Windows 自带的 curl 客户端发送 HTTP 请求。
- `/api/stats`：查询当前代理进程的实时首页统计。
- `/api/evidence/dashboard`：根据最近一次 Web 验收日志重建首页统计和排行。
- `stats.total_blocked`：域名、客户端、URL、方法、正文、认证和限流拦截次数之和。
- `profile=web`：读取隔离保存的 Web 验收证据，而不是当前运行日志。
- `kind=blocked`：只读取拦截日志。
- `profile=rules`：读取隔离保存的规则管理验收证据。
- `limit=100`：最多返回最近 100 条记录。
