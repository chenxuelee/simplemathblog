import json
import tempfile
import unittest
from pathlib import Path

from blog import absolute_url, load_posts, main as build_site, rss_date
from md2html import json_for_script
from server import source_snapshot


class BlogBuildTests(unittest.TestCase):
    def test_script_serialization_cannot_close_tag(self):
        value = json_for_script("</script><script>alert(1)</script>")
        self.assertNotIn("</script>", value)
        self.assertIn("\\u003c", value)

    def test_load_posts_rewrites_local_markdown_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            posts = Path(tmp)
            (posts / "one.md").write_text("[next](two.md#part)", encoding="utf-8")
            item = load_posts(posts)[0]
            self.assertIn("two.html#part", item["body"])

    def test_production_url_helpers(self):
        self.assertEqual(absolute_url("文章.html", "https://example.com/"), "https://example.com/%E6%96%87%E7%AB%A0.html")
        self.assertEqual(rss_date("2026-01-02"), "Fri, 02 Jan 2026 00:00:00 +0000")

    def test_source_snapshot_tracks_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "content" / "post.md"
            target.parent.mkdir()
            target.write_text("one", encoding="utf-8")
            first = source_snapshot((root / "content",))
            self.assertIn(str(target), first)
            target.write_text("two", encoding="utf-8")
            self.assertNotEqual(first, source_snapshot((root / "content",)))

    def test_full_build_writes_publishable_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts, output = root / "content", root / "site"
            (posts / "assets").mkdir(parents=True)
            (posts / "assets" / "diagram.txt").write_text("asset", encoding="utf-8")
            (posts / "a.md").write_text("---\ntitle: A\ndate: 2026-01-02\ntags: [math]\n---\n# A", encoding="utf-8")
            (posts / "b.md").write_text("---\ntitle: B\ndate: 2026-01-01\ntags: [math]\n---\n[go](a.md)", encoding="utf-8")
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["blog.py", "--posts", str(posts), "--out", str(output), "--base-url", "https://example.test/blog"]
                build_site()
            finally:
                sys.argv = old_argv
            self.assertTrue((output / "assets" / "diagram.txt").exists())
            self.assertTrue((output / "rss.xml").exists())
            self.assertTrue((output / "sitemap.xml").exists())
            data = json.loads((output / "search-index.json").read_text(encoding="utf-8"))
            self.assertEqual([p["title"] for p in data], ["A", "B"])
            self.assertIn("a.html", (output / "b.html").read_text(encoding="utf-8"))
            self.assertIn("https://example.test/blog/a.html", (output / "sitemap.xml").read_text(encoding="utf-8"))

    def test_rejects_unsafe_slugs_and_bad_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            posts = Path(tmp)
            (posts / "bad.md").write_text("---\nslug: ../escape\ndate: 2026-01-02\n---\n# no", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_posts(posts)

    def test_build_rejects_duplicate_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content"
            posts.mkdir()
            (posts / "one.md").write_text("---\nslug: same\n---\n# one", encoding="utf-8")
            (posts / "two.md").write_text("---\nslug: same\n---\n# two", encoding="utf-8")
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["blog.py", "--posts", str(posts), "--out", str(root / "site")]
                with self.assertRaises(SystemExit):
                    build_site()
            finally:
                sys.argv = old_argv
            (posts / "bad.md").write_text("---\nslug: safe\ndate: tomorrow\n---\n# no", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_posts(posts)
            (posts / "bad.md").write_text("---\nslug: safe\ndate: 2026-01-02\ncover: javascript:alert(1)\n---\n# no", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_posts(posts)

    def test_full_build_replaces_stale_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts, output = root / "content", root / "site"
            posts.mkdir()
            (posts / "fresh.md").write_text("# fresh", encoding="utf-8")
            output.mkdir()
            (output / "stale.html").write_text("old", encoding="utf-8")
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["blog.py", "--posts", str(posts), "--out", str(output)]
                build_site()
            finally:
                sys.argv = old_argv
            self.assertTrue((output / "fresh.html").exists())
            self.assertFalse((output / "stale.html").exists())

    def test_build_refuses_an_output_directory_containing_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = root / "content"
            posts.mkdir()
            (posts / "one.md").write_text("# one", encoding="utf-8")
            import sys
            old_argv = sys.argv
            try:
                sys.argv = ["blog.py", "--posts", str(posts), "--out", str(root)]
                with self.assertRaises(SystemExit):
                    build_site()
            finally:
                sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
