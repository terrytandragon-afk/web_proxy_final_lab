# 08 后端命令行与逐模块验收总表

本文件用于现场验收。它分成两部分：

1. 前半部分：规则组支持的两种后端修改方式。
2. 后半部分：原有各功能模块的逐项验证命令。

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
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

命令解释：

```text
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
```

进入测试网页目录。

```text
python -m http.server 9000
```

使用 Python 标准库启动一个本地 HTTP 服务器，监听端口 `9000`。

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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期：

```text
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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/private/page.html
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

## 七、逐模块验收命令

### 模块 1：HTTP 代理转发

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
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
curl.exe -i -x http://127.0.0.1:8080 http://blocked.test/
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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

预期：

```text
网页已被过滤
blocked by keyword filter: forbidden
```

命令解释：

```text
forbidden.html
```

测试页面，正文包含默认正文关键字 `forbidden`。

### 模块 4：URL 关键字拦截

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
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

默认 URL 关键字。URL 中包含它时会被拦截。

### 模块 5：请求方法过滤

```powershell
curl.exe -i -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
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

连续执行两次：

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
第一次：缓存未命中。
第二次：日志出现 CACHE_HIT。
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

外网不可用时：

```powershell
python tests\stage9_connect_smoke.py
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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

非白名单域名：

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://not-allowed.test/
```

预期：

```text
domain_not_in_whitelist
```

### 模块 9：代理认证

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\auth.example.json
```

未认证访问：

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

正确认证访问：

```powershell
curl.exe -i -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

命令解释：

```text
--proxy-user student:123456
```

向代理服务器发送用户名 `student` 和密码 `123456`。

### 模块 10：访问频率限制

停止默认代理后，重新启动：

```powershell
python src\proxy.py --config configs\rate_limit.example.json
```

连续访问：

```powershell
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
429 Too Many Requests
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

一键验证全部模块：

```powershell
python tests\run_all_smoke.py
```

预期：

```text
stage15 rule management smoke test passed
stage16 rule cli smoke test passed
stage17 runtime settings smoke test passed
all smoke tests passed
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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
407 Proxy Authentication Required
```

验证带认证可以访问：

```powershell
curl.exe -i -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

```text
--proxy-user student:123456
```

向代理服务器发送用户名 `student` 和密码 `123456`。

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
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
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
