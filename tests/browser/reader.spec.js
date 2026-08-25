const { test, expect } = require('@playwright/test');

test('reader renders math, theorem, cross-reference, and callout', async ({ page }) => {
  await page.goto('/index.html');
  await expect(page.locator('.katex').first()).toBeVisible();
  await expect(page.locator('.thm-env').first()).toContainText('定义 1');
  await expect(page.locator('a.ref-link').first()).toHaveAttribute('href', /#lbl-/);

  await page.locator('#btn-edit').click();
  const editor = page.locator('#editor');
  await editor.fill(':::tip 浏览器测试\n提示内容\n:::\n\n$E=mc^2$\n\n```javascript\nconst answer = 42;\n```');
  await page.locator('#btn-edit').click();
  await expect(page.locator('blockquote')).toContainText('提示：浏览器测试');
  await expect(page.locator('.katex')).toBeVisible();
  await expect(page.locator('.math-copy-target .copy-button').first()).toHaveText('复制公式');
  await expect(page.locator('pre code.hljs.language-javascript')).toContainText('const answer');
  await expect(page.locator('pre .copy-button')).toHaveText('复制代码');

  await page.locator('#btn-edit').click();
  await editor.fill('[unsafe](javascript:alert(1))');
  await page.locator('#btn-edit').click();
  await expect(page.locator('#container a')).toHaveCount(0);
});
