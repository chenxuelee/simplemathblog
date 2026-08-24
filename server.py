#!/usr/bin/env python3
"""本地预览生成的静态博客。

用法：
    python3 server.py
    python3 server.py --watch --port 8080
"""

import argparse
import functools
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HERE = Path(__file__).parent.resolve()


class NoCacheHandler(SimpleHTTPRequestHandler):
    """开发预览时禁用缓存，刷新即可看到最新生成内容。"""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {args[0]}")


def source_snapshot(paths: tuple[Path, ...]) -> dict[str, int]:
    """返回可重建输入的修改时间快照；缺失文件也会纳入状态。"""
    snapshot = {}
    for path in paths:
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            if candidate.is_file():
                try:
                    snapshot[str(candidate)] = candidate.stat().st_mtime_ns
                except FileNotFoundError:
                    pass
    return snapshot


def rebuild_site(site: Path, base_url: str = "") -> None:
    command = [sys.executable, str(HERE / "blog.py"), "--out", str(site)]
    if base_url:
        command += ["--base-url", base_url]
    subprocess.run(command, check=True)


def watch_sources(paths: tuple[Path, ...], site: Path, interval: float, base_url: str) -> None:
    """在守护线程中轮询源文件；构建失败时保留上一版 site。"""
    previous = source_snapshot(paths)
    while True:
        time.sleep(interval)
        current = source_snapshot(paths)
        if current == previous:
            continue
        previous = current
        print("♻️  检测到源文件变更，正在重建…")
        try:
            rebuild_site(site, base_url)
            print("✅ 自动重建完成；刷新浏览器即可查看。")
        except subprocess.CalledProcessError as error:
            print(f"❌ 自动重建失败（退出码 {error.returncode}）；将继续服务上一版站点。")


def main() -> None:
    parser = argparse.ArgumentParser(description="预览 Enhanced Markdown Reader 静态站点")
    parser.add_argument("--site", default=str(HERE / "site"), help="静态站点目录")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--build", action="store_true", help="启动前运行 blog.py 重建站点")
    parser.add_argument("--watch", action="store_true", help="监视文章与渲染器改动并自动重建（隐含 --build）")
    parser.add_argument("--watch-interval", type=float, default=0.75, help="轮询间隔秒数（默认 0.75）")
    parser.add_argument("--base-url", default="", help="传递给 blog.py 的生产站点根 URL")
    args = parser.parse_args()

    if args.watch_interval <= 0:
        parser.error("--watch-interval 必须大于 0")

    site = Path(args.site).expanduser().resolve()
    if args.build or args.watch:
        rebuild_site(site, args.base_url)
    if not (site / "index.html").is_file():
        parser.error(f"找不到 {site / 'index.html'}；请先运行 python3 blog.py，或传入 --build。")

    handler = functools.partial(NoCacheHandler, directory=str(site))
    with ThreadingHTTPServer((args.host, args.port), handler) as httpd:
        if args.watch:
            watched = (HERE / "content", HERE / "index.html", HERE / "renderer.js", HERE / "md2html.py", HERE / "blog.py")
            threading.Thread(target=watch_sources, args=(watched, site, args.watch_interval, args.base_url), daemon=True).start()
            print("👀 自动重建已启用：监视 content/、index.html、renderer.js、md2html.py、blog.py。")
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
