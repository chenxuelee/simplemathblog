#!/usr/bin/env python3
"""
enhanced-md2html.py —— 把增强 Markdown（数学环境 / AMSL 定理环境 / 交叉引用 /
YAML Front Matter）转换为单个独立 HTML 文件，目录渲染在左侧边栏。

用法:
    python3 md2html.py input.md [-o output.html] [--renderer path/to/renderer.js]

原理:
    复用阅读器 index.html 中经过验证的 JS 渲染管线（占位符隔离 → marked → KaTeX
    → 定理回填 → 引用回填），将 Markdown 源码以 JSON 字符串嵌入模板，
    由浏览器端完成全部渲染。因此导出文件与阅读器预览 100% 一致。

    输出为单文件：仅 KaTeX/marked/highlight.js 走 CDN（离线可用 --offline-fonts
    说明见文末注释），文档内容与全部逻辑内联。
"""

import argparse
import html as html_mod
import json
import re
import sys
from datetime import date
from pathlib import Path

DEFAULT_RENDERER = Path(__file__).with_name("renderer.js")

# ---------------------------------------------------------------- reader 管线提取

def extract_pipeline_js(renderer_path: Path = DEFAULT_RENDERER) -> str:
    """读取唯一的共享渲染管线；导出页会将其内联以保持单文件特性。"""
    if not renderer_path.is_file():
        sys.exit(f"错误：找不到渲染器 {renderer_path}")
    return renderer_path.read_text(encoding="utf-8").strip()


def json_for_script(value: str) -> str:
    """安全嵌入普通 script：防止 Markdown 中的 </script> 结束脚本。"""
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))

# ---------------------------------------------------------------- 导出模板

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css">
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<style>
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #6b7280;
  --accent: #4f46e5; --border: #e5e7eb; --card: #f9fafb;
  --sidebar-w: 280px;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #111318; --fg: #e5e7eb; --muted: #9ca3af;
          --accent: #818cf8; --border: #2d3139; --card: #1a1d24; }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif; }

/* ---- 布局：左侧固定目录栏 + 右侧内容 ---- */
#layout { display: flex; min-height: 100vh; }
#sidebar {
  width: var(--sidebar-w); flex: none; position: sticky; top: 0;
  height: 100vh; overflow-y: auto; padding: 24px 18px 60px;
  background: var(--card); border-right: 1px solid var(--border);
}
#sidebar .sb-title { font-weight: 700; font-size: 15px; margin-bottom: 4px;
  word-break: break-all; }
#sidebar .sb-sub { color: var(--muted); font-size: 12px; margin-bottom: 14px; }
#sidebar nav a { display: block; padding: 3px 8px; border-radius: 6px;
  color: var(--fg); text-decoration: none; font-size: 13px; line-height: 1.5; }
#sidebar nav a:hover { background: var(--bg); color: var(--accent); }
#sidebar nav a.lv3 { margin-left: 1.2em; color: var(--muted); font-size: 12.5px; }
#main { flex: 1; min-width: 0; }
#container { max-width: 880px; margin: 0 auto; padding: 40px 36px 140px;
  line-height: 1.75; font-size: 16px; }

/* ---- 窄屏折叠侧栏 ---- */
@media (max-width: 900px) {
  #layout { display: block; }
  #sidebar { position: static; width: auto; height: auto; max-height: 40vh;
    border-right: none; border-bottom: 1px solid var(--border); }
}

/* ---- Markdown 元素 ---- */
h1,h2,h3,h4 { line-height: 1.35; margin-top: 1.6em; }
h1 { font-size: 2em; border-bottom: 2px solid var(--border); padding-bottom: .3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: .25em; }
a { color: var(--accent); }
blockquote { border-left: 4px solid var(--accent); margin: 1em 0; padding: .4em 1em;
  background: var(--card); border-radius: 0 8px 8px 0; }
code { background: var(--card); border: 1px solid var(--border); border-radius: 4px;
  padding: .15em .4em; font-size: .88em; }
pre code { display: block; padding: 14px; overflow-x: auto; border-radius: 10px; }
table { border-collapse: collapse; width: 100%; margin: 1.2em 0; }
th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
th { background: var(--card); }
tr:nth-child(even) td { background: var(--card); }
img { max-width: 100%; }
img.zoomable { cursor: zoom-in; }
.image-lightbox { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center;
  padding: 30px; background: rgba(0,0,0,.82); cursor: zoom-out; }
.image-lightbox img { max-width: 100%; max-height: 100%; object-fit: contain; }
hr { border: none; border-top: 1px solid var(--border); }
.katex-display { overflow-x: auto; overflow-y: hidden; padding: 4px 2px; }
.math-error { color: #ef4444; background: rgba(239,68,68,.08); border-radius: 6px;
  padding: 2px 6px; font-family: monospace; font-size: .85em; }

/* ---- 定理环境 ---- */
.thm-env { margin: 1.2em 0; padding: .8em 1.1em; border-radius: 8px;
  background: var(--card); border-left: 4px solid var(--accent); font-style: normal; }
.thm-env.proof { background: transparent; border-left-color: var(--border); }
.thm-head { font-weight: 700; font-style: normal; }
.thm-title { font-weight: 400; }
.thm-body { margin-top: .35em; }
.qed { float: right; }
a.ref-link { color: var(--accent); text-decoration: none;
  border-bottom: 1px dotted var(--accent); }

/* ---- Front Matter 卡片 ---- */
.fm-card { background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: .9em 1.2em; margin-bottom: 1.8em; font-size: .92em; }
.fm-card h1 { margin: 0 0 .3em; font-size: 1.7em; border-bottom: none; padding-bottom: 0; }
.fm-meta { display: flex; flex-wrap: wrap; gap: .35em 1.4em; color: var(--muted); }
.fm-tags { display: inline-flex; gap: .45em; flex-wrap: wrap; }
.fm-tag { background: var(--accent); color: #fff; opacity: .85;
  border-radius: 999px; padding: .05em .7em; font-size: .82em; }
.cover { width: 100%; max-height: 360px; object-fit: cover; border-radius: 10px; margin-top: 1em; }

@media print {
  #sidebar { display: none; }
  #container { max-width: none; padding: 0; }
}
</style>
</head>
<body>
<div id="layout">
  <aside id="sidebar">
    <div class="sb-title">__SIDEBAR_TITLE__</div>
    <div class="sb-sub">__SIDEBAR_SUB__</div>
    <nav id="toc"></nav>
  </aside>
  <div id="main"><article id="container"></article></div>
</div>

<script>
__PIPELINE_JS__

// ==================== 导出驱动 ====================
const container = document.getElementById("container");
const SRC = __SRC_JSON__;

function renderExport(src) {
  thmStore = []; crefStore = [];
  for (const k in counters) delete counters[k];
  const { meta, body } = parseFrontMatter(src);
  if (meta && meta.title) document.title = meta.title;
  let s = extractTheorems(preprocessMarkdown(body));
  s = processCrossrefs(s);
  const stashed = protectMath(s);
  let html = marked.parse(stashed);
  html = restoreMath(html);
  html = renderTheorems(html);
  if (meta) html = renderFrontMatter(meta) + html;
  container.innerHTML = html;
  renderBareEnvironments();
  resolveCrossrefs(container);
  enhanceImages(container);
  buildSidebarToc(meta);
}

// 目录写入左侧边栏；无 toc:true 时也生成（可传 toc:false 关闭）
function buildSidebarToc(meta) {
  const show = !meta || !/^(false|no)$/i.test(String(meta.toc));
  const nav = document.getElementById("toc");
  if (!show) { document.getElementById("sidebar").style.display = "none"; return; }
  let i = 0;
  const lis = [];
  container.querySelectorAll("h2, h3").forEach(h => {
    if (!h.id) h.id = "sec-" + (++i);
    const lv = h.tagName === "H3" ? "lv3" : "";
    lis.push(`<a class="${lv}" href="#${esc(h.id)}">${esc(h.textContent)}</a>`);
  });
  nav.innerHTML = lis.join("") ||
    '<span style="color:var(--muted);font-size:13px">（无章节标题）</span>';
}

renderExport(SRC);
</script>
</body>
</html>
"""


def convert(md_path: Path, out_path: Path, renderer_path: Path) -> Path:
    src = md_path.read_text(encoding="utf-8")
    pipeline = extract_pipeline_js(renderer_path)

    # 侧栏标题：优先 Front Matter 的 title，否则用第一个 h1，否则文件名
    fm_title = None
    m = re.match(r"^---\r?\n[\s\S]*?\r?\n---", src)
    if m:
        t = re.search(r"^title:\s*(.+)$", m.group(0), re.M)
        if t:
            fm_title = t.group(1).strip().strip("\"'")
    h1 = re.search(r"^#\s+(.+)$", src, re.M)
    title = fm_title or (h1.group(1).strip() if h1 else md_path.stem)
    sub = f"{md_path.name} · 导出于 {date.today().isoformat()}"

    html = (TEMPLATE
            .replace("__TITLE__", html_mod.escape(title, quote=True))
            .replace("__SIDEBAR_TITLE__", html_mod.escape(title, quote=True))
            .replace("__SIDEBAR_SUB__", html_mod.escape(sub, quote=True))
            .replace("__PIPELINE_JS__", pipeline)
            .replace("__SRC_JSON__", json_for_script(src)))
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="增强 Markdown → 单文件 HTML（左侧目录）")
    ap.add_argument("input", help="输入 .md 文件")
    ap.add_argument("-o", "--output", help="输出 .html 路径（默认同名 .html）")
    ap.add_argument("--renderer", default=str(DEFAULT_RENDERER),
                    help=f"共享 renderer.js 路径（默认 {DEFAULT_RENDERER}）")
    args = ap.parse_args()

    md_path = Path(args.input).expanduser().resolve()
    if not md_path.exists():
        sys.exit(f"错误：找不到输入文件 {md_path}")
    if md_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        sys.exit(f"错误：输入应为 Markdown 文件（.md/.markdown/.txt），收到 {md_path.name}。\n"
                 f"（防止误把 HTML 等文件当输入而覆盖重要文件）")
    renderer_path = Path(args.renderer).expanduser().resolve()

    out_path = (Path(args.output).expanduser().resolve() if args.output
                else md_path.with_suffix(".html"))
    convert(md_path, out_path, renderer_path)
    print(f"✅ 已生成: {out_path}  ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
