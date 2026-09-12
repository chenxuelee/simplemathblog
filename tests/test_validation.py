import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from blog import absolute_url, load_posts, main, validate_posts, validate_rendering


class ValidationTests(unittest.TestCase):
    def test_reserved_and_ambiguous_slugs(self):
        for slug in ('index', 'tags', 'search', 'INDEX', 'a#b', 'a?b', 'a%20b', 'a\\b'):
            with self.subTest(slug=slug), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                (path / 'a.md').write_text(f'---\nslug: {slug}\n---\nA')
                with self.assertRaises(ValueError):
                    load_posts(path)

    def test_custom_slug_and_code_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'a.md').write_text('[B](b.md#section)\n`[B](b.md)`\n```md\n[B](b.md)\n```')
            (path / 'b.md').write_text('---\nslug: custom\n---\nB')
            post = next(p for p in load_posts(path) if p['source'] == 'a.md')
            self.assertIn('[B](custom.html#section)', post['body'])
            self.assertIn('`[B](b.md)`', post['body'])
            self.assertIn('```md\n[B](b.md)\n```', post['body'])

    def test_external_cover_is_not_prefixed(self):
        self.assertEqual(absolute_url('https://img.test/a.png', 'https://blog.test'),
                         'https://img.test/a.png')

    def test_missing_resources_have_source_and_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / 'a.md').write_text('# A\n![pic](assets/missing.png)\n[[absent]]\n`[[code]]`')
            problems = validate_posts(load_posts(path), path)
            self.assertEqual(len(problems), 2)
            self.assertTrue(problems[0].startswith('a.md:3:'))
            self.assertTrue(problems[1].startswith('a.md:2:'))

    def test_semantic_diagnostics_and_literal_code(self):
        body = r'''\ref{missing} \cite{absent}
$$x\label{same}$$
$$y\label{same}$$
$$\notARealCommand$$
`\ref{literal}`
'''
        messages = validate_rendering([{'source': 'a.md', 'body': body}])
        for expected in ('未定义引用：missing', '缺失文献：absent', '重复标签：same', '无效公式'):
            self.assertTrue(any(expected in message for message in messages), messages)
        self.assertFalse(any('literal' in message for message in messages))

    def test_strict_failure_preserves_previous_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts, out = root / 'content', root / 'site'
            posts.mkdir(); out.mkdir()
            (posts / 'a.md').write_text('[bad](missing.html)')
            (out / 'index.html').write_text('previous')
            with patch('sys.argv', ['blog.py', '--posts', str(posts), '--out', str(out), '--strict']):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual((out / 'index.html').read_text(), 'previous')
