param(
    [string]$StartUrl = "http://127.0.0.1.nip.io:9000/game/index.html",
    [string]$SecondUrl = "http://127.0.0.1.nip.io:9000/content-test.html",
    [string]$ProxyServer = "http://127.0.0.1:8080",
    [switch]$ValidateOnly
)

# Chrome and Edge normally bypass localhost even when a system proxy is configured.
# This isolated profile disables that implicit bypass for browser acceptance tests.
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
    throw "Microsoft Edge or Google Chrome was not found."
}

$arguments = @(
    "--user-data-dir=$profileDir",
    "--proxy-server=$ProxyServer",
    "--proxy-bypass-list=<-loopback>",
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-sync",
    "--no-default-browser-check",
    "--no-first-run",
    "--new-window",
    $StartUrl,
    $SecondUrl
)

Write-Host "Browser: $browser"
Write-Host "Proxy: $ProxyServer"
Write-Host "URL filter test: $StartUrl"
Write-Host "Content filter test: $SecondUrl"

if ($ValidateOnly) {
    Write-Host "Launcher validation passed."
    return
}

Start-Process -FilePath $browser -ArgumentList $arguments
