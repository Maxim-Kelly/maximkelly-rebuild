#!/usr/bin/env python3
import json, html, re
from pathlib import Path

ROOT = Path(".")
RENDERED = ROOT / "rendered"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

PAGE_FILES = {}
PAGE_DATA = {}

def load_pages():
    for f in sorted(RENDERED.glob("*.json")):
        if f.name == "summary.json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or "page" not in d:
            continue
        PAGE_DATA[d["page"]] = d

def filename_for(page):
    return "index.html" if page == "home" else f"{page}.html"

def normalize_lookup_key(s):
    return (s or "").strip().lower()

def build_lookup():
    lookup = {}
    for page in PAGE_DATA:
        lookup[normalize_lookup_key(page)] = filename_for(page)
        lookup[normalize_lookup_key(page.replace("_", "-"))] = filename_for(page)
        lookup[normalize_lookup_key(page.replace("-", "_"))] = filename_for(page)
    aliases = {
        "portfolio": "Portfolio.html",
        "films-1": "Portfolio.html",
        "films": "Portfolio.html",
        "menu": "Menu.html",
        "contact": "Contact.html",
        "home": "index.html",
        "selected-press": "Selected-Press.html",
        "belief": "BELIEF.html",
        "hot-chip": "HOT-CHIP.html",
        "pdm_disco": "PDM_DISCO.html",
        "pdm-disco": "PDM_DISCO.html",
        "vollebak_sonic": "Vollebak_Sonic.html",
        "vollebak-sonic": "Vollebak_Sonic.html",
    }
    lookup.update(aliases)
    return lookup

def unescape_unicode(s):
    if not s:
        return s
    try:
        return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        return s

def clean_title(s):
    s = unescape_unicode(s or "")
    return html.escape(s, quote=False)

def rewrite_links(content, lookup):
    if not content:
        return ""
    content = content.replace('href=\\"', 'href="').replace('\\"', '"')
    content = content.replace("\\/", "/")

    def repl(m):
        href = m.group(1)
        raw = href.strip()

        if raw.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
            return f'href="{raw}"'

        key = normalize_lookup_key(raw)
        if key in lookup:
            return f'href="{lookup[key]}"'

        key2 = normalize_lookup_key(raw.replace(" ", "-"))
        if key2 in lookup:
            return f'href="{lookup[key2]}"'

        return f'href="{raw}"'

    content = re.sub(r'href="([^"]+)"', repl, content)
    return content

def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

load_pages()
lookup = build_lookup()

base_css = """
html,body{
  margin:0;padding:0;background:#000;color:#fff;
  font-family:Arial,Helvetica,sans-serif;
}
*{box-sizing:border-box}
body{min-height:100vh}
.page{
  min-height:100vh;
  padding:3.5rem;
}
.topbar{
  position:sticky; top:0;
  display:flex; justify-content:space-between; align-items:flex-start;
  gap:1rem; padding-bottom:2rem; margin-bottom:1rem;
  background:#000; z-index:10;
}
.topbar .left,.topbar .right{width:23%}
.topbar .right{text-align:right}
.topbar a{
  color:#fff; text-decoration:none;
}
.content-wrap{
  display:flex; justify-content:center;
}
.content{
  width:min(100%, 960px);
  text-align:center;
}
.content h1,.content h2,.content p,.content br{margin:0}
.content h1,.content h2{font-weight:normal}
.content iframe{
  display:block; width:min(100%,640px); max-width:100%;
  aspect-ratio:16/9; height:auto; margin:0 auto;
}
.content img{
  display:block; max-width:100%; height:auto; margin:0 auto;
}
.content a{color:#fff}
@media (max-width: 768px){
  .page{padding:1.25rem}
  .topbar .left,.topbar .right{width:auto}
  .content{text-align:center}
}
"""

template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
{base_css}
{local_css}
</style>
</head>
<body>
<main class="page">
  <header class="topbar">
    <div class="left"><a href="Menu.html">MAXIM KELLY</a></div>
    <div class="right"><a href="Menu.html">+</a></div>
  </header>
  <div class="content-wrap">
    <article class="content">
      {content}
    </article>
  </div>
</main>
</body>
</html>
"""

built = 0

for page, d in PAGE_DATA.items():
    title = clean_title(d.get("title") or page)
    content = d.get("content_html") or ""
    content = rewrite_links(content, lookup)

    local_css = d.get("local_css", "") or ""
    local_css = local_css.replace("\\n", "\n").replace("\\/", "/")

    description = strip_html(content)[:160].replace('"', "&quot;")

    out = SITE / filename_for(page)
    out.write_text(
        template.format(
            title=title,
            description=html.escape(description, quote=True),
            base_css=base_css,
            local_css=local_css,
            content=content
        ),
        encoding="utf-8"
    )
    built += 1

print("built", built, "pages")
