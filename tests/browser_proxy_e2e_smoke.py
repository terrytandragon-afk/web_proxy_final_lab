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
    try:
        completed = subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--no-default-browser-check",
                "--no-first-run",
                "--disable-features=HttpsUpgrades,HttpsFirstModeV2,AutomaticHttps",
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
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        # Some Windows/CI browser installations cannot start a headless renderer.
        return None
    unavailable_markers = (
        "GPU process isn't usable",
        "Failed to create",
        "Headless mode is not supported",
    )
    if completed.returncode != 0 and any(
        marker in completed.stderr for marker in unavailable_markers
    ):
        return None
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def request_through_proxy(path):
    """Use a deterministic HTTP request when this machine cannot start headless Edge."""
    chunks = []
    with socket.create_connection((HOST, PROXY_PORT), timeout=5) as client:
        client.sendall(
            (
                f"GET http://{HOST}:{HTTP_PORT}{path} HTTP/1.1\r\n"
                f"Host: {HOST}:{HTTP_PORT}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ascii")
        )
        while True:
            data = client.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")


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
            # Separate profiles avoid a lingering Chromium profile lock between invocations.
            url_block = browse_through_proxy(
                browser,
                Path(profile_dir) / "url",
                "/game/index.html",
            )
            content_block = browse_through_proxy(
                browser,
                Path(profile_dir) / "content",
                "/content-test.html",
            )

        used_browser = url_block is not None and content_block is not None
        if not used_browser:
            # The launcher test still validates browser proxy flags. This fallback keeps
            # the batch deterministic on machines where headless Edge cannot render.
            url_block = request_through_proxy("/game/index.html")
            content_block = request_through_proxy("/content-test.html")

        assert "url_keyword:game" in url_block
        assert "content_keyword:forbidden" in content_block
        assert "403" in url_block
        assert "403" in content_block
        stats = state.snapshot()["stats"]
        assert stats["blocked_url"] >= 1
        assert stats["filtered_keyword"] >= 1
        result_kind = "browser" if used_browser else "protocol fallback"
        print(f"browser proxy e2e smoke test passed ({result_kind})")
    finally:
        demo.terminate()
        demo.wait(timeout=10)


if __name__ == "__main__":
    main()
