import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


HOST = "127.0.0.1"
PROXY_PORT = 18300
HTTP_PORT = 19300
ECHO_PORT = 19301


def wait_for_port(port):
    """等待手动演示目标启动，避免测试因进程刚创建尚未监听而偶发失败。"""
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"port did not open: {port}")


def curl_through_proxy(curl, path):
    """使用与手动文档相同的 --noproxy 参数，强制本机目标经过代理。"""
    completed = subprocess.run(
        [
            curl,
            "-s",
            "-i",
            "--noproxy",
            "no-host-bypass.invalid",
            "-x",
            f"http://{HOST}:{PROXY_PORT}",
            f"http://{HOST}:{HTTP_PORT}{path}",
        ],
        cwd=str(PROJECT_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def main():
    curl = shutil.which("curl.exe") or shutil.which("curl")
    assert curl, "curl command is required for the manual acceptance workflow smoke test"

    demo = subprocess.Popen(
        [
            sys.executable,
            str(PROJECT_ROOT / "tests" / "manual_demo_server.py"),
            "--http-port",
            str(HTTP_PORT),
            "--echo-port",
            str(ECHO_PORT),
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port(HTTP_PORT)
        wait_for_port(ECHO_PORT)

        config = {
            "mode": "blacklist",
            "blocked_domains": [],
            "blocked_url_keywords": ["game"],
            "blocked_content_keywords": ["forbidden"],
            "cache_enabled": True,
            "cache_ttl_seconds": 60,
            "cache_max_items": 10,
            "rate_limit_enabled": False,
            "timeout_seconds": 5,
        }
        state = proxy.RuntimeState(config)
        proxy_thread = threading.Thread(
            target=proxy.start_server,
            args=(HOST, PROXY_PORT, state),
            daemon=True,
        )
        proxy_thread.start()
        wait_for_port(PROXY_PORT)

        url_block = curl_through_proxy(curl, "/game/index.html")
        assert "403 Forbidden" in url_block and "url_keyword:game" in url_block

        content_block = curl_through_proxy(curl, "/content-test.html")
        assert "blocked by keyword filter: forbidden" in content_block

        state.clear_cache()
        first_cache = curl_through_proxy(curl, "/cache.txt")
        second_cache = curl_through_proxy(curl, "/cache.txt")
        assert "upstream-hit=1" in first_cache
        assert "upstream-hit=1" in second_cache
        assert state.snapshot()["stats"]["cache_hits"] == 1

        tunnel = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "tests" / "manual_connect_tunnel.py"),
                "--proxy-port",
                str(PROXY_PORT),
                "--target-port",
                str(ECHO_PORT),
            ],
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert tunnel.returncode == 0, tunnel.stdout + tunnel.stderr
        assert "manual CONNECT tunnel data forwarding passed" in tunnel.stdout

        state.update_settings(
            {
                "cache_enabled": False,
                "rate_limit_enabled": True,
                "rate_limit_per_minute": 1,
                "rate_limit_window_seconds": 60,
            }
        )
        state.clear_rate_limits()
        first_rate = curl_through_proxy(curl, "/rate-limit.txt")
        second_rate = curl_through_proxy(curl, "/rate-limit.txt")
        assert "200 OK" in first_rate
        assert "429 Too Many Requests" in second_rate

        print("manual acceptance workflow smoke test passed")
    finally:
        demo.terminate()
        demo.wait(timeout=10)


if __name__ == "__main__":
    main()
