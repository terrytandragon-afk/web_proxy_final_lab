# 01 最低要求实现步骤

本文件只拆解最低要求，不直接给完整代码。你可以按阶段逐步实现，每完成一阶段就用命令验证。

## 阶段 1：建立代理监听端口

目标：

- 程序监听 `127.0.0.1:8080`。
- 客户端能连接到代理端口。
- 代理能读取客户端发来的 HTTP 请求文本。

需要实现：

- 创建 TCP socket。
- 绑定 host 和 port。
- `listen()` 等待客户端。
- `accept()` 接收连接。
- `recv()` 读取请求。
- 打印请求首行和 Host 请求头。

启动代理：

```powershell
python src\proxy.py --host 127.0.0.1 --port 8080 --config config.example.json
```

测试命令：

```powershell
curl.exe --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期现象：

- curl 此时可以暂时失败。
- 但代理终端必须能打印类似内容：

```text
GET http://127.0.0.1:9000/ HTTP/1.1
Host: 127.0.0.1:9000
```

报告截图建议：

- 截图 1：代理启动成功。
- 截图 2：curl 访问代理后，代理打印 HTTP 请求。

## 阶段 2：解析 HTTP 请求

目标：

- 从请求中解析出方法、目标主机、端口、路径。

需要实现：

- 解析请求首行。
- 支持代理格式：

```text
GET http://127.0.0.1:9000/index.html HTTP/1.1
```

- 得到：

```text
method = GET
host = 127.0.0.1
port = 9000
path = /index.html
```

测试命令：

```powershell
curl.exe --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/index.html
```

预期现象：

```text
method=GET host=127.0.0.1 port=9000 path=/index.html
```

## 阶段 3：转发请求到真实 Web 服务器

目标：

- 代理主动连接目标服务器。
- 把客户端请求转发给目标服务器。

关键处理：

客户端发给代理时通常是完整 URL：

```text
GET http://127.0.0.1:9000/index.html HTTP/1.1
```

代理转发给真实服务器时应改成相对路径：

```text
GET /index.html HTTP/1.1
Host: 127.0.0.1:9000
Connection: close
Accept-Encoding: identity
```

说明：

- `Connection: close` 可以让服务器返回后关闭连接，降低初版实现难度。
- `Accept-Encoding: identity` 尽量避免 gzip 压缩，方便后续关键字过滤。

测试命令：

```powershell
curl.exe --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/index.html
```

预期现象：

- curl 能看到 `index.html` 的内容。
- 本地 Web 服务器终端能看到访问记录。

## 阶段 4：把服务器响应返回给客户端

目标：

- 代理接收目标服务器响应。
- 代理把完整响应原样发送给客户端。

需要实现：

- 循环 `recv()` 目标服务器响应。
- 每收到一块数据就 `sendall()` 给客户端。
- 直到目标服务器关闭连接。

测试命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期现象：

- 可以看到 HTTP 状态码。
- 可以看到网页正文。

## 阶段 5：域名黑名单拦截

目标：

- 命中指定域名时，代理直接返回 `403 Forbidden`。
- 不再连接真实服务器。

配置来源：

```json
"blocked_domains": [
  "blocked.test",
  "example-blocked.com",
  "*.badsite.test"
]
```

需要实现：

- 读取 `config.example.json`。
- 判断请求 host 是否命中黑名单。
- 命中后返回拦截页面。

测试命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

预期现象：

```text
HTTP/1.1 403 Forbidden
```

报告截图建议：

- 截图 1：配置文件中有 `blocked.test`。
- 截图 2：访问 `blocked.test` 返回 403。
- 截图 3：代理日志显示 `BLOCK_DOMAIN`。

## 阶段 6：网页关键字过滤

目标：

- 代理收到服务器响应后，检查网页正文是否包含指定关键字。
- 如果包含，返回过滤提示页，而不是原网页。

配置来源：

```json
"blocked_content_keywords": [
  "forbidden",
  "attack",
  "virus",
  "secret"
]
```

关键限制：

- 只对文本类型做关键字过滤。
- 图片、压缩包、视频等二进制内容不要按字符串处理。

建议过滤的 Content-Type：

```text
text/html
text/plain
text/css
application/javascript
application/json
```

测试命令：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

预期现象：

```text
HTTP/1.1 403 Forbidden
```

页面正文显示：

```text
网页已被过滤
```

浏览器中原网页会被代理生成的拦截页替代，可展开查看 `content_keyword:<关键字>` 等详细原因。

报告截图建议：

- 截图 1：原始页面里存在敏感词。
- 截图 2：通过代理访问时返回过滤提示。
- 截图 3：代理日志显示 `BLOCK_KEYWORD`。

## 阶段 7：最低要求验收命令

开发阶段也可以先跑本地烟测，不需要手动启动多个终端：

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
```

先启动本地测试 Web：

```powershell
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

再启动代理：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --host 127.0.0.1 --port 8080 --config config.example.json
```

验证普通转发：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

验证指定域名拦截：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

验证指定关键字过滤：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```
