const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function render(source) {
  const context = vm.createContext({ console, source });
  for (const file of ['assets/vendor/marked.min.js', 'assets/vendor/katex/katex.min.js',
    'assets/vendor/highlight.min.js', 'renderer.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  return vm.runInContext(`(() => {
    const result = prepareDocument(source);
    const root = { innerHTML: result.html, insertAdjacentHTML: (_, html) => root.innerHTML += html };
    resolveCrossrefs(root); renderCitations(root); renderBibliography(root);
    return { html: root.innerHTML, diagnostics: renderDiagnostics };
  })()`, context);
}

test('code is opaque to math, labels and citations', () => {
  const result = render('`$x$ \\ref{code} \\cite{code}`\n\n~~~text\n$y$ \\label{code}\n~~~');
  assert.equal(result.diagnostics.length, 0);
  assert.ok(result.html.includes('$x$ \\ref{code} \\cite{code}'));
  assert.ok(!result.html.includes('class="katex"'));
});

test('citations in proofs share numbering with bibliography', () => {
  const result = render('\\cite{missing}\n\\begin{proof}\n\\cite{book}\n\\end{proof}\n\n```bibtex\n@book{book,\n title={Book},\n year={2026}\n}\n```');
  assert.ok(result.html.includes('href="#ref-book">[2]</a>'));
  assert.ok(result.html.includes('class="ref-number">[2]</span>'));
});

test('formula numbering follows source order and has real anchors', () => {
  const result = render(String.raw`\eqref{a} \eqref{b}
\begin{theorem}{thm:a}
$$x=1\label{a}$$
\end{theorem}
\begin{equation}y=2\label{b}\end{equation}`);
  assert.equal(result.diagnostics.length, 0);
  for (const [id, number] of [['a', 1], ['b', 2]]) {
    assert.ok(result.html.includes(`id="lbl-${id}"`));
    assert.ok(result.html.includes(`href="#lbl-${id}">(${number})</a>`));
  }
});

test('forward theorem references resolve after all labels are collected', () => {
  const result = render(String.raw`\begin{proof}Use \autoref{later}.\end{proof}
\begin{theorem}{later}Result.\end{theorem}`);
  assert.equal(result.diagnostics.length, 0);
  assert.ok(result.html.includes('href="#lbl-later">定理 1</a>'));
});

test('invalid math, missing references and duplicate labels are diagnosed', () => {
  const result = render(String.raw`\ref{missing} $$\unknownCommand$$
$$x\label{a}$$ $$y\label{a}$$`);
  for (const expected of ['未定义引用', '无效公式', '重复标签']) {
    assert.ok(result.diagnostics.some(x => x.includes(expected)));
  }
});

test('literal code inside a theorem is preserved', () => {
  const result = render('\\begin{theorem}{a}\n`$x$ \\cite{literal}`\n\\end{theorem}');
  assert.equal(result.diagnostics.length, 0);
  assert.ok(result.html.includes('<code>$x$ \\cite{literal}</code>'));
});
