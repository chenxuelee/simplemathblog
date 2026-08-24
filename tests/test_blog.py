import json
import tempfile
import unittest
from pathlib import Path

from blog import load_posts, main as build_site
from md2html import json_for_script


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
                sys.argv = ["blog.py", "--posts", str(posts), "--out", str(output)]
                build_site()
            finally:
                sys.argv = old_argv
            self.assertTrue((output / "assets" / "diagram.txt").exists())
            self.assertTrue((output / "rss.xml").exists())
            self.assertTrue((output / "sitemap.xml").exists())
            data = json.loads((output / "search-index.json").read_text(encoding="utf-8"))
            self.assertEqual([p["title"] for p in data], ["A", "B"])
            self.assertIn("a.html", (output / "b.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
