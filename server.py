#!/usr/bin/env python3
"""本地预览生成的静态博客。

用法：
    python3 server.py
    python3 server.py --build --port 8080
"""

import argparse
import functools
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HERE = Path(__file__).parent.resolve()


class NoCacheHandler(SimpleHTTPRequestHandler):
    """开发预览时禁用缓存，刷新即可看到最新生成内容。"""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="预览 Enhanced Markdown Reader 静态站点")
    parser.add_argument("--site", default=str(HERE / "site"), help="静态站点目录")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--build", action="store_true", help="启动前运行 blog.py 重建站点")
    args = parser.parse_args()

    site = Path(args.site).expanduser().resolve()
    if args.build:
        command = [sys.executable, str(HERE / "blog.py"), "--out", str(site)]
        subprocess.run(command, check=True)
    if not (site / "index.html").is_file():
        parser.error(f"找不到 {site / 'index.html'}；请先运行 python3 blog.py，或传入 --build。")

    handler = functools.partial(NoCacheHandler, directory=str(site))
    with ThreadingHTTPServer((args.host, args.port), handler) as httpd:
        print(f"✅ 正在服务 {site}")
        print(f"   打开 http://{args.host}:{args.port}/ ；按 Ctrl-C 停止。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
        finally:
            httpd.server_close()


if __name__ == "__main__":
    main()
