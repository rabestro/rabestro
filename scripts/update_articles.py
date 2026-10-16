#!/usr/bin/env python3
"""Refresh only the marked README block from the blog's Atom feed."""

import argparse
from datetime import datetime
import html
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

FEED_URL = "https://jc.id.lv/feed.xml"
README = Path(__file__).resolve().parents[1] / "README.md"
START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
MAX_BYTES = 1_000_000


def markdown_title(title):
    title = html.escape(" ".join(title.split()), quote=False)
    return re.sub(r"([\\`*_\[\]])", r"\\\1", title)


def article_lines(feed):
    root = ET.fromstring(feed)
    if root.tag != f"{{{ATOM['a']}}}feed":
        raise ValueError("Expected the blog's Atom feed")
    articles = []
    for entry in root.findall("a:entry", ATOM):
        title_node = entry.find("a:title", ATOM)
        title = "".join(title_node.itertext()).strip() if title_node is not None else ""
        published = datetime.fromisoformat(entry.findtext("a:published", "", ATOM))
        if not title or published.utcoffset() is None:
            raise ValueError("Every article needs a title and a timezone-aware publication date")
        link = next(
            (link for link in entry.findall("a:link", ATOM)
             if link.get("rel", "alternate") == "alternate"),
            None,
        )
        url = link.get("href", "") if link is not None else ""
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != "jc.id.lv"
                or not parsed.path.startswith("/posts/") or any(c.isspace() for c in url)):
            raise ValueError("Every article must link to an HTTPS post on jc.id.lv")
        articles.append((published, title, url))
    if not articles:
        raise ValueError("Feed has no articles; keeping the existing list")

    lines, seen = [], set()
    for published, title, url in sorted(articles, key=lambda article: article[0], reverse=True):
        if url in seen:
            continue
        seen.add(url)
        safe_url = quote(url, safe=":/%?#=&")
        lines.append(f"- {published:%Y-%m-%d} · [{markdown_title(title)}]({safe_url})")
        if len(lines) == 5:
            break
    return "\n".join(lines)


def updated_readme(readme, feed):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("README must contain exactly one pair of blog markers")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if start > end:
        raise ValueError("README blog markers are reversed")
    return readme[:start] + "\n" + article_lines(feed) + "\n" + readme[end:]


def fetch_feed():
    request = Request(FEED_URL, headers={"User-Agent": "rabestro-profile-articles/1.0"})
    with urlopen(request, timeout=20) as response:
        feed = response.read(MAX_BYTES + 1)
    if len(feed) > MAX_BYTES:
        raise ValueError("Feed exceeds the size limit")
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the list without writing")
    args = parser.parse_args()
    try:
        feed = fetch_feed()
        current = README.read_text(encoding="utf-8")
        updated = updated_readme(current, feed)
        if args.dry_run:
            print(article_lines(feed))
        elif updated != current:
            README.write_text(updated, encoding="utf-8")
            print("Updated latest articles")
        else:
            print("Latest articles are already up to date")
    except (URLError, OSError, ValueError, ET.ParseError) as error:
        print(f"Could not update articles: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
