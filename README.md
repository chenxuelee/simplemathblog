# SimpleMathBlog · 增强 Markdown 阅读器与数学博客

面向数学笔记的 Markdown 阅读、发布和导出工具，支持 KaTeX 公式、定理环境、LaTeX 风格交叉引用和 BibTeX 文献。

浏览器阅读器无需构建；Python 工具可生成静态博客、离线 HTML 和 PDF。PDF 导出使用 Playwright + Chromium，不需要安装 LaTeX。

| 需求 | 入口 | 运行要求 |
| --- | --- | --- |
| 阅读或编辑 Markdown | `index.html` | 浏览器 |
| 导出离线 HTML | `md2html.py` | Python 3.11+ |
| 构建、预览博客 | `blog.py` / `server.py` | Python 3.11+；严格构建另需 Node.js |
| 导出 PDF | `md2pdf.py` | Python 3.11+、Playwright、Chromium；中文需系统字体 |

以下命令默认在仓库根目录执行；`uv` 用于管理 Python 环境，PDF 章节也提供 pip 安装方式。

## ✨ 特性

- **完整数学环境支持** —— `$...$`、`$$...$$`、`\(...\)`、`\[...\]` 四种定界符，以及不包 `$` 直接书写的裸 `\begin{align}` 等环境
- **AMSL 定理环境** —— `theorem`、`lemma`、`proposition`、`corollary` 等 9 种环境，自动编号、样式化渲染
- **交叉引用（crossref）** —— `\label` / `\ref` / `\eqref` / `\autoref`，引用渲染为可点击链接
- **BibTeX 文献管理** —— 导入 `.bib` 文件或内嵌 `bibtex` 代码块；支持 `\cite{key}`、`[@key]` 与自动参考文献
- **Front Matter** —— YAML 元数据块渲染为标题卡片（作者/日期/标签），支持自动目录
- **离线 HTML 导出** —— `md2html.py` 生成带左侧目录的 HTML，并复制所需运行时资源
- **Python PDF 导出** —— `md2pdf.py` 支持纸张、页边距、横向排版、页码和严格数学校验
- **静态博客系统** —— 附带 `blog.py`，`content/` 目录一键生成完整站点（首页 / 标签归档 / 文章页）
- **文章引用与插图** —— `[[slug]]` 生成推荐阅读卡片；带标题的 Markdown 图片自动成为可放大的带图注插图
- **共享渲染管线** —— 阅读器、博客、HTML 与 PDF 导出复用 `renderer.js`
- **自定义宏** —— 内置 `\RR`、`\norm` 等常用宏，可自行扩展
- **阅读体验** —— GFM 表格与任务列表、代码高亮、深色模式自适应、长公式横向滚动
- **高效检索与摘录** —— 目录随滚动高亮、阅读器正文搜索、博客全文搜索；一键复制代码块
- **发布能力** —— 文章页显示前后分页与篇次，RSS 提供分类、作者、更新时间和自链接元数据
- **使用方式** —— 打开本地 `.md` 文件、拖拽进窗口、或直接在编辑器中书写实时预览；一键导出 PDF

## 🚀 快速开始

### 统一开发命令

需要 Python 3.11+、uv 和 Node.js 20+（CI 使用 Node.js 22）。在仓库根目录安装依赖：

```bash
npm ci
uv sync --locked --extra pdf --group pdf-test
npx playwright install chromium
uv run --locked --extra pdf python -m playwright install chromium --only-shell
```

| 命令 | 用途 |
| --- | --- |
| `npm run dev` | 构建并预览博客，监视源码变化，默认端口 8000 |
| `npm run build` | 严格构建博客到 `site/` |
| `npm test` | 运行 Python（含 PDF 集成）、渲染器及浏览器测试；浏览器测试先严格构建站点 |
| `npm run test:python` | 运行完整 Python 测试，包括 PDF 集成测试 |
| `npm run test:renderer` | 运行 JavaScript 渲染器测试 |
| `npm run test:browser` | 运行浏览器测试 |
| `npm run pdf -- <文件.md>` | 导出 PDF |

通过 `--` 传递原有工具参数，例如：

```bash
npm run dev -- --port 8080
npm run build -- --base-url https://example.com/blog --out dist
npm run pdf -- content/fourier-series.md -o output/notes.pdf --strict
```

如果已有 Chrome/Chromium，可跳过上述两个浏览器下载命令，设置
`CHROMIUM_EXECUTABLE_PATH`。浏览器测试和 PDF 导出共用此变量：

```bash
# macOS/Linux；路径按实际安装位置设置
export CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
npm test
npm run pdf -- content/fourier-series.md -o output/notes.pdf
```

PowerShell 使用 `$env:CHROMIUM_EXECUTABLE_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'`。
PDF 的 `--browser` 参数（Python API 的 `browser=`）优先于环境变量；
两者都未设置或环境变量为空时使用 Playwright 管理的 Chromium。PDF 中文排版仍需系统中文字体。

运行完整测试前应停止手动启动的 4173 端口服务，确保浏览器测试使用本次构建。
仅在已有正确构建产物时设置 `BLOG_SKIP_BUILD=1`；CI 使用独立服务，
本地测试可复用已有 4173 端口服务。

仅使用阅读器时，无需安装依赖，直接用浏览器打开 `index.html` 即可。

```bash
# 或者本地起个服务（可选）
uv run python -m http.server 8000 --directory .
# 浏览器访问 http://localhost:8000
```

预览生成的博客时，可以使用项目内置的无缓存服务器：

```bash
uv run python server.py                  # 服务 site/，默认 http://127.0.0.1:8000
uv run python server.py --build --port 8080  # 先重建，再以 8080 端口服务
uv run python server.py --watch              # 监视文章与渲染器改动，自动重建
```

界面按钮：

| 按钮 | 功能 |
|---|---|
| 📂 打开文件 | 加载本地 `.md` / `.markdown` / `.txt` 文件 |
| ✏️ 编辑源码 | 在源码编辑与渲染预览之间切换，编辑时实时渲染 |
| 🖨️ 导出 PDF | 调用浏览器打印功能 |
| ↔ 宽度 / A 字号 | 切换阅读宽度与字号（记住本机设置） |
| 📚 导入 BibTeX | 加载本地 `.bib` 文献库，供当前阅读器会话引用 |

也可以把 `.md` 文件直接拖进窗口。

## 📤 导出为离线 HTML（左侧目录）

`md2html.py` 可以把增强 Markdown 转换为离线 HTML 页面——目录渲染在左侧固定侧边栏，右侧为正文，滚动时侧栏保持可见。为保证离线渲染，导出时会在输出文件旁复制 `assets/vendor/` 运行时资源：

```bash
# 基本用法（输出同名 .html）
uv run python md2html.py notes.md

# 指定输出路径
uv run python md2html.py notes.md -o notes_export.html

# 指定其他共享渲染器版本
uv run python md2html.py notes.md --renderer /path/to/renderer.js
```

导出文件的特点：

- **复用阅读器的数学渲染逻辑** —— 转换器读取 `renderer.js`，Python 将 Markdown 源码嵌入 HTML 模板；版式由导出模板控制
- **左侧目录侧栏** —— 自动收集 h2/h3 生成可点击目录（h3 缩进一级）；窄屏（<900px）自动折叠为顶部块；打印时隐藏
- **侧栏开关** —— Front Matter 中 `toc: false` 可隐藏侧栏（默认显示）
- **深色模式** —— 与阅读器一致，跟随系统设置
- **离线可用** —— KaTeX、marked、highlight.js 固定在仓库的 `assets/vendor/`；导出页会自动复制这些资源，不依赖 CDN
- **输入保护** —— 仅接受 `.md` / `.markdown` / `.txt` 输入，防止误覆盖其他文件

分享离线 HTML 时，请同时附带输出目录中的 `assets/vendor/`，并保留文章图片的相对路径。它不是把所有字体和图片都嵌入 HTML 的单文件包。

侧栏标题的取值优先级：Front Matter `title` → 文档第一个 `# h1` → 文件名。

## 📄 Markdown 转 PDF

`md2pdf.py` 通过 [Python Playwright 的 Chromium PDF 接口](https://playwright.dev/python/docs/api/class-page#page-pdf)
打印项目已有的 HTML 渲染结果。支持数学公式、定理环境、交叉引用、内嵌 BibTeX、
中文、代码、表格和本地图片，无需安装 LaTeX。生成的正文可选择、搜索，公式保持矢量渲染。

首次安装（Python 3.11+）：

```bash
uv sync --extra pdf
uv run --extra pdf python -m playwright install chromium --only-shell
```

使用方法：

```bash
# 默认生成 content/fourier-series.pdf
uv run --extra pdf python md2pdf.py content/fourier-series.md

# 指定输出位置，严格检查公式与引用
uv run --extra pdf python md2pdf.py content/fourier-series.md -o output/notes.pdf --strict

# 调整纸张、页边距（毫米）和方向
uv run --extra pdf python md2pdf.py notes.md -o notes.pdf --paper A5 --margin 15
uv run --extra pdf python md2pdf.py notes.md --paper Letter --landscape
```

也可用 pip 安装依赖后直接执行 `python md2pdf.py`：

```bash
python -m pip install 'playwright>=1.58,<2'
python -m playwright install chromium --only-shell
python md2pdf.py notes.md -o notes.pdf
```

### PDF 命令参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `input` | 必填 | UTF-8 的 `.md`、`.markdown` 或 `.txt` 文件 |
| `-o, --output` | 与输入同目录、同名的 `.pdf` | 输出路径；自动创建父目录 |
| `--paper` | `A4` | `A4`、`A5` 或 `Letter` |
| `--margin` | `18` | 四边页边距，单位 mm |
| `--landscape` | 关闭 | 横向纸张 |
| `--timeout` | `30` | 页面及资源等待超时，单位秒 |
| `--browser` | Playwright 管理的 Chromium | 已有 Chrome/Chromium 的可执行文件路径 |
| `--strict` | 关闭 | 数学公式、标签或文献引用有错误时拒绝导出 |

### 资源与排版

- 页边距至少 10 mm 时显示页码；更小页边距下隐藏页码。
- `--timeout 60` 可延长页面和资源加载等待时间；`--browser /path/to/chrome`
  可指定已有的 Chrome/Chromium 可执行文件。
- 本地图片以 Markdown 所在目录为基准，允许其子目录；请把图片放在该目录树内。
  HTTP(S) 图片需要网络。缺失图片或渲染失败时不会覆盖已有 PDF。
- 默认将无效公式和缺失引用报告到终端，并保留页面上的错误提示；`--strict` 会拒绝导出。
- 使用浅色打印样式，去掉侧栏和复制按钮；加载完字体及图片后才打印。
  长代码行自动换行，超宽独立公式缩小适应纸宽；较长推导建议手动使用 `aligned` 分行。
- 中文字体使用系统字体；macOS 可使用宋体，Linux 建议安装 `fonts-noto-cjk`。
  Linux 缺少浏览器系统依赖时，可运行 `python -m playwright install --with-deps chromium --only-shell`。
- 命令需在本项目内使用，依赖 `md2html.py`、`renderer.js` 和 `assets/vendor/`。
  输出 PDF 可单独分享，不需要附带这些文件。

### Python 调用

```python
from pathlib import Path
from md2pdf import convert

convert(Path("notes.md"), Path("output/notes.pdf"), paper="A4", margin_mm=18, strict=True)
```

### 常见问题

| 现象 | 处理方法 |
| --- | --- |
| 提示缺少 Playwright | 执行 `uv sync --extra pdf`，并用 `uv run --extra pdf` 运行命令 |
| Chromium 无法启动 | 安装浏览器及系统依赖，或用 `--browser` 指定已有浏览器 |
| 中文显示为方框 | 安装中文系统字体后重新导出 |
| 图片加载失败 | 检查相对路径、文件是否在 Markdown 目录树内，以及远程图片是否可访问 |
| 严格模式拒绝导出 | 根据终端中的公式、标签或文献提示修正源码；代码示例请放在代码块内 |

PDF 导出处理单篇文档；博客专用的 `[[slug]]` 推荐卡片由 `blog.py` 处理。
HTML 导出和 PDF 导出使用文章内嵌的 BibTeX，不会读取浏览器阅读器里临时导入的文献库。

## 📝 静态博客系统

`blog.py` 把项目扩展为一个完整的**数学博客**：`content/` 目录放文章，一条命令生成整个静态站点。

```bash
uv run python blog.py                              # content/ → site/
uv run python blog.py --posts myposts --out dist   # 自定义文章/输出目录
uv run python blog.py --base-url https://example.com  # 生产部署：绝对 RSS/sitemap/SEO URL
```

### 站点结构

```
content/*.md  ──blog.py──▶  site/
                              ├── index.html    # 首页
                              ├── tags.html     # 标签归档
                              └── <slug>.html   # 文章页（文件名即 URL slug）
```

| 页面 | 内容 |
|---|---|
| 首页 | 按 `date` 倒序的文章列表（标题 / 日期 / 标签胶囊 / 摘要）+ 底部标签云（带计数） |
| 归档页 | 按标签分组的文章列表；标签云点击直达对应分组锚点 |
| 文章页 | Front Matter 元数据卡片 + 左侧 sticky 目录侧栏（h2/h3 两级缩进） |

文章页内嵌阅读器的 JS 渲染管线，**数学环境、定理环境、交叉引用、BibTeX、Front Matter 全部支持**，渲染效果与阅读器预览一致。

### 文章 Front Matter 字段

```yaml
---
title: 文章标题            # 缺省用文件名
date: 2026-08-23          # 缺省用今天；首页按此倒序
tags: [分析, 傅里叶]       # 行内数组、短横线列表或逗号分隔均可
excerpt: 手写摘要          # 缺省自动提取正文前 120 字
toc: false                 # 关闭该篇文章的左侧目录（默认显示）
draft: true                # 草稿：不发布
---
```

### 写作与部署

写作流程：往 `content/` 丢 `.md` → `uv run python blog.py` → 完成。部署只需把 `site/` 上传到任意静态托管（GitHub Pages、Netlify、Vercel 等）。

示例文章见 `content/fourier-series.md` 与 `banach-fixed-point.md`（覆盖定理环境 + crossref + 数学环境 + Front Matter 的完整用法）。

### 发布与写作增强

构建器还会生成 `search.html`、`search-index.json`、`rss.xml` 和 `sitemap.xml`。首页与搜索页均可按标题、标签和摘要检索；文章页包含相邻文章与同标签相关文章。每次构建先写入临时目录，成功后完整替换旧 `site/`，不会残留已删除文章。

- 在 `content/assets/` 放本地资源；文章用 `![](assets/figure.png)` 引用，构建时自动复制到 `site/assets/`。
- 用 `[[other-post]]` 引用同一博客中的其他文章；构建后会显示标题、摘要和跳转链接。`other-post` 是目标文章的 `slug`。
- 图片可写为 `![替代文字](assets/figure.svg "图 1：图注")`；构建后自动生成带图注的插图卡片，点击图片可放大查看。
- 文内相对文章链接 `[下一篇](next.md)` 会按目标文章的实际 slug 改写；未自定义 slug 时为 `next.html`。
- 支持 `cover`、`description`、`updated`、`series`、`slug` 等 Front Matter 字段；其中 `cover` 同时生成文章头图和 Open Graph 图片元数据。
- `:::note`、`:::tip`、`:::warning` 块会被渲染为提示引用块；文章图片支持点击放大。
- 阅读器提供阅读进度、宽版排版和大字号开关；Front Matter 的 `updated`、`series`、`cover` 会显示在元数据卡片中。

```yaml
---
title: 文章标题
date: 2026-08-23
updated: 2026-08-25
tags: [分析, 教学]
description: 用于搜索结果和社交分享的摘要
cover: assets/cover.png
series: 泛函分析入门
slug: custom-url
---
```

`slug` 必须是单个文件名（不能包含 `/`、`..` 或 `.html` 后缀），同一站点内不可重复；`date` 与 `updated` 必须是 `YYYY-MM-DD`。Front Matter 支持标量、行内列表和短横线列表；该格式由 Python 构建器与浏览器渲染器共同遵循。

为保护从外部获得的文章，Markdown 链接和图片仅允许普通相对路径、锚点、`http(s)` 与 `mailto`；博客封面仅允许站点内相对路径或 `http(s)` URL。

仓库包含 [GitHub Pages 工作流](.github/workflows/pages.yml)：将默认分支设为 `main`、在仓库设置中启用 GitHub Pages 后，推送会先运行测试、构建 `site/`，再部署页面。

### 测试

```bash
uv run python -m unittest discover -s tests -v
node --test tests/renderer.test.cjs
npm ci
npx playwright install chromium
npm run test:browser
```

PDF 集成测试需要额外安装浏览器和测试依赖：

```bash
uv sync --extra pdf --group pdf-test
uv run --extra pdf python -m playwright install chromium --only-shell
RUN_PDF_TESTS=1 uv run --extra pdf --group pdf-test python -m unittest discover -s tests -p test_md2pdf.py -v
```

上述环境变量写法适用于 macOS/Linux。测试覆盖中文文本、数学引用跳转、图片、分页、
横向纸张及失败时保留旧 PDF；普通测试默认跳过需要浏览器的 PDF 集成测试。
CI 的 `pdf-sample` 工件包含生成的样例 PDF，可用于检查版式。

### 严格发布检查与 CI

发布前建议运行（需要 Python 3.11+ 和 Node.js）：

```bash
uv run python blog.py --strict --base-url https://example.com/blog
```

`--strict` 使用仓库自带的渲染器和固定版本前端库，检查重复标签、未定义的
`\ref`/`\eqref`/`\autoref`、缺失文献和 KaTeX 解析错误；同时检查
`[[slug]]`、内联 Markdown 本地链接/图片及封面路径。外部 URL 不联网检查，
普通 HTML 片段锚点和引用式 Markdown 链接不在这轮路径校验范围内。
路径错误附文件名和行号，渲染错误附文件名与标签/公式；失败时保留原站点。
普通预览仍可不加 `--strict`。

`index`、`tags`、`search` 是保留 slug。文章间 `.md` 链接会依据目标文章的
自定义 slug 重写，代码示例不受影响。外部 `https://` 封面保持原 URL。

所有分支推送和 PR 都执行测试及严格构建；仅 `main` 可进入单独的部署 job。
浏览器测试检查最终构建产物；独立 PDF job 检查导出功能并上传样例 PDF。部署等待构建与 PDF 检查成功后，直接复用站点产物。生产地址默认使用项目的
GitHub Pages 地址；使用自定义域名时设置仓库变量 `SITE_BASE_URL`。
仍需在 GitHub 仓库设置中启用 Pages，并选择 GitHub Actions 作为发布来源。
Pylint 在 Python 3.11/3.12 上检查错误级问题；风格告警暂不作为发布门槛。

阅读器、博客、HTML 和 PDF 导出共用 `prepareDocument()`：代码先隔离，文献按源码
顺序编号（缺失文献保留编号槽位），公式引用具有真实跳转锚点。

## 📐 数学环境

所有 KaTeX 支持的环境开箱即用，包括：

| 类别 | 环境 |
|---|---|
| 矩阵 | `matrix`, `pmatrix`, `bmatrix`, `Bmatrix`, `vmatrix`, `Vmatrix`, `smallmatrix` 及全部 `*` 变体 |
| 数组 | `array`（含 `|` `:` 竖线、`\hline`、`\hdashline`）, `subarray`, `darray` |
| 多行对齐 | `align`, `aligned`, `alignat`, `gather`, `gathered`, `equation`, `multline`, `split`, `flalign` |
| 分支 | `cases`, `rcases`, `dcases`, `drcases` |

```markdown
行内公式：$E = mc^2$

显示公式：
$$ \int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi} $$

LaTeX 原生定界符也支持：
\[
\nabla \times \mathbf{B} = \mu_0 \mathbf{J}
\]
```

### 裸环境语法（本阅读器扩展）

可以直接写 LaTeX 的多行环境而不用包 `$`/`$$`——Markdown 引擎不会破坏其中的 `_`、`*` 等字符：

```latex
\begin{align*}
(x+y)^2 &= x^2 + 2xy + y^2 \\
(x-y)^2 &= x^2 - 2xy + y^2
\end{align*}
```

## 📖 新语法：定理环境（AMSL 风格）

这是本阅读器的核心扩展。支持 9 种环境，带中文标题和自动编号：

| 环境 | 渲染效果 | 计数器 |
|---|---|---|
| `theorem` | **定理 1 (标题).** | 与 lemma/proposition/corollary/conjecture 共享 |
| `lemma` | **引理 1 (标题).** | 同上 |
| `proposition` | **命题 1.** | 同上 |
| `corollary` | **推论 1.** | 同上 |
| `conjecture` | **猜想 1.** | 同上 |
| `definition` | 定义 1. | 独立计数器 |
| `example` | 例 1. | 独立计数器 |
| `remark` | 注 1. | 独立计数器 |
| `proof` | 证明. …… ∎ | 无编号，末尾自动 QED 符号 |

### 基本语法

```latex
\begin{theorem}[标题]{标签}
定理内容……
\end{theorem}
```

参数顺序灵活，`[方括号]` 是标题，`{花括号}` 是标签，两种写法均可：

```latex
\begin{theorem}{thm:pyth}[勾股定理]   % 标签在前、标题在后
...
\end{theorem}

\begin{theorem}[勾股定理]{thm:pyth}   % 标题在前、标签在后
...
\end{theorem}

\begin{theorem}{label=thm:pyth}       % 显式 label= 写法
...
\end{theorem}
```

- 不需要编号时用星号版本：`\begin{theorem*}...\end{theorem*}`
- `proof` 环境不编号，以「证明.」开头、∎ 结尾

### 完整示例

```latex
\begin{definition}{def:metric}[度量空间]
设 $X$ 是集合。若映射 $d: X \times X \to \RR$ 满足非负性、对称性与三角不等式，
则称 $(X, d)$ 为度量空间。
\end{definition}

\begin{theorem}{thm:pythagoras}[勾股定理]
若角 $C = 90^\circ$，则
$$ a^2 + b^2 = c^2. \label{eq:pyth} $$
\end{theorem}

\begin{proof}
由引理 1 立得。
\end{proof}
```

渲染效果（示意）：

> **定义 1 (度量空间).** 设 $X$ 是集合……
>
> **定理 1 (勾股定理).** 若角 $C = 90°$，则 $a^2 + b^2 = c^2$. （右侧有编号 (1)）
>
> **证明.** 由引理 1 立得。 ∎

## 🔗 新语法：交叉引用（Crossref）

LaTeX 用户熟悉的引用系统完整移植：

| 命令 | 效果 |
|---|---|
| `\label{x}` | 放在定理的 `{}` 参数里给定理打标签；放在公式内则自动转为公式编号 `\tag{n}` |
| `\ref{x}` | 渲染为纯数字链接，如 `1` |
| `\eqref{x}` | 带括号，如 `(1)` |
| `\autoref{x}` | 自动加类型前缀，如 `定理 1`、`定义 1`、`式 1` |

所有引用渲染为**可点击链接**，跳转到目标位置。引用未定义的标签会显示红色警告 `?? (x)`，方便排查。

```markdown
由式 \eqref{eq:pyth} 可知两直角边平方和等于斜边平方，
结合 \autoref{def:metric} 中距离的正性即得结论。
```

编号规则：

- 定理类环境按共享计数器递增（定义、定理、引理、推论各归其位，与 LaTeX 的 `\newtheorem` 共享计数器惯例一致）
- 每个含 `\label` 的公式独立编号，从 1 开始
- 编号在每次重新渲染时重算，编辑实时预览时始终准确

## 📚 新语法：BibTeX 引用与参考文献

阅读器支持两种引用写法，都会渲染成按首次出现顺序编号的可点击链接：

```markdown
经典结果参见 \cite{duoandikoetxea2001}。
也支持 Pandoc 风格的 [@duoandikoetxea2001]。
```

文献库可以通过工具栏的“📚 导入 BibTeX”按钮加载本地 `.bib` 文件，也可以写在文章内的 `bibtex` 代码块中。后者适合博客和离线导出，因为文献会随 Markdown 一起发布：

````markdown
```bibtex
@book{duoandikoetxea2001,
  author = {Javier Duoandikoetxea},
  title = {Fourier Analysis},
  publisher = {American Mathematical Society},
  year = {2001}
}
```
````

渲染时 `bibtex` 代码块不会显示，页面末尾会自动生成“参考文献”列表。当前支持常见的 `article`、`book`、`inproceedings` 等条目以及 `author`、`title`、`journal`、`booktitle`、`publisher`、`year` 字段；未找到的 key 会显示红色提示。

## 🧮 内置宏

可在源码顶部的 `MACROS` 对象中扩展：

| 宏 | 展开 | 宏 | 展开 |
|---|---|---|---|
| `\RR` | `\mathbb{R}` | `\dd` | `\mathrm{d}` |
| `\NN` / `\ZZ` / `\QQ` / `\CC` | $\mathbb{N}$/$\mathbb{Z}$/$\mathbb{Q}$/$\mathbb{C}$ | `\norm{x}` | `\left\|x\right\|` |
| `\EE` | `\mathbb{E}` | `\abs{x}` | `\left\vert x\right\vert`（单竖线绝对值） |

## ⚙️ 技术实现

浏览器运行时资源固定在仓库的 `assets/vendor/`，无需 CDN：

- [marked](https://github.com/markedjs/marked) — Markdown 解析
- [KaTeX](https://katex.org/) — 数学渲染（速度快、覆盖绝大多数 LaTeX 环境）
- [highlight.js](https://highlightjs.org/) — 代码高亮

渲染流程：

1. 解析 Front Matter 与内嵌 BibTeX，隔离代码示例。
2. 按源码顺序收集文献引用和公式标签，再提取定理环境。
3. 保护数学区域，交给 marked 解析 Markdown；使用 KaTeX 渲染公式。
4. 回填定理，解析前向引用，生成公式锚点与参考文献。
5. 添加目录、插图和复制按钮等阅读功能。

PDF 导出先使用 HTML 导出模板，再由 Python Playwright 等待字体、图片和渲染完成，
应用打印样式后调用 Chromium 生成 PDF。中间 HTML 在临时目录中清理，
成功后才替换目标 PDF。

## 📁 项目结构

```
simplemathblog/
├── index.html    # 阅读器（HTML + CSS + JS 单文件）
├── renderer.js    # 共享渲染管线：数学、定理、引用、BibTeX、代码高亮
├── md2html.py    # 增强 Markdown → 离线 HTML（左侧目录）
├── md2pdf.py     # 增强 Markdown → PDF（Playwright + Chromium）
├── server.py     # 本地预览与监视重建
├── frontmatter.py # Python 元数据解析
├── tests/        # Python、渲染、浏览器与 PDF 回归测试
├── pyproject.toml # Python 可选依赖与测试依赖
├── uv.lock       # Python 依赖锁文件
├── blog.py       # 静态博客系统：content/ → site/（首页/归档/文章页）
├── assets/vendor/ # 固定版本的 marked、KaTeX、highlight.js 运行时资源
├── content/      # 博客文章目录（.md，含示例文章）
└── README.md     # 本文件
```

## 🗺️ 可能的后续方向

- [ ] 按章节编号（Theorem 2.1）
- [ ] 英文界面切换
- [ ] BibTeX 的 CSL 引用样式与更多嵌套字段
- [ ] 博客：归档按年份分组
- [ ] HTML 导出时内联字体和资源，实现真正的单文件 HTML

---

基于开源组件构建 · marked (MIT) · KaTeX (MIT) · highlight.js (BSD-3)
