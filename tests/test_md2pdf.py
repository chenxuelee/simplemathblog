import os
import shutil
import tempfile
import unittest
from pathlib import Path

from md2pdf import ORIGIN, convert, local_resource, validate_options


class PdfOptionsTests(unittest.TestCase):
    def test_invalid_options_do_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'note.md'
            source.write_text('# Original', encoding='utf-8')
            with self.assertRaises(ValueError):
                convert(source, source)
            for margin in (-1, 110, float('nan'), float('inf')):
                with self.subTest(margin=margin), self.assertRaises(ValueError):
                    validate_options(source, source.with_suffix('.pdf'), 'A4', margin, 30)
            self.assertEqual(source.read_text(), '# Original')

    def test_local_images_and_vendor_assets_resolve_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, html = root / 'notes', root / 'render'
            source.mkdir(); html.mkdir()
            (source / '图 1.svg').write_text('<svg/>')
            (html / 'assets' / 'vendor').mkdir(parents=True)
            (html / 'assets' / 'vendor' / 'katex.js').write_text('')
            self.assertEqual(local_resource(f'{ORIGIN}/%E5%9B%BE%201.svg', source, html), source / '图 1.svg')
            self.assertEqual(local_resource(f'{ORIGIN}/assets/vendor/katex.js', source, html), html / 'assets/vendor/katex.js')
            self.assertIsNone(local_resource('https://example.com/image.png', source, html))
            with self.assertRaises(ValueError):
                local_resource(f'{ORIGIN}/%2E%2E/secret.txt', source, html)


@unittest.skipUnless(os.environ.get('RUN_PDF_TESTS') == '1', 'Requires PDF extra and Chromium')
class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        fixtures = Path(__file__).parent / 'fixtures'
        shutil.copy(fixtures / 'pdf.md', self.root / 'note.md')
        shutil.copy(fixtures / 'diagram.svg', self.root / 'diagram.svg')

    def test_chinese_math_images_links_and_pagination(self):
        from pypdf import PdfReader
        output = convert(self.root / 'note.md', self.root / 'output' / 'note.pdf', strict=True)
        # Retain the sample even when a later assertion fails, for visual review.
        artifact = Path('test-results/pdf/sample.pdf')
        artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(output, artifact)
        self.assertTrue(output.read_bytes().startswith(b'%PDF-'))
        reader = PdfReader(output)
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('数学', text)
        self.assertIn('Energy Methods', text)
        self.assertIn('energy', text)
        self.assertNotIn('复制代码', text)
        self.assertGreaterEqual(len(reader.pages), 2)
        self.assertAlmostEqual(float(reader.pages[0]['/MediaBox'][2]), 595.28, delta=2)
        annotations = [obj.get_object() for page in reader.pages for obj in page.get('/Annots', [])]
        self.assertTrue(any('/Dest' in obj or obj.get('/A', {}).get('/S') == '/GoTo' for obj in annotations))

    def test_missing_image_preserves_existing_pdf(self):
        source = self.root / 'broken.md'
        source.write_text('![missing](absent.png)')
        output = self.root / 'previous.pdf'
        output.write_bytes(b'previous')
        with self.assertRaisesRegex(RuntimeError, '资源|图片'):
            convert(source, output)
        self.assertEqual(output.read_bytes(), b'previous')

    def test_strict_math_error_and_landscape(self):
        from pypdf import PdfReader
        source = self.root / 'bad.md'
        source.write_text(r'$$\unknowncommand$$')
        with self.assertRaisesRegex(RuntimeError, '无效公式'):
            convert(source, strict=True)
        self.assertFalse(source.with_suffix('.pdf').exists())
        source.write_text('# Landscape\nHello PDF')
        output = convert(source, paper='Letter', landscape=True, margin_mm=12)
        page = PdfReader(output).pages[0]
        self.assertGreater(float(page['/MediaBox'][2]), float(page['/MediaBox'][3]))
