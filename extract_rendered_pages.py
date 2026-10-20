#!/usr/bin/env python3
import json, re, html
from pathlib import Path

RAW = Path("raw")
OUT = Path("rendered")
OUT.mkdir(exist_ok=True)

def read_text(p):
    return p.read_text(encoding="utf-8", errors="ignore")

def page_name(path):
    rel = path.relative_to(RAW)
    return "home" if str(rel) == "index.html" else rel.parts[0]

def unescape_payload(s):
    s = s.replace(r"\/", "/")
    s = s.replace(r"\n", "\n").replace(r"\r", "")
    s = s.replace(r"\"", '"')
    s = s.replace(r"\t", "\t")
    s = s.replace(r"\u00a0", " ")
    s = html.unescape(s)
    return s

def first_match(patterns, text, flags=re.S):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return m
    return None

summary = []

for f in sorted(RAW.glob("**/index.html")):
    text = read_text(f)
    page = page_name(f)

    m_content = first_match([
        r'"content":"(.*?)","content_no_html":"',
        r'"content":"(.*?)","contentnohtml":"',
        r'"content":"(.*?)","content_no_html":',
    ], text)

    m_text = first_match([
        r'"content_no_html":"(.*?)"(?:,|})',
        r'"contentnohtml":"(.*?)"(?:,|})',
    ], text)

    content_html = unescape_payload(m_content.group(1)) if m_content else ""
    content_text = unescape_payload(m_text.group(1)) if m_text else ""

    vimeo = re.findall(r'https://player\.vimeo\.com/video/[0-9]+(?:\?[^"\']*)?', text)
    youtube = re.findall(r'https://www\.youtube\.com/watch\?v=[^"\'\\ ]+', text)
    images = re.findall(r'https://[^"\' ]+\.(?:jpg|jpeg|png|webp|gif|avif)(?:\?[^"\' ]*)?', text, re.I)

    title = ""
    if content_html:
        mt = re.search(r'<h1[^>]*>(.*?)</h1>', content_html, re.I | re.S)
        if mt:
            title = re.sub(r'<[^>]+>', '', mt.group(1)).strip()
    if not title:
        mt = re.search(r'<title>(.*?)</title>', text, re.I | re.S)
        if mt:
            title = html.unescape(mt.group(1)).strip()

    payload = {
        "page": page,
        "file": str(f),
        "title": title,
        "content_html": content_html,
        "content_text": content_text,
        "vimeo": sorted(set(vimeo)),
        "youtube": sorted(set(youtube)),
        "images": sorted(set(images))[:100]
    }

    (OUT / f"{page}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    summary.append({
        "page": page,
        "title": title,
        "has_content_html": bool(content_html),
        "content_html_len": len(content_html),
        "content_text_len": len(content_text),
        "vimeo_count": len(set(vimeo)),
        "youtube_count": len(set(youtube)),
        "image_count": len(set(images))
    })

(OUT / "summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(summary, indent=2, ensure_ascii=False))
