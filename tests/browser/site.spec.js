const { test, expect } = require('@playwright/test');

test('generated site search and article navigation work', async ({ page }) => {
  await page.goto('/site/index.html');
  const input = page.locator('#site-search');
  await input.fill('傅里叶');
  await expect(page.locator('#search-results a').first()).toContainText('傅里叶级数');
  await page.locator('#search-results a').first().click();
  await expect(page.locator('.thm-env').first()).toBeVisible();
  await expect(page.locator('.post-nav a')).toHaveCount(1);
  await expect(page.locator('.cite-link')).toHaveText('[1]');
  await expect(page.locator('.bibliography')).toContainText('Fourier Analysis');
  await expect(page.locator('figure.illustration figcaption')).toContainText('Fourier 模态');
  await expect(page.locator('blockquote a[href="banach-fixed-point.html"]')).toContainText('Banach 不动点');
  await page.locator('.sidebar-toggle').click();
  await expect(page.locator('body')).toHaveClass(/sidebar-collapsed/);
});
