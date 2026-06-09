# 04 前后端拆解说明

本项目现在拆成两个后端端口和一个前端页面。

## 0. 源码分层

项目属于前后端项目，但前端和后端不需要使用不同的编程语言：

```text
frontend/index.html
```

负责浏览器中的规则管理、运行设置、统计和日志展示。

```text
frontend/logs.html
```

负责结构化日志查询。管理台统计数字可以点击，跳转后按照日志类型、事件类型和全文关键字查询记录，并可把当前查询结果导出为 CSV。

```text
src/proxy.py
```

是后端命令行入口，负责代理服务、管理 API 和服务器生命周期。

```text
src/webproxy/config_rules.py
```

是后端配置与规则基础模块，负责读取配置、定义可编辑规则组、标准化规则值和处理 Windows 命令行传来的 JSON。拆分后原来的启动命令、管理 API 和前端地址保持不变。

```text
src/webproxy/audit.py
```

是后端日志审计模块，负责将事件写入访问日志、拦截日志和错误日志，并为管理前端提供日志查询与清空功能。

## 1. 端口划分

代理服务端口：

```text
127.0.0.1:8080
```

作用：

```text
接收 curl / 浏览器代理请求，转发 Web 请求，执行域名拦截、URL 拦截、方法拦截和网页关键字过滤。
```

管理服务端口：

```text
127.0.0.1:8088
```

作用：

```text
提供管理前端页面和 JSON API，用来显示当前过滤规则、增删过滤规则、保存运行设置、查看统计和日志。
```

## 2. 前端页面

文件：

```text
frontend/index.html
```

打开地址：

```text
http://127.0.0.1:8088/
```

页面显示：

- 当前代理地址和管理地址。
- 黑名单模式或白名单模式。
- 域名黑名单，并支持新增、删除、查询。
- 域名白名单，并支持新增、删除、查询。
- URL 关键字，并支持新增、删除、查询。
- 正文关键字，并支持新增、删除、查询。
- 禁止的 HTTP 方法，并支持新增、删除、查询。
- 支持修改单条规则和替换整个规则组。
- 支持规则变更回显和按操作类型筛选。
- 运行设置，例如模式、缓存、认证、限流。
- 总请求数、放行数、拦截数、过滤数、HTTPS 隧道数。
- 访问日志、拦截日志、错误日志。
- 域名访问排行。
- 关键字命中排行。
- 点击统计数字进入对应事件的日志查询详情页。

## 3. 后端 API

查看配置：

```powershell
curl.exe http://127.0.0.1:8088/api/config
```

查看可编辑规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

新增正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

删除正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

修改正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

替换正文关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","values":["forbidden","attack","virus"]}'
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

新增白名单域名：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

删除白名单域名：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"allowed_domains","value":"127.0.0.1"}'
```

切换白名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"whitelist"}}'
```

切换回黑名单模式：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/settings/update -H "Content-Type: application/json" -d '{"settings":{"mode":"blacklist"}}'
```

查看统计：

```powershell
curl.exe http://127.0.0.1:8088/api/stats
```

查看访问日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=proxy&limit=100"
```

查看拦截日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=blocked&limit=100"
```

查看错误日志：

```powershell
curl.exe "http://127.0.0.1:8088/api/logs?kind=error&limit=100"
```

重新加载配置文件：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/reload
```

命令参数含义：

```text
curl.exe
```

Windows 下明确调用 curl 程序，避免 PowerShell 把 `curl` 当成别名。

```text
-X POST
```

指定 HTTP 请求方法为 POST，用于新增、删除、保存等会改变服务器状态的操作。

```text
-H "Content-Type: application/json"
```

告诉后端请求体是 JSON 格式。

```text
-d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

发送 JSON 请求体。`rule_type` 指定规则类型，`value` 是要新增或删除的规则值。

```text
blocked_domains
```

域名黑名单。

```text
allowed_domains
```

域名白名单。

```text
blocked_url_keywords
```

URL 关键字规则。

```text
blocked_content_keywords
```

网页正文关键字规则。

```text
blocked_methods
```

禁止的 HTTP 方法规则。

```text
old_value
```

修改规则时的原规则值。

```text
new_value
```

修改规则时的新规则值。

```text
values
```

替换规则组时的新规则列表。

## 4. 后端命令行工具

除了 `curl.exe`，也可以使用项目自带命令行工具：

```powershell
python tools\rule_cli.py list
python tools\rule_cli.py add blocked_content_keywords classroom
python tools\rule_cli.py update blocked_content_keywords classroom lecture
python tools\rule_cli.py delete blocked_content_keywords lecture
python tools\rule_cli.py replace blocked_url_keywords private exam
```

详细验收说明：

```text
docs/08_backend_cli_rule_management.md
```

## 5. 启动命令

使用配置文件默认端口启动：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

指定代理端口和管理端口：

```powershell
python src\proxy.py --host 127.0.0.1 --port 8080 --admin-host 127.0.0.1 --admin-port 8088 --config config.example.json
```

只启动代理，不启动管理前端：

```powershell
python src\proxy.py --config config.example.json --no-admin
```

## 6. 手动验证流程

启动测试网站：

```powershell
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

启动代理和管理前端：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

访问普通页面：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

访问敏感词页面：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/forbidden.html
```

访问 URL 关键字页面：

```powershell
curl -i -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

访问域名黑名单：

```powershell
curl -i -x http://127.0.0.1:8080 http://blocked.test/
```

验证 HTTPS CONNECT：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

然后打开：

```text
http://127.0.0.1:8088/
```

管理前端中应该能看到统计数字和日志变化。

## 7. 报告写法

可以在报告中写：

```text
系统采用前后端分离式设计。代理服务负责接收和转发客户端 Web 请求，并根据配置文件执行访问控制和内容过滤；管理服务负责提供前端页面和 JSON API，用于展示当前过滤规则、访问统计和日志审计结果。两个服务运行在同一个 Python 程序中，但监听不同端口，从而将代理业务流量和管理页面访问分离。
```

后端源码组织可以补充写为：

```text
后端采用入口程序与功能模块分层的组织方式。proxy.py 保持稳定的命令行入口，config_rules.py 封装配置和规则处理逻辑，使规则管理代码能够被代理服务、管理 API 和测试代码共同复用。
```
