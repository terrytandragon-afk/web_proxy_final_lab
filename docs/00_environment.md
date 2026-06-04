# 00 环境准备

你的环境是 Windows + Docker 命令行 + VS Code，所以建议先用 Windows 本机开发，遇到环境问题再放到 Docker 里跑。

## 1. 检查 Python

在 PowerShell 中执行：

```powershell
python --version
```

如果没有 Python，可以检查 Windows Python 启动器：

```powershell
py --version
```

## 1.1 PowerShell 中文显示问题

如果用 `Get-Content` 查看 Markdown 时中文乱码，优先用 VS Code 打开文件。也可以在当前 PowerShell 中切换到 UTF-8：

```powershell
chcp 65001
```

然后用 UTF-8 方式读取：

```powershell
Get-Content .\README.md -Encoding UTF8
```

## 2. 进入项目目录

```powershell
cd E:\eve_jump\web_proxy_final_lab
```

## 3. 用 VS Code 打开

```powershell
code .
```

如果 `code` 命令不可用，直接在 VS Code 里选择 `File -> Open Folder`，打开：

```text
E:\eve_jump\web_proxy_final_lab
```

## 4. 创建虚拟环境

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 不允许执行脚本，可以临时放开当前用户策略：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

再次激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 5. 本项目基础阶段不需要安装第三方库

基础代理建议只使用 Python 标准库：

```text
socket
threading
urllib.parse
json
time
logging
fnmatch
select
```

所以不需要执行 `pip install`。

## 6. 准备本地测试 Web 服务器

打开一个新的 PowerShell 终端：

```powershell
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

这个命令会启动一个本地 Web 服务器：

```text
http://127.0.0.1:9000/
```

直接访问测试：

```powershell
curl http://127.0.0.1:9000/
```

访问包含敏感词的页面：

```powershell
curl http://127.0.0.1:9000/forbidden.html
```

## 7. 代理运行命令

等 `src/proxy.py` 实现到对应阶段后，用下面命令运行：

```powershell
cd E:\eve_jump\web_proxy_final_lab
python src\proxy.py --host 127.0.0.1 --port 8080 --config config.example.json
```

通过代理访问本地 Web 服务器：

```powershell
curl -x http://127.0.0.1:8080 http://127.0.0.1:9000/
```
