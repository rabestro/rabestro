import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import update_articles as updater


def entry(title="An article", url="https://jc.id.lv/posts/example/", date="2026-07-05T12:00:00+03:00"):
    return (f"<entry><title>{title}</title><published>{date}</published>"
            f'<link rel="alternate" href="{url}" /></entry>')


def feed(*entries):
    return '<feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entries) + "</feed>"


class UpdateArticlesTests(unittest.TestCase):
    def test_newest_five_unique_posts_by_publication_instant(self):
        entries = [entry(f"Post {day}", f"https://jc.id.lv/posts/{day}/",
                         f"2026-07-0{day}T12:00:00+03:00") for day in range(1, 8)]
        lines = updater.article_lines(feed(entries[-1], *entries)).splitlines()
        self.assertEqual(len(lines), 5)
        self.assertIn("Post 7", lines[0])
        self.assertIn("Post 3", lines[-1])
        self.assertNotIn("Post 2", "\n".join(lines))

    def test_sort_uses_timezone_and_not_the_entry_updated_date(self):
        early = entry("Earlier", date="2026-07-05T12:00:00+03:00")
        early = early.replace("</entry>", "<updated>2026-10-16T00:00:00Z</updated></entry>")
        later = entry("Later", "https://jc.id.lv/posts/later/", "2026-07-05T10:00:00Z")
        self.assertIn("Later", updater.article_lines(feed(early, later)).splitlines()[0])

    def test_titles_cannot_inject_markdown_or_html(self):
        line = updater.article_lines(feed(entry("A [link] *bold* &lt;img&gt;\n next")))
        self.assertIn(r"A \[link\] \*bold\* &lt;img&gt; next", line)
        self.assertEqual(len(line.splitlines()), 1)

    def test_parentheses_in_url_are_encoded(self):
        line = updater.article_lines(feed(entry(url="https://jc.id.lv/posts/a(b)/")))
        self.assertIn("/a%28b%29/)", line)

    def test_untrusted_article_links_are_rejected(self):
        for url in ("http://jc.id.lv/posts/a/", "https://example.com/posts/a/",
                    "javascript:alert(1)", "https://jc.id.lv@evil.test/posts/a/",
                    "https://jc.id.lv/about/", "https://jc.id.lv/posts/a b/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                updater.article_lines(feed(entry(url=url)))

    def test_invalid_or_empty_feeds_are_rejected(self):
        for xml in ("<broken", "<html />", feed(), feed(entry(date="invalid")),
                    feed(entry(date="2026-07-05T12:00:00")), feed(entry(title=" "))):
            with self.subTest(xml=xml), self.assertRaises((ValueError, updater.ET.ParseError)):
                updater.article_lines(xml)

    def test_only_marked_block_changes_and_second_run_is_identical(self):
        before = f"Introduction\n{updater.START}\nOld list\n{updater.END}\nFooter\n"
        after = updater.updated_readme(before, feed(entry()))
        self.assertTrue(after.startswith(f"Introduction\n{updater.START}\n"))
        self.assertTrue(after.endswith(f"\n{updater.END}\nFooter\n"))
        self.assertNotIn("Old list", after)
        self.assertEqual(after, updater.updated_readme(after, feed(entry())))

    def test_missing_duplicate_or_reversed_markers_are_rejected(self):
        for text in ("no markers", updater.START, updater.END,
                     updater.START * 2 + updater.END, updater.END + updater.START):
            with self.subTest(text=text), self.assertRaises(ValueError):
                updater.updated_readme(text, feed(entry()))

    def test_fetch_errors_leave_readme_unchanged(self):
        self.check_main_preserves_file(error=URLError("blog unavailable"))

    def test_invalid_feed_leaves_readme_unchanged(self):
        self.check_main_preserves_file(xml=feed())

    def test_missing_title_leaves_readme_unchanged(self):
        self.check_main_preserves_file(xml=feed("<entry><published>2026-07-05T12:00:00Z</published></entry>"))

    def test_dry_run_leaves_readme_unchanged(self):
        self.check_main_preserves_file(xml=feed(entry()), args=["--dry-run"], expected=0)

    def check_main_preserves_file(self, xml=None, error=None, args=None, expected=1):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            original = f"Intro\n{updater.START}\nKeep this\n{updater.END}\nFooter\n"
            path.write_text(original, encoding="utf-8")
            with (patch.object(updater, "README", path),
                  patch.object(updater, "fetch_feed", return_value=xml, side_effect=error),
                  patch("sys.argv", ["update_articles.py", *(args or [])]),
                  patch("sys.stdout"), patch("sys.stderr")):
                self.assertEqual(updater.main(), expected)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
