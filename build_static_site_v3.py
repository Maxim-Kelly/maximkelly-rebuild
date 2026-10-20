#!/usr/bin/env python3
"""Rebuild the GitHub Pages static site from the cleaned Cargo export data.

This script deliberately avoids touching downloaded assets. It rewrites only HTML files
and the small shared stylesheet used by those HTML files.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
RENDERED = ROOT / "rendered"
FINAL_DATA = ROOT / "final-data"
CONTENT = ROOT / "content"
SITE = ROOT / "site"
ASSETS = SITE / "assets"
CARGO_ASSETS = ASSETS / "cargo"
STYLE = ASSETS / "style.css"

SITE.mkdir(exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)

NON_PROJECT_PAGES = {
    "summary",
    "home",
    "Portfolio",
    "Menu",
    "Contact",
    "Selected-Press",
}
TOP_PAGE_FILENAMES = {
    "Menu": "menu.html",
    "Portfolio": "portfolio.html",
    "Contact": "contact.html",
    "Selected-Press": "selected-press.html",
    "home": "index.html",
}

EXTERNAL_HREF_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "#",
    "javascript:",
    "data:",
)


THEME_CSS = (
    """
:root{
  --bg:#0a0a0b;
  --fg:#f2f1ed;
  --muted:#a8a59e;
  --dim:#6e6b65;
  --rule:rgba(242,241,237,.13);
  --pad:clamp(20px,3.5vw,64px);
  --header-height:4.5rem;
  --font:'Helvetica Neue',Helvetica,Arial,sans-serif;
  --text-caption:.75rem;
  --text-body:1rem;
  --text-title:1.6875rem;
  --text-display:4.5rem;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;scroll-padding-block-start:var(--header-height)}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);font-family:var(--font);min-height:100%}
body{font-size:var(--text-body);line-height:1.55}
a{color:inherit;text-decoration:none}
img,video{display:block;max-width:100%;height:auto}
.site-header{position:fixed;inset:0 0 auto 0;z-index:50;display:flex;justify-content:space-between;align-items:baseline;padding:22px var(--pad);pointer-events:none;background:linear-gradient(to bottom,rgba(10,10,11,.94),rgba(10,10,11,.55) 55%,rgba(10,10,11,0))}
.site-header a{pointer-events:auto;transition:opacity .25s ease}
.site-header a:hover{opacity:.5;text-decoration:none}
.brand{font-size:var(--text-caption);line-height:1.2;letter-spacing:.22em;text-transform:uppercase;font-weight:500}
.nav-toggle{font-size:1.375rem;line-height:1.1}
.menu-main{min-height:100vh;min-height:100dvh;display:flex;align-items:center;padding:calc(var(--pad) + 84px) var(--pad) var(--pad)}
.menu-wrap{width:100%;max-width:1120px;margin:0 auto}
.menu-kicker{font-size:var(--text-caption);line-height:1.2;letter-spacing:.32em;text-transform:uppercase;color:var(--dim);margin-bottom:clamp(26px,4vw,52px)}
.menu-list{display:grid}
.menu-list a{display:flex;align-items:baseline;justify-content:space-between;gap:1.5rem;padding:clamp(14px,2vw,26px) 0;border-top:1px solid var(--rule);font-size:clamp(2rem,6.4vw,var(--text-display));line-height:1.1;letter-spacing:-.05em;text-wrap:balance;transition:opacity .3s ease,padding-inline-start .35s ease}
.menu-list a:last-child{border-bottom:1px solid var(--rule)}
.menu-list a:hover{opacity:.5;padding-inline-start:.4em;text-decoration:none}
.menu-list .idx{font-size:var(--text-caption);line-height:1.2;letter-spacing:.26em;color:var(--dim)}
.portfolio-main{min-height:100vh;min-height:100dvh;padding:0;margin:0}
.image-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;background:var(--bg)}
.image-gallery .image-link{position:relative;display:block;background:#101012}
.image-gallery .tile-media{display:block;overflow:hidden}
.image-gallery img{width:100%;height:auto;display:block;transition:transform .9s cubic-bezier(.2,.7,.2,1),opacity .5s ease}
.image-gallery .image-link:hover img{transform:scale(1.04)}
.tile-caption{position:absolute;left:0;right:0;bottom:0;z-index:2;padding:clamp(20px,2.6vw,32px) clamp(16px,2vw,26px);font-size:clamp(var(--text-caption),.82vw,.8125rem);line-height:1.2;letter-spacing:.22em;text-transform:uppercase;color:rgba(255,255,255,.92);background:linear-gradient(to top,rgba(0,0,0,.68),rgba(0,0,0,0))}
.tile-caption:empty{display:none}
.project-main{min-height:100vh;min-height:100dvh;display:flex;justify-content:center;padding:calc(var(--pad) + 98px) var(--pad) var(--pad)}
.project-content{width:min(100%,1080px);margin:0 auto;text-align:center}
.project-back{width:min(100%,640px);margin:0 auto clamp(22px,3.5vw,42px);text-align:start}
.project-back--bottom{margin:clamp(38px,6vw,72px) auto 0}
.project-back a{font-size:var(--text-caption);line-height:1.2;letter-spacing:.26em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--rule);padding-bottom:3px;transition:color .25s ease,border-color .25s ease}
.project-back a:hover{color:var(--fg);border-bottom-color:var(--fg);text-decoration:none}
.project-head h1{margin:0;font-size:clamp(1.75rem,4.2vw,3.5rem);line-height:1.08;letter-spacing:-.035em;font-weight:400;text-wrap:balance}
.project-head h2{margin:clamp(12px,1.6vw,18px) 0 0;font-size:clamp(.875rem,1.3vw,1.125rem);line-height:1.3;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);font-weight:400;text-wrap:balance}
.project-player{margin:clamp(38px,6vw,80px) 0 0}
.project-player iframe{width:100%!important;height:auto!important;aspect-ratio:16/9;border:0;display:block;background:#000;box-shadow:0 40px 100px rgba(0,0,0,.55)}
.project-credits{margin:clamp(36px,5vw,64px) auto 0;display:grid;gap:clamp(16px,2.2vw,26px);width:min(100%,640px);text-align:start}
.credit{display:grid;gap:5px;padding-top:15px;border-top:1px solid var(--rule)}
.credit-label{font-size:var(--text-caption);line-height:1.2;letter-spacing:.26em;text-transform:uppercase;color:var(--dim)}
.credit-value{font-size:clamp(.875rem,1.3vw,1.125rem);letter-spacing:-.015em;line-height:1.45;overflow-wrap:break-word}
.info-main{padding:calc(var(--pad) + 108px) var(--pad) var(--pad)}
.info-content{width:min(100%,1120px);margin:0 auto}
.info-content .rule{border:0;border-top:1px solid var(--rule);margin:clamp(26px,3.5vw,44px) 0}
.info-content [grid-row]{display:grid;grid-template-columns:minmax(160px,.62fr) minmax(0,1.6fr);gap:clamp(18px,3vw,56px);align-items:start}
.info-content [grid-col]{min-width:0}
.info-content [grid-col] h1,.info-content [grid-col] h2{margin:0}
.info-content [grid-col]:nth-child(1) h1{font-size:clamp(var(--text-caption),1vw,.8125rem);letter-spacing:.26em;text-transform:uppercase;color:var(--dim);line-height:1.6}
.info-content [grid-col]:nth-child(2) h2{margin-block-start:clamp(34px,4.6vw,58px);margin-block-end:12px;font-size:var(--text-caption);line-height:1.2;letter-spacing:.26em;text-transform:uppercase;color:var(--muted)}
.info-content [grid-col]:nth-child(2) h2:first-child{margin-block-start:0}
.info-content [grid-col]:nth-child(2) h1{margin-block-start:10px;font-size:clamp(1.0625rem,1.5vw,1.3125rem);letter-spacing:-.02em;line-height:1.35;text-wrap:balance}
.info-content [grid-col]:nth-child(2) h2 + h1{margin-block-start:0}
.info-content a{border-bottom:1px solid var(--rule);padding-bottom:2px;overflow-wrap:anywhere;transition:border-color .25s ease,opacity .25s ease}
.info-content a:hover{border-bottom-color:var(--fg);opacity:.85;text-decoration:none}
.redirect-main{min-height:100vh;min-height:100dvh;display:flex;align-items:center;justify-content:center;text-align:center;padding:var(--pad)}
@media (max-width:760px){
  .site-header{padding:16px}
  .image-gallery{grid-template-columns:repeat(1,minmax(0,1fr))}
  .tile-caption{font-size:var(--text-caption);letter-spacing:.18em;padding:38px 14px 12px}
  .project-main,.info-main,.menu-main{padding-inline:16px}
  .info-content [grid-row]{grid-template-columns:minmax(0,1fr);gap:8px}
  .info-content [grid-col]:nth-child(2) h1{font-size:1.125rem}
  .menu-list a{font-size:clamp(1.875rem,11vw,3.25rem)}
}
""".strip()
    + "\n"
)

STYLE_VERSION = hashlib.sha1(THEME_CSS.encode("utf-8")).hexdigest()[:8]
STYLESHEET = f"assets/style.css?v={STYLE_VERSION}"

BACK_TOP = '<p class="project-back"><a href="portfolio.html">\u2190 Portfolio</a></p>'
BACK_BOTTOM = (
    '<p class="project-back project-back--bottom">'
    '<a href="portfolio.html">\u2190 Back to portfolio</a></p>'
)


def clean_content_noise(fragment: str) -> str:
    """Strip Cargo editor layout noise so the stylesheet owns presentation."""
    fragment = re.sub(r'\s+style="[^"]*"', "", fragment, flags=re.I)
    fragment = re.sub(r"\s+style='[^']*'", "", fragment, flags=re.I)
    # Columns the Cargo grid left empty.
    fragment = re.sub(r"<div[^>]*grid-col[^>]*>\s*</div>", "", fragment, flags=re.I)
    # Runs of <br> are only spacing; a single break inside a heading is real.
    fragment = re.sub(r"(?:<br\s*/?>\s*){2,}", "", fragment, flags=re.I)
    # Drop breaks that only hug a block boundary.
    fragment = re.sub(
        r"<br\s*/?>\s*(</?(?:div|h[12]|p|article|main|nav)\b)", r"\1", fragment, flags=re.I
    )
    fragment = re.sub(
        r"(</?(?:div|h[12]|p|article|main|nav)\b[^>]*>)\s*<br\s*/?>",
        r"\1",
        fragment,
        flags=re.I,
    )
    fragment = re.sub(r"<hr\b[^>]*>", '<div class="rule"></div>', fragment, flags=re.I)
    # Rows that held nothing but empty columns.
    fragment = re.sub(r"<div[^>]*grid-row[^>]*>\s*</div>", "", fragment, flags=re.I)

    # Cargo pads headings with non-breaking spaces, which pushes centred text off-axis.
    def trim_heading(match: re.Match[str]) -> str:
        inner = re.sub(r"^(?:\s|\xa0|&nbsp;)+", "", match.group(3))
        inner = re.sub(r"(?:\s|\xa0|&nbsp;)+$", "", inner)
        return f"{match.group(1)}{inner}{match.group(4)}"

    fragment = re.sub(
        r"(<h([12])[^>]*>)(.*?)(</h\2>)", trim_heading, fragment, flags=re.I | re.S
    )
    # Cargo pads with stacked non-breaking spaces, which trails link underlines past the text.
    fragment = re.sub(r"\xa0{2,}", "\xa0", fragment)
    fragment = re.sub(r"(?:\s|\xa0)+(?=</a>)", "", fragment, flags=re.I)
    return fragment.strip()


def build_credit_rows(fragment: str) -> str:
    """Group the h1/h2 award pairs into tidy credit rows."""
    items = re.findall(r"<h([12])[^>]*>(.*?)</h\1>", fragment, flags=re.I | re.S)
    rows: list[tuple[str, str]] = []
    pending = ""
    for level, text in items:
        text = strip_tags(text).strip()
        if not text:
            continue
        if level == "1":
            if pending:
                rows.append((pending, ""))
            pending = text
        elif pending:
            rows.append((pending, text))
            pending = ""
        else:
            rows.append(("", text))
    if pending:
        rows.append((pending, ""))
    if not rows:
        return ""
    body = "\n".join(
        '<div class="credit">'
        f'<span class="credit-label">{html.escape(label)}</span>'
        f'<span class="credit-value">{html.escape(value)}</span>'
        "</div>"
        for label, value in rows
    )
    return f'<div class="project-credits">\n{body}\n</div>'


def build_project_content(fragment: str) -> str:
    """Turn a raw Cargo project body into a structured, designed page."""
    fragment = re.sub(
        r"<h1[^>]*>\s*<a\b[^>]*icon-link[^>]*>.*?</a>\s*</h1>",
        "",
        fragment,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<a\b[^>]*icon-link[^>]*>.*?</a>", "", fragment, flags=re.I | re.S)
    fragment = re.sub(r'<p class="project-back[^"]*"[^>]*>.*?</p>', "", fragment, flags=re.I | re.S)
    fragment = fragment.replace("\ue04a\ufe0e\ufe0e\ufe0e", "")

    match = re.search(r"<iframe\b[^>]*>.*?</iframe>", fragment, flags=re.I | re.S)
    if match:
        head = fragment[: match.start()]
        player = match.group(0)
        credits_raw = fragment[match.end() :]
    else:
        head, player, credits_raw = fragment, "", ""

    head_html = clean_content_noise(head)
    credits_html = build_credit_rows(credits_raw)

    parts = [BACK_TOP]
    if head_html:
        parts.append(f'<div class="project-head">\n{head_html}\n</div>')
    if player:
        parts.append(f'<div class="project-player">\n{player}\n</div>')
    if credits_html:
        parts.append(credits_html)
    parts.append(BACK_BOTTOM)
    return "\n".join(parts)


# --- content/ : plain-YAML source of truth -------------------------------

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def inline_markup(value: str) -> str:
    """Render [text](url) links and escape everything else."""
    out: list[str] = []
    pos = 0
    for match in LINK_RE.finditer(value):
        out.append(html.escape(value[pos : match.start()]))
        out.append(
            f'<a href="{html.escape(match.group(2), quote=True)}">'
            f"{html.escape(match.group(1))}</a>"
        )
        pos = match.end()
    out.append(html.escape(value[pos:]))
    return "".join(out)


def build_project_from_yaml(doc: dict[str, Any]) -> str:
    title = html.escape(str(doc.get("title") or ""))
    artist = html.escape(str(doc.get("artist") or ""))
    parts = [
        BACK_TOP,
        f'<div class="project-head">\n<h1>{title}</h1><h2>{artist}</h2>\n</div>',
    ]

    vimeo = str(doc.get("vimeo") or "").strip()
    if vimeo:
        parts.append(
            '<div class="project-player">\n'
            f'<iframe src="{html.escape(vimeo, quote=True)}" '
            'frameborder="0" allow="autoplay; fullscreen; picture-in-picture" '
            "allowfullscreen></iframe>\n</div>"
        )

    credits = doc.get("credits") or []
    if credits:
        rows = []
        for credit in credits:
            label = html.escape(str(credit.get("label") or ""))
            value = html.escape(str(credit.get("value") or ""))
            rows.append(
                '<div class="credit">'
                f'<span class="credit-label">{label}</span>'
                f'<span class="credit-value">{value}</span>'
                "</div>"
            )
        parts.append(f'<div class="project-credits">\n{"\n".join(rows)}\n</div>')

    parts.append(BACK_BOTTOM)
    return "\n".join(parts)


def build_portfolio_from_yaml(tiles: list[dict[str, Any]]) -> str:
    cells = []
    for tile in tiles:
        slug = html.escape(str(tile.get("slug") or ""), quote=True)
        caption = html.escape(str(tile.get("caption") or ""))
        image = str(tile.get("image") or "").strip()
        src = html.escape(f"assets/cargo/{image}" if image else "", quote=True)
        width = tile.get("width")
        height = tile.get("height")
        size = f' width="{int(width)}" height="{int(height)}"' if width and height else ""
        cells.append(
            f'<a href="{slug}.html" class="image-link">'
            f'<span class="tile-media"><img{size} src="{src}" '
            f'alt="{caption}" data-caption="{caption}"/></span>'
            f'<span class="tile-caption">{caption}</span></a>'
        )
    return '<div class="image-gallery">\n' + "\n".join(cells) + "\n</div>"


def build_info_from_yaml(
    rows: list[dict[str, Any]], *, kind: str
) -> str:
    blocks = []
    for row in rows:
        if kind == "contact":
            left = f"<h1>{html.escape(str(row.get('region') or ''))}"
            if row.get("org"):
                url = html.escape(str(row.get("org_url") or ""), quote=True)
                left += f'<br><a href="{url}" target="_blank">{html.escape(str(row["org"]))}</a>'
            left += "</h1>"

            right = f"<h2>{html.escape(str(row.get('person') or ''))}</h2>"
            if row.get("email"):
                email = str(row["email"])
                right += (
                    f'<h1><a href="mailto:{html.escape(email, quote=True)}">'
                    f"{html.escape(email)}</a></h1>"
                )
        else:
            left = f"<h1>{html.escape(str(row.get('outlet') or ''))}</h1>"
            inner = []
            for group in row.get("groups") or []:
                inner.append(f"<h2>{html.escape(str(group.get('label') or ''))}</h2>")
                for item in group.get("items") or []:
                    inner.append(f"<h1>{inline_markup(str(item))}</h1>")
            right = "<div>" + "\n".join(inner) + "</div>"

        blocks.append(
            '<div grid-row>\n'
            f"<div grid-col><div>{left}</div></div>\n"
            f"<div grid-col><div>{right}</div></div>\n"
            '</div>\n<div class="rule"></div>'
        )
    return "\n".join(blocks)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def decode_literal_escapes(value: Any) -> str:
    """Decode literal Cargo/JSON escape leftovers without corrupting real Unicode."""
    if value is None:
        return ""
    text = str(value)

    def repl_u4(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    def repl_u8(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    text = re.sub(r"\\u([0-9a-fA-F]{4})", repl_u4, text)
    text = re.sub(r"\\U([0-9a-fA-F]{8})", repl_u8, text)
    text = text.replace(r"\/", "/")
    text = text.replace(r"\n", "\n").replace(r"\r", "").replace(r"\t", "\t")
    text = text.replace(r"\"", '"')
    return html.unescape(text)


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def load_rendered_pages() -> dict[str, dict[str, Any]]:
    pages: dict[str, dict[str, Any]] = {}
    for path in sorted(RENDERED.glob("*.json")):
        if path.stem == "summary":
            continue
        data = read_json(path)
        if isinstance(data, dict) and data.get("page"):
            pages[str(data["page"])] = data
    return pages


def load_final_page(json_name: str, project_url: str) -> dict[str, Any] | None:
    path = FINAL_DATA / json_name
    if not path.exists():
        return None
    data = read_json(path)
    if not isinstance(data, list):
        return None
    for item in data:
        if isinstance(item, dict) and item.get("project_url") == project_url:
            return item
    return None


def project_display_title(slug: str) -> str:
    title = slug.replace("_", " ").replace("-", " ")
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Project"


def canonical_filename(page_or_slug: str) -> str:
    return TOP_PAGE_FILENAMES.get(page_or_slug, f"{page_or_slug}.html")


def normalize_lookup_key(raw: str) -> str:
    key = html.unescape(raw or "").strip()
    key = key.replace("\\/", "/")
    if key.startswith("https://maximpkelly.cargo.site/"):
        key = key.removeprefix("https://maximpkelly.cargo.site/")
    if key.startswith("http://maximpkelly.cargo.site/"):
        key = key.removeprefix("http://maximpkelly.cargo.site/")
    key = key.strip("/")
    if key.endswith("/index.html"):
        key = key[: -len("/index.html")]
    elif key.endswith("/index"):
        key = key[: -len("/index")]
    elif key.endswith(".html"):
        key = key[: -len(".html")]
    return key.lower()


def build_lookup(project_slugs: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}

    def add(raw: str, target: str) -> None:
        lookup[normalize_lookup_key(raw)] = target

    add("PORTFOLIO", "portfolio.html")
    add("Portfolio", "portfolio.html")
    add("portfolio", "portfolio.html")
    add("FILMS", "portfolio.html")
    add("FILMS-1", "portfolio.html")
    add("films", "portfolio.html")
    add("Menu", "menu.html")
    add("menu", "menu.html")
    add("Contact", "contact.html")
    add("contact", "contact.html")
    add("Selected-Press", "selected-press.html")
    add("Selected_Press", "selected-press.html")
    add("selected-press", "selected-press.html")
    add("selected_press", "selected-press.html")
    add("Home", "index.html")
    add("home", "index.html")

    for slug in project_slugs:
        target = f"{slug}.html"
        variants = {
            slug,
            slug.lower(),
            slug.replace("_", "-"),
            slug.replace("_", "-").lower(),
            slug.replace("-", "_"),
            slug.replace("-", "_").lower(),
        }
        for variant in variants:
            add(variant, target)
    return lookup


def split_href_suffix(href: str) -> tuple[str, str]:
    match = re.match(r"^([^?#]*)(.*)$", href)
    if not match:
        return href, ""
    return match.group(1), match.group(2)


def rewrite_href_value(href: str, lookup: dict[str, str]) -> str:
    href = html.unescape(href.strip())
    if not href or href.startswith(EXTERNAL_HREF_PREFIXES):
        return href
    base, suffix = split_href_suffix(href)
    key = normalize_lookup_key(base)
    if key in lookup:
        return lookup[key] + suffix
    alt_key = normalize_lookup_key(base.replace(" ", "-"))
    if alt_key in lookup:
        return lookup[alt_key] + suffix
    return href


def rewrite_links(fragment: str, lookup: dict[str, str]) -> str:
    fragment = fragment.replace('href=\\"', 'href="').replace('\\"', '"')
    fragment = fragment.replace(r"\/", "/")
    fragment = re.sub(r"\s+rel=([\"'])history\1", "", fragment, flags=re.I)
    fragment = re.sub(r"\s+rel=([\"'])home_page\1", "", fragment, flags=re.I)

    def repl(match: re.Match[str]) -> str:
        quote = match.group(1)
        href = match.group(2)
        rewritten = rewrite_href_value(href, lookup)
        return f"href={quote}{html.escape(rewritten, quote=True)}{quote}"

    return re.sub(r"href=([\"'])(.*?)\1", repl, fragment, flags=re.I | re.S)


def strip_embedded_document_markup(fragment: str) -> str:
    fragment = re.sub(r"<meta\b[^>]*>", "", fragment, flags=re.I)
    fragment = re.sub(r"<title\b[^>]*>.*?</title>", "", fragment, flags=re.I | re.S)
    fragment = re.sub(r"<style\b[^>]*>.*?</style>", "", fragment, flags=re.I | re.S)
    return fragment


def sanitize_fragment(
    fragment: str, lookup: dict[str, str], *, strip_document_bits: bool = False
) -> str:
    fragment = decode_literal_escapes(fragment)
    if strip_document_bits:
        fragment = strip_embedded_document_markup(fragment)
    fragment = rewrite_links(fragment, lookup)
    fragment = re.sub(r"\s+border=([\"'])0\1", "", fragment, flags=re.I)
    fragment = re.sub(r"\s+width_o=([\"']).*?\1", "", fragment, flags=re.I | re.S)
    fragment = re.sub(r"\s+height_o=([\"']).*?\1", "", fragment, flags=re.I | re.S)
    fragment = re.sub(r"\s+class=([\"'])\1", "", fragment, flags=re.I)
    return fragment.strip()


def filename_from_url(url: str) -> str:
    clean = re.sub(r"[?#].*$", "", url or "")
    return urllib.parse.unquote(clean.rstrip("/").split("/")[-1])


def local_asset_src_for(url: str) -> str | None:
    filename = filename_from_url(url)
    if not filename:
        return None

    # optimize_images.py may have converted e.g. Foo.png to Foo.jpg.
    stem = Path(filename).stem
    candidates = [
        filename,
        f"{stem}.jpg",
        f"{stem}.jpeg",
        f"{stem}.webp",
        f"{stem}.png",
    ]
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        candidate = CARGO_ASSETS / name
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            return f"assets/cargo/{name}"
    return None


def attr_pattern(attr: str) -> str:
    # Do not let `src` match the tail of Cargo's `data-src` attribute.
    return rf"(?<![\w:-]){re.escape(attr)}=([\"'])(.*?)\1"


def img_attr(img: str, attr: str) -> str:
    match = re.search(attr_pattern(attr), img, flags=re.I | re.S)
    return match.group(2) if match else ""


def set_or_replace_img_src(img: str, src: str) -> str:
    escaped = html.escape(src, quote=True)
    src_re = attr_pattern("src")
    data_src_re = attr_pattern("data-src")
    if re.search(src_re, img, flags=re.I | re.S):
        img = re.sub(src_re, f'src="{escaped}"', img, count=1, flags=re.I | re.S)
    elif re.search(data_src_re, img, flags=re.I | re.S):
        img = re.sub(data_src_re, f'src="{escaped}"', img, count=1, flags=re.I | re.S)
    else:
        img = re.sub(r"<img\b", f'<img src="{escaped}"', img, count=1, flags=re.I)
    img = re.sub(r"\s+(?<![\w:-])data-src=([\"']).*?\1", "", img, flags=re.I | re.S)
    return img


def rewrite_portfolio_gallery(fragment: str, lookup: dict[str, str]) -> str:
    fragment = sanitize_fragment(fragment, lookup, strip_document_bits=True)

    def repl(match: re.Match[str]) -> str:
        href = match.group(1)
        img = match.group(2)
        target = rewrite_href_value(href, lookup)

        img = re.sub(r"\s+border=([\"'])0\1", "", img, flags=re.I)
        img = re.sub(r"\s+width_o=([\"']).*?\1", "", img, flags=re.I | re.S)
        img = re.sub(r"\s+height_o=([\"']).*?\1", "", img, flags=re.I | re.S)

        raw_src = img_attr(img, "src") or img_attr(img, "data-src")
        local_src = local_asset_src_for(raw_src)
        if local_src:
            img = set_or_replace_img_src(img, local_src)
        elif raw_src and img_attr(img, "data-src"):
            img = set_or_replace_img_src(img, raw_src)

        caption = decode_literal_escapes(
            img_attr(img, "data-caption") or img_attr(img, "alt")
        )
        caption = strip_tags(caption)
        return (
            f'<a href="{html.escape(target, quote=True)}" class="image-link">'
            f'<span class="tile-media">{img}</span>'
            f'<span class="tile-caption">{html.escape(caption)}</span></a>'
        )

    return re.sub(
        r"<a\b[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*class=[\"\'][^\"\']*\bimage-link\b[^\"\']*[\"\'][^>]*>\s*(<img\b[^>]*>)\s*</a>",
        repl,
        fragment,
        flags=re.I | re.S,
    )


def normalize_project_back_link(fragment: str) -> str:
    back_html = '<p class="project-back"><a href="portfolio.html" class="back-link">← Back to portfolio</a></p>'
    fragment = re.sub(
        r"<h1[^>]*>\s*<a\b[^>]*class=[\"\'][^\"\']*\bicon-link\b[^\"\']*[\"\'][^>]*>.*?</a>\s*</h1>",
        back_html,
        fragment,
        flags=re.I | re.S,
    )
    fragment = re.sub(
        r"<a\b[^>]*class=[\"\'][^\"\']*\bicon-link\b[^\"\']*[\"\'][^>]*>.*?</a>",
        '<a href="portfolio.html" class="back-link">← Back to portfolio</a>',
        fragment,
        flags=re.I | re.S,
    )
    fragment = fragment.replace("\ue04a\ufe0e\ufe0e\ufe0e", "")
    if 'class="back-link"' not in fragment:
        fragment = fragment.rstrip() + "\n" + back_html
    return fragment


def render_shell(title: str, body_class: str, main_class: str, content: str) -> str:
    title_escaped = html.escape(title, quote=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_escaped}</title>
  <meta name="description" content="Maxim Kelly is a British Director and Photographer based in Barcelona.">
  <link rel="stylesheet" href="{STYLESHEET}">
</head>
<body class="{html.escape(body_class, quote=True)}">
  <header class="site-header" aria-label="Site header">
    <a class="brand" href="menu.html">MAXIM KELLY</a>
    <a class="nav-toggle" href="menu.html" aria-label="Menu">+</a>
  </header>
  <main class="{html.escape(main_class, quote=True)}">
{content}
  </main>
</body>
</html>
"""


def render_redirect(target: str, title: str = "Redirecting") -> str:
    target_escaped = html.escape(target, quote=True)
    script_target = json.dumps(target)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title, quote=False)}</title>
  <link rel="canonical" href="{target_escaped}">
  <meta http-equiv="refresh" content="0; url={target_escaped}">
</head>
<body style="background:#000;color:#fff;font-family:Arial,Helvetica,sans-serif;">
  <main style="min-height:100vh;min-height:100dvh;display:flex;align-items:center;justify-content:center;text-align:center;">
    <p>Redirecting to <a style="color:#fff" href="{target_escaped}">{target_escaped}</a></p>
  </main>
  <script>window.location.replace({script_target});</script>
</body>
</html>
"""


def write_file(relative: str | Path, content: str) -> None:
    path = SITE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_root_redirect(filename: str, target: str) -> None:
    # macOS is commonly case-insensitive. Writing `Menu.html` after `menu.html`
    # would overwrite the real page locally, even though GitHub Pages would treat
    # them as distinct paths. Skip case-only aliases and catch those via the
    # extensionless directory redirects instead.
    if filename == target or filename.casefold() == target.casefold():
        return
    write_file(filename, render_redirect(target, f"Redirecting to {target}"))


def write_directory_redirect(directory: str, target_from_directory: str) -> None:
    write_file(
        Path(directory) / "index.html",
        render_redirect(target_from_directory, "Redirecting"),
    )


def alias_variants(slug: str) -> set[str]:
    return {
        slug,
        slug.lower(),
        slug.replace("_", "-"),
        slug.replace("_", "-").lower(),
        slug.replace("-", "_"),
        slug.replace("-", "_").lower(),
    }


def build_404_alias_map(project_slugs: list[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}

    def add(raw: str, target: str) -> None:
        key = raw.strip("/").lower()
        if key:
            aliases[key] = target
            if key.endswith(".html"):
                aliases[key[:-5]] = target
            else:
                aliases[f"{key}.html"] = target

    for raw, target in {
        "portfolio": "portfolio.html",
        "portfolio.html": "portfolio.html",
        "PORTFOLIO": "portfolio.html",
        "films": "portfolio.html",
        "FILMS-1": "portfolio.html",
        "menu": "menu.html",
        "Menu": "menu.html",
        "contact": "contact.html",
        "Contact": "contact.html",
        "selected-press": "selected-press.html",
        "Selected-Press": "selected-press.html",
        "selected_press": "selected-press.html",
        "home": "menu.html",
        "Home": "menu.html",
    }.items():
        add(raw, target)

    for slug in project_slugs:
        target = f"{slug}.html"
        for variant in alias_variants(slug):
            add(variant, target)
            add(f"{variant}.html", target)
    return aliases


def write_404_redirect(project_slugs: list[str]) -> None:
    alias_map = build_404_alias_map(project_slugs)
    alias_json = json.dumps(alias_map, ensure_ascii=False, sort_keys=True)
    content = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Page not found — Maxim Kelly | Director</title>
  <link rel=\"stylesheet\" href=\"{STYLESHEET}\">
</head>
<body>
  <main class=\"redirect-main\">
    <p>Looking for the right page…</p>
  </main>
  <script>
    const aliases = {alias_json};
    const path = window.location.pathname;
    const trimmed = path.replace(/\\/+$/, '');
    const slash = trimmed.lastIndexOf('/');
    const prefix = slash >= 0 ? trimmed.slice(0, slash + 1) : '/';
    const last = slash >= 0 ? trimmed.slice(slash + 1) : trimmed;
    const key = decodeURIComponent(last || '').toLowerCase();
    const target = aliases[key] || aliases[key.replace(/\\.html$/, '')];
    if (target) {{
      window.location.replace(prefix + target + window.location.search + window.location.hash);
    }} else {{
      const p = document.querySelector('p');
      const a = document.createElement('a');
      a.href = prefix + 'menu.html';
      a.textContent = 'Go to menu';
      p.textContent = 'Page not found. ';
      p.appendChild(a);
    }}
  </script>
</body>
</html>
"""
    write_file("404.html", content)


def build_site() -> None:
    rendered_pages = load_rendered_pages()
    project_slugs = sorted(
        slug for slug in rendered_pages if slug not in NON_PROJECT_PAGES
    )
    # A project can also exist only in content/projects/, so it needs no JSON at all.
    for path in sorted((CONTENT / "projects").glob("*.yml")):
        if path.stem not in project_slugs:
            project_slugs.append(path.stem)
    project_slugs.sort()
    lookup = build_lookup(project_slugs)

    STYLE.write_text(THEME_CSS, encoding="utf-8")

    # Menu: explicitly clean and simple, not the broken extracted header-only page.
    menu_content = """    <div class="menu-wrap">
      <div class="menu-kicker">Maxim Kelly \u2014 Director</div>
      <nav class="menu-list" aria-label="Main navigation">
        <a href="portfolio.html"><span>Films</span><span class="idx">01</span></a>
        <a href="selected-press.html"><span>Selected Press</span><span class="idx">02</span></a>
        <a href="contact.html"><span>Contact</span><span class="idx">03</span></a>
      </nav>
    </div>"""
    write_file(
        "menu.html",
        render_shell(
            "Menu — Maxim Kelly | Director", "menu-page", "menu-main", menu_content
        ),
    )

    # Index/home redirects to the menu.
    write_file("index.html", render_redirect("menu.html", "Maxim Kelly | Director"))
    write_root_redirect("home.html", "menu.html")
    write_root_redirect("Home.html", "menu.html")

    # Portfolio gallery.
    tiles = load_yaml(CONTENT / "portfolio.yml")
    if tiles:
        portfolio_content = build_portfolio_from_yaml(tiles)
    else:
        final_portfolio = load_final_page("portfolio.json", "Portfolio")
        portfolio_fragment = ""
        if final_portfolio and final_portfolio.get("content"):
            portfolio_fragment = str(final_portfolio.get("content"))
        else:
            portfolio_fragment = str(
                rendered_pages.get("Portfolio", {}).get("content_html", "")
            )
        portfolio_content = rewrite_portfolio_gallery(portfolio_fragment, lookup)
    write_file(
        "portfolio.html",
        render_shell(
            "Portfolio — Maxim Kelly | Director",
            "portfolio-page",
            "portfolio-main",
            portfolio_content,
        ),
    )

    # Contact and Selected Press use final-data because rendered/* captured the pinned header instead.
    for json_name, project_url, out_name, page_title in [
        ("contact.json", "Contact", "contact.html", "Contact — Maxim Kelly | Director"),
        (
            "selected-press.json",
            "Selected-Press",
            "selected-press.html",
            "Selected Press — Maxim Kelly | Director",
        ),
    ]:
        kind = "contact" if out_name == "contact.html" else "press"
        source = load_yaml(CONTENT / f"{kind}.yml")
        if source:
            fragment = build_info_from_yaml(source, kind=kind)
        else:
            final_page = load_final_page(json_name, project_url)
            fragment = (
                str(final_page.get("content", ""))
                if final_page
                else str(rendered_pages.get(project_url, {}).get("content_html", ""))
            )
            fragment = sanitize_fragment(fragment, lookup, strip_document_bits=True)
            fragment = clean_content_noise(fragment)
        content = (
            f'    <article class="info-content">\n      {fragment}\n    </article>'
        )
        body_class = (
            "contact-page info-page"
            if out_name == "contact.html"
            else "press-page info-page"
        )
        write_file(out_name, render_shell(page_title, body_class, "info-main", content))

    # Project pages.
    for slug in project_slugs:
        doc = load_yaml(CONTENT / "projects" / f"{slug}.yml")
        if doc:
            fragment = build_project_from_yaml(doc)
        else:
            data = rendered_pages[slug]
            fragment = sanitize_fragment(
                str(data.get("content_html", "")), lookup, strip_document_bits=True
            )
            fragment = build_project_content(fragment)
        content = (
            f'    <article class="project-content">\n      {fragment}\n    </article>'
        )
        title = f"{project_display_title(slug)} — Maxim Kelly | Director"
        write_file(
            f"{slug}.html", render_shell(title, "project-page", "project-main", content)
        )

    # Root-level aliases for old Cargo/title-case/lowercase routes.
    top_aliases = {
        "Menu.html": "menu.html",
        "Portfolio.html": "portfolio.html",
        "Contact.html": "contact.html",
        "Selected-Press.html": "selected-press.html",
        "selected_press.html": "selected-press.html",
        "films.html": "portfolio.html",
        "FILMS-1.html": "portfolio.html",
    }
    for alias, target in top_aliases.items():
        write_root_redirect(alias, target)

    # Directory redirects for old extensionless Cargo links.
    top_dirs = {
        "Menu": "../menu.html",
        "menu": "../menu.html",
        "Portfolio": "../portfolio.html",
        "portfolio": "../portfolio.html",
        "Contact": "../contact.html",
        "contact": "../contact.html",
        "Selected-Press": "../selected-press.html",
        "selected-press": "../selected-press.html",
        "Home": "../menu.html",
        "home": "../menu.html",
        "FILMS-1": "../portfolio.html",
        "films": "../portfolio.html",
    }
    for directory, target in top_dirs.items():
        write_directory_redirect(directory, target)

    for slug in project_slugs:
        canonical = f"{slug}.html"
        # Canonical extensionless directory, e.g. /Vollebak_Sonic/.
        write_directory_redirect(slug, f"../{canonical}")
        for variant in sorted(alias_variants(slug)):
            alias_file = f"{variant}.html"
            write_root_redirect(alias_file, canonical)
            # Also catch extensionless lowercase/alternate paths, e.g. /vollebak-sonic/.
            # Case-only directory variants may collapse on macOS, but they redirect
            # to the same canonical target so they are harmless.
            if variant != slug:
                write_directory_redirect(variant, f"../{canonical}")

    write_404_redirect(project_slugs)

    print(f"built {len(project_slugs)} project pages")
    print("built menu.html, portfolio.html, contact.html, selected-press.html")
    print("wrote redirect aliases for old Cargo/lowercase routes")


def is_external_href(href: str) -> bool:
    href = href.strip()
    return not href or href.startswith(EXTERNAL_HREF_PREFIXES)


def validate_internal_links() -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for path in sorted(SITE.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw_href in re.findall(r"href=([\"'])(.*?)\1", text, flags=re.I | re.S):
            href = html.unescape(raw_href[1]).strip()
            if is_external_href(href):
                continue
            base = href.split("#", 1)[0].split("?", 1)[0]
            if not base:
                continue
            resolved = (path.parent / base).resolve()
            try:
                resolved.relative_to(SITE.resolve())
            except ValueError:
                continue
            if not resolved.exists():
                missing.append((str(path.relative_to(SITE)), href))
    return missing


def validate_no_stale_cargo_links() -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    patterns = [
        ("PORTFOLIO", re.compile(r"href=[\"\']PORTFOLIO[\"\']", re.I)),
        ("icon-link", re.compile(r"\bicon-link\b", re.I)),
        ("Cargo back glyph", re.compile("\ue04a")),
        ("placeholder", re.compile(r"placeholder|lorem ipsum", re.I)),
    ]
    for path in sorted(SITE.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in patterns:
            if pattern.search(text):
                problems.append((str(path.relative_to(SITE)), label))
    return problems


def main() -> int:
    build_site()
    missing = validate_internal_links()
    stale = validate_no_stale_cargo_links()
    if missing:
        print("\nMissing internal links:")
        for rel, href in missing[:50]:
            print(f"  {rel}: {href}")
        if len(missing) > 50:
            print(f"  ...and {len(missing) - 50} more")
    else:
        print("internal link check: ok")
    if stale:
        print("\nStale Cargo/placeholder markers:")
        for rel, label in stale[:50]:
            print(f"  {rel}: {label}")
        if len(stale) > 50:
            print(f"  ...and {len(stale) - 50} more")
    else:
        print("stale Cargo marker check: ok")
    return 1 if missing or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
