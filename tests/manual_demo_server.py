import argparse
import socket
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PATH_HITS = Counter()


class ManualDemoHandler(BaseHTTPRequestHandler):
    """提供互不干扰的手动验收页面，并在响应头中显示上游命中次数。"""

    ROUTES = {
        "/": ("text/html; charset=utf-8", "<h1>Manual proxy demo home</h1>"),
        "/content-test.html": (
            "text/html; charset=utf-8",
            "<h1>Content filter demo</h1><p>This body contains forbidden text.</p>",
        ),
        "/game/index.html": (
            "text/html; charset=utf-8",
            "<h1>URL keyword demo page</h1>",
        ),
        "/cache.txt": ("text/plain; charset=utf-8", "cache demo"),
        "/rate-limit.txt": ("text/plain; charset=utf-8", "rate limit demo"),
    }

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route not in self.ROUTES:
            self.send_error(404, "manual demo route not found")
            return

        PATH_HITS[route] += 1
        content_type, text = self.ROUTES[route]
        hit = PATH_HITS[route]
        body = f"{text}\nupstream-hit={hit}\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Upstream-Hit", str(hit))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # 保留一行简洁上游记录，方便观察缓存命中时是否再次访问测试站。
        print(f"[manual-http] {self.address_string()} {format % args}", flush=True)


def echo_server(host, port):
    """提供本地 TCP 回显目标，用于证明 CONNECT 建立后仍能双向转发数据。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(20)
    while True:
        connection, address = server.accept()
        threading.Thread(
            target=handle_echo_client,
            args=(connection, address),
            daemon=True,
        ).start()


def handle_echo_client(connection, address):
    """回显一个连接收到的数据；每次隧道验收使用一个新连接。"""
    with connection:
        data = connection.recv(4096)
        connection.sendall(b"echo:" + data)
    print(f"[manual-echo] {address[0]}:{address[1]} bytes={len(data)}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Start deterministic manual acceptance targets")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=9000)
    parser.add_argument("--echo-port", type=int, default=9001)
    return parser.parse_args()


def main():
    args = parse_args()
    echo_thread = threading.Thread(
        target=echo_server,
        args=(args.host, args.echo_port),
        daemon=True,
    )
    echo_thread.start()

    http_server = ThreadingHTTPServer((args.host, args.http_port), ManualDemoHandler)
    print(f"Manual HTTP demo: http://{args.host}:{args.http_port}/", flush=True)
    print(f"Manual CONNECT echo target: {args.host}:{args.echo_port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()


if __name__ == "__main__":
    main()
