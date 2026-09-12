// Use the shipped browser libraries, not a second implementation of math syntax.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const context = vm.createContext({ console });
for (const file of ['assets/vendor/marked.min.js', 'assets/vendor/katex/katex.min.js',
  'assets/vendor/highlight.min.js', 'renderer.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, { filename: file });
}
const posts = JSON.parse(fs.readFileSync(0, 'utf8'));
const problems = [];
for (const post of posts) {
  context.source = post.body;
  const diagnostics = vm.runInContext('prepareDocument(source); [...new Set(renderDiagnostics)]', context);
  problems.push(...diagnostics.map(message => `${post.source}: ${message}`));
}
process.stdout.write(JSON.stringify(problems));
