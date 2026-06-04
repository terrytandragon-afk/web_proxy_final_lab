# 02 可选功能路线图

本文件整理你粘贴文本中的扩展想法。建议按优先级做，先保底，再加分。

## 优先级 A：建议完成

### 1. 多线程并发

功能：

- 多个客户端可以同时访问代理。
- 每个连接用一个线程处理。

实现关键词：

```text
threading.Thread
daemon=True
```

测试命令：

```powershell
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

也可以开多个 PowerShell 窗口同时执行。

### 2. 日志审计

功能：

- 记录允许访问、域名拦截、关键字过滤、错误。

建议日志文件：

```text
logs/proxy.log
logs/blocked.log
logs/error.log
```

查看日志命令：

```powershell
Get-Content .\logs\proxy.log
Get-Content .\logs\blocked.log
Get-Content .\logs\error.log
```

实时查看日志：

```powershell
Get-Content .\logs\proxy.log -Wait
```

### 3. 配置文件

功能：

- 从 `config.example.json` 读取规则。
- 命令行指定配置文件。

运行命令：

```powershell
python src\proxy.py --config config.example.json
```

命令行覆盖端口：

```powershell
python src\proxy.py --host 127.0.0.1 --port 8081 --config config.example.json
```

### 4. URL 关键字拦截

功能：

- 如果 URL 路径包含 `game`、`download`、`admin` 等关键字，直接返回 403。

测试命令：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

预期：

```text
HTTP/1.1 403 Forbidden
```

### 5. 请求方法过滤

功能：

- 禁止 `PUT`、`DELETE`，可选禁止 `POST`。

测试命令：

```powershell
curl -i -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 403 Forbidden
```

## 优先级 B：可以做成加分

### 6. HTTPS CONNECT 隧道

功能：

- 支持浏览器或 curl 通过代理访问 HTTPS 网站。
- 对 HTTPS 只做域名拦截，不做正文关键字过滤。

测试命令：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

域名拦截测试：

```powershell
curl -I -x http://127.0.0.1:8080 https://blocked.test/
```

报告说明建议：

```text
本系统支持 HTTPS CONNECT 隧道转发，并可根据 CONNECT 请求中的目标域名进行访问控制。由于 HTTPS 正文经过 TLS 加密，普通代理无法读取网页正文，因此本系统不对 HTTPS 正文进行关键字过滤。
```

### 7. 白名单模式

功能：

- 黑名单模式：默认允许，命中规则才拦截。
- 白名单模式：默认拦截，只允许配置中的域名。

配置：

```json
"mode": "whitelist",
"allowed_domains": ["127.0.0.1", "localhost", "example.com"]
```

测试命令：

```powershell
curl -i -x http://127.0.0.1:8080 http://example.com/
curl -i -x http://127.0.0.1:8080 http://not-allowed.test/
```

### 8. 客户端 IP 限制

功能：

- 只允许 `127.0.0.1` 使用代理。
- 防止代理被局域网其他主机滥用。

查看监听地址：

```powershell
netstat -ano | findstr 8080
```

如果只监听本机，应显示：

```text
127.0.0.1:8080
```

### 9. 统计信息

功能：

- 总请求数。
- 允许数。
- 域名拦截数。
- 关键字过滤数。
- 错误数。

建议程序每 30 秒输出：

```text
[STATUS] requests=20 allowed=15 blocked_domain=2 blocked_keyword=3 errors=0
```

测试命令：

```powershell
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl -x http://127.0.0.1:8080 http://blocked.test/
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

## 优先级 C：只建议写进展望

### 10. 缓存

功能：

- 缓存 HTTP 静态资源。
- 再次访问同一 URL 时直接返回缓存。

测试命令设想：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

第二次日志中显示：

```text
CACHE_HIT
```

### 11. 关键字替换

功能：

- 不拦截整个页面，只把指定词替换为 `***`。

测试命令：

```powershell
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

预期：

```text
secret -> ***
```

### 12. 限速与频率限制

功能：

- 限制单个客户端每分钟请求数。
- 超过限制返回 429。

测试命令设想：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

预期：

```text
HTTP/1.1 429 Too Many Requests
```

## 最终建议

课程最低要求只需要完成：

```text
HTTP 代理转发 + 域名拦截 + 网页关键字过滤
```

最推荐加分组合：

```text
配置文件 + 日志 + 多线程 + URL 关键字拦截 + HTTPS CONNECT 域名拦截
```

