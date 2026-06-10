from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "tools" / "start_proxy_browser.ps1"


def main():
    """验证浏览器验收启动器会强制 Chromium 的本机地址经过代理。"""
    script = LAUNCHER.read_text(encoding="utf-8")
    assert "--proxy-server=$ProxyServer" in script
    assert "--proxy-bypass-list=<-loopback>" in script
    assert "--user-data-dir=$profileDir" in script
    assert "127.0.0.1:9000" in script
    assert "127.0.0.1:8080" in script
    print("browser proxy launcher smoke test passed")


if __name__ == "__main__":
    main()
