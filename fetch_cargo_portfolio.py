from pathlib import Path
import json, re, html, urllib.parse
from playwright.sync_api import sync_playwright

BASE = Path("final-data")
SITE = Path("site")
ASSETS = SITE / "assets" / "cargo"
ASSETS.mkdir(parents=True, exist_ok=True)

portfolio = json.loads((BASE / "portfolio.json").read_text(encoding="utf-8"))
item = next(x for x in portfolio if x.get("project_url") == "Portfolio")
raw = item["content"]

raw = re.sub(r'<meta[^>]*>', '', raw, flags=re.I)
raw = re.sub(r'<title[^>]*>.*?</title>', '', raw, flags=re.I | re.S)
raw = raw.replace('rel="history"', '')
raw = raw.replace('data-src=', 'src=')
raw = re.sub(r'\sborder="0"', '', raw)

imgs = []
for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*class="image-link"[^>]*>(<img[^>]+>)</a>', raw, flags=re.I | re.S):
    slug = m.group(1)
    img = m.group(2)
    src_m = re.search(r'src="([^"]+)"', img)
    alt_m = re.search(r'alt="([^"]*)"', img)
    cap_m = re.search(r'data-caption="([^"]*)"', img)
    src = src_m.group(1) if src_m else ""
    caption = html.unescape(cap_m.group(1) if cap_m else (alt_m.group(1) if alt_m else ""))
    fname = urllib.parse.unquote(re.sub(r'[?#].*$', '', src).split('/')[-1])
    imgs.append((slug, src, fname, caption, img))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://cargo.site", wait_until="domcontentloaded")

    for slug, src, fname, caption, img_tag in imgs:
        out = ASSETS / fname
        if out.exists() and out.stat().st_size > 0:
            print("EXISTS", fname)
            continue
        try:
            resp = page.request.get(src, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://cargo.site/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            })
            if resp.ok:
                out.write_bytes(resp.body())
                print("SAVED", fname, out.stat().st_size)
            else:
                print("FAILED", fname, resp.status)
        except Exception as e:
            print("ERROR", fname, str(e))
    browser.close()

local_files = {p.name for p in ASSETS.glob("*") if p.is_file() and p.stat().st_size > 0}

def repl(m):
    slug = m.group(1)
    img = m.group(2)

    src_m = re.search(r'src="([^"]+)"', img)
    alt_m = re.search(r'alt="([^"]*)"', img)
    cap_m = re.search(r'data-caption="([^"]*)"', img)

    src = src_m.group(1) if src_m else ""
    caption = html.unescape(cap_m.group(1) if cap_m else (alt_m.group(1) if alt_m else ""))
    fname = urllib.parse.unquote(re.sub(r'[?#].*$', '', src).split('/')[-1])

    if fname in local_files:
        img = re.sub(r'src="[^"]+"', f'src="assets/cargo/{fname}"', img, count=1)

    return f'<a href="{slug}.html" class="image-link">{img}<span class="tile-caption">{html.escape(caption)}</span></a>'

content = re.sub(
    r'<a[^>]+href="([^"]+)"[^>]*class="image-link"[^>]*>(<img[^>]+>)</a>',
    repl,
    raw,
    flags=re.I | re.S
)

doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portfolio</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <main class="gallery-wrap">
    <div class="image-gallery">
      {content}
    </div>
  </main>
</body>
</html>
"""
(SITE / "portfolio.html").write_text(doc, encoding="utf-8")
print("WROTE site/portfolio.html")
