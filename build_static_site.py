#!/usr/bin/env python3
import json, html, re
from pathlib import Path

rendered = Path("rendered")
site = Path("site")
site.mkdir(exist_ok=True)

def slug_to_filename(page):
    if page == "home":
        return "index.html"
    return f"{page}.html"

def safe(s):
    return html.escape(str(s), quote=False)

template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
{css}
</style>
</head>
<body>
<main class="page">
  <header class="topbar">
    <a href="index.html">Home</a>
    <a href="Menu.html">Menu</a>
    <a href="Portfolio.html">Portfolio</a>
  </header>
  <article class="content">
    {content}
  </article>
</main>
</body>
</html>
"""

css = """
html,body{margin:0;padding:0;background:#000;color:#fff;font-family:Arial,sans-serif}
.page{min-height:100vh;padding:32px}
.topbar{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px}
.topbar a{color:#fff;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.3);padding-bottom:2px}
.content{max-width:960px}
.content h1,.content h2,.content p{margin:0 0 16px}
.content iframe{display:block;max-width:100%;width:100%;aspect-ratio:16/9;height:auto}
.content a{color:#fff}
img{max-width:100%;height:auto;display:block}
"""

built = 0

for f in sorted(rendered.glob("*.json")):
    if f.name == "summary.json":
        continue

    d = json.loads(f.read_text(encoding="utf-8"))

    if not isinstance(d, dict) or "page" not in d:
        print("skipping non-page json:", f.name)
        continue

    page = d.get("page", "")
    title = d.get("title") or page
    content = d.get("content_html") or ""
    description = re.sub(r"<[^>]+>", "", content)
    description = description.replace('"', "&quot;").strip()[:160]

    out = site / slug_to_filename(page)
    out.write_text(
        template.format(
            title=safe(title),
            description=safe(description),
            content=content,
            css=css
        ),
        encoding="utf-8"
    )
    built += 1

print("built", built, "pages")
