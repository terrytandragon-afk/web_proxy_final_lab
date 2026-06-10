import argparse
import socket


def parse_args():
    parser = argparse.ArgumentParser(
        description="Manually prove that the proxy forwards bytes after CONNECT"
    )
    parser.add_argument("--proxy-host", default="127.0.0.1")
    parser.add_argument("--proxy-port", type=int, default=8080)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=9001)
    parser.add_argument("--message", default="hello-through-manual-tunnel")
    return parser.parse_args()


def recv_until(sock, marker):
    """读取 CONNECT 响应头，避免把后续隧道回显误当作握手内容。"""
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def main():
    args = parse_args()
    with socket.create_connection((args.proxy_host, args.proxy_port), timeout=10) as client:
        request = (
            f"CONNECT {args.target_host}:{args.target_port} HTTP/1.1\r\n"
            f"Host: {args.target_host}:{args.target_port}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        client.sendall(request)
        handshake = recv_until(client, b"\r\n\r\n")
        print(handshake.decode("iso-8859-1", errors="replace").strip())
        if b"200 Connection Established" not in handshake:
            raise SystemExit("CONNECT tunnel was not established")

        payload = args.message.encode("utf-8")
        client.sendall(payload)
        echoed = client.recv(4096)
        expected = b"echo:" + payload
        print(echoed.decode("utf-8", errors="replace"))
        if echoed != expected:
            raise SystemExit("CONNECT established, but tunneled data was not echoed correctly")

    print("manual CONNECT tunnel data forwarding passed")


if __name__ == "__main__":
    main()
