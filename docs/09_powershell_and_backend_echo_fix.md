# 09 PowerShell/CMD 规则修改兼容与后端回显

## 一、实现了什么功能

本模块补充解决两个验收问题：

1. PowerShell 和 CMD 使用 `curl.exe -d` 传 JSON 时，引号处理方式不同，可能导致后端收到的请求体不是标准 JSON。
2. 通过 `curl.exe` 或 `python tools\rule_cli.py` 修改规则后，前端管理端也需要能看到规则变更回显。

现在后端支持：

```text
标准 JSON
{"rule_type":"blocked_domains","value":"*.baidu.com"}
```

```text
CMD 误传外层单引号
'{"rule_type":"blocked_domains","value":"*.baidu.com"}'
```

```text
PowerShell 吞掉内部双引号
{rule_type:blocked_domains,value:*.baidu.com}
```

同时新增后端变更历史接口：

```text
/api/changes
```

前端点击“刷新”后，会读取该接口，所以命令行修改的规则也能显示在“规则变更回显”区域。

## 二、代码位置

```text
src/proxy.py
```

实现内容：

```text
parse_loose_json_object()
parse_loose_json_value()
split_top_level_csv()
```

用于兼容 PowerShell/CMD 常见 JSON 引号问题。

```text
RuntimeState.change_history
RuntimeState.get_change_history()
RuntimeState._record_change_locked()
```

用于保存新增、删除、修改、替换规则和运行设置修改记录。

```text
/api/changes
```

用于查询后端规则变更历史。

```text
frontend/index.html
```

实现内容：

```text
loadChanges()
```

用于刷新页面时读取后端变更历史。

```text
tools/rule_cli.py
```

实现内容：

```text
changes
```

用于通过 Python 命令行工具查询规则变更历史。

## 三、PowerShell 验收命令

新增域名黑名单：

```powershell
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{`"rule_type`":`"blocked_domains`",`"value`":`"*.baidu.com`"}"
```

命令解释：

```text
curl.exe
```

调用 Windows 自带的 curl 程序。

```text
-X POST
```

指定 HTTP 请求方法为 POST。

```text
http://127.0.0.1:8088/api/rules/add
```

管理后端的新增规则接口。

```text
-H "Content-Type: application/json"
```

设置请求头，告诉后端请求体是 JSON。

```text
-d
```

发送请求体数据。

```text
`"
```

PowerShell 中的反引号转义双引号，表示把真实双引号传给 `curl.exe`。

通配符解释：

```text
*
```

表示任意长度的字符。

```text
*.baidu.com
```

推荐用于拦截百度子域名，可以匹配 `www.baidu.com`、`map.baidu.com`。

```text
baidu.com
```

推荐用于拦截 `baidu.com` 以及它的子域名，例如 `www.baidu.com`。

```text
*baidu*
```

显式包含匹配，可以匹配所有域名中含 `baidu` 的地址。这个范围更宽，可能误拦其他域名，只有确实需要时再使用。

```text
baidu
```

普通短词不会自动作为包含匹配生效，避免误拦。

## 四、CMD 验收命令

新增域名黑名单：

```cmd
curl.exe -X POST http://127.0.0.1:8088/api/rules/add -H "Content-Type: application/json" -d "{\"rule_type\":\"blocked_domains\",\"value\":\"*.baidu.com\"}"
```

命令解释：

```text
\"
```

CMD/curl 常用写法，用于把双引号作为 JSON 内容传递。

## 五、查询规则变更回显

通过 curl 查询：

```powershell
curl.exe "http://127.0.0.1:8088/api/changes?limit=20"
```

命令解释：

```text
/api/changes
```

查询后端规则变更历史。

```text
limit=20
```

最多返回 20 条记录。

通过 Python 命令行工具查询：

```powershell
python tools\rule_cli.py changes --limit 20
```

命令解释：

```text
python
```

运行 Python 脚本。

```text
tools\rule_cli.py
```

项目提供的后端规则管理命令行工具。

```text
changes
```

查询规则变更历史。

```text
--limit 20
```

最多返回 20 条记录。

## 六、前端回显验证

打开：

```text
http://127.0.0.1:8088/
```

操作步骤：

1. 使用 PowerShell 或 CMD 执行新增规则命令。
2. 打开或切换到前端管理端。
3. 点击“刷新”。
4. 查看“规则变更回显”区域。

预期结果：

```text
能看到 action=add 或新增记录。
能看到 rule_type=blocked_domains。
能看到 value=*.baidu.com。
能看到 changed=true 或 changed=false。
能看到 saved=true。
```

## 七、自动测试命令

```powershell
python tests\stage8_admin_smoke.py
python tests\stage16_rule_cli_smoke.py
python tests\run_all_smoke.py
```

预期结果：

```text
stage8 admin smoke test passed
stage16 rule cli smoke test passed
all smoke tests passed
```
