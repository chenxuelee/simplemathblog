const { test, expect } = require('@playwright/test');

test('generated site search and article navigation work', async ({ page }) => {
  await page.goto('/site/index.html');
  const input = page.locator('#site-search');
  await input.fill('傅里叶');
  await expect(page.locator('#search-results a').first()).toContainText('傅里叶级数');
  await page.locator('#search-results a').first().click();
  await expect(page.locator('.thm-env').first()).toBeVisible();
  await expect(page.locator('.post-nav a')).toHaveCount(1);
});
