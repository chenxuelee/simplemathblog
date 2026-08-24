# Enhanced Markdown Reader（增强 Markdown 阅读器）

一个单文件、零构建的 Markdown 阅读器，专为**数学文档**设计：完整支持 KaTeX 数学环境、AMSL 定理环境和 LaTeX 风格的交叉引用。

参考了 Typora / Obsidian / GitHub 等主流方案的技术路线（marked + KaTeX），并在其基础上做了数学感知的解析管线增强。附带 Python 导出器，可将文档转换为带左侧目录的单文件 HTML。

## ✨ 特性

- **完整数学环境支持** —— `$...$`、`$$...$$`、`\(...\)`、`\[...\]` 四种定界符，以及不包 `$` 直接书写的裸 `\begin{align}` 等环境
- **AMSL 定理环境** —— `theorem`、`lemma`、`proposition`、`corollary` 等 9 种环境，自动编号、样式化渲染
- **交叉引用（crossref）** —— `\label` / `\ref` / `\eqref` / `\autoref`，引用渲染为可点击链接
- **Front Matter** —— YAML 元数据块渲染为标题卡片（作者/日期/标签），支持自动目录
- **单文件 HTML 导出** —— 附带 `md2html.py`，一键转换为带左侧目录侧栏的独立 HTML
- **静态博客系统** —— 附带 `blog.py`，`content/` 目录一键生成完整站点（首页 / 标签归档 / 文章页）
- **自定义宏** —— 内置 `\RR`、`\norm` 等常用宏，可自行扩展
- **阅读体验** —— GFM 表格与任务列表、代码高亮、深色模式自适应、长公式横向滚动
- **使用方式** —— 打开本地 `.md` 文件、拖拽进窗口、或直接在编辑器中书写实时预览；一键导出 PDF

## 🚀 快速开始

无需安装，直接用浏览器打开 `index.html` 即可。

```bash
# 或者本地起个服务（可选）
python3 -m http.server 8000 --directory .
# 浏览器访问 http://localhost:8000
```

预览生成的博客时，可以使用项目内置的无缓存服务器：

```bash
python3 server.py                  # 服务 site/，默认 http://127.0.0.1:8000
python3 server.py --build --port 8080  # 先重建，再以 8080 端口服务
```

界面按钮：

| 按钮 | 功能 |
|---|---|
| 📂 打开文件 | 加载本地 `.md` / `.markdown` / `.txt` 文件 |
| ✏️ 编辑源码 | 在源码编辑与渲染预览之间切换，编辑时实时渲染 |
| 🖨️ 导出 PDF | 调用浏览器打印功能 |
| ↔ 宽度 / A 字号 | 切换阅读宽度与字号（记住本机设置） |

也可以把 `.md` 文件直接拖进窗口。

## 📤 导出为单文件 HTML（左侧目录）

`md2html.py` 可以把增强 Markdown 转换为**单个独立 HTML 文件**——目录渲染在左侧固定侧边栏，右侧为正文，滚动时侧栏保持可见：

```bash
# 基本用法（输出同名 .html）
python3 md2html.py notes.md

# 指定输出路径
python3 md2html.py notes.md -o notes_export.html

# 指定其他阅读器版本作为管线来源
python3 md2html.py notes.md --reader /path/to/index.html
```

导出文件的特点：

- **渲染结果与阅读器预览 100% 一致** —— 转换器直接复用 `index.html` 中经过验证的 JS 渲染管线（数学环境、定理环境、交叉引用、Front Matter 全部支持），Python 只负责把 Markdown 源码嵌入模板
- **左侧目录侧栏** —— 自动收集 h2/h3 生成可点击目录（h3 缩进一级）；窄屏（<900px）自动折叠为顶部块；打印时隐藏
- **侧栏开关** —— Front Matter 中 `toc: false` 可隐藏侧栏（默认显示）
- **深色模式** —— 与阅读器一致，跟随系统设置
- **零依赖** —— 只需 Python 3 标准库；KaTeX/marked/highlight.js 走 CDN，联网即可渲染
- **输入保护** —— 仅接受 `.md` / `.markdown` / `.txt` 输入，防止误覆盖其他文件

侧栏标题的取值优先级：Front Matter `title` → 文档第一个 `# h1` → 文件名。

## 📝 静态博客系统

`blog.py` 把项目扩展为一个完整的**数学博客**：`content/` 目录放文章，一条命令生成整个静态站点。

```bash
python3 blog.py                              # content/ → site/
python3 blog.py --posts myposts --out dist   # 自定义文章/输出目录
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

文章页内嵌阅读器的 JS 渲染管线，**数学环境、定理环境、交叉引用、Front Matter 全部支持**，渲染效果与阅读器预览一致。

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

写作流程：往 `content/` 丢 `.md` → `python3 blog.py` → 完成。部署只需把 `site/` 上传到任意静态托管（GitHub Pages、Netlify、Vercel 等）。

示例文章见 `content/fourier-series.md` 与 `banach-fixed-point.md`（覆盖定理环境 + crossref + 数学环境 + Front Matter 的完整用法）。

### 发布与写作增强

构建器还会生成 `search.html`、`search-index.json`、`rss.xml` 和 `sitemap.xml`。首页与搜索页均可按标题、标签和摘要检索；文章页包含相邻文章与同标签相关文章。

- 在 `content/assets/` 放本地资源；文章用 `![](assets/figure.png)` 引用，构建时自动复制到 `site/assets/`。
- 文内相对文章链接会由 `[下一篇](next.md)` 自动改为 `next.html`。
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

仓库包含 [GitHub Pages 工作流](.github/workflows/pages.yml)：将默认分支设为 `main`、在仓库设置中启用 GitHub Pages 后，推送会先运行测试、构建 `site/`，再部署页面。

### 测试

```bash
python3 -m unittest discover -s tests -v
```

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
\begin{theorem}[标题]{标签}[可选：第二个参数会被当作标签]
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
- `proof` 环境无参数，渲染为斜体「证明.」开头、右对齐 ∎ 结尾

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

## 🧮 内置宏

可在源码顶部的 `MACROS` 对象中扩展：

| 宏 | 展开 | 宏 | 展开 |
|---|---|---|---|
| `\RR` | `\mathbb{R}` | `\dd` | `\mathrm{d}` |
| `\NN` / `\ZZ` / `\QQ` / `\CC` | $\mathbb{N}$/$\mathbb{Z}$/$\mathbb{Q}$/$\mathbb{C}$ | `\norm{x}` | `\left\|x\right\|` |
| `\EE` | `\mathbb{E}` | `\abs{x}` | `\left\vert x\right\vert`（单竖线绝对值） |

## ⚙️ 技术实现

单 HTML 文件，依赖通过 CDN 加载：

- [marked](https://github.com/markedjs/marked) — Markdown 解析
- [KaTeX](https://katex.org/) — 数学渲染（速度快、覆盖绝大多数 LaTeX 环境）
- [highlight.js](https://highlightjs.org/) — 代码高亮

渲染管线（顺序很关键）：

```
源文本
 │
 ├─ ① 提取定理环境 → 占位符（防止 Markdown 破坏内部语法）
 ├─ ② 处理 \label → 登记编号；\ref/\eqref/\autoref → 占位符
 ├─ ③ 保护数学区域（$...$、$$...$$、\(...\)、\[...\]）→ 占位符
 ├─ ④ marked 解析剩余 Markdown
 ├─ ⑤ KaTeX 渲染占位的公式（含宏展开）
 ├─ ⑥ 回填定理块（内部再做一遍数学+引用处理）
 └─ ⑦ 回填交叉引用 → 可点击链接
```

关键设计点：

- **占位符隔离** —— 数学与定理内容在 Markdown 解析前被摘出，避免 `*`、`_`、反斜杠等被误解析
- **两遍引用** —— 先收集所有 `\label` 建立编号表，再统一替换引用，因此前向引用（引用后文）也能正确解析
- **兜底渲染** —— 未包裹 `$` 的裸 `equation`/`align`/`gather` 等环境由 TreeWalker 二次扫描补渲染

## 📁 项目结构

```
md-reader/
├── index.html    # 阅读器（HTML + CSS + JS 单文件）
├── md2html.py    # 导出器：增强 Markdown → 单文件 HTML（左侧目录）
├── blog.py       # 静态博客系统：content/ → site/（首页/归档/文章页）
├── content/      # 博客文章目录（.md，含示例文章）
└── README.md     # 本文件
```

## 🗺️ 可能的后续方向

- [ ] 按章节编号（Theorem 2.1）
- [ ] 英文界面切换
- [ ] 侧栏目录滚动高亮当前章节
- [ ] 博客：RSS/Atom 订阅、归档按年份分组
- [ ] 导出时内联 KaTeX 字体实现完全离线

---

基于开源组件构建 · marked (MIT) · KaTeX (MIT) · highlight.js (BSD-3)
