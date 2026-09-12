#!/usr/bin/env python3
"""
blog.py —— 基于增强 Markdown 的静态博客系统。

用法:
    python3 blog.py                 # 构建 site/
    python3 blog.py --posts dir     # 指定文章目录（默认 content/）
    python3 blog.py --out dir       # 指定输出目录（默认 site/）

特性:
    - 全部增强语法支持：数学环境 / AMSL 定理环境 / crossref / Front Matter
      （复用 renderer.js 的共享渲染管线，浏览器端渲染）
    - 首页：按日期倒序的文章列表 + 标签云
    - 文章页：元数据卡片 + 左侧目录侧栏（toc: false 可关闭）
    - tags.html：标签归档页
    - 纯静态输出，任意静态托管可直接部署
"""

import argparse
import html as html_mod
import json
import re
import shutil
import sys
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter import parse_front_matter
from md2html import RUNTIME_ASSETS, extract_pipeline_js, json_for_script

HERE = Path(__file__).parent.resolve()


class Post(TypedDict):
    source: str
    slug: str
    title: str
    date: str
    tags: list[str]
    meta: dict[str, Any]
    body: str
    excerpt: str
    description: str
    updated: str
    cover: str
    series: str
    author: str


def plain_text(text: str) -> str:
    """用于摘要、搜索和 RSS 的保守纯文本版本。"""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[$\\{}]|\\begin\{[^}]*\}|\\end\{[^}]*\}|[#*`>\[\]()-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


CODE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^ {0,3}\1[ \t]*$|\Z)|(`+)[\s\S]*?\2(?!`)", re.M)


def transform_prose(text: str, transform) -> str:
    """Apply a transform only outside fenced/inline code."""
    chunks, end = [], 0
    for match in CODE_RE.finditer(text):
        chunks.extend((transform(text[end:match.start()]), match.group()))
        end = match.end()
    return "".join(chunks) + transform(text[end:])


def rewrite_local_links(text: str, targets: dict[str, str] | None = None) -> str:
    """博客根目录中将 Markdown 文章链接改为生成的 HTML 链接。"""
    def replace(match: re.Match[str]) -> str:
        path = unquote(match[2]).removeprefix("./")
        slug = (targets or {}).get(path, str(Path(path).with_suffix("")))
        return f"{match[1]}{quote(slug)}.html{match[3] or ''}{match[4]}"
    return transform_prose(text, lambda part: re.sub(
        r"(\]\()([^:)#?]+\.(?:md|markdown))([?#][^\s)]*)?(\))", replace, part))


def rewrite_article_citations(text: str, posts: list[Post]) -> str:
    """Turn [[slug]] into a portable Markdown recommendation card."""
    by_slug = {post["slug"]: post for post in posts}
    def replace(match: re.Match[str]) -> str:
        slug = match.group(1).strip()
        post = by_slug.get(slug)
        if not post:
            return f"**[未找到文章：{slug}]**"
        return f"\n\n> **推荐阅读 · [{post['title']}]({post['slug']}.html)**\n>\n> {post['excerpt']}\n\n"
    return transform_prose(text, lambda part: re.sub(r"\[\[([^\]]+)\]\]", replace, part))


def absolute_url(path: str, base_url: str = "") -> str:
    """为 RSS、sitemap 与 meta 标签生成规范 URL。"""
    if urlsplit(path).scheme in {"http", "https"}:
        return path
    encoded = quote(path.lstrip("/"), safe="/%#?=&")
    return f"{base_url.rstrip('/')}/{encoded}" if base_url else encoded


def rss_date(value: str) -> str:
    """将 Front Matter 的 ISO 日期转换为 RSS 所需的 RFC 822 日期。"""
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    except ValueError:
        return value

# ---------------------------------------------------------------- front matter 解析（与阅读器一致的 Python 侧）

def validate_slug(value: object, source: Path) -> str:
    slug = str(value).strip()
    if (not slug or slug.lower() in {"index", "tags", "search", ".", ".."}
            or Path(slug).name != slug or slug.endswith(".html")
            or re.search(r'[\\?#%:\s]', slug)):
        raise ValueError(f"{source.name}: slug 必须是单个文件名，不能包含路径或 .html 后缀")
    return slug


def validate_date(value: object, field: str, source: Path) -> str:
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as error:
        raise ValueError(f"{source.name}: {field} 必须是 YYYY-MM-DD 日期") from error


def validate_resource_url(value: object, field: str, source: Path) -> str:
    url = str(value).strip()
    if not url:
        return ""
    if re.match(r"^https?://", url):
        return url
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url) or ".." in Path(url).parts or url.startswith(("/", "\\")):
        raise ValueError(f"{source.name}: {field} 只允许 http(s) URL 或站点内相对路径")
    return url


def load_posts(posts_dir: Path) -> list[Post]:
    posts: list[Post] = []
    for f in sorted(posts_dir.glob("*.md")) + sorted(posts_dir.glob("*.markdown")):
        raw = f.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        if meta.get("draft", "").lower() in ("true", "yes"):
            continue
        slug = validate_slug(meta.get("slug") or f.stem, f)
        title = str(meta.get("title") or slug)
        d = validate_date(meta.get("date") or date.today().isoformat(), "date", f)
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in re.split(r"[,，]", tags) if t.strip()]
        # 摘要：excerpt 字段优先，否则取正文前 120 字符（剥掉语法标记）
        excerpt = meta.get("excerpt")
        if not excerpt:
            plain = plain_text(body)
            excerpt = plain[:120] + ("…" if len(plain) > 120 else "")
        posts.append({"source": f.name, "slug": slug, "title": title, "date": d, "tags": tags,
                      "meta": meta, "body": raw, "excerpt": excerpt,
                      "description": str(meta.get("description") or excerpt),
                      "updated": validate_date(meta.get("updated") or d, "updated", f),
                      "cover": validate_resource_url(meta.get("cover") or "", "cover", f),
                      "series": str(meta.get("series") or ""), "author": str(meta.get("author") or "")})
    targets = {p["source"]: p["slug"] for p in posts}
    for post in posts:
        post["body"] = rewrite_local_links(post["body"], targets)
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def validate_posts(posts: list[Post], posts_dir: Path) -> list[str]:
    """Validate local inline links/images/cards; never fetch external URLs."""
    problems = []
    slugs = {p["slug"] for p in posts}
    pages = {"index.html", "tags.html", "search.html", *(s + ".html" for s in slugs)}
    for post in posts:
        raw = post["body"]
        prose = CODE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), raw)
        def report(offset: int, message: str) -> None:
            problems.append(f"{post['source']}:{raw.count(chr(10), 0, offset) + 1}: {message}")
        for match in re.finditer(r"\[\[([^\]]+)\]\]", prose):
            if match[1].strip() not in slugs:
                report(match.start(), f"未找到文章：{match[1]}")
        resources = [(m.start(), m[1]) for m in re.finditer(r'!?\[[^\]\n]*\]\(<?([^\s)>]+)>?(?:\s+"[^"\n]*")?\)', prose)]
        if post["cover"]:
            resources.append((0, post["cover"]))
        for offset, resource in resources:
            url = urlsplit(resource)
            if url.scheme or url.netloc or not url.path:
                continue
            path = unquote(url.path).removeprefix("./")
            if path in pages:
                continue
            target = (posts_dir / path).resolve()
            if not target.is_relative_to(posts_dir.resolve()) or not target.is_file():
                report(offset, f"缺失本地链接或图片：{resource}")
    return problems


def validate_rendering(posts: list[Post]) -> list[str]:
    """Use the same vendored JS renderer for publishing checks."""
    try:
        result = subprocess.run(["node", str(HERE / "scripts" / "check-renderer.cjs")],
                                input=json.dumps(posts), text=True, capture_output=True, check=True)
    except FileNotFoundError as error:
        raise ValueError("--strict 需要 Node.js 来校验数学渲染") from error
    except subprocess.CalledProcessError as error:
        raise ValueError(f"渲染校验失败：{error.stderr}") from error
    return json.loads(result.stdout)


# ---------------------------------------------------------------- 页面模板

BASE_CSS = """
:root { --bg:#fbfcff; --fg:#172033; --muted:#667085; --accent:#4f46e5;
  --accent-soft:#eef2ff; --border:#e6eaf1; --card:#ffffff; --sidebar-w:270px; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111318; --fg:#e5e7eb; --muted:#9ca3af; --accent:#818cf8;
          --border:#2d3139; --card:#1a1d24; } }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:radial-gradient(circle at 18% -10%,#e9edff 0,transparent 32rem),var(--bg); color:var(--fg);
  font-family:-apple-system,"PingFang SC","Segoe UI",sans-serif; letter-spacing:.01em; }
a { color:var(--accent); text-decoration:none; transition:color .18s ease,background .18s ease,transform .18s ease; }
.wrap { max-width:1080px; margin:0 auto; padding:0 24px; }

/* 顶栏 */
header.site { border-bottom:1px solid color-mix(in srgb,var(--border) 85%,transparent); background:rgba(251,252,255,.82);
  backdrop-filter:blur(16px); position:sticky; top:0; z-index:10; }
header.site .wrap { display:flex; align-items:center; justify-content:space-between; gap:22px; height:64px; }
header.site .brand { font-weight:850; font-size:16px; color:var(--fg); letter-spacing:.08em; }
header.site nav { display:flex; gap:5px; font-size:14px; }
header.site nav a { color:var(--muted); padding:7px 10px; border-radius:999px; }
header.site nav a:hover { color:var(--accent); background:var(--accent-soft); }
.hero { max-width:760px; margin:58px auto 26px; }
.hero .eyebrow { color:var(--accent); font-size:12px; font-weight:800; letter-spacing:.13em; }
.hero h1 { font-size:clamp(2.2rem,6vw,4.1rem); line-height:1.05; letter-spacing:-.055em; margin:.24em 0 .28em; border:0; padding:0; }
.hero p { max-width:550px; color:var(--muted); font-size:1.05rem; line-height:1.85; }
.search-box { max-width:760px; margin:24px auto 0; }
.search-box input { width:100%; padding:11px 13px; border:1px solid var(--border);
  background:rgba(255,255,255,.85); color:var(--fg); border-radius:12px; font:inherit; box-shadow:0 8px 28px rgba(57,69,107,.06); }
.search-box input:focus { outline:3px solid var(--accent-soft); border-color:var(--accent); }
.search-results { list-style:none; padding:0; margin:10px 0; }
.search-results li { padding:9px 0; border-bottom:1px dashed var(--border); }
.post-nav,.related { border-top:1px solid var(--border); margin-top:34px; padding-top:20px; }
.post-nav { display:flex; justify-content:space-between; gap:18px; }
.post-nav a { max-width:48%; }
.cover { width:100%; max-height:360px; object-fit:cover; border-radius:12px; margin:0 0 1.4em; }
img.zoomable { cursor:zoom-in; }
.illustration { margin:1.9em 0; padding:10px; border:1px solid var(--border); border-radius:16px; background:var(--card); }
.illustration img { display:block; width:100%; border-radius:10px; } .illustration figcaption { color:var(--muted); font-size:.88em; text-align:center; padding:10px 6px 2px; }
.image-lightbox { position:fixed; inset:0; z-index:30; display:grid; place-items:center;
  padding:30px; background:rgba(0,0,0,.8); cursor:zoom-out; }
.image-lightbox img { max-width:100%; max-height:100%; object-fit:contain; }

/* 首页文章列表 */
.post-list { list-style:none; margin:30px auto 44px; padding:0; max-width:760px; display:grid; gap:14px; }
.post-item { padding:23px 25px; border:1px solid var(--border); border-radius:16px; background:rgba(255,255,255,.82); box-shadow:0 8px 26px rgba(44,55,88,.045); }
.post-item:hover { border-color:#c9d2f5; transform:translateY(-2px); box-shadow:0 15px 34px rgba(44,55,88,.09); }
.post-item h2 { margin:0 0 8px; font-size:1.38em; letter-spacing:-.025em; }
.post-item h2 a { color:var(--fg); }
.post-item h2 a:hover { color:var(--accent); }
.post-date { color:var(--muted); font-size:13px; }
.post-excerpt { color:var(--muted); font-size:14px; line-height:1.7; margin-top:6px; }
.tag { display:inline-block; background:var(--accent-soft); color:var(--accent); font-weight:650;
  border-radius:999px; padding:.18em .72em; font-size:.78em; margin-right:.35em; }
.tag:hover { background:var(--accent); color:#fff; }
.tagcloud { max-width:760px; margin:28px auto; padding:24px; border:1px solid var(--border); border-radius:16px; background:rgba(255,255,255,.65); }
.tagcloud h3 { font-size:.95em; color:var(--muted); }
.cite-link { font-size:.82em; font-weight:700; margin:0 .08em; } .citation-missing { color:#dc2626; font-size:.86em; }
.bibliography { margin-top:3.4em; padding-top:1.5em; border-top:2px solid var(--border); } .bibliography ol { padding-left:1.6em; } .bibliography li { margin:.65em 0; padding-left:.3em; line-height:1.7; } .ref-number { color:var(--accent); font-weight:700; }
.toc-active { color:var(--accent) !important; font-weight:700; background:var(--bg); }
.copy-button { border:1px solid var(--border); background:var(--card); color:var(--fg); border-radius:6px; padding:3px 7px; cursor:pointer; font-size:12px; }
pre { position:relative; display:block; } pre > .copy-button { position:absolute;top:7px;right:7px;z-index:1; }

/* 文章布局：左侧目录 */
#layout { display:flex; align-items:flex-start; }
#sidebar { width:var(--sidebar-w); flex:none; position:sticky; top:82px;
  max-height:calc(100vh - 90px); overflow-y:auto; padding:20px 16px;
  background:rgba(255,255,255,.76); backdrop-filter:blur(12px); border:1px solid var(--border); border-radius:16px;
  margin:32px 26px 60px 0; font-size:13px; transition:width .2s ease,padding .2s ease,margin .2s ease; }
#sidebar .sidebar-toggle { position:absolute; top:10px; right:10px; width:28px; height:28px; border:1px solid var(--border); border-radius:8px; background:var(--card); color:var(--muted); cursor:pointer; }
#sidebar .sidebar-toggle:hover { color:var(--accent); border-color:var(--accent); }
#sidebar .sidebar-content { transition:opacity .15s ease; }
body.sidebar-collapsed #sidebar { width:50px; padding:10px; margin-right:18px; overflow:visible; }
body.sidebar-collapsed #sidebar .sidebar-content { opacity:0; pointer-events:none; visibility:hidden; }
body.sidebar-collapsed #sidebar .sidebar-toggle { position:static; transform:rotate(180deg); }
#sidebar .sb-title { font-weight:700; margin-bottom:10px; font-size:14px; word-break:break-all; }
#sidebar nav a { display:block; padding:3px 8px; border-radius:6px; color:var(--fg); line-height:1.5; }
#sidebar nav a:hover { color:var(--accent); background:var(--bg); }
#sidebar nav a.lv3 { margin-left:1.1em; color:var(--muted); font-size:12.5px; }
#main { flex:1; min-width:0; }
#container { max-width:820px; padding:48px 0 140px; line-height:1.82; font-size:16px; }
@media (max-width:900px) {
  #layout { display:block; }
  #sidebar { position:static; width:auto; max-height:none; margin:20px 0; }
  body.sidebar-collapsed #sidebar { width:auto; padding:20px 16px; margin:20px 0; }
  body.sidebar-collapsed #sidebar .sidebar-content { opacity:1; pointer-events:auto; visibility:visible; }
  body.sidebar-collapsed #sidebar .sidebar-toggle { position:absolute; transform:none; }
}

/* 正文元素 */
h1,h2,h3,h4 { line-height:1.35; margin-top:1.6em; }
h1 { font-size:2.25em; letter-spacing:-.045em; border-bottom:2px solid var(--border); padding-bottom:.3em; }
h2 { font-size:1.55em; letter-spacing:-.03em; border-bottom:1px solid var(--border); padding-bottom:.3em; }
blockquote { border-left:4px solid var(--accent); margin:1em 0; padding:.4em 1em;
  background:var(--card); border-radius:0 8px 8px 0; }
code { background:var(--card); border:1px solid var(--border); border-radius:4px;
  padding:.15em .4em; font-size:.88em; }
pre code { display:block; padding:14px; overflow-x:auto; border-radius:10px; }
table { border-collapse:collapse; width:100%; margin:1.2em 0; }
th, td { border:1px solid var(--border); padding:8px 12px; text-align:left; }
th { background:var(--card); }
img { max-width:100%; }
hr { border:none; border-top:1px solid var(--border); }
.katex-display { overflow-x:auto; overflow-y:hidden; padding:4px 2px; }
.math-error { color:#ef4444; background:rgba(239,68,68,.08); border-radius:6px;
  padding:2px 6px; font-family:monospace; font-size:.85em; }

/* 定理环境 */
.thm-env { margin:1.2em 0; padding:.8em 1.1em; border-radius:8px;
  background:var(--card); border-left:4px solid var(--accent); font-style:normal; }
.thm-env.proof { background:transparent; border-left-color:var(--border); }
.thm-head { font-weight:700; font-style:normal; }
.thm-title { font-weight:400; }
.thm-body { margin-top:.35em; }
.qed { float:right; }
a.ref-link { border-bottom:1px dotted var(--accent); }

/* Front Matter 卡片 */
.fm-card { background:linear-gradient(135deg,#f4f6ff,#fff); border:1px solid #dce3ff; border-radius:16px;
  padding:1.35em 1.45em; margin-bottom:2em; font-size:.92em; box-shadow:0 12px 30px rgba(63,73,140,.07); }
.fm-card h1 { margin:0 0 .3em; font-size:1.7em; border-bottom:none; padding-bottom:0; }
.fm-meta { display:flex; flex-wrap:wrap; gap:.35em 1.4em; color:var(--muted); }
.fm-tags { display:inline-flex; gap:.45em; flex-wrap:wrap; }
.fm-tag { background:var(--accent); color:#fff; opacity:.85; border-radius:999px;
  padding:.05em .7em; font-size:.82em; }

/* 归档页 */
.archive-group h3 { color:var(--muted); font-size:.95em; margin:30px 0 8px; }
.archive-list { list-style:none; margin:0; padding:0; max-width:760px; }
.archive-list li { padding:7px 0; border-bottom:1px dashed var(--border);
  display:flex; justify-content:space-between; gap:16px; }
.archive-list .d { color:var(--muted); font-size:13px; white-space:nowrap; }

footer.site { border-top:1px solid var(--border); color:var(--muted);
  font-size:13px; text-align:center; padding:34px 0; margin-top:56px; }
@media print { header.site,#sidebar,footer.site { display:none; } #container{max-width:none;} }
"""


def page_shell(title: str, body: str, active: str = "", description: str = "", canonical: str = "") -> str:
    e = html_mod.escape
    def navlink(href: str, label: str, key: str) -> str:
        cls = ' style="color:var(--accent);font-weight:600"' if key == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
{f'<link rel="canonical" href="{e(canonical)}">' if canonical else ''}
<link rel="stylesheet" href="assets/vendor/katex/katex.min.css">
<link rel="stylesheet" href="assets/vendor/github-dark.min.css">
<style>{BASE_CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html">📝 My Blog</a>
  <nav>{navlink('index.html','首页','index')}{navlink('tags.html','归档','tags')}{navlink('search.html','搜索','search')}</nav>
</div></header>
{body}
<footer class="site">Powered by Enhanced Markdown Reader · 数学 · 定理 · Crossref</footer>
</body>
</html>"""


CDN_AND_PIPELINE = """<script src="assets/vendor/marked.min.js"></script>
<script src="assets/vendor/katex/katex.min.js"></script>
<script src="assets/vendor/highlight.min.js"></script>"""

POST_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<meta name="description" content="__DESCRIPTION__">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESCRIPTION__">
<meta property="og:url" content="__OG_URL__">
<link rel="canonical" href="__CANONICAL__">
__COVER_META__
__HEAD__
<style>__CSS__</style>
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html">📝 My Blog</a>
  <nav><a href="index.html">首页</a><a href="tags.html">归档</a><a href="search.html">搜索</a></nav>
</div></header>
<div class="wrap"><div id="layout">
  <aside id="sidebar">
    <button class="sidebar-toggle" type="button" aria-label="收起目录" title="收起目录">‹</button>
    <div class="sidebar-content">
      <div class="sb-title">__SIDEBAR_TITLE__</div>
      <div style="color:var(--muted);font-size:12px;margin-bottom:12px">__SIDEBAR_SUB__</div>
      <nav id="toc"></nav>
    </div>
  </aside>
  <div id="main"><article id="container"></article>__POST_NAV__</div>
</div></div>
<footer class="site">Powered by Enhanced Markdown Reader · __DATE__</footer>
__CDN__
<script>
__PIPELINE__

// ==================== 博客文章渲染 ====================
const container = document.getElementById("container");
const SRC = __SRC_JSON__;
const COVER_HTML = __COVER_HTML__;

(function renderPost(src) {
  const prepared = prepareDocument(src);
  const { meta } = prepared;
  if (meta && meta.title) document.title = meta.title;
  let html = prepared.html;
  if (meta) html = renderFrontMatter(meta) + html;
  container.innerHTML = html;
  if (COVER_HTML) container.insertAdjacentHTML("afterbegin", COVER_HTML);
  renderBareEnvironments();
  resolveCrossrefs(container);
  renderCitations(container);
  renderBibliography(container);
  enhanceImages(container);
  enhanceCopyButtons(container);
  // 左侧目录（toc:false 关闭）
  const show = !meta || !/^(false|no)$/i.test(String(meta.toc));
  const nav = document.getElementById("toc");
  if (!show) { document.getElementById("sidebar").style.display = "none"; return; }
  let i = 0; const lis = [];
  container.querySelectorAll("h2, h3").forEach(h => {
    if (!h.id) h.id = "sec-" + (++i);
    lis.push(`<a class="${h.tagName === "H3" ? "lv3" : ""}" href="#${esc(h.id)}">${esc(h.textContent)}</a>`);
  });
  nav.innerHTML = lis.join("") || '<span style="color:var(--muted)">（无章节）</span>';
  setupTocScrollSpy(container, nav);
  const toggle = document.querySelector(".sidebar-toggle");
  const setSidebar = collapsed => {
    document.body.classList.toggle("sidebar-collapsed", collapsed);
    toggle.textContent = collapsed ? "›" : "‹";
    toggle.setAttribute("aria-label", collapsed ? "展开目录" : "收起目录");
    toggle.title = toggle.getAttribute("aria-label");
    localStorage.setItem("blog-sidebar-collapsed", collapsed ? "1" : "0");
  };
  setSidebar(localStorage.getItem("blog-sidebar-collapsed") === "1");
  toggle.onclick = () => setSidebar(!document.body.classList.contains("sidebar-collapsed"));
})(SRC);
</script>
</body>
</html>"""


def esc(s: object) -> str:
    return html_mod.escape(str(s))


def sync_assets(posts_dir: Path, out_dir: Path) -> None:
    """复制 content/assets；文章可直接写 ![](assets/example.png)。"""
    assets = posts_dir / "assets"
    if assets.is_dir():
        shutil.copytree(assets, out_dir / "assets", dirs_exist_ok=True)
    if not RUNTIME_ASSETS.is_dir():
        raise RuntimeError(f"找不到离线渲染资源：{RUNTIME_ASSETS}")
    shutil.copytree(RUNTIME_ASSETS, out_dir / "assets" / "vendor", dirs_exist_ok=True)


def related_posts(post: Post, posts: list[Post], limit: int = 3) -> list[Post]:
    tags = set(post["tags"])
    ranked = [p for p in posts if p["slug"] != post["slug"] and tags.intersection(p["tags"])]
    ranked.sort(key=lambda p: (-len(tags.intersection(p["tags"])), p["date"]), reverse=False)
    return ranked[:limit]


def build_index(posts: list[Post], out_dir: Path, base_url: str = "") -> None:
    items = []
    for p in posts:
        tags = " ".join(
            f'<a class="tag" href="tags.html#{esc(t)}">{esc(t)}</a>' for t in p["tags"])
        items.append(f"""<li class="post-item">
  <h2><a href="{esc(p['slug'])}.html">{esc(p['title'])}</a></h2>
  <div class="post-date">{esc(p['date'])}{(" &nbsp;·&nbsp; " + tags) if tags else ""}</div>
  <div class="post-excerpt">{esc(p["excerpt"])}</div>
</li>""")
    tagcount = {}
    for p in posts:
        for t in p["tags"]:
            tagcount[t] = tagcount.get(t, 0) + 1
    cloud = " ".join(f'<a class="tag" href="tags.html#{esc(t)}">{esc(t)} ×{n}</a>'
                     for t, n in sorted(tagcount.items(), key=lambda x: -x[1]))
    body = f"""
<div class="wrap">
  <section class="hero">
    <div class="eyebrow">MATH NOTES · {len(posts):02d} POSTS</div>
    <h1>把推导与灵感，<br>写成可阅读的证明。</h1>
    <p>这里收录关于分析、几何与数学方法的笔记。每一篇文章都支持公式、定理、交叉引用与全文检索。</p>
  </section>
  <div class="search-box"><input id="site-search" type="search" placeholder="搜索标题、标签和全文正文…" autocomplete="off"><ul id="search-results" class="search-results"></ul></div>
  <ul class="post-list">{"".join(items) or "<li class='post-item'>暂无文章 — 在 content/ 中添加 .md 后重新构建。</li>"}</ul>
  <div class="tagcloud"><h3>🏷️ 标签</h3>{cloud}</div>
</div>"""
    script = """<script>
const input=document.getElementById('site-search'), results=document.getElementById('search-results');
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
let searchIndex=[];
fetch('search-index.json').then(r=>r.json()).then(x=>searchIndex=x).catch(()=>{});
input.addEventListener('input',()=>{const q=input.value.trim().toLowerCase();
 const found=q?searchIndex.filter(p=>p.search.includes(q)).slice(0,8):[];
 results.innerHTML=found.map(p=>`<li><a href="${esc(p.url)}">${esc(p.title)}</a><div class="post-excerpt">${esc(p.excerpt)}</div></li>`).join('');});
</script>"""
    (out_dir / "index.html").write_text(page_shell("My Blog", body + script, "index", canonical=absolute_url("index.html", base_url)), encoding="utf-8")


def build_search(posts: list[Post], out_dir: Path, base_url: str = "") -> None:
    body = """<div class="wrap"><div class="search-box"><h1>搜索</h1>
<input id="site-search" type="search" placeholder="搜索标题、标签和全文正文…" autofocus>
<ul id="search-results" class="search-results"></ul></div></div>
<script>const input=document.getElementById('site-search'),results=document.getElementById('search-results');const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');let data=[];
fetch('search-index.json').then(r=>r.json()).then(x=>{data=x;run();});
function run(){const q=input.value.trim().toLowerCase(),found=q?data.filter(p=>p.search.includes(q)):data;
results.innerHTML=found.map(p=>`<li><a href="${esc(p.url)}">${esc(p.title)}</a><div class="post-excerpt">${esc(p.excerpt)}</div></li>`).join('');}
input.addEventListener('input',run);</script>"""
    (out_dir / "search.html").write_text(page_shell("搜索 · My Blog", body, "search", canonical=absolute_url("search.html", base_url)), encoding="utf-8")


def build_search_index(posts: list[Post], out_dir: Path) -> None:
    data = [{"title": p["title"], "excerpt": p["excerpt"], "url": f"{p['slug']}.html",
             "search": " ".join([p["title"], p["excerpt"], plain_text(p["body"]), *p["tags"]]).lower()} for p in posts]
    (out_dir / "search-index.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def build_rss(posts: list[Post], out_dir: Path, base_url: str = "") -> None:
    def item(post: Post) -> str:
        url = esc(absolute_url(post["slug"] + ".html", base_url))
        categories = "".join(f"<category>{esc(tag)}</category>" for tag in post["tags"])
        creator = f"<dc:creator>{esc(post['author'])}</dc:creator>" if post["author"] else ""
        return (f"<item><title>{esc(post['title'])}</title><link>{url}</link><guid isPermaLink=\"true\">{url}</guid>"
                f"<pubDate>{esc(rss_date(post['date']))}</pubDate><lastBuildDate>{esc(rss_date(post['updated']))}</lastBuildDate>"
                f"{categories}{creator}<description>{esc(post['description'])}</description></item>")
    items = "".join(item(post) for post in posts)
    latest = rss_date(posts[0]['updated']) if posts else rss_date(date.today().isoformat())
    self_link = absolute_url("rss.xml", base_url)
    rss = f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>My Blog</title><link>{esc(base_url or "./")}</link><description>数学博客</description><language>zh-CN</language><lastBuildDate>{esc(latest)}</lastBuildDate><atom:link href="{esc(self_link)}" rel="self" type="application/rss+xml"/>{items}</channel></rss>'
    (out_dir / "rss.xml").write_text(rss, encoding="utf-8")


def build_sitemap(posts: list[Post], out_dir: Path, base_url: str = "") -> None:
    urls = ["index.html", "tags.html", "search.html", *[f"{p['slug']}.html" for p in posts]]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{esc(absolute_url(url, base_url))}</loc></url>" for url in urls) + "</urlset>"
    (out_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def build_tags(posts: list[Post], out_dir: Path, base_url: str = "") -> None:
    bytag = {}
    for p in posts:
        for t in p["tags"]:
            bytag.setdefault(t, []).append(p)
    groups = []
    for t, ps in sorted(bytag.items()):
        lis = "".join(f'<li><a href="{esc(p["slug"])}.html">{esc(p["title"])}</a>'
                      f'<span class="d">{esc(p["date"])}</span></li>' for p in ps)
        groups.append(f'<div class="archive-group" id="{esc(t)}"><h3>🏷️ {esc(t)}</h3>'
                      f'<ul class="archive-list">{lis}</ul></div>')
    body = f'<div class="wrap" style="max-width:820px">{"".join(groups) or "<p>暂无标签。</p>"}</div>'
    (out_dir / "tags.html").write_text(page_shell("归档 · My Blog", body, "tags", canonical=absolute_url("tags.html", base_url)), encoding="utf-8")


def build_post(p: Post, pipeline_js: str, out_dir: Path, newer: Post | None = None,
               older: Post | None = None, related: tuple[Post, ...] | list[Post] = (),
               base_url: str = "", position: int = 1, total: int = 1,
               all_posts: list[Post] | None = None) -> None:
    sub = f"{p['date']}"
    cover = f'<img class="cover" src="{esc(p["cover"])}" alt="{esc(p["title"])}">' if p["cover"] else ""
    nav = '<nav class="post-nav">' + (f'<a href="{esc(newer["slug"])}.html">← 更新文章</a>' if newer else '<span></span>') + f'<span>第 {position} / {total} 篇</span>' + (f'<a href="{esc(older["slug"])}.html">更早文章 →</a>' if older else '<span></span>') + '</nav>'
    related_html = ""
    if related:
        related_html = '<section class="related"><b>相关文章</b><ul>' + ''.join(
            f'<li><a href="{esc(x["slug"])}.html">{esc(x["title"])}</a></li>' for x in related) + '</ul></section>'
    html = (POST_TEMPLATE
            .replace("__TITLE__", esc(p["title"]))
            .replace("__DESCRIPTION__", esc(p["description"]))
            .replace("__CANONICAL__", absolute_url(p["slug"] + ".html", base_url))
            .replace("__OG_URL__", absolute_url(p["slug"] + ".html", base_url))
            .replace("__COVER_META__", f'<meta property="og:image" content="{esc(absolute_url(p["cover"], base_url))}">' if p["cover"] else "")
            .replace("__SIDEBAR_TITLE__", esc(p["title"]))
            .replace("__SIDEBAR_SUB__", esc(sub))
            .replace("__DATE__", esc(p["updated"]))
            .replace("__POST_NAV__", nav + related_html)
            .replace("__HEAD__", '<link rel="stylesheet" href="assets/vendor/katex/katex.min.css"><link rel="stylesheet" href="assets/vendor/github-dark.min.css">')
            .replace("__CSS__", BASE_CSS)
            .replace("__CDN__", CDN_AND_PIPELINE)
            .replace("__PIPELINE__", pipeline_js)
            .replace("__COVER_HTML__", json_for_script(cover))
            .replace("__SRC_JSON__", json_for_script(rewrite_article_citations(p["body"], all_posts or [p]))))
    (out_dir / f"{p['slug']}.html").write_text(html, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="增强 Markdown 静态博客系统")
    ap.add_argument("--posts", default=str(HERE / "content"))
    ap.add_argument("--out", default=str(HERE / "site"))
    ap.add_argument("--base-url", default="", help="生产站点根 URL，例如 https://example.com")
    ap.add_argument("--strict", action="store_true", help="拒绝断链、缺失图片/文献、重复标签和无效公式（需 Node.js）")
    args = ap.parse_args()

    posts_dir, out_dir = Path(args.posts).resolve(), Path(args.out).resolve()
    if not posts_dir.exists():
        sys.exit(f"错误：文章目录不存在 {posts_dir}")
    try:
        posts_dir.relative_to(out_dir)
        sys.exit("错误：--out 不能是 --posts 或其父目录，否则会清空文章源文件。")
    except ValueError:
        pass
    if out_dir.exists() and not out_dir.is_dir():
        sys.exit(f"错误：输出路径不是目录：{out_dir}")

    pipeline_js = extract_pipeline_js(HERE / "renderer.js")
    posts = load_posts(posts_dir)

    seen_slugs: set[str] = set()
    for post in posts:
        if post["slug"] in seen_slugs:
            sys.exit(f"错误：重复 slug：{post['slug']}")
        seen_slugs.add(post["slug"])

    if args.strict:
        problems = validate_posts(posts, posts_dir) + validate_rendering(posts)
        if problems:
            sys.exit("发布校验失败：\n" + "\n".join(problems))

    # Build into a sibling staging directory. A successful build replaces the
    # complete old tree, so deleted posts/assets cannot linger in production.
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.build-", dir=out_dir.parent))
    sync_assets(posts_dir, staging)
    base_url = args.base_url.rstrip("/")
    if not base_url:
        print("⚠️  未设置 --base-url：RSS、sitemap 和 canonical 将使用相对 URL；部署前请补充。")
    build_index(posts, staging, base_url)
    build_tags(posts, staging, base_url)
    build_search(posts, staging, base_url)
    build_search_index(posts, staging)
    build_rss(posts, staging, base_url)
    build_sitemap(posts, staging, base_url)
    for i, p in enumerate(posts):
        build_post(p, pipeline_js, staging,
                   newer=posts[i - 1] if i else None,
                   older=posts[i + 1] if i + 1 < len(posts) else None,
                   related=related_posts(p, posts), base_url=base_url,
                   position=i + 1, total=len(posts), all_posts=posts)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    staging.replace(out_dir)

    print(f"✅ 构建完成: {out_dir}")
    print(f"   文章 {len(posts)} 篇 → index.html / tags.html / search.html / rss.xml / sitemap.xml / " +
          " ".join(p["slug"] + ".html" for p in posts[:3]) + (" …" if len(posts) > 3 else ""))


if __name__ == "__main__":
    main()
