const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:4173', headless: true },
  webServer: {
    // Serve the repository root: reader tests use /index.html, while site
    // tests use /site/index.html. Build the latter before starting.
    command: 'uv run python blog.py && uv run python -m http.server 4173 --directory .',
    url: 'http://127.0.0.1:4173/',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
