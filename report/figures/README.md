# 期末报告截图放置说明

将实操截图保存到本目录，文件名必须与下表一致。重新运行：

```powershell
cd E:\eve_jump\web_proxy_final_lab\report
latexmk -xelatex -interaction=nonstopmode final_report.tex
```

LaTeX 会自动用截图替换报告中的占位框。

| 文件名 | 需要截取的内容 |
|---|---|
| `batch-all-passed.png` | PowerShell 完整显示 Web/代理功能 `15/15`、规则与运行模式 `7/7`、最后一行 `all test batches passed` |
| `batch-dashboard.png` | 管理首页选择“最近验收”后显示总请求、总拦截、各类统计、排行和日志 |
| `manual-domain-bing.png` | Edge 访问 `https://www.bing.com/` 后显示代理 403 页面，展开详情显示 `domain_blacklist` |
| `manual-url-httpforever.png` | Edge 访问 `http://httpforever.com/url-filter-demo` 后显示 403 页面，展开详情显示 `url_keyword:url-filter-demo` |
| `manual-content-neverssl.png` | Edge 访问 `http://neverssl.com/` 后显示正文过滤 403 页面，展开详情显示 `content_keyword:NeverSSL` |
| `manual-blocked-logs.png` | 管理前端日志详情页显示上述三类真实网站拦截记录 |
| `manual-rule-changes.png` | 规则变更详情页显示域名、URL 和正文规则的新增与删除操作 |

截图建议：

1. 保留浏览器地址栏或 PowerShell 命令与结果，使验收对象清晰。
2. 拦截页面点击“查看详细信息”，让原因和命中规则出现在截图中。
3. 截图使用 PNG，避免过度裁剪。
4. 图片不需要手动调整尺寸，LaTeX 会按页面宽高等比例缩放。
