# 期末报告截图放置说明

将实操截图保存到本目录，文件名必须与下表一致。重新运行：

```powershell
cd E:\eve_jump\web_proxy_final_lab\report
latexmk -xelatex -interaction=nonstopmode final_report.tex
```

LaTeX 会自动用截图替换报告中的占位框。

| 文件名 | 需要截取的内容 |
|---|---|
| `batch-web.png` | PowerShell 显示 Web/代理功能批量测试 `15/15` |
| `batch_rules.png` | PowerShell 显示规则与运行模式批量测试 `7/7` |
| `batch-dashboard-web.png` | 管理首页选择“最近验收”后显示总请求、总拦截和各类 Web 统计 |
| `batch-dashboard-rules.png` | 规则变更总览选择“批量验收”，显示操作汇总、规则组汇总和详情 |
| `manual-domain-bing-normal.png` | 未设置 Bing 域名规则时，Edge 通过代理正常访问 Bing |
| `manual-domain-bing.png` | 添加 `*.bing.com` 后，Edge 显示 `ERR_TUNNEL_CONNECTION_FAILED` |
| `manual-domain-bing-log.png` | 当前运行拦截日志显示 `host=www.bing.com` 和 `reason=domain_blacklist` |
| `manual-url-httpforever.png` | Edge 访问 `http://httpforever.com/url-filter-demo` 后显示 403 页面，展开详情显示 `url_keyword:url-filter-demo` |
| `manual-content-neverssl.png` | Edge 访问 `http://neverssl.com/?proxy-lab=content-check` 后显示正文过滤 403 页面和 `content_keyword:NeverSSL` |
| `manual-cache-log.png` | 当前运行访问日志中，同一地址依次出现 `CACHE_MISS`、`ALLOW`、`CACHE_HIT` |
| `manual-auth.png` | 当前运行日志显示错误或缺失凭据产生 `AUTH_REQUIRED`，随后出现正常 CONNECT |
| `rate-limit.png` | 浏览器在代理限流开启后出现访问失败 |
| `rate-limit-log.png` | 当前运行日志显示 `RATE_LIMIT`、`count`、`limit` 和 `retry_after` |
| `manual-blocked-logs.png` | 当前运行日志详情页显示域名、URL、正文、认证或限流记录 |
| `manual-rule-changes.png` | 规则变更总览选择“当前运行”，显示手工规则和运行设置修改 |

截图建议：

1. 保留浏览器地址栏或 PowerShell 命令与结果，使验收对象清晰。
2. HTTP URL 与正文拦截页面点击“查看详细信息”，让原因和命中规则出现在截图中。
3. HTTPS 域名拦截截图显示隧道失败属于正常现象，具体原因需要同时截取拦截日志。
4. 截图使用 PNG，避免过度裁剪。
5. 图片不需要手动调整尺寸，LaTeX 会按页面宽高等比例缩放。
