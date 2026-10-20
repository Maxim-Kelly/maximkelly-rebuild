#!/usr/bin/env python3
"""One-time migration: move page content out of JSON-with-HTML into plain YAML.

After this, `content/` is the source of truth and build_static_site_v3.py reads it.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
RENDERED = ROOT / "rendered"
FINAL = ROOT / "final-data"
CONTENT = ROOT / "content"
PROJECTS = CONTENT / "projects"

SKIP = {"summary", "home", "Portfolio", "Menu", "Contact", "Selected-Press"}


def unescape(s: str) -> str:
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s or "")
    s = s.replace(r"\/", "/").replace(r"\\n", "\n").replace(r'\\"', '"')
    return html.unescape(s)


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def trim_headings(fragment: str) -> str:
    def trim(m: re.Match[str]) -> str:
        inner = re.sub(r"^(?:\s|\xa0|&nbsp;)+", "", m.group(3))
        inner = re.sub(r"(?:\s|\xa0|&nbsp;)+$", "", inner)
        return f"{m.group(1)}{inner}{m.group(4)}"

    return re.sub(r"(<h([12])[^>]*>)(.*?)(</h\2>)", trim, fragment, flags=re.I | re.S)


def strip_back_links(fragment: str) -> str:
    fragment = re.sub(
        r"<h1[^>]*>\s*<a\b[^>]*icon-link[^>]*>.*?</a>\s*</h1>",
        "",
        fragment,
        flags=re.I | re.S,
    )
    fragment = re.sub(r"<a\b[^>]*icon-link[^>]*>.*?</a>", "", fragment, flags=re.I | re.S)
    fragment = re.sub(
        r'<p class="project-back[^"]*"[^>]*>.*?</p>', "", fragment, flags=re.I | re.S
    )
    return fragment.replace("\ue04a\ufe0e\ufe0e\ufe0e", "")


def pairs(fragment: str) -> list[tuple[str, str]]:
    return [
        (level, plain(inner))
        for level, inner in re.findall(r"<h([12])[^>]*>(.*?)</h\1>", fragment, flags=re.I | re.S)
    ]


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False, width=1000)


def import_projects() -> list[str]:
    warnings = []
    for path in sorted(RENDERED.glob("*.json")):
        slug = path.stem
        if slug in SKIP:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        body = trim_headings(strip_back_links(unescape(data.get("content_html", ""))))

        match = re.search(r"<iframe\b[^>]*>.*?</iframe>", body, flags=re.I | re.S)
        if not match:
            warnings.append(f"{slug}: no iframe")
            continue

        head = trim_headings(body[: match.start()])
        credits_raw = trim_headings(body[match.end() :])
        src = re.search(r'src="([^"]+)"', match.group(0))
        vimeo = html.unescape(src.group(1)) if src else ""

        title = artist = ""
        for level, value in pairs(head):
            if level == "1" and not title:
                title = value
            elif level == "2" and not artist:
                artist = value

        rows: list[dict[str, str]] = []
        pending = ""
        for level, value in pairs(credits_raw):
            if not value:
                continue
            if level == "1":
                if pending:
                    rows.append({"label": pending, "value": ""})
                pending = value
            elif pending:
                rows.append({"label": pending, "value": value})
                pending = ""
            else:
                rows.append({"label": "", "value": value})
        if pending:
            rows.append({"label": pending, "value": ""})

        doc: dict[str, object] = {
            "slug": slug,
            "title": title,
            "artist": artist,
            "vimeo": vimeo,
        }
        if rows:
            doc["credits"] = rows
        dump(PROJECTS / f"{slug}.yml", doc)
    return warnings


def markdown(fragment: str) -> str:
    fragment = trim_headings(unescape(fragment))
    found: list[tuple[str, str]] = []

    def keep(m: re.Match[str]) -> str:
        found.append((html.unescape(m.group(1)), plain(m.group(2))))
        return f"\x00{len(found) - 1}\x00"

    fragment = re.sub(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', keep, fragment, flags=re.I | re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    fragment = re.sub(r"[\s\xa0]+", " ", fragment).strip()
    for i, (url, label) in enumerate(found):
        replacement = label if not url or url == "#" else f"[{label}]({url})"
        fragment = fragment.replace(f"\x00{i}\x00", replacement)
    return fragment


def import_portfolio() -> None:
    data = json.loads((FINAL / "portfolio.json").read_text(encoding="utf-8"))
    content = unescape(next(x["content"] for x in data if x.get("project_url") == "Portfolio"))
    tiles = []
    pattern = re.compile(
        r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*image-link[^"]*"[^>]*>\s*(<img\b[^>]*>)\s*</a>',
        re.I | re.S,
    )
    for m in pattern.finditer(content):
        img = m.group(2)
        src = re.search(r'\bsrc="([^"]+)"', img) or re.search(r'\bdata-src="([^"]+)"', img)
        cap = re.search(r'\bdata-caption="([^"]*)"', img) or re.search(r'\balt="([^"]*)"', img)
        w = re.search(r'\bwidth="([^"]*)"', img)
        h = re.search(r'\bheight="([^"]*)"', img)
        tiles.append(
            {
                "slug": m.group(1),
                "image": Path(html.unescape(src.group(1))).name if src else "",
                "caption": unescape(cap.group(1)) if cap else "",
                "width": int(w.group(1)) if w else None,
                "height": int(h.group(1)) if h else None,
            }
        )
    dump(CONTENT / "portfolio.yml", tiles)


def import_contact() -> None:
    data = json.loads((FINAL / "contact.json").read_text(encoding="utf-8"))
    content = unescape(next(x["content"] for x in data if x.get("project_url") == "Contact"))
    rows = []
    for m in re.finditer(r"<div[^>]*grid-row[^>]*>(.*?)(?=<hr|$)", content, flags=re.I | re.S):
        cols = re.findall(r"<div[^>]*grid-col[^>]*>(.*?)</div>", m.group(1), flags=re.I | re.S)
        if len(cols) < 2:
            continue
        left, right = cols[0], cols[1]
        lm = re.search(r"<h1[^>]*>(.*?)</h1>", left, flags=re.I | re.S)
        region = plain(re.split(r"<br\s*/?>", lm.group(1), maxsplit=1, flags=re.I)[0]) if lm else ""
        org = re.search(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', left, flags=re.I | re.S)
        person = re.search(r"<h2[^>]*>(.*?)</h2>", right, flags=re.I | re.S)
        email = re.search(r'<a\b[^>]*href="mailto:([^"]*)"', right, flags=re.I)
        row = {
            "region": region,
            "person": plain(person.group(1)) if person else "",
            "email": html.unescape(email.group(1)) if email else "",
        }
        if org:
            row["org"] = plain(org.group(2))
            row["org_url"] = html.unescape(org.group(1))
        if any(row.values()):
            rows.append(row)
    dump(CONTENT / "contact.yml", rows)


def import_press() -> None:
    data = json.loads((FINAL / "selected-press.json").read_text(encoding="utf-8"))
    content = unescape(
        next(x["content"] for x in data if x.get("project_url") == "Selected-Press")
    )
    rows = []
    for m in re.finditer(r"<div[^>]*grid-row[^>]*>(.*?)(?=<hr|$)", content, flags=re.I | re.S):
        cols = re.findall(r"<div[^>]*grid-col[^>]*>(.*?)</div>", m.group(1), flags=re.I | re.S)
        if len(cols) < 2:
            continue
        lm = re.search(r"<h1[^>]*>(.*?)</h1>", cols[0], flags=re.I | re.S)
        outlet = plain(lm.group(1)) if lm else ""
        groups: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        for level, inner in re.findall(r"<h([12])[^>]*>(.*?)</h\1>", cols[1], flags=re.I | re.S):
            item = markdown(inner)
            if not item:
                continue
            if level == "2":
                current = {"label": item, "items": []}
                groups.append(current)
            elif current is not None:
                current["items"].append(item)
            else:
                current = {"label": "", "items": [item]}
                groups.append(current)
        rows.append({"outlet": outlet, "groups": groups})
    dump(CONTENT / "press.yml", rows)


def main() -> int:
    warnings = import_projects()
    import_portfolio()
    import_contact()
    import_press()
    print(f"wrote {len(list(PROJECTS.glob('*.yml')))} project files")
    print("wrote content/portfolio.yml, content/contact.yml, content/press.yml")
    for w in warnings:
        print("WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
