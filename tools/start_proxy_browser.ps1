param(
    [string]$StartUrl = "http://127.0.0.1:9000/",
    [string]$ProxyServer = "http://127.0.0.1:8080"
)

# Chrome/Edge normally bypass localhost even when a system proxy is configured.
# This isolated browser profile disables that implicit loopback bypass for lab verification.
$projectRoot = Split-Path -Parent $PSScriptRoot
$profileDir = Join-Path $projectRoot ".manual-browser-profile"
$candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe")
)
$browser = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $browser) {
    throw "未找到 Microsoft Edge 或 Google Chrome。请手动启动浏览器并取消本地地址代理绕过。"
}

$arguments = @(
    "--user-data-dir=$profileDir",
    "--proxy-server=$ProxyServer",
    "--proxy-bypass-list=<-loopback>",
    "--no-first-run",
    "--new-window",
    $StartUrl
)

Write-Host "Browser: $browser"
Write-Host "Proxy: $ProxyServer"
Write-Host "Opening: $StartUrl"
Start-Process -FilePath $browser -ArgumentList $arguments
