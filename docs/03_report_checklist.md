# 03 实验报告与截图清单

## 1. 报告结构

建议报告按下面结构写：

```text
一、实验目的
二、实验环境
三、系统总体设计
四、功能模块设计
五、关键实现步骤
六、测试过程与结果
七、问题与解决方法
八、实验总结
```

## 2. 实验环境写法

```text
操作系统：Windows
开发工具：VS Code
运行环境：Python 3.x
测试工具：curl、PowerShell
可选环境：Docker
```

## 3. 总体设计图

报告中可以画成：

```text
客户端 curl / 浏览器
        |
        v
本地代理服务器 127.0.0.1:8080
        |
        v
目标 Web 服务器 127.0.0.1:9000 / example.com
        |
        v
本地代理服务器
        |
        v
客户端
```

## 4. 必须截图

### 截图 A：代理启动

命令：

```powershell
python src\proxy.py --host 127.0.0.1 --port 8080 --config config.example.json
```

截图内容：

```text
Proxy started at 127.0.0.1:8080
```

### 截图 B：普通网页转发成功

命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

截图内容：

```text
HTTP/1.0 200 OK
```

### 截图 C：域名拦截成功

命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

截图内容：

```text
HTTP/1.1 403 Forbidden
```

### 截图 D：网页关键字过滤成功

命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

截图内容：

```text
HTTP/1.1 403 Forbidden
网页已被过滤
```

浏览器演示时，使用 `tools/start_proxy_browser.ps1` 启动专用验收浏览器，截图代理替代原网页的 `403` 拦截页及“查看详细信息”区域。

### 截图 E：日志记录

命令：

```powershell
Get-Content .\logs\proxy.log
Get-Content .\logs\blocked.log
```

截图内容示例：

```text
ALLOW client=127.0.0.1 method=GET host=127.0.0.1 path=/ status=200
BLOCK_DOMAIN client=127.0.0.1 host=blocked.test
BLOCK_KEYWORD client=127.0.0.1 host=127.0.0.1 keyword=forbidden
```

### 截图 F：管理前端

打开：

```text
http://127.0.0.1:8088/
```

截图内容：

```text
过滤规则
过滤规则管理
添加
删除
总请求
放行
域名拦截
正文过滤
访问日志
```

### 截图 G：管理 API

命令：

```powershell
curl.exe http://127.0.0.1:8088/api/config
curl.exe http://127.0.0.1:8088/api/rules
curl.exe http://127.0.0.1:8088/api/stats
```

截图内容：

```text
blocked_domains
blocked_content_keywords
groups
total_requests
allowed_requests
```

### 截图 G2：过滤规则增删改查

查询规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

新增正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

修改正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

后端命令行工具：

```powershell
python tools\rule_cli.py update blocked_content_keywords classroom lecture
```

验证新增后过滤：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

删除正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"lecture"}'
```

截图内容：

```text
"ok": true
blocked by keyword filter: classroom
old_value
new_value
```

### 截图 H：HTTPS CONNECT 隧道

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage9_connect_smoke.py
```

截图内容：

```text
CONNECT client=127.0.0.1 host=127.0.0.1
stage9 connect smoke test passed
```

如果网络环境允许，也可以执行：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

截图内容：

```text
HTTP/1.1 200 Connection Established
```

或显示目标网站的 HTTPS 响应头。

### 截图 I：HTTP GET 缓存

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage10_cache_smoke.py
```

截图内容：

```text
CACHE_HIT client=127.0.0.1
stage10 cache smoke test passed
```

手动展示时可以连续访问同一 URL：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

管理前端中截图：

```text
缓存命中
缓存未命中
缓存条目
```

## 5. 核心功能描述模板

### HTTP 代理转发

```text
代理服务器首先监听本地端口，接收客户端发送的 HTTP 请求。程序解析请求首行和 Host 头部，得到目标服务器地址、端口和路径。随后代理服务器主动连接目标 Web 服务器，将请求转发给目标服务器，并把服务器响应返回给客户端，从而完成客户端与目标服务器之间的中间转发。
```

### 域名拦截

```text
系统维护一个域名黑名单，当客户端请求的目标域名命中黑名单时，代理服务器不再连接目标服务器，而是直接向客户端返回 403 Forbidden 响应，实现指定域名的访问控制。
```

### 网页关键字过滤

```text
系统在接收到目标服务器响应后，根据响应头中的 Content-Type 判断资源类型。对于 HTML、文本、CSS、JavaScript、JSON 等文本类资源，代理服务器读取响应正文并检测是否包含配置文件中的禁止关键字。如果命中关键字，则返回过滤提示页面；对于图片、压缩包等二进制资源则直接转发，避免破坏文件内容。
```

### HTTPS CONNECT 隧道

```text
系统支持 HTTPS CONNECT 隧道。当客户端请求 HTTPS 网站时，代理首先解析 CONNECT 请求中的目标域名和端口，然后连接目标服务器，并向客户端返回 200 Connection Established。隧道建立后，代理只负责在客户端和目标服务器之间转发加密字节流。由于 HTTPS 正文经过 TLS 加密，代理不能直接读取网页内容，因此系统仅对 HTTPS 目标域名进行拦截，不对 HTTPS 正文进行关键字过滤。
```

### HTTP GET 缓存

```text
系统支持对 HTTP GET 请求进行简单内存缓存。客户端第一次访问某个 URL 时，代理从目标服务器获取响应并写入缓存；在缓存有效期内再次访问同一 URL 时，代理直接返回缓存内容，不再连接目标服务器。系统通过缓存命中数、缓存未命中数和缓存条目数展示缓存运行效果。

系统支持客户端 IP/CIDR 访问控制。代理接收请求后，首先根据客户端套接字地址执行客户端黑名单和白名单策略，再执行认证、限流和目标网站过滤。规则支持单个 IPv4/IPv6 地址及 CIDR 网段，可通过前端、管理 API 和命令行实时修改。命中规则时系统返回 403 Forbidden，并记录独立的客户端拦截统计和审计日志。
```

### 截图 J：白名单模式

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage11_whitelist_smoke.py
```

截图内容：

```text
Mode: whitelist
domain_not_in_whitelist
stage11 whitelist smoke test passed
```

### 截图 K：一键全量验收

命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_all_smoke.py
```

截图内容：

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
all test batches passed
```

### 截图 L：前端展示验收

自动验证命令：

```powershell
python tests\stage12_frontend_display_smoke.py
```

截图内容：

```text
stage12 frontend display smoke test passed
```

前端页面手动打开：

```text
http://127.0.0.1:8088/
```

截图内容：

```text
过滤规则
过滤规则管理
缓存命中
HTTPS 隧道
访问日志
```

### 截图 M：代理认证

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage13_auth_smoke.py
```

截图内容：

```text
AUTH_REQUIRED
407 Proxy Authentication Required
stage13 auth smoke test passed
```

手动展示命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 --proxy-user student:123456 http://127.0.0.1:9000/
```

### 截图 N：访问频率限制

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage14_rate_limit_smoke.py
```

截图内容：

```text
RATE_LIMIT
429 Too Many Requests
stage14 rate limit smoke test passed
```

### 截图 O：规则管理自动验证

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage15_rule_management_smoke.py
```

截图内容：

```text
FILTER client=127.0.0.1 method=GET
BLOCK client=127.0.0.1 method=GET
stage15 rule management smoke test passed
```

### 截图 P：后端命令行规则管理

自动验证命令：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\stage16_rule_cli_smoke.py
```

截图内容：

```text
python tools\rule_cli.py update blocked_content_keywords classroom lecture
stage16 rule cli smoke test passed
```

## 6. HTTPS 说明模板

如果实现了 HTTPS CONNECT，可以写：

```text
系统支持 HTTPS CONNECT 隧道转发。客户端访问 HTTPS 网站时，代理服务器根据 CONNECT 请求建立到目标服务器 443 端口的 TCP 连接，并在两端之间转发加密字节流。由于 HTTPS 正文经过 TLS 加密，普通代理无法读取网页内容，因此系统只对 HTTPS 目标域名进行拦截，不对 HTTPS 正文进行关键字过滤。
```

如果没有实现 HTTPS CONNECT，可以写：

```text
本实验重点实现 HTTP 明文代理转发、域名拦截和网页关键字过滤。HTTPS CONNECT 隧道属于扩展功能，由于 HTTPS 内容加密，正文过滤需要中间人代理和证书信任机制，超出本实验基础范围。
```
