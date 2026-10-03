const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    launchOptions: {
      executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
    },
  },
  webServer: {
    // Serve the repository root: reader tests use /index.html, while site
    // tests use /site/index.html. Build the latter before starting.
    command: (process.env.BLOG_SKIP_BUILD ? '' : 'npm run build && ') +
      'uv run --locked python -m http.server 4173 --bind 127.0.0.1 --directory .',
    url: 'http://127.0.0.1:4173/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
