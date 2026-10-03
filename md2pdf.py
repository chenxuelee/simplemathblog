#!/usr/bin/env python3
"""Export enhanced Markdown to PDF using the shared renderer and Chromium.

    uv sync --extra pdf
    uv run --extra pdf python -m playwright install chromium --only-shell
    uv run --extra pdf python md2pdf.py content/fourier-series.md -o notes.pdf
"""

import argparse
import math
import mimetypes
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from md2html import DEFAULT_RENDERER, convert as convert_html

PAPER_SIZES = {"A4": (210, 297), "A5": (148, 210), "Letter": (215.9, 279.4)}
ORIGIN = "http://md2pdf.local"

PRINT_CSS = """
@media print {
  html, body { background: white !important; color: #202124 !important; }
  body { font-family: 'Noto Serif CJK SC', 'Source Han Serif SC', 'Songti SC',
    'SimSun', 'Noto Serif', 'DejaVu Serif', serif; }
  #layout, #main { display: block; min-height: 0; width: 100%; }
  #container { max-width: none; margin: 0; padding: 0; font-size: 11pt;
    line-height: 1.65; overflow-wrap: anywhere; }
  #sidebar, .copy-button, .image-lightbox { display: none !important; }
  h1, h2, h3, h4, .thm-head { break-after: avoid; }
  h1 { font-size: 21pt; } h2 { font-size: 16pt; } h3 { font-size: 13pt; }
  p { orphans: 3; widows: 3; }
  .thm-env { break-inside: auto; box-decoration-break: clone; }
  .katex-display { overflow: visible !important; break-inside: avoid; }
  .katex-display > .katex { white-space: nowrap; }
  pre, pre code { white-space: pre-wrap !important; overflow-wrap: anywhere;
    overflow: visible !important; }
  pre code { background: #f5f6f8 !important; color: #202124 !important;
    font-size: 9pt; padding: 10px; }
  pre code span { color: inherit !important; }
  table { table-layout: fixed; font-size: 10pt; }
  thead { display: table-header-group; }
  tr, figure, .fm-card { break-inside: avoid; }
  th, td { padding: 6px 8px; }
  figure { margin: 1.2em 0; }
  img, .illustration img, .cover { width: auto; max-width: 100%;
    object-fit: contain; }
  .bibliography { margin-top: 2em; }
  .bibliography ol { list-style: none; padding-left: 0; }
  a { color: #303f77; text-decoration: none; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""


def validate_options(source: Path, output: Path, paper: str, margin_mm: float,
                     timeout: float) -> None:
    """Validate before launching a browser or touching the destination."""
    if not source.is_file():
        raise ValueError(f"找不到输入文件：{source}")
    if source.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError("输入应为 .md、.markdown 或 .txt 文件")
    if source == output or output.suffix.lower() != ".pdf":
        raise ValueError("输出须使用 .pdf 后缀，且不能覆盖输入文件")
    if output.exists() and not output.is_file():
        raise ValueError(f"输出路径不是文件：{output}")
    if paper not in PAPER_SIZES:
        raise ValueError(f"不支持的纸张：{paper}")
    if not math.isfinite(margin_mm) or not 0 <= margin_mm < min(PAPER_SIZES[paper]) / 2 - 10:
        raise ValueError("页边距必须为非负有限数，且纸张需保留至少 20 mm 内容宽度")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("超时必须为正的有限秒数")


def local_resource(url: str, source_dir: Path, html_dir: Path) -> Path | None:
    """Resolve local resource requests without exposing sibling directories."""
    parsed = urlsplit(url)
    if f"{parsed.scheme}://{parsed.netloc}" != ORIGIN:
        return None
    relative = unquote(parsed.path).lstrip("/")
    root = html_dir if relative == "document.html" or relative.startswith("assets/vendor/") else source_dir
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        raise ValueError(f"找不到本地资源或资源超出 Markdown 所在目录：{relative}")
    return candidate


def convert(source: Path, output: Path | None = None, *, paper: str = "A4",
            margin_mm: float = 18, landscape: bool = False, timeout: float = 30,
            browser: str | None = None, strict: bool = False) -> Path:
    """Render UTF-8 Markdown; replace an existing PDF only after successful export.

    Local images resolve relative to the Markdown file. Chromium and a Chinese
    system font are needed for Chinese documents. No web server is opened.
    """
    source = Path(source).expanduser().resolve()
    output = Path(output).expanduser().resolve() if output else source.with_suffix(".pdf")
    validate_options(source, output, paper, margin_mm, timeout)
    try:
        from playwright.sync_api import Error as BrowserError, sync_playwright
    except ImportError as error:
        raise RuntimeError("请先安装 PDF 依赖：uv sync --extra pdf") from error

    with tempfile.TemporaryDirectory(prefix="md2pdf-") as scratch:
        html_dir = Path(scratch)
        convert_html(source, html_dir / "document.html", DEFAULT_RENDERER)
        failures: list[str] = []
        with sync_playwright() as playwright:
            try:
                chromium = playwright.chromium.launch(
                    headless=True,
                    executable_path=browser or os.environ.get("CHROMIUM_EXECUTABLE_PATH") or None,
                    timeout=timeout * 1000)
            except BrowserError as error:
                raise RuntimeError("无法启动 Chromium。请运行：uv run --extra pdf python -m "
                                   "playwright install chromium --only-shell；或用 --browser / "
                                   "CHROMIUM_EXECUTABLE_PATH 指定 Chrome 可执行文件。"
                                   f"\n{error}") from error
            try:
                page = chromium.new_page(viewport={"width": 1000, "height": 800},
                                         color_scheme="light", device_scale_factor=1)
                page.set_default_timeout(timeout * 1000)
                page.on("pageerror", lambda error: failures.append(str(error)))

                def serve(route):
                    try:
                        asset = local_resource(route.request.url, source.parent, html_dir)
                        if asset is None:
                            route.continue_()
                        else:
                            content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                            route.fulfill(path=str(asset), content_type=content_type)
                    except (ValueError, OSError) as error:
                        failures.append(str(error))
                        route.abort()

                page.route("**/*", serve)
                page.goto(f"{ORIGIN}/document.html", wait_until="load")
                if failures:
                    raise RuntimeError("页面渲染失败：\n" + "\n".join(failures))
                page.emulate_media(media="print", color_scheme="light")
                page.add_style_tag(content=PRINT_CSS)
                width, height = PAPER_SIZES[paper]
                if landscape:
                    width, height = height, width
                content_width = (width - 2 * margin_mm) * 96 / 25.4
                page.add_style_tag(content=f"#container {{ width: {content_width}px; }} "
                                   f"img {{ max-height: {height - 2 * margin_mm - 20}mm; }}")
                # Lazy images below the initial viewport must be loaded before printing.
                page.eval_on_selector_all("img", "images => images.forEach(img => img.loading = 'eager')")
                page.wait_for_function("Array.from(document.images).every(img => img.complete)")
                broken = page.eval_on_selector_all("img", "images => images.filter(img => !img.naturalWidth).map(img => img.getAttribute('src'))")
                if broken or failures:
                    raise RuntimeError("图片或资源加载失败：\n" + "\n".join(broken + failures))
                page.wait_for_function("document.fonts.status === 'loaded'")
                # A complete font face may still have failed; do not silently print broken math.
                bad_fonts = page.evaluate("Array.from(document.fonts).filter(font => font.status === 'error').map(font => font.family)")
                if bad_fonts:
                    raise RuntimeError("字体加载失败：" + ", ".join(bad_fonts))
                diagnostics = page.evaluate("renderDiagnostics")
                if diagnostics:
                    message = "数学渲染提示：\n" + "\n".join(diagnostics)
                    if strict:
                        raise RuntimeError(message)
                    print(message, file=sys.stderr)
                # Fit wide display equations to the printable column, not the screen viewport.
                page.eval_on_selector_all(".katex-display", """blocks => blocks.forEach(block => {
                  const math = block.querySelector('.katex');
                  if (math && math.scrollWidth > block.clientWidth) {
                    const size = parseFloat(getComputedStyle(math).fontSize);
                    math.style.fontSize = `${size * block.clientWidth / math.scrollWidth}px`;
                  }
                })""")
                page.eval_on_selector_all("a[href]", """(links, base) => links.forEach(link => {
                  const href = link.getAttribute('href');
                  if (href && !href.startsWith('#') && new URL(href, location.href).origin === location.origin)
                    link.href = new URL(href, base).href;
                })""", source.parent.as_uri() + "/")
                data = page.pdf(format=paper, landscape=landscape,
                                margin={side: f"{margin_mm}mm" for side in ("top", "right", "bottom", "left")},
                                print_background=True, tagged=True, outline=True,
                                display_header_footer=margin_mm >= 10,
                                header_template="<span></span>",
                                footer_template='<div style="width:100%;text-align:center;font-size:9px;color:#777">'
                                                '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            except BrowserError as error:
                raise RuntimeError(f"浏览器导出失败（可用 --timeout 增加等待时间）：{error}") from error
            finally:
                chromium.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        # Same-directory staging makes replacement atomic, including on Windows.
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".pdf", delete=False) as staged:
            temporary = Path(staged.name)
        try:
            temporary.write_bytes(data)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="增强 Markdown → PDF（公式、定理、文献、中文和图片）")
    parser.add_argument("input", type=Path, help="UTF-8 Markdown 文件")
    parser.add_argument("-o", "--output", type=Path, help="输出 PDF，默认与源文件同名")
    parser.add_argument("--paper", choices=PAPER_SIZES, default="A4")
    parser.add_argument("--margin", type=float, default=18, metavar="MM", help="四边页边距，默认 18 mm")
    parser.add_argument("--landscape", action="store_true", help="横向纸张")
    parser.add_argument("--timeout", type=float, default=30, metavar="SECONDS")
    parser.add_argument("--browser", help="Chrome/Chromium 路径，优先于 CHROMIUM_EXECUTABLE_PATH")
    parser.add_argument("--strict", action="store_true", help="公式、引用或文献错误时拒绝生成 PDF")
    args = parser.parse_args()
    try:
        output = convert(args.input, args.output, paper=args.paper, margin_mm=args.margin,
                         landscape=args.landscape, timeout=args.timeout,
                         browser=args.browser, strict=args.strict)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"错误：{error}\n")
    print(f"已生成：{output}（{output.stat().st_size:,} bytes）")


if __name__ == "__main__":
    main()
