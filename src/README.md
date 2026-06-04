# src 目录说明

这里放代理服务器源码。当前主程序是：

```text
proxy.py
```

当前为了便于课程验收和阅读，核心功能集中在 `proxy.py` 中，并通过函数和注释划分模块。

## 已实现核心函数

1. `main()`：读取命令行参数。
2. `load_config()`：读取 JSON 配置。
3. `start_server()`：监听代理端口。
4. `handle_client()`：处理单个客户端连接。
5. `parse_http_request()`：解析 method、host、port、path。
6. `check_access_policy()`：执行域名、URL、方法、白名单策略。
7. `forward_http()`：转发 HTTP 请求并返回响应。
8. `filter_response_content()`：检查网页正文关键字。
9. `forward_connect()`：处理 HTTPS CONNECT 隧道。
10. `RuntimeState.add_list_rule()`：新增过滤规则并保存配置。
11. `RuntimeState.delete_list_rule()`：删除过滤规则并保存配置。
12. `AdminHandler`：提供前端页面和管理 API。

## 项目边界

```text
HTTPS MITM
数据库
多用户分组策略
```

这些内容可以写进报告展望。当前项目已经实现 HTTP 代理转发、过滤、缓存、HTTPS CONNECT、日志统计、规则增删改查和管理前端。
