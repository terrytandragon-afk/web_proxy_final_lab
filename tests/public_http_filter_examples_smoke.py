import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src import proxy


def main():
    """Verify the public HTTP examples documented for Edge acceptance."""
    url_request = {
        "method": "GET",
        "host": "httpforever.com",
        "port": 80,
        "path": "/url-filter-demo",
        "target": "http://httpforever.com/url-filter-demo",
    }
    allowed, reason = proxy.check_access_policy(
        url_request,
        {
            "mode": "blacklist",
            "blocked_domains": [],
            "blocked_url_keywords": ["url-filter-demo"],
        },
    )
    assert allowed is False
    assert reason == "url_keyword:url-filter-demo"

    # Use a representative plain-HTTP response body from the documented
    # NeverSSL example so the content-filter behavior does not depend on
    # external network availability during automated acceptance.
    upstream_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: 61\r\n"
        b"\r\n"
        b"<html><body>NeverSSL plain HTTP acceptance page.</body></html>"
    )
    filtered, keyword = proxy.filter_response_content(
        upstream_response,
        {"blocked_content_keywords": ["NeverSSL"]},
        {
            "method": "GET",
            "host": "neverssl.com",
            "path": "/",
        },
        "127.0.0.1",
    )
    text = filtered.decode("utf-8", errors="replace")
    assert keyword == "NeverSSL"
    assert "403 Forbidden" in text
    assert "content_keyword:NeverSSL" in text
    assert "NeverSSL plain HTTP acceptance page" not in text

    # 真实网站常使用 chunked 传输，关键词即使跨越数据块也必须被识别。
    chunked_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"5\r\nNever\r\n"
        b"3\r\nSSL\r\n"
        b"0\r\n\r\n"
    )
    chunked_filtered, chunked_keyword = proxy.filter_response_content(
        chunked_response,
        {"blocked_content_keywords": ["NeverSSL"]},
        {"method": "GET", "host": "neverssl.com", "path": "/"},
        "127.0.0.1",
    )
    assert chunked_keyword == "NeverSSL"
    assert b"403 Forbidden" in chunked_filtered

    # 中文关键词按网页声明的 GB18030 字符集解码后同样能够过滤。
    chinese_body = "课程保密实验".encode("gb18030")
    chinese_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html; charset=gb18030\r\n"
        + f"Content-Length: {len(chinese_body)}\r\n".encode("ascii")
        + b"\r\n"
        + chinese_body
    )
    chinese_filtered, chinese_keyword = proxy.filter_response_content(
        chinese_response,
        {"blocked_content_keywords": ["保密"]},
        {"method": "GET", "host": "example.test", "path": "/"},
        "127.0.0.1",
    )
    assert chinese_keyword == "保密"
    assert b"403 Forbidden" in chinese_filtered
    print("public HTTP filter examples smoke test passed")


if __name__ == "__main__":
    main()
