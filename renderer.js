/* Shared Enhanced Markdown rendering pipeline. */
// ============ 核心：数学感知的 Markdown 渲染管线 ============
// 关键点：在 marked 解析前，先把数学区域提取为占位符，
// 避免 $...$ 内部的 *、_、\\ 等被 Markdown 引擎破坏。

const PLACEHOLDER_PREFIX = "\u0000MATH";
let mathStore = [];
let externalBibtex = "";
let bibEntries = {};
let citationOrder = [];
let codeStore = [];
let renderDiagnostics = [];

// Protect code before ANY extension processes labels, citations or math.
function protectCode(src) {
  return src.replace(/^( {0,3})(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^\1\2[ \t]*$|(?![\s\S]))|(`+)[\s\S]*?\3(?!`)/gm, code => {
    const token = `CODEZ${codeStore.length}ENDCODE`;
    codeStore.push(code);
    return token;
  });
}
function restoreCode(src) {
  return src.replace(/CODEZ(\d+)ENDCODE/g, (token, n) => codeStore[+n] ?? token);
}

function prepareDocument(src, bibliography = "") {
  thmStore = []; crefStore = []; codeStore = []; renderDiagnostics = [];
  refTable = {}; eqCounter = 0;
  bibEntries = parseBibtex(bibliography); citationOrder = [];
  for (const k in counters) delete counters[k];
  const { meta, body } = parseFrontMatter(src);
  // BibTeX fences are intentionally consumed; all other code stays literal.
  let s = protectCode(extractBibtexBlocks(body));
  const labels = new Set();
  for (const match of s.matchAll(/\\label\{([^}]+)\}|\\begin\{(?:theorem|lemma|proposition|corollary|conjecture|definition|example|remark)\*?\}((?:\[[^\]]*\]|\{[^}]*\}){0,2})/g)) {
    const label = match[1] || parseThmArgs(match[2] || "").label;
    if (label && labels.has(label)) renderDiagnostics.push(`重复标签：${label}`);
    if (label) labels.add(label);
  }
  // Collect citations in source order, including theorem/proof bodies.
  s = extractTheorems(processCrossrefs(processCitations(preprocessMarkdown(s))));
  let html = restoreMath(marked.parse(restoreCode(protectMath(s))));
  html = renderTheorems(html);
  for (const { label } of crefStore) {
    if (!refTable[label]) renderDiagnostics.push(`未定义引用：${label}`);
  }
  for (const key of citationOrder) {
    if (!bibEntries[key]) renderDiagnostics.push(`缺失文献：${key}`);
  }
  return { meta, html };
}

function equationAnchors(tex, html) {
  const ids = Object.entries(refTable).filter(([, entry]) =>
    entry.kind === "equation" && tex.includes(`\\tag{${entry.number}}`));
  return ids.map(([label]) => `<span id="lbl-${esc(label)}" class="equation-anchor"></span>`).join("") + html;
}

function protectMath(src) {
  mathStore = [];
  const stash = (tex, display) => {
    const token = PLACEHOLDER_PREFIX + (mathStore.length) + "\u0000";
    mathStore.push({ tex, display });
    return token;
  };
  let out = "";
  let i = 0, n = src.length;
  while (i < n) {
    const bare = src.slice(i).match(/^\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|eqnarray\*?|split|flalign\*?)\}[\s\S]*?\\end\{\1\}/);
    if (bare) { out += stash(bare[0], true); i += bare[0].length; continue; }
    // 跳过代码块/行内代码，其中的 $ 不算数学定界符
    const fence = src.slice(i).match(/^(```+|~~~+)/);
    if (fence) {
      const fenceStr = fence[1];
      const end = src.indexOf("\n" + fenceStr.trim()[0].repeat(fenceStr.length), i + fenceStr.length);
      const stop = end === -1 ? n : end + fenceStr.length + 1;
      out += src.slice(i, stop); i = stop; continue;
    }
    if (src.startsWith("$$", i)) {
      // $$ ... $$ 或 $$ ... $ （多行）
      let j = src.indexOf("$$", i + 2);
      // 处理 "$$\n...\n$$" 与 "$$...$$"
      if (j !== -1 && j > i + 2) { out += stash(src.slice(i + 2, j).trim(), true); i = j + 2; continue; }
    }
    if (src[i] === "\\" && src[i + 1] === "[") {          // \[ ... \] display
      const j = src.indexOf("\\]", i + 2);
      if (j !== -1) { out += stash(src.slice(i + 2, j).trim(), true); i = j + 2; continue; }
    }
    if (src[i] === "\\" && src[i + 1] === "(") {          // \( ... \) inline
      const j = src.indexOf("\\)", i + 2);
      if (j !== -1) { out += stash(src.slice(i + 2, j).trim(), false); i = j + 2; continue; }
    }
    if (src[i] === "$" && src[i + 1] !== "$") {           // $ ... $ inline
      const j = findInlineDollarEnd(src, i + 1);
      if (j !== -1) { out += stash(src.slice(i + 1, j).trim(), false); i = j + 1; continue; }
    }
    out += src[i++];
  }
  return out;
}

// 行内 $ 结束位置：不允许紧贴空白开头，内部不能有换行后紧跟空行的规则从简
function findInlineDollarEnd(s, start) {
  for (let k = start; k < s.length; k++) {
    if (s[k] === "\\") { k++; continue; }        // 转义 \$ 等
    if (s[k] === "\n") return -1;                 // 行内公式不跨行
    if (s[k] === "$") {
      if (s[start] === undefined || /[\s]/.test(s[start])) return -1;
      return k;
    }
  }
  return -1;
}

function restoreMath(html) {
  return html.replace(new RegExp(PLACEHOLDER_PREFIX + "(\\d+)\u0000", "g"), (_, idx) => {
    const m = mathStore[+idx];
    try {
      const rendered = katex.renderToString(m.tex, {
        displayMode: m.display,
        throwOnError: true,
        strict: false,
        trust: false,
        macros: MACROS,
      }).replace("katex-display", m.display ? "katex-display eq-block" : "katex");
      if (rendered.includes('class="katex-error"')) renderDiagnostics.push(`无效公式：${m.tex}`);
      return equationAnchors(m.tex, rendered);
    } catch (e) {
      renderDiagnostics.push(`无效公式：${m.tex} — ${e.message}`);
      return `<span class="math-error">${esc(m.tex)} — ${esc(e.message)}</span>`;
    }
  });
}

// 用户可扩展的宏表
const MACROS = {
  "\\RR": "\\mathbb{R}", "\\NN": "\\mathbb{N}", "\\ZZ": "\\mathbb{Z}",
  "\\QQ": "\\mathbb{Q}", "\\CC": "\\mathbb{C}", "\\EE": "\\mathbb{E}",
  "\\dd": "\\mathrm{d}", "\\norm": "\\left\\|#1\\right\\|",
  "\\abs": "\\left|#1\\right|",
};

// ============ 定理环境（AMSL 风格）============
// 支持 \begin{theorem}[标题]{label=xxx} ... \end{theorem} 及
// \begin{theorem}{thm:pythagoras} 两种 label 写法
const THM_KINDS = {
  theorem:     { zh: "定理",   en: "Theorem",     counter: "thm" },
  lemma:       { zh: "引理",   en: "Lemma",       counter: "thm" },
  proposition: { zh: "命题",   en: "Proposition", counter: "thm" },
  corollary:   { zh: "推论",   en: "Corollary",   counter: "thm" },
  conjecture:  { zh: "猜想",   en: "Conjecture",  counter: "thm" },
  definition:  { zh: "定义",   en: "Definition",  counter: "def" },
  example:     { zh: "例",     en: "Example",     counter: "ex" },
  remark:      { zh: "注",     en: "Remark",      counter: "rmk", bodyItalic: true },
  proof:       { zh: "证明",   en: "Proof" },
};
const THM_ENV_RE = /[ \t]*(?:(?:^|\n)```[\s\S]*?```(?:\n|$))|\\begin\{(theorem|lemma|proposition|corollary|conjecture|definition|example|remark|proof)\*?\}((?:\[[^\]]*\]|\{[^}]*\}){0,2})([\s\S]*?)\\end\{\1\*?\}/g;

// 引用表：label -> { number, kind, text }
let refTable = {};
let eqCounter = 0;

function parseThmArgs(argStr) {
  let title = "", label = null;
  const re = /\[([^\]]*)\]|\{([^}]*)\}/g; let m;
  while ((m = re.exec(argStr))) {
    if (m[1] !== undefined) title = m[1].trim();
    else {
      const inner = m[2].trim();
      const lm = inner.match(/^label\s*=\s*(.+)$/i);
      label = lm ? lm[1].trim() : (inner || null);
    }
  }
  return { title, label };
}

function extractTheorems(src) {
  return src.replace(THM_ENV_RE, (match, kind, argStr, body) => {
    if (!kind) return match; // 是代码块，原样保留
    const starred = match.includes("\\begin{" + kind + "*}");
    const isProof = kind === "proof";
    const { title, label } = parseThmArgs(argStr || "");
    const token = "\u0000THM" + thmStore.length + "\u0000";
    thmStore.push({ kind, title, label, body: body.trim(), starred, isProof });
    return "\n\n" + token + "\n\n";
  });
}

let thmStore = [];
const counters = {};

function renderTheorems(html) {
  return html.replace(/\u0000THM(\d+)\u0000/g, (_, idx) => {
    const t = thmStore[+idx];
    const meta = THM_KINDS[t.kind];
    let headName;
    if (t.isProof) {
      headName = `<span class="thm-head">${meta.zh}.</span>`;
    } else {
      if (t.starred) {
        headName = `<span class="thm-head"${t.label ? ` id="lbl-${esc(t.label)}"` : ""}>${meta.zh}${starredSuffix(meta)}.</span>`;
        if (t.label) refTable[t.label] = { number: "", kind: t.kind, zh: meta.zh };
      }
      else {
        counters[meta.counter] = (counters[meta.counter] || 0) + 1;
        const num = counters[meta.counter];
        headName = `<span class="thm-head"${t.label ? ` id="lbl-${esc(t.label)}"` : ""}>${meta.zh} ${num}${t.title ? ` <span class="thm-title">(${renderInlineText(t.title)})</span>` : ""}.</span>`;
        if (t.label) refTable[t.label] = { number: num, kind: t.kind, zh: meta.zh };
      }
    }
    const bodyHtml = restoreMath(marked.parse(restoreCode(protectMath(processCrossrefs(t.body)))));
    const qed = t.isProof ? '<span class="qed">∎</span>' : "";
    return `<div class="thm-env ${t.kind}">${headName}<div class="thm-body">${bodyHtml}</div>${qed}</div>`;
  });
}
function starredSuffix(meta){ return ""; }
function renderInlineText(s){ return esc(s); }
function esc(s){
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/\"/g,"&quot;").replace(/'/g,"&#39;");
}

// Markdown may come from files shared by other people. Escaping HTML is not
// sufficient for URLs: javascript: remains executable when used in href.
function safeUrl(value) {
  const url = String(value || "").trim();
  if (!url) return "";
  if (/^(https?:|mailto:|#|\/(?!\/)|\.\.?\/)/i.test(url)) return url;
  return /^[a-z][a-z0-9+.-]*:/i.test(url) ? "" : url; // ordinary relative path
}

// ============ BibTeX citations ============
// Supports a practical BibTeX subset (article/book/inproceedings etc.) and
// keeps citations portable: a fenced `bibtex` block can travel with a note.
function setBibtexSource(source) { externalBibtex = String(source || ""); }
function parseBibtex(source) {
  const entries = {};
  const entryRe = /@(\w+)\s*\{\s*([^,\s]+)\s*,([\s\S]*?)^\s*\}/gm;
  let match;
  while ((match = entryRe.exec(source))) {
    const fields = { type: match[1].toLowerCase(), key: match[2].trim() };
    const fieldRe = /(\w+)\s*=\s*(?:\{([^{}]*)\}|"([^"]*)"|([^,\n]+))\s*,?/g;
    let field;
    while ((field = fieldRe.exec(match[3]))) fields[field[1].toLowerCase()] = (field[2] ?? field[3] ?? field[4] ?? "").trim();
    entries[fields.key] = fields;
  }
  return entries;
}
function extractBibtexBlocks(src) {
  return src.replace(/^```bibtex\s*\n([\s\S]*?)^```\s*$/gmi, (_, bib) => {
    Object.assign(bibEntries, parseBibtex(bib)); return "";
  });
}
function processCitations(src) {
  return src.replace(/\\cite\{([^}]+)\}|\[@([^\]]+)\]/g, (_, latexKeys, markdownKeys) => {
    const keys = (latexKeys || markdownKeys).split(",").map(k => k.trim()).filter(Boolean);
    return keys.map(key => {
      if (!citationOrder.includes(key)) citationOrder.push(key);
      return `CITEZ${citationOrder.indexOf(key)}ENDCITE`;
    }).join(", ");
  });
}
function renderCitations(root) {
  root.innerHTML = root.innerHTML.replace(/CITEZ(\d+)ENDCITE/g, (_, index) => {
    const key = citationOrder[+index];
    return bibEntries[key] ? `<a class="cite-link" href="#ref-${esc(key)}">[${+index + 1}]</a>` : `<span class="citation-missing">[? ${esc(key)}]</span>`;
  });
}
function bibliographyText(entry) {
  const author = entry.author || "Unknown author";
  const title = entry.title || entry.key;
  const venue = entry.journal || entry.booktitle || entry.publisher || "";
  return [author, `“${title}.”`, venue, entry.year].filter(Boolean).join(" ");
}
function renderBibliography(root) {
  const cited = citationOrder.filter(key => bibEntries[key]);
  if (!cited.length) return;
  const items = cited.map(key => `<li id="ref-${esc(key)}"><span class="ref-number">[${citationOrder.indexOf(key) + 1}]</span> ${esc(bibliographyText(bibEntries[key]))}</li>`).join("");
  root.insertAdjacentHTML("beforeend", `<section class="bibliography"><h2>参考文献</h2><ol>${items}</ol></section>`);
}

// ============ 交叉引用 ============
// 处理 \ref{...}, \eqref{...}, \autoref{...} —— 在公式渲染前替换为占位，
// 公式渲染后回填为链接。同时处理公式内的 \label -> 自动 \tag。
function processCrossrefs(src) {
  // 1) 公式内 \label{x}：登记编号并转为 \tag{n}
  src = src.replace(/\\label\{([^}]+)\}/g, (m, label) => {
    if (refTable[label]) return m; // 已被定理环境占用
    eqCounter += 1;
    refTable[label] = { number: eqCounter, kind: "equation", zh: "式" };
    return `\\tag{${eqCounter}}`;
  });
  // 2) 正文中的引用 -> 占位符（防止 Markdown 破坏）
  return src.replace(/(\\eqref|\\autoref|\\ref)\{([^}]+)\}/g, (m, cmd, label) => {
    const idx = crefStore.length;
    crefStore.push({ cmd, label });
    return `XREFZ${idx}ENDX`;
  });
}
let crefStore = [];

function resolveCrossrefs(root) {
  // 直接在整个容器的 innerHTML 上做替换，占位符 \u0000 不会出现在正常 HTML 中，
  // 且此时公式已渲染完毕，不会被破坏。
  let html = root.innerHTML;
  if (!html.includes("XREFZ")) return;
  html = html.replace(/XREFZ(\d+)ENDX/g, (_, i) => {
    const { cmd, label } = crefStore[+i];
    const entry = refTable[label];
    if (!entry) return `<span class="math-error">?? (${esc(label)})</span>`;
    let text = `${entry.number}`;
    if (cmd === "\\eqref") text = `(${text})`;
    else if (cmd === "\\autoref") text = `${entry.zh} ${entry.number}`;
    return `<a class="ref-link" href="#lbl-${esc(label)}">${text}</a>`;
  });
  root.innerHTML = html;
}

// marked 配置
const markdownRenderer = new marked.Renderer();
markdownRenderer.html = raw => esc(raw);
markdownRenderer.link = (href, title, text) => {
  const safe = safeUrl(href);
  return safe ? `<a href="${esc(safe)}"${title ? ` title="${esc(title)}"` : ""}>${text}</a>` : text;
};
markdownRenderer.image = (href, title, text) => {
  const safe = safeUrl(href);
  return safe ? `<img src="${esc(safe)}" alt="${esc(text || "")}"${title ? ` data-caption="${esc(title)}"` : ""}>` : esc(text || "");
};
markdownRenderer.code = (code, infostring) => {
  // marked v12 calls renderers with a token object; older supported versions
  // pass (code, infostring). Supporting both keeps exported pages portable.
  const token = typeof code === "object" && code !== null ? code : null;
  const text = token ? token.text : String(code);
  const lang = String(token ? token.lang || "" : infostring || "").trim().split(/\s+/)[0];
  let highlighted;
  try {
    highlighted = lang && hljs.getLanguage(lang)
      ? hljs.highlight(text, { language: lang }).value
      : hljs.highlightAuto(text).value;
  } catch { highlighted = esc(text); }
  const languageClass = lang ? ` language-${esc(lang)}` : "";
  return `<pre><code class="hljs${languageClass}">${highlighted}</code></pre>\n`;
};
marked.setOptions({
  gfm: true, breaks: false,
  renderer: markdownRenderer,
});

// ============ Front Matter (YAML) ============
// 解析文档开头的 --- ... --- 元数据块。支持标量、行内数组 [a, b]、
// 短横线列表、嵌套一层对象；toc: true 时自动生成目录。
function parseFrontMatter(src) {
  const m = src.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return { meta: null, body: src };
  const meta = {};
  let currentKey = null;
  for (const line of m[1].split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    // 列表项 "- item"
    const li = line.match(/^\s+-\s+(.+)$/);
    if (li && currentKey) {
      if (!Array.isArray(meta[currentKey])) meta[currentKey] = [];
      meta[currentKey].push(stripQuotes(li[1].trim()));
      continue;
    }
    const kv = line.match(/^([A-Za-z0-9_-]+)\s*:\s*(.*)$/);
    if (!kv) continue;
    const key = kv[1]; let val = kv[2].trim();
    currentKey = key;
    if (val === "") { meta[key] = ""; continue; }
    // 行内数组 [a, b, c]
    const arr = val.match(/^\[(.*)\]$/);
    if (arr) { meta[key] = arr[1] ? arr[1].split(",").map(s => stripQuotes(s.trim())) : []; continue; }
    meta[key] = stripQuotes(val);
  }
  return { meta, body: src.slice(m[0].length) };
}
function stripQuotes(s) {
  return ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))
    ? s.slice(1, -1) : s;
}

function renderFrontMatter(meta) {
  const esc2 = esc;
  let html = '<div class="fm-card">';
  if (meta.title) html += `<h1>${esc2(meta.title)}</h1>`;
  const items = [];
  for (const k of ["author", "date", "updated", "series", "affiliation", "email"]) {
    if (meta[k]) items.push(`<span><b>${esc2(k)}</b>: ${esc2(Array.isArray(meta[k]) ? meta[k].join(", ") : meta[k])}</span>`);
  }
  if (items.length) html += `<div class="fm-meta">${items.join("")}</div>`;
  if (meta.tags) {
    const tags = Array.isArray(meta.tags) ? meta.tags : String(meta.tags).split(/[,，]\s*/);
    if (tags.length) html += `<div style="margin-top:.5em"><span class="fm-tags">${tags.map(t=>`<span class="fm-tag">${esc2(t)}</span>`).join("")}</span></div>`;
  }
  if (meta.cover && safeUrl(meta.cover)) html += `<img class="cover zoomable" src="${esc2(safeUrl(meta.cover))}" alt="${esc2(meta.title || "封面")}">`;
  html += "</div>";
  return html;
}

// 轻量写作扩展：:::note / :::tip / :::warning 块会变为可移植的引用提示块。
function preprocessMarkdown(src) {
  const labels = { note: "注", tip: "提示", warning: "注意" };
  return src.replace(/^:::(note|tip|warning)(?:\s+([^\n]+))?\n([\s\S]*?)^:::\s*$/gm,
    (_, kind, title, body) => `> **${labels[kind]}${title ? "：" + title.trim() : ""}**\n>\n` +
      body.trim().split("\n").map(line => `> ${line}`).join("\n"));
}

function enhanceImages(root) {
  root.querySelectorAll("img").forEach(img => {
    img.loading = "lazy";
    img.classList.add("zoomable");
    img.onclick = () => {
      const overlay = document.createElement("div");
      overlay.className = "image-lightbox";
      const full = document.createElement("img");
      full.src = img.currentSrc || img.src; full.alt = img.alt;
      overlay.append(full); overlay.onclick = () => overlay.remove();
      document.body.append(overlay);
    };
    const caption = img.dataset.caption;
    if (caption && !img.closest("figure")) {
      const figure = document.createElement("figure");
      figure.className = "illustration";
      const parent = img.parentElement;
      if (parent?.tagName === "P" && parent.childNodes.length === 1) parent.replaceWith(figure);
      else img.before(figure);
      figure.append(img);
      const figcaption = document.createElement("figcaption");
      figcaption.textContent = caption;
      figure.append(figcaption);
    }
  });
}

async function copyText(value, button) {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const area = document.createElement("textarea");
    area.value = value; document.body.append(area); area.select(); document.execCommand("copy"); area.remove();
  }
  const old = button.textContent; button.textContent = "已复制";
  setTimeout(() => { button.textContent = old; }, 1200);
}

// Add copy controls after all transformations so code and TeX source remain intact.
function enhanceCopyButtons(root) {
  root.querySelectorAll("pre").forEach(pre => {
    if (pre.querySelector(":scope > .copy-button")) return;
    const button = document.createElement("button");
    button.className = "copy-button"; button.type = "button"; button.textContent = "复制代码";
    button.onclick = () => copyText(pre.querySelector("code")?.textContent || "", button);
    pre.append(button);
  });
}

let stopTocSpy = () => {};
function setupTocScrollSpy(container, nav) {
  stopTocSpy();
  if (!nav) return;
  const links = [...nav.querySelectorAll('a[href^="#"]')];
  const pairs = links.map(link => [link, container.querySelector(link.getAttribute("href"))]).filter(([, head]) => head);
  if (!pairs.length) return;
  const update = () => {
    let active = pairs[0][0];
    for (const [link, head] of pairs) if (head.getBoundingClientRect().top <= 130) active = link;
    links.forEach(link => { const on = link === active; link.classList.toggle("toc-active", on); link.toggleAttribute("aria-current", on); });
  };
  window.addEventListener("scroll", update, { passive: true }); update();
  stopTocSpy = () => window.removeEventListener("scroll", update);
}

// toc: true —— 从渲染后的 HTML 收集 h2/h3 生成目录（在标题上加锚点）
function buildToc(container, insertBeforeEl) {
  const heads = container.querySelectorAll("h2, h3");
  if (!heads.length) return null;
  let i = 0;
  const lis = [];
  heads.forEach(h => {
    if (!h.id) h.id = "sec-" + (++i);
    lis.push(`<li style="margin-left:${h.tagName === "H3" ? "1.2em" : "0"}"><a href="#${esc(h.id)}">${esc(h.textContent)}</a></li>`);
  });
  insertBeforeEl.insertAdjacentHTML("beforebegin",
    `<div class="toc-box"><div class="toc-title">目录</div><ol>${lis.join("")}</ol></div>`);
  return insertBeforeEl.previousElementSibling;
}

function render(src) {
  const prepared = prepareDocument(src, externalBibtex);
  const { meta } = prepared;
  if (meta && meta.title) document.title = meta.title + " · MD Reader";
  else document.title = "Enhanced Markdown Reader";
  // 管线顺序：定理提取 → 交叉引用占位 → 数学保护 → marked 解析
  let html = prepared.html;
  if (meta) html = renderFrontMatter(meta) + html;
  container.innerHTML = html;
  // toc: true —— 目录插在元数据卡片之后（无卡片则在最前）
  if (meta && /^(true|yes)$/i.test(String(meta.toc))) {
    const anchor = container.querySelector(".fm-card") || container.firstElementChild;
    if (anchor) setupTocScrollSpy(container, buildToc(container, anchor)); else { const d = document.createElement("div"); container.prepend(d); setupTocScrollSpy(container, buildToc(container, d)); }
  }
  renderBareEnvironments();
  resolveCrossrefs(container);
  renderCitations(container);
  renderBibliography(container);
  enhanceImages(container);
  enhanceCopyButtons(container);
}

// 对未包裹 $ 的 \begin{equation}/align/gather 等做兜底渲染
const ENV_RE = /\u0000?\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|eqnarray\*?|split|flalign\*?)\}[\s\S]*?\\end\{\1\}\u0000?/g;
function renderBareEnvironments() {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const targets = [];
  while (walker.nextNode()) {
    if (!walker.currentNode.parentElement.closest("pre, code") && ENV_RE.test(walker.currentNode.textContent)) targets.push(walker.currentNode);
    ENV_RE.lastIndex = 0;
  }
  targets.forEach(node => {
    const fragment = document.createDocumentFragment();
    const text = node.textContent;
    const re = new RegExp(ENV_RE.source, "g");
    let last = 0, match;
    while ((match = re.exec(text))) {
      fragment.append(document.createTextNode(text.slice(last, match.index)));
      const span = document.createElement("span");
      try {
        span.innerHTML = equationAnchors(match[0], katex.renderToString(match[0].replace(/^\u0000|\u0000$/g, ""),
          { displayMode: true, throwOnError: false, strict: false, trust: false, macros: MACROS }));
        fragment.append(span);
      } catch {
        fragment.append(document.createTextNode(match[0]));
      }
      last = re.lastIndex;
    }
    fragment.append(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(fragment, node);
  });
}
