#!/usr/bin/env python3
"""
Simple script to fetch a Substack RSS feed and write a JSON file usable by GitLab Pages.

Usage: python scripts/fetch_essays.py --feed <feed_url> --out public/essays.json
"""
import argparse
import json
import sys
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET


def fetch(url):
    req = Request(url, headers={"User-Agent": "fetch_essays/1.0"})
    with urlopen(req, timeout=20) as r:
        return r.read()


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
    out = []
    for item in items:
        title = text(item, 'title')
        link = text(item, 'link')
        pubDate = text(item, 'pubDate')
        # content:encoded is in a namespace sometimes; try to find it
        content = ''
        for child in item:
            if child.tag.endswith('content:encoded') or 'content' in child.tag:
                content = (child.text or '')
                break
        out.append({
            'slug': slug_from(link, title),
            'title': title,
            'link': link,
            'date': pubDate,
            'html': content
        })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--feed', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()

    try:
        raw = fetch(args.feed)
    except Exception as e:
        print('Failed to fetch feed:', e, file=sys.stderr)
        sys.exit(2)

    posts = parse_rss(raw)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
