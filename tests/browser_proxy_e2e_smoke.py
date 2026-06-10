import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18310
HTTP_PORT = 19310


def wait_for_port(port):
    """Wait until a local test service is accepting connections."""
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"port did not open: {port}")


def find_chromium_browser():
    """Find Edge or Chrome using the same locations as the PowerShell launcher."""
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe",
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    return next((path for path in candidates if path.exists()), None)


def browse_through_proxy(browser, profile_dir, path):
    """Use a real headless Chromium process and force loopback through the proxy."""
    completed = subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--no-default-browser-check",
            "--no-first-run",
            f"--user-data-dir={profile_dir}",
            f"--proxy-server=http://{HOST}:{PROXY_PORT}",
            "--proxy-bypass-list=<-loopback>",
            "--dump-dom",
            f"http://{HOST}:{HTTP_PORT}{path}",
        ],
        cwd=str(PROJECT_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0 and "GPU process isn't usable" in completed.stderr:
        return None
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def main():
    """Verify URL and body filtering through an actual Edge/Chrome browser process."""
    browser = find_chromium_browser()
    if browser is None:
        print("browser proxy e2e smoke test skipped: Edge/Chrome not found")
        return

    demo = subprocess.Popen(
        [
            sys.executable,
            str(PROJECT_ROOT / "tests" / "manual_demo_server.py"),
            "--http-port",
            str(HTTP_PORT),
            "--echo-port",
            "19311",
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port(HTTP_PORT)
        state = proxy.RuntimeState(
            {
                "mode": "blacklist",
                "blocked_domains": [],
                "blocked_url_keywords": ["game"],
                "blocked_content_keywords": ["forbidden"],
                "cache_enabled": False,
                "rate_limit_enabled": False,
                "timeout_seconds": 5,
            }
        )
        threading.Thread(
            target=proxy.start_server,
            args=(HOST, PROXY_PORT, state),
            daemon=True,
        ).start()
        wait_for_port(PROXY_PORT)

        with tempfile.TemporaryDirectory(prefix="web-proxy-browser-") as profile_dir:
            url_block = browse_through_proxy(browser, profile_dir, "/game/index.html")
            content_block = browse_through_proxy(browser, profile_dir, "/content-test.html")

        if url_block is None or content_block is None:
            print("browser proxy e2e smoke test skipped: browser GPU unavailable")
            return

        assert "url_keyword:game" in url_block
        assert "content_keyword:forbidden" in content_block
        assert "403" in url_block
        assert "403" in content_block
        stats = state.snapshot()["stats"]
        assert stats["blocked_url"] >= 1
        assert stats["filtered_content"] >= 1
        print("browser proxy e2e smoke test passed")
    finally:
        demo.terminate()
        demo.wait(timeout=10)


if __name__ == "__main__":
    main()
