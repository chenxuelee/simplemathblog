const { test, expect } = require('@playwright/test');

async function show(page, source) {
  await page.goto('/index.html');
  await page.evaluate(source => render(source), source);
}

test('theorem citations retain source order, even with a missing key', async ({ page }) => {
  await show(page, '\\cite{missing}\n\\begin{theorem}{thm:a}\nInside \\cite{book}.\n\\end{theorem}\nOutside \\cite{book}.\n\n```bibtex\n@book{book,\n title = {A Book},\n year = {2026}\n}\n```');
  await expect(page.locator('.thm-body .cite-link')).toHaveText('[2]');
  await expect(page.locator('.bibliography .ref-number')).toHaveText('[2]');
});

test('math and reference syntax remains literal in code', async ({ page }) => {
  const literal = String.raw`$x$ \ref{literal} \cite{literal}`;
  await show(page, '`' + literal + '`\n\n~~~latex\n' + literal + '\n~~~');
  await expect(page.locator('#container code')).toHaveCount(2);
  for (const code of await page.locator('#container code').all()) {
    await expect(code).toHaveText(literal);
  }
  await expect(page.locator('#container .katex, #container .ref-link, .citation-missing')).toHaveCount(0);
});

test('equation links have targets inside and outside theorems', async ({ page }) => {
  await show(page, String.raw`See \eqref{eq:inside} and \eqref{eq:outside}.
\begin{theorem}{thm:a}
$$x=1\label{eq:inside}$$
\end{theorem}
\begin{equation}y=2\label{eq:outside}\end{equation}`);
  await expect(page.locator('.ref-link').first()).toHaveText('(1)');
  await expect(page.locator('.ref-link').last()).toHaveText('(2)');
  for (const link of await page.locator('.ref-link').all()) {
    const href = await link.getAttribute('href');
    expect(await page.evaluate(id => Boolean(document.getElementById(id)), href.slice(1))).toBe(true);
    await link.click();
    expect(await page.evaluate(() => decodeURIComponent(location.hash))).toBe(href);
  }
});

test('invalid math is visible and reported to strict validation', async ({ page }) => {
  await show(page, String.raw`$$\notARealCommand$$`);
  await expect(page.locator('.math-error')).toBeVisible();
  expect(await page.evaluate(() => renderDiagnostics.some(x => x.includes('无效公式')))).toBe(true);
});

test('article remains readable on mobile, dark mode and print', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/site/fourier-series.html');
  await expect(page.locator('.thm-env').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('#sidebar')).toBeHidden();
  await expect(page.locator('#container')).toBeVisible();
});
