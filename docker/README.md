# Docker 运行方案

如果 Windows 本机 Python 环境不好用，可以用 Docker 跑代理。

## 1. 思路

Docker 容器只负责运行 Python 代理程序。Windows 通过端口映射访问容器里的代理。

建议映射：

```text
Windows 127.0.0.1:8080 -> container 0.0.0.0:8080
Windows 127.0.0.1:8088 -> container 0.0.0.0:8088
```

注意：

- 容器内监听地址建议用 `0.0.0.0`。
- Windows 本机访问时仍然使用 `127.0.0.1:8080`。

## 2. 临时用 Python 镜像运行

在项目根目录执行：

```powershell
cd E:\eve_jump\web_proxy_final_lab
docker run --rm -it -p 8080:8080 -p 8088:8088 -v ${PWD}:/app -w /app python:3.12-slim python src/proxy.py --host 0.0.0.0 --port 8080 --admin-host 0.0.0.0 --admin-port 8088 --config config.example.json
```

如果 PowerShell 的 `${PWD}` 映射有问题，可以写绝对路径：

```powershell
docker run --rm -it -p 8080:8080 -p 8088:8088 -v E:\eve_jump\web_proxy_final_lab:/app -w /app python:3.12-slim python src/proxy.py --host 0.0.0.0 --port 8080 --admin-host 0.0.0.0 --admin-port 8088 --config config.example.json
```

管理前端打开：

```text
http://127.0.0.1:8088/
```

## 3. Docker 中访问 Windows 本机测试网站

如果本地测试网站运行在 Windows：

```powershell
cd E:\eve_jump\web_proxy_final_lab\tests\webroot
python -m http.server 9000
```

容器里访问 Windows 主机一般可以用：

```text
host.docker.internal
```

通过代理测试：

```powershell
curl -i -x http://127.0.0.1:8080 http://host.docker.internal:9000/
```

关键字过滤测试：

```powershell
curl -i -x http://127.0.0.1:8080 http://host.docker.internal:9000/forbidden.html
```

## 4. 查看容器

```powershell
docker ps
```

## 5. 停止容器

如果用 `--rm -it` 前台运行，按：

```text
Ctrl+C
```

即可停止。
