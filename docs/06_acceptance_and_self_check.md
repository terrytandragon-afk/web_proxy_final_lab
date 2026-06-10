# 06 验收与自测流程

本文件专门回答两个问题：

1. 老师验收时怎么展示。
2. 自己平时怎么验证项目没坏。

## 一、自己验证项目

自己验证分两种：一种是快速全量验证，另一种是逐模块熟悉项目。

如果你想一步步熟悉项目，优先看：

```text
docs/07_manual_module_verification.md
```

里面每个功能都有实现位置、命令、参数含义和前端观察点。

如果你要现场照着命令验收，尤其是展示后端命令行增删改查规则，优先看：

```text
docs/08_backend_cli_rule_management.md
```

里面区分了 PowerShell 和 Windows CMD 的 JSON 写法，并解释了 `curl.exe` 的 `-x`、`-X`、`-H`、`-d`、`-i`、`-I` 等参数。

如果重点验证 PowerShell/CMD 引号兼容、后端命令行修改规则后的前端回显，补充查看：

```text
docs/09_powershell_and_backend_echo_fix.md
```

快速验证的目标是：确认所有功能模块都能正常运行。

只验证基础 Web/代理功能：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\run_web_features_smoke.py
```

只验证规则组更改、模式切换和运行时设置：

```powershell
python tests\run_rule_management_smoke.py
```

最后验证全部批次：

```powershell
python tests\run_all_smoke.py
```

这三个命令都会使用专用测试配置，不受当前正式规则组内容影响。测试证据位置、重复运行机制、前端查看命令和限流首次放行说明见：

```text
docs/08_backend_cli_rule_management.md
```

命令含义：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python
```

使用 Python 解释器运行脚本。

```text
tests\run_all_smoke.py
```

一键自动验收脚本。它会依次运行基础功能批次和规则管理批次。

预期输出：

```text
all test batches passed
```

如果出现失败：

```text
FAILED: stageX_xxx.py
```

说明对应模块需要检查。可以单独运行这个失败脚本。

## 二、老师验收展示流程

老师验收时，建议按“启动服务 -> 访问代理 -> 查看前端 -> 跑一键测试 -> 解释核心模块”的顺序展示。

### 步骤 1：启动本地测试网站

打开第一个 PowerShell：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python tests\manual_demo_server.py
```

命令含义：

```text
cd E:\eve_jump\web_proxy_final_lab
```

进入项目根目录。

```text
python tests\manual_demo_server.py
```

启动专用手动验收目标：HTTP 测试站端口为 `9000`，CONNECT 回显目标端口为 `9001`。

展示说明：

```text
这个本地网站模拟真实 Web 服务器，用来测试代理转发和网页过滤。
```

PowerShell 访问本机测试站的代理命令必须包含 `--noproxy no-host-bypass.invalid`，防止 Windows `curl.exe` 根据 `NO_PROXY` 绕过代理。验收前准备规则：

```powershell
python tools\rule_cli.py add blocked_url_keywords game
python tools\rule_cli.py add blocked_content_keywords forbidden
```

浏览器访问本机测试站时，Edge/Chrome 也会默认绕过代理。请打开第三个 PowerShell，启动专用验收浏览器：

```powershell
powershell -ExecutionPolicy Bypass -File tools\start_proxy_browser.ps1
```

该脚本使用独立浏览器配置，并强制 `127.0.0.1` 请求经过 `8080`。命中规则时，浏览器中的原网页会被代理生成的 `403` 拦截页替代；点击“查看详细信息”可查看原因和命中规则。

### 步骤 2：启动代理服务和管理前端

打开第二个 PowerShell：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --config config.example.json
```

命令含义：

```text
python src\proxy.py
```

启动代理服务器主程序。

```text
--config config.example.json
```

指定配置文件，里面包含监听端口、黑名单、关键字、缓存、日志等规则。

启动后显示：

```text
Proxy started at 127.0.0.1:8080
Admin dashboard started at http://127.0.0.1:8088/
```

展示说明：

```text
8080 是代理端口，8088 是管理前端端口。
```

### 步骤 3：打开管理前端

浏览器打开：

```text
http://127.0.0.1:8088/
```

展示重点：

- 当前过滤规则。
- 过滤规则增删改查。
- 总请求数。
- 放行数。
- 域名拦截。
- 正文过滤。
- HTTPS 隧道。
- 缓存命中。
- 认证拦截。
- 限流拦截。
- 访问日志。

### 步骤 4：验证普通代理转发

打开第三个 PowerShell：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```

命令含义：

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

指定使用本项目代理服务器。

```text
http://127.0.0.1:9000/
```

目标 Web 服务器地址。

预期结果：

```text
HTTP/1.0 200 OK
```

### 步骤 5：验证域名拦截

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://blocked.test/
```

预期结果：

```text
HTTP/1.1 403 Forbidden
domain_blacklist
```

展示说明：

```text
blocked.test 在配置文件黑名单中，因此代理直接拦截，不访问真实服务器。
```

### 步骤 6：验证网页关键字过滤

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/content-test.html
```

预期结果：

```text
HTTP/1.1 403 Forbidden
网页已被过滤
content_keyword:forbidden
```

也可以在专用验收浏览器中打开 `http://127.0.0.1:9000/content-test.html`，应看到代理生成的 `403` 拦截页，而不是原网页。

展示说明：

```text
HTTP 明文网页正文包含 `forbidden`，但 URL 不包含该词，因此代理返回过滤提示页可以明确证明正文过滤生效。
```

### 步骤 7：验证 URL 关键字和请求方法过滤

URL 关键字：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/game/index.html
```

这里的 URL 关键字检查请求地址中的域名、路径/子文件和查询参数，不检查网页正文。规则 `game` 会命中路径 `/game/index.html`。

请求方法：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 -X DELETE http://127.0.0.1:9000/
```

命令含义：

```text
-X DELETE
```

指定 HTTP 请求方法为 `DELETE`。

预期结果：

```text
HTTP/1.1 403 Forbidden
```

### 步骤 8：验证缓存

先启用并清空缓存：

```powershell
python tools\rule_cli.py set cache_enabled true
curl.exe -X POST http://127.0.0.1:8088/api/cache/clear
```

连续访问同一 URL 两次：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/cache.txt
```

展示重点：

```text
第一次请求缓存未命中。
第二次请求缓存命中。
两次响应均显示 `X-Upstream-Hit: 1` 和 `upstream-hit=1`。
管理前端中的“缓存命中”“缓存条目”会变化。
```

### 步骤 9：验证过滤规则增删改查

查询规则：

```powershell
curl.exe http://127.0.0.1:8088/api/rules
```

新增正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"classroom"}'
```

访问包含该关键字的测试页面：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期结果：

```text
网页已被过滤
blocked by keyword filter: classroom
```

修改正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/update -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","old_value":"classroom","new_value":"lecture"}'
```

替换 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":["private","exam"]}'
```

演示后可以清空这个 URL 关键字规则组：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/replace -H "Content-Type: application/json" -d '{"rule_type":"blocked_url_keywords","values":[]}'
```

删除正文关键字：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/delete -H "Content-Type: application/json" -d '{"rule_type":"blocked_content_keywords","value":"lecture"}'
```

后端命令行工具也可以完成同样操作：

```powershell
python tools\rule_cli.py list
python tools\rule_cli.py add blocked_content_keywords classroom
python tools\rule_cli.py update blocked_content_keywords classroom lecture
python tools\rule_cli.py delete blocked_content_keywords lecture
python tools\rule_cli.py replace blocked_url_keywords private exam
```

再次访问：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/classroom.html
```

预期结果：

```text
HTTP/1.0 200 OK
Classroom Rule Demo
```

展示说明：

```text
规则不是写死在代码里，而是可以通过前端、后端 API 或 Python 命令行工具新增、删除、修改、查询和替换规则组，并立即影响代理过滤结果。
```

### 步骤 10：验证 HTTPS CONNECT

如果外网可用：

```powershell
curl -I -x http://127.0.0.1:8080 https://example.com/
```

命令含义：

```text
-I
```

只请求响应头。

展示说明：

```text
HTTPS 使用 CONNECT 隧道。代理能控制目标域名，但不能读取 HTTPS 正文。
```

本地确定性验收，证明 CONNECT 建立后确实转发数据：

```powershell
python tests\manual_connect_tunnel.py
```

预期包含：

```text
echo:hello-through-manual-tunnel
manual CONNECT tunnel data forwarding passed
```

### 步骤 10.1：验证访问频率限制

启用限流、设置窗口内仅允许一次请求并清空计数：

```powershell
python tools\rule_cli.py set rate_limit_enabled true
python tools\rule_cli.py set rate_limit_per_minute 1
python tools\rule_cli.py set rate_limit_window_seconds 60
python tools\rule_cli.py rate-reset
```

连续请求两次：

```powershell
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
curl.exe -i --noproxy no-host-bypass.invalid -x http://127.0.0.1:8080 http://127.0.0.1:9000/rate-limit.txt
```

第一次返回 `200`，第二次返回 `429 Too Many Requests`。默认配置关闭限流，只修改 `rate_limit_per_minute` 不会启用限流。

演示后关闭限流：

```powershell
python tools\rule_cli.py set rate_limit_enabled false
python tools\rule_cli.py rate-reset
```

### 步骤 11：一键全量验收

最后展示：

```powershell
python tests\run_all_smoke.py
```

预期结果：

```text
all smoke tests passed
```

## 三、已实现模块清单

已实现：

- HTTP 代理转发。
- 域名黑名单拦截。
- 网页正文关键字过滤。
- URL 关键字拦截。
- HTTP 方法过滤。
- 日志审计。
- 管理前端。
- 管理 API。
- HTTPS CONNECT 隧道。
- HTTP GET 缓存。
- 白名单模式。
- 配置热加载。
- 过滤规则增删改查。
- 代理认证。
- 访问频率限制。
- 一键自动验收。

未实现但可写进展望：

- HTTPS 中间人解密过滤。
- 数据库存储日志。
- 多用户分组策略。
