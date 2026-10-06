import asyncio
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
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


class PdfProtocolTests(unittest.TestCase):
    def setUp(self):
        try:
            import playwright.async_api  # noqa: F401
        except ImportError:
            self.skipTest('Requires PDF extra, but no browser')
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.source = Path(scratch.name) / 'note.md'
        self.source.write_text('# Timeout regression', encoding='utf-8')
        self.output = self.source.with_suffix('.pdf')
        self.output.write_bytes(b'previous')
        self.page = MagicMock()
        for name in ('route', 'goto', 'emulate_media', 'add_style_tag',
                     'wait_for_function', 'eval_on_selector_all', 'evaluate'):
            setattr(self.page, name, AsyncMock(return_value=[]))
        self.page.pdf = AsyncMock(return_value=b'%PDF-sample')
        self.browser = MagicMock()
        self.browser.new_page = AsyncMock(return_value=self.page)
        self.browser.close = AsyncMock()
        self.factory_patch = patch('playwright.async_api.async_playwright')
        factory = self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.launch = AsyncMock(return_value=self.browser)
        factory.return_value.__aenter__.return_value.chromium.launch = self.launch

    def test_custom_timeout_is_applied_and_export_succeeds(self):
        convert(self.source, timeout=67)
        self.assertEqual(self.output.read_bytes(), b'%PDF-sample')
        self.assertEqual(self.launch.call_args.kwargs['timeout'], 67000)
        self.page.set_default_timeout.assert_called_once_with(67000)
        self.page.set_default_navigation_timeout.assert_called_once_with(67000)
        self.browser.close.assert_awaited_once()

    def test_pdf_timeout_cancels_generation_and_preserves_previous_pdf(self):
        cancelled = []

        async def blocked_pdf(**_kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        self.page.pdf.side_effect = blocked_pdf
        with self.assertRaisesRegex(RuntimeError, 'PDF 生成超时'):
            convert(self.source, timeout=0.05)
        self.assertEqual(cancelled, [True])
        self.assertEqual(self.output.read_bytes(), b'previous')
        self.browser.close.assert_awaited_once()

    def test_resource_wait_timeout_preserves_previous_pdf(self):
        from playwright.async_api import TimeoutError as BrowserTimeout
        self.page.wait_for_function.side_effect = BrowserTimeout('resource wait expired')
        with self.assertRaisesRegex(RuntimeError, '浏览器导出失败'):
            convert(self.source, timeout=2)
        self.assertEqual(self.output.read_bytes(), b'previous')
        self.page.pdf.assert_not_awaited()
        self.browser.close.assert_awaited_once()


@unittest.skipUnless(os.environ.get('RUN_PDF_TESTS') == '1', 'Requires PDF extra and Chromium')
class PdfExportTests(unittest.TestCase):
    def test_browser_selection_and_explicit_override(self):
        from playwright.async_api import Error

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'note.md'
            source.write_text('# Browser selection', encoding='utf-8')
            for configured, explicit, expected in [
                ('/system/chromium', None, '/system/chromium'),
                ('/system/chromium', '/custom/chrome', '/custom/chrome'),
                ('', None, None),
            ]:
                with self.subTest(configured=configured, explicit=explicit):
                    with patch.dict(os.environ, {'CHROMIUM_EXECUTABLE_PATH': configured}), \
                            patch('playwright.async_api.async_playwright') as factory:
                        launch = factory.return_value.__aenter__.return_value.chromium.launch
                        launch = AsyncMock(side_effect=Error('Browser unavailable'))
                        factory.return_value.__aenter__.return_value.chromium.launch = launch
                        with self.assertRaisesRegex(RuntimeError, '无法启动 Chromium'):
                            convert(source, browser=explicit)
                        self.assertEqual(launch.call_args.kwargs['executable_path'], expected)

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

    def test_strict_error_preserves_existing_pdf(self):
        source = self.root / 'invalid.md'
        source.write_text(r'$$\unknowncommand$$', encoding='utf-8')
        output = self.root / 'previous.pdf'
        output.write_bytes(b'previous')
        with self.assertRaisesRegex(RuntimeError, '无效公式'):
            convert(source, output, strict=True)
        self.assertEqual(output.read_bytes(), b'previous')

    def test_remote_image_failure_without_network_preserves_existing_pdf(self):
        source = self.root / 'remote.md'
        source.write_text('![remote](https://example.invalid/image.png)', encoding='utf-8')
        output = self.root / 'previous.pdf'
        output.write_bytes(b'previous')
        resolve = local_resource

        def fail_remote(url, source_dir, html_dir):
            if url.startswith('https://example.invalid/'):
                raise OSError('simulated remote image failure')
            return resolve(url, source_dir, html_dir)

        with patch('md2pdf.local_resource', side_effect=fail_remote):
            with self.assertRaisesRegex(RuntimeError, 'simulated remote image failure'):
                convert(source, output)
        self.assertEqual(output.read_bytes(), b'previous')

    def test_failed_math_font_preserves_existing_pdf(self):
        from playwright.async_api import Route
        original = Route.fulfill

        async def fail_fonts(route, **kwargs):
            if str(kwargs.get('path', '')).endswith(('.woff2', '.woff', '.ttf')):
                await route.abort()
            else:
                await original(route, **kwargs)

        output = self.root / 'previous.pdf'
        output.write_bytes(b'previous')
        with patch.object(Route, 'fulfill', fail_fonts):
            with self.assertRaisesRegex(RuntimeError, '字体加载失败'):
                convert(self.root / 'note.md', output, strict=True)
        self.assertEqual(output.read_bytes(), b'previous')

    def test_wide_equation_reports_source_and_preserves_strict_output(self):
        from pypdf import PdfReader
        source = self.root / 'wide.md'
        source.write_text('$$' + ' + '.join(['x_i'] * 100) + '$$', encoding='utf-8')
        output = self.root / 'previous.pdf'
        output.write_bytes(b'previous')
        with self.assertRaisesRegex(RuntimeError, '公式过宽.*9 pt'):
            convert(source, output, strict=True)
        self.assertEqual(output.read_bytes(), b'previous')
        warnings = io.StringIO()
        with contextlib.redirect_stderr(warnings):
            convert(source, output)
        self.assertIn('x_i', warnings.getvalue())
        self.assertIn('aligned', warnings.getvalue())
        self.assertTrue(PdfReader(output).pages)

    def test_moderately_wide_equation_fits_without_clipping(self):
        from playwright.async_api import Page
        original = Page.pdf
        measurements = []

        async def measure_before_print(page, **kwargs):
            measurements.extend(await page.eval_on_selector_all('.katex-display', """blocks =>
              blocks.map(block => ({width: block.clientWidth,
                mathWidth: block.querySelector('.katex').scrollWidth,
                fontSize: parseFloat(getComputedStyle(block.querySelector('.katex')).fontSize)}))"""))
            return await original(page, **kwargs)

        source = self.root / 'moderate.md'
        source.write_text('$$' + ' + '.join(['x_i'] * 20) + '$$', encoding='utf-8')
        with patch.object(Page, 'pdf', measure_before_print):
            output = convert(source, strict=True)
        self.assertTrue(output.read_bytes().startswith(b'%PDF-'))
        self.assertEqual(len(measurements), 1)
        self.assertLessEqual(measurements[0]['mathWidth'], measurements[0]['width'] + 1)
        self.assertGreaterEqual(measurements[0]['fontSize'], 12)
        self.assertLess(measurements[0]['fontSize'], 17)
        artifact = Path('test-results/pdf/wide-equation.pdf')
        artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(output, artifact)
