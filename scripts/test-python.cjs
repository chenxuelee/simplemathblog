const { spawnSync } = require('node:child_process');
const path = require('node:path');

// Enable the PDF integration tests on Windows as well as macOS/Linux.
const result = spawnSync('uv', [
  'run', '--locked', '--extra', 'pdf', '--group', 'pdf-test',
  'python', '-m', 'unittest', 'discover', '-s', 'tests', '-v',
], {
  cwd: path.resolve(__dirname, '..'),
  env: { ...process.env, RUN_PDF_TESTS: '1' },
  stdio: 'inherit',
});
if (result.error) {
  console.error(result.error.message);
}
process.exit(result.status ?? 1);
