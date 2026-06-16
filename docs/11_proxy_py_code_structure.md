# proxy.py 源码结构与函数功能说明

本文专门解释 `src/proxy.py` 这一个主代码文件。阅读时可以把它理解成三条线：

1. **数据状态线**：保存配置、统计、缓存、限流、规则变更。
2. **代理处理线**：接收浏览器请求，检查规则，转发到目标服务器，再返回响应。
3. **管理控制线**：给前端和命令行提供规则管理、日志查询、统计查询 API。

## 一、proxy.py 的代码分区

`proxy.py` 已按功能划分为 10 个区：

| 分区 | 位置/代表对象 | 作用 |
| --- | --- | --- |
| 1. 运行状态区 | `RuntimeState` | 保存配置、统计、缓存、限流桶、规则变更历史 |
| 2. 参数与请求解析区 | `parse_args()`、`parse_http_request()` | 解析启动参数和 HTTP/CONNECT 请求 |
| 3. 本代理生成响应区 | `send_simple_response()`、`build_policy_block_response()` | 生成错误响应、403 拦截页、407 认证挑战 |
| 4. 请求阶段访问控制区 | `check_access_policy()`、`check_proxy_auth()` | 在访问目标服务器之前判断是否拦截 |
| 5. 缓存与响应解析区 | `receive_http_response()`、`parse_status_code()` | 接收完整 HTTP 响应，判断缓存和报文边界 |
| 6. 响应阶段正文过滤区 | `filter_response_content()` | 检查 HTTP 明文网页正文关键字 |
| 7. 代理转发区 | `build_upstream_request()`、`forward_http()`、`forward_connect()` | 改写请求、HTTP 转发、HTTPS 隧道 |
| 8. 客户端连接处理区 | `handle_client()` | 单次请求的总调度入口 |
| 9. 管理后端区 | `AdminHandler` | 前端页面和后端 API |
| 10. 服务启动区 | `start_admin_server()`、`start_server()`、`main()` | 启动 8088 管理端口和 8080 代理端口 |

## 二、最核心调用链

浏览器或 curl 使用代理访问网页时，最重要的调用链如下：

```text
main()
  ├─ load_config()
  ├─ RuntimeState(config, config_path)
  ├─ start_admin_server()     # 启动 8088 管理前端/API
  └─ start_server()           # 启动 8080 代理服务
       └─ accept()
          └─ handle_client()             # 处理单个客户端连接
             ├─ parse_http_request()     # 解析 method、host、port、path
             ├─ check_client_access_policy()
             ├─ check_proxy_auth()
             ├─ RuntimeState.check_rate_limit()  # 执行访问频率控制
             ├─ check_access_policy()    # 执行域名、URL、方法、白名单策略
             ├─ RuntimeState.get_cache()
             ├─ forward_http() 或 forward_connect()
             └─ log_event()
```

其中 `handle_client()` 是代理处理的总入口，所有过滤、缓存、转发和日志记录都会经过它。

## 三、RuntimeState：运行状态与热更新

`RuntimeState` 保存代理运行时共享数据。项目使用多线程处理客户端连接，所以这些共享数据都通过 `self.lock` 保护。

关键属性：

| 属性 | 含义 |
| --- | --- |
| `config` | 当前规则和运行参数的内存副本 |
| `config_path` | JSON 配置文件路径，用于 API 修改后写回磁盘 |
| `stats` | 总请求、总拦截、缓存命中、认证失败、限流等统计 |
| `host_hits` | 目标主机访问排行 |
| `keyword_hits` | 正文关键词命中排行 |
| `cache` | HTTP GET 上游原始响应缓存 |
| `rate_limits` | 按客户端 IP 记录的限流计数桶 |
| `change_history` | 规则和运行设置变更历史 |

关键方法：

| 方法 | 用途 |
| --- | --- |
| `add_list_rule()` | 新增规则，例如新增一个域名黑名单 |
| `delete_list_rule()` | 删除规则 |
| `update_list_rule()` | 修改单条规则 |
| `replace_list_rules()` | 替换整个规则组 |
| `update_settings()` | 修改缓存、认证、限流、黑/白名单模式等运行设置 |
| `get_cache()` / `set_cache()` | 读取和写入 HTTP GET 缓存 |
| `check_rate_limit()` | 判断某客户端 IP 是否超过访问频率限制 |
| `snapshot()` | 给首页返回实时统计 |

## 四、请求解析：parse_http_request()

`parse_http_request()` 把客户端请求解析成统一字典，后续过滤和转发都读这个字典。

它兼容三类请求：

```text
GET http://example.com/index.html HTTP/1.1   # 浏览器发给正向代理的 HTTP 请求
CONNECT www.example.com:443 HTTP/1.1         # HTTPS 隧道请求
GET /index.html HTTP/1.1                     # 本地测试时的普通源服务器格式请求
```

返回字段：

| 字段 | 含义 |
| --- | --- |
| `method` | HTTP 方法，如 GET、POST、CONNECT |
| `target` | 请求行中的原始目标 |
| `version` | HTTP 版本 |
| `host` | 目标主机 |
| `port` | 目标端口，HTTP 默认 80，CONNECT 默认 443 |
| `path` | 请求路径和查询参数 |
| `host_header` | 原始 Host 头 |
| `headers` | 小写化后的请求头字典 |

## 五、请求阶段过滤：访问目标服务器之前就能判断的规则

请求阶段过滤由以下函数完成：

| 函数 | 功能 |
| --- | --- |
| `client_ip_matches()` | 判断客户端 IP 是否命中 IP/CIDR 规则 |
| `check_client_access_policy()` | 执行客户端 IP 黑白名单 |
| `domain_matches()` | 判断目标域名是否命中完整域名、父域名或通配符 |
| `check_access_policy()` | 执行 HTTP 方法、域名黑白名单、URL 关键字过滤 |
| `check_proxy_auth()` | 检查 Proxy-Authorization 代理认证头 |

请求阶段能处理：

```text
客户端 IP 黑/白名单
代理认证
访问频率限制
HTTP 方法限制
域名黑名单
域名白名单
URL 关键字
```

请求阶段不能处理网页正文，因为正文还没有从目标服务器返回。

## 六、普通 HTTP 转发：forward_http()

明文 HTTP 请求走 `forward_http()`：

```text
forward_http()
  ├─ build_upstream_request()      # 把代理格式请求改写成普通 HTTP 请求
  ├─ socket.create_connection()    # 连接目标服务器
  ├─ upstream_socket.sendall()     # 发送改写后的请求
  ├─ receive_http_response()       # 接收完整响应
  ├─ filter_response_content()     # 正文关键词过滤
  └─ client_socket.sendall()       # 把原响应或拦截页返回给客户端
```

`build_upstream_request()` 的作用很重要。浏览器给代理的请求行通常是：

```text
GET http://example.com/index.html HTTP/1.1
```

目标 Web 服务器需要的是：

```text
GET /index.html HTTP/1.1
Host: example.com
```

所以代理必须改写请求行，并去掉 `Proxy-Authorization`、`Proxy-Connection` 等代理专用头。

## 七、正文关键词过滤：filter_response_content()

正文过滤发生在响应阶段，也就是代理已经拿到目标服务器返回的 HTTP 响应之后。

处理流程：

```text
filter_response_content()
  ├─ 拆分响应头和响应体
  ├─ 判断 Content-Type 是否为文本类
  ├─ 如果是 chunked，先 decode_chunked_body()
  ├─ 如果是 gzip/deflate，先解压
  ├─ decode_text_body() 转成字符串
  ├─ 遍历 blocked_content_keywords
  └─ 命中后 build_policy_block_response() 生成 403 页面
```

注意：HTTPS 正文是 TLS 加密的，本项目没有做中间人证书解密，所以正文关键词过滤只适用于明文 HTTP。

## 八、HTTPS CONNECT 隧道：forward_connect()

HTTPS 请求不会走普通 HTTP 转发，而是走 CONNECT 隧道：

```text
CONNECT www.example.com:443 HTTP/1.1
```

`forward_connect()` 的处理过程：

```text
连接目标服务器 443 端口
  ↓
向浏览器返回 200 Connection Established
  ↓
浏览器和目标服务器开始 TLS 握手
  ↓
代理只用 select() 在两个 socket 之间搬运加密字节
```

因此，HTTPS 模块能实现：

```text
建立隧道
统计 CONNECT
按 CONNECT 目标域名拦截
记录隧道日志
```

但不能实现：

```text
检查 HTTPS URL 路径
检查 HTTPS 网页正文关键词
读取 HTTPS 页面内容
```

## 九、handle_client()：单次请求总调度

`handle_client()` 是最值得先读的函数。它把所有模块串起来：

```text
1. recv() 读取客户端请求
2. parse_http_request() 解析请求
3. check_client_access_policy() 检查客户端 IP
4. check_proxy_auth() 检查代理认证
5. check_rate_limit() 检查访问频率
6. check_access_policy() 检查方法/域名/URL
7. get_cache() 尝试缓存命中
8. forward_connect() 或 forward_http()
9. set_cache() 写入缓存
10. log_event() 写运行日志和拦截日志
```

如果你要向老师说明“代理服务器怎么工作”，可以围绕这个函数讲。

### 9.1 典型拦截代码怎么读

以客户端 IP 策略为例：

```python
client_allowed, client_reason = check_client_access_policy(client_address[0], config)
if not client_allowed:
    update_block_stats(state, client_reason)
    bytes_sent = send_policy_block_response(
        client_socket,
        client_reason,
        request_info,
        client_address[0],
    )
    state.increment("bytes_to_clients", bytes_sent)
    log_event(...)
    return
```

这段代码可以拆成下面几步理解：

| 代码 | 传入什么 | 得到什么 | 作用 |
| --- | --- | --- | --- |
| `client_address[0]` | 客户端地址元组 | 客户端 IP 字符串 | 例如 `127.0.0.1` |
| `check_client_access_policy(client_address[0], config)` | 客户端 IP、当前配置 | `(是否允许, 原因)` | 判断客户端是否能使用代理 |
| `if not client_allowed` | 上一步的布尔结果 | 分支判断 | 不允许时进入拦截流程 |
| `update_block_stats(state, client_reason)` | 运行状态、拦截原因 | 无返回值 | 增加首页对应拦截计数 |
| `send_policy_block_response(...)` | 客户端 socket、原因、请求信息、客户端 IP | 已发送字节数 | 向浏览器返回代理生成的 403 页面 |
| `state.increment("bytes_to_clients", bytes_sent)` | 统计字段、字节数 | 无返回值 | 统计代理发给客户端的数据量 |
| `log_event(...)` | 状态、事件类型、日志文本 | 无返回值 | 写入访问日志和拦截日志 |
| `return` | 无 | 结束函数 | 已经拦截，不再继续访问目标服务器 |

认证、限流、域名拦截、URL 拦截的代码结构也类似：先调用一个检查函数，拿到“是否允许”和“原因”，如果不允许就更新统计、返回响应、写日志、结束本次请求。

## 十、管理后端：AdminHandler

`AdminHandler` 运行在 8088 端口，既提供前端 HTML，也提供 API。

常用 GET API：

| API | 用途 |
| --- | --- |
| `/` 或 `/index.html` | 管理首页 |
| `/logs.html` | 日志详情页 |
| `/changes.html` | 规则变更详情页 |
| `/api/config` | 当前配置 |
| `/api/rules` | 当前规则组 |
| `/api/stats` | 实时统计 |
| `/api/logs/query` | 查询结构化日志 |
| `/api/logs/export.csv` | 导出日志 CSV |

常用 POST API：

| API | 用途 |
| --- | --- |
| `/api/rules/add` | 新增规则 |
| `/api/rules/delete` | 删除规则 |
| `/api/rules/update` | 修改规则 |
| `/api/rules/replace` | 替换整个规则组 |
| `/api/settings/update` | 修改缓存、认证、限流等设置 |
| `/api/cache/clear` | 清空缓存 |
| `/api/rate/reset` | 清空限流计数 |
| `/api/stats/reset` | 重置首页统计 |
| `/api/logs/clear` | 清空运行日志 |

前端和 `tools/rule_cli.py` 都调用这些 API，所以它们修改的是同一套运行状态和配置文件。

## 十一、建议阅读顺序

如果你是第一次读代码，建议按下面顺序：

1. `main()`：看启动流程。
2. `start_server()`：看代理端口如何监听。
3. `handle_client()`：看单次请求如何处理。
4. `parse_http_request()`：看请求如何变成结构化字段。
5. `check_access_policy()`：看请求阶段怎么拦截。
6. `forward_http()`：看普通 HTTP 怎么转发。
7. `filter_response_content()`：看正文关键词怎么过滤。
8. `forward_connect()`：看 HTTPS 隧道怎么转发。
9. `RuntimeState`：看规则热更新、统计、缓存和限流怎么保存。
10. `AdminHandler`：看前端和命令行怎么控制代理。
