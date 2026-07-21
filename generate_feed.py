#!/usr/bin/env python3
"""Generate an RSS 2.0 feed (blog/feed.xml) from the published blog HTML files.

The feed is what Substack's "Import posts" and other RSS-based importers read, so
publishing a new post and re-running this script is all that is needed to keep the
import source up to date.

Usage:
    python generate_feed.py                 # scan ./blog, write ./blog/feed.xml
    python generate_feed.py --blog-dir blog # explicit blog directory
    python generate_feed.py --check         # validate without writing

Every post link and image is emitted as an absolute https URL because Medium and
Substack cannot resolve relative paths. SVG images are kept as-is and reported,
since those importers do not render SVG.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_ERROR = 2

SITE_BASE = "https://sendtoshailesh.github.io"
BLOG_BASE = f"{SITE_BASE}/blog"
FEED_URL = f"{BLOG_BASE}/feed.xml"

FEED_TITLE = "Shailesh Mishra — Blog"
FEED_DESCRIPTION = (
    "Technical deep-dives, case studies, and field notes on AI code assistants, "
    "PostgreSQL, cloud engineering, and architecture."
)
FEED_AUTHOR_NAME = "Shailesh Mishra"
FEED_AUTHOR_EMAIL = "sendtoshailesh@gmail.com"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)


@dataclass
class Post:
    """A single blog post extracted from its HTML file."""

    slug: str
    title: str
    description: str
    url: str
    published: datetime
    image: str | None = None
    tags: list[str] = field(default_factory=list)
    body_html: str = ""


def _meta(pattern: str, source: str) -> str | None:
    """Return the first regex capture group in source, or None."""
    match = re.search(pattern, source, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _absolute(url: str) -> str:
    """Rewrite a blog-relative asset URL to an absolute https URL."""
    url = url.strip()
    if url.startswith(("http://", "https://", "data:")):
        return url
    if url.startswith("../"):
        return f"{SITE_BASE}/{url[3:]}"
    if url.startswith("/"):
        return f"{SITE_BASE}{url}"
    return f"{BLOG_BASE}/{url}"


def _png_twin(absolute_svg: str, blog_dir: Path) -> str | None:
    """Return the absolute PNG URL if a same-name PNG exists next to the SVG."""
    if not absolute_svg.startswith(f"{BLOG_BASE}/"):
        return None
    relative = absolute_svg[len(f"{BLOG_BASE}/"):]
    twin = (blog_dir / relative).with_suffix(".png")
    if twin.is_file():
        return absolute_svg[: -len(".svg")] + ".png"
    return None


def _rewrite_assets(body: str, blog_dir: Path) -> tuple[str, list[str]]:
    """Make every src/href absolute; swap SVG images for PNG twins when present.

    Substack and Medium cannot render SVG, so any SVG image that has a PNG twin
    on disk is rewritten to the PNG. SVGs without a twin are returned for warning.
    """
    unresolved_svgs: list[str] = []

    def repl(match: re.Match[str]) -> str:
        attr, quote, value = match.group(1), match.group(2), match.group(3)
        absolute = _absolute(value)
        if attr == "src" and absolute.lower().endswith(".svg"):
            twin = _png_twin(absolute, blog_dir)
            if twin is not None:
                absolute = twin
            else:
                unresolved_svgs.append(absolute)
        return f"{attr}={quote}{absolute}{quote}"

    rewritten = re.sub(r'(src|href)=(["\'])([^"\']+)\2', repl, body)
    return rewritten, unresolved_svgs


def parse_post(path: Path) -> Post | None:
    """Extract a Post from a blog HTML file, or None if it is not an article."""
    source = path.read_text(encoding="utf-8")

    url = (
        _meta(r'<link\s+rel="canonical"\s+href="([^"]+)"', source)
        or _meta(r'<meta\s+property="og:url"\s+content="([^"]+)"', source)
        or f"{BLOG_BASE}/{path.name}"
    )

    title = (
        _meta(r'<meta\s+property="og:title"\s+content="([^"]+)"', source)
        or _meta(r"<title>(.*?)</title>", source)
        or path.stem
    )
    title = html.unescape(title).split(" | ")[0].strip()

    description = (
        _meta(r'<meta\s+property="og:description"\s+content="([^"]+)"', source)
        or _meta(r'<meta\s+name="description"\s+content="([^"]+)"', source)
        or ""
    )
    description = html.unescape(description).strip()

    image = _meta(r'<meta\s+property="og:image"\s+content="([^"]+)"', source)
    if image:
        image = _absolute(image)
        if image.lower().endswith(".svg"):
            # Substack/Medium cannot render an SVG thumbnail; prefer a PNG twin.
            site_root = path.parent.parent
            relative = image[len(f"{SITE_BASE}/"):] if image.startswith(f"{SITE_BASE}/") else ""
            twin = (site_root / relative).with_suffix(".png") if relative else None
            if twin is not None and twin.is_file():
                image = image[: -len(".svg")] + ".png"

    date_match = _DATE_RE.search(source)
    if not date_match:
        print(f"  ! skipping {path.name}: no publish date found", file=sys.stderr)
        return None
    month = _MONTHS[date_match.group(1).lower()]
    published = datetime(
        int(date_match.group(3)), month, int(date_match.group(2)),
        tzinfo=timezone.utc,
    )

    tags = re.findall(
        r'<span\s+class="post-tag">([^<]+)</span>', source, re.IGNORECASE
    )
    tags = [html.unescape(t.strip()) for t in tags]
    seen: set[str] = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]

    body_match = re.search(
        r'<div\s+class="post-content">(.*?)</div>\s*</article>',
        source,
        re.IGNORECASE | re.DOTALL,
    )
    body_html = ""
    if body_match:
        body, unresolved_svgs = _rewrite_assets(body_match.group(1).strip(), path.parent)
        body_html = body
        for svg in unresolved_svgs:
            print(
                f"  ~ {path.name}: SVG has no PNG twin, will not render in Substack/Medium: {svg}",
                file=sys.stderr,
            )

    return Post(
        slug=path.stem,
        title=title,
        description=description,
        url=url,
        published=published,
        image=image,
        tags=tags,
        body_html=body_html,
    )


def collect_posts(blog_dir: Path) -> list[Post]:
    """Parse every top-level blog HTML file (except the index) newest-first."""
    posts: list[Post] = []
    for path in sorted(blog_dir.glob("*.html")):
        if path.name == "index.html":
            continue
        post = parse_post(path)
        if post is not None:
            posts.append(post)
    posts.sort(key=lambda p: (p.published, p.slug), reverse=True)
    return posts


def _item_xml(post: Post) -> str:
    """Render a single <item> element for a post."""
    parts = [
        "  <item>",
        f"    <title>{html.escape(post.title)}</title>",
        f"    <link>{html.escape(post.url)}</link>",
        f'    <guid isPermaLink="true">{html.escape(post.url)}</guid>',
        f"    <pubDate>{format_datetime(post.published)}</pubDate>",
        f'    <dc:creator>{html.escape(FEED_AUTHOR_NAME)}</dc:creator>',
        f"    <description>{html.escape(post.description)}</description>",
    ]
    for tag in post.tags:
        parts.append(f"    <category>{html.escape(tag)}</category>")
    if post.image:
        mime = "image/svg+xml" if post.image.lower().endswith(".svg") else "image/png"
        parts.append(
            f'    <enclosure url="{html.escape(post.image)}" type="{mime}" length="0" />'
        )
        parts.append(
            f'    <media:content url="{html.escape(post.image)}" medium="image" />'
        )
    if post.body_html:
        parts.append(
            f"    <content:encoded><![CDATA[{post.body_html}]]></content:encoded>"
        )
    parts.append("  </item>")
    return "\n".join(parts)


def build_feed(posts: list[Post], now: datetime) -> str:
    """Assemble the full RSS 2.0 document."""
    items = "\n".join(_item_xml(post) for post in posts)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>{html.escape(FEED_TITLE)}</title>
  <link>{BLOG_BASE}/</link>
  <atom:link href="{FEED_URL}" rel="self" type="application/rss+xml" />
  <description>{html.escape(FEED_DESCRIPTION)}</description>
  <language>en-us</language>
  <managingEditor>{FEED_AUTHOR_EMAIL} ({html.escape(FEED_AUTHOR_NAME)})</managingEditor>
  <webMaster>{FEED_AUTHOR_EMAIL} ({html.escape(FEED_AUTHOR_NAME)})</webMaster>
  <lastBuildDate>{format_datetime(now)}</lastBuildDate>
  <generator>generate_feed.py</generator>
{items}
</channel>
</rss>
"""


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blog-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "blog",
        help="Directory containing the published blog HTML files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Feed output path (default: <blog-dir>/feed.xml).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Parse and validate posts without writing the feed.",
    )
    return parser


def main() -> int:
    """Main entry point for the script."""
    args = create_parser().parse_args()
    blog_dir: Path = args.blog_dir
    if not blog_dir.is_dir():
        print(f"error: blog directory not found: {blog_dir}", file=sys.stderr)
        return EXIT_ERROR

    posts = collect_posts(blog_dir)
    if not posts:
        print("error: no posts found to include in the feed", file=sys.stderr)
        return EXIT_FAILURE

    print(f"Collected {len(posts)} posts:")
    for post in posts:
        print(f"  - {post.published:%Y-%m-%d}  {post.slug}")

    if args.check:
        print("Check complete — feed not written.")
        return EXIT_SUCCESS

    output: Path = args.output or (blog_dir / "feed.xml")
    feed = build_feed(posts, datetime.now(timezone.utc))
    output.write_text(feed, encoding="utf-8")
    print(f"Wrote {output} ({len(feed):,} bytes)")
    print(f"Feed URL: {FEED_URL}")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
