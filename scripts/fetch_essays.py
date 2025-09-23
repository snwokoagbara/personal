#!/usr/bin/env python3
"""
Simple script to fetch a Substack RSS feed and write a JSON file usable by GitLab Pages.

Usage: python scripts/fetch_essays.py --feed <feed_url> --out public/essays.json
"""
import argparse
import json
import sys
import time
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET
from urllib.error import URLError, HTTPError

# Substack feed might be available at several URLs - try them in order
FEED_VARIANTS = [
    "{base}/feed",           # Main RSS feed
    "{base}/feed/",          # With trailing slash
    "{base}/latest/feed",    # Latest posts feed
    "{base}/rss",           # Alternative RSS path
]

def normalize_feed_url(url):
    """Remove common RSS suffixes to get base URL for variants."""
    for suffix in ['/feed', '/feed/', '/latest/feed', '/rss']:
        if url.endswith(suffix):
            return url[:-len(suffix)]
    return url

def fetch_with_retries(url, max_retries=3, delay=1):
    """Fetch URL with retries and exponential backoff."""
    headers = {"User-Agent": "Mozilla/5.0 (fetch_essays/1.0)"}
    last_error = None

    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(delay * (2 ** (attempt - 1)))  # Exponential backoff
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as r:
                return r.read()
        except (URLError, HTTPError) as e:
            last_error = e
            print(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}", file=sys.stderr)
            continue
    raise last_error if last_error else RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")

def fetch_feed(feed_url):
    """Try multiple feed URL variants and return first successful response."""
    base_url = normalize_feed_url(feed_url)
    errors = []

    for variant in FEED_VARIANTS:
        try:
            url = variant.format(base=base_url)
            print(f"Trying feed URL: {url}", file=sys.stderr)
            return fetch_with_retries(url)
        except Exception as e:
            errors.append(f"{url}: {str(e)}")
            continue

    raise RuntimeError(f"All feed variants failed:\n" + "\n".join(errors))


def text(node, tag):
    el = node.find(tag)
    return el.text.strip() if el is not None and el.text else ''


def slug_from(link, title):
    if not link:
        return title.lower().replace(' ', '-')
    parts = [p for p in link.split('/') if p]
    return parts[-1] if parts else title.lower().replace(' ', '-')


def parse_rss(raw):
    root = ET.fromstring(raw)
    items = root.findall('.//item')
    if not items:
        # Try with explicit Atom namespace (some Substack feeds use this)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//atom:entry', ns)
        if not items:
            raise ValueError("No items/entries found in feed")

    out = []
    for item in items:
        title = text(item, 'title')
        link = text(item, 'link')
        pubDate = text(item, 'pubDate') or text(item, 'published')
        # Try multiple content tags/namespaces
        content = ''
        for child in item:
            if any(x in child.tag.lower() for x in ['content:encoded', 'content', 'description']):
                content = (child.text or '')
                break
        out.append({
            'slug': slug_from(link, title),
            'title': title,
            'link': link,
            'date': pubDate,
            'html': content
        })
    
    if not out:
        raise ValueError("Found feed items but couldn't extract post data")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--feed', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()

    try:
        raw = fetch_feed(args.feed)
        posts = parse_rss(raw)
        
        if not posts:
            print("Warning: No posts found in feed", file=sys.stderr)
            sys.exit(1)
            
        print(f"Found {len(posts)} posts in feed", file=sys.stderr)
        
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f'Error processing feed:\n{str(e)}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
