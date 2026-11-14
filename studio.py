#!/usr/bin/env python3
"""Treatment & site studio — a local drag-and-drop front-end for content/.

Run:  python3 studio.py   → opens http://localhost:8777

Everything it writes is the same content/ files the build already reads
(treatments/*.md, projects/*.yml, portfolio.yml, press.yml, contact.yml),
so the pipeline is unchanged and git stays the undo button.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.request
from urllib.parse import parse_qs, urlencode, urlparse

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"
PORT = 8777

ASSET_DIRS = {
    "treatments": SITE / "assets" / "treatments",
    "cargo": SITE / "assets" / "cargo",
}

IMG_BLOCK_RE = re.compile(
    r"^!\[\]\(\s*(?:(?P<w>wide|full)\s*:\s*)?(?P<src>[^)\s]+)\s*\)"
    r"\s*(?:\n\*\s*(?P<cap>.+?)\s*\*)?$",
    re.S,
)
VIDEO_BLOCK_RE = re.compile(r"^\{\{\s*video\s*:\s*(?P<url>[^}]+?)\s*\}\}\s*(?:\n\*\s*(?P<cap>.+?)\s*\*)?$", re.S)
BLOCK_OPEN_RE = re.compile(r"^\s*\{\{\s*(split|work|awards)\b", re.I)
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

RESOLVE_EXTS = (".jpg", ".jpeg", ".webp", ".png", ".mp4", ".webm", ".mov", ".gif")

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
BROWSER_SAFE_CODECS = {"h264", "vp8", "vp9"}


def _video_codec(path: Path) -> str:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True,
        )
        return out.stdout.strip().lower()
    except Exception:
        return ""


# ---------------------------------------------------------------- content IO

def read_yaml(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or default


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(text, encoding="utf-8")


def split_blocks(body: str) -> list[str]:
    """Split a treatment body into blocks: blank-line separated, except
    {{split}} / {{work}} / {{awards}} which run until their closing }}."""
    lines = body.splitlines()
    blocks: list[str] = []
    cur: list[str] = []

    def flush() -> None:
        nonlocal cur
        text = "\n".join(cur).strip("\n")
        if text.strip():
            blocks.append(text)
        cur = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if BLOCK_OPEN_RE.match(line):
            flush()
            cur.append(line)
            i += 1
            while i < len(lines):
                cur.append(lines[i])
                if lines[i].strip() == "}}":
                    i += 1
                    break
                i += 1
            flush()
            continue
        if not line.strip():
            flush()
        else:
            cur.append(line)
        i += 1
    flush()
    return blocks


def text_style(raw: str) -> str:
    s = raw.strip()
    if s.startswith("{{"):
        return "raw"
    if re.match(r"^###\s", s):
        return "subheading"
    if re.match(r"^##\s", s):
        return "section"
    if s.startswith(">"):
        return "quote"
    if re.match(r"^- ", s):
        return "list"
    return "body"


SPLIT_SIDE_RE = re.compile(r"^\s*(left|right)\s*:\s*$", re.I)
BLOCK_KIND_RE = re.compile(r"^\{\{\s*(split|work|awards)\s*$", re.I)
LEDE_RE = re.compile(r"^(?:\{\{\s*lede\s*\}\}\s*)+", re.I)


def describe_blocks(chunks: list[str]) -> list[dict]:
    """Consecutive body paragraphs form one passage (one card in the studio)."""
    blocks: list[dict] = []
    for chunk in chunks:
        b = describe_block(chunk)
        if (
            b.get("type") == "text"
            and b.get("style") == "body"
            and blocks
            and blocks[-1].get("type") == "text"
            and blocks[-1].get("style") == "body"
        ):
            blocks[-1]["text"] += "\n\n" + b["text"]
        else:
            blocks.append(b)
    return blocks


def parse_split(text: str) -> dict:
    sides: dict[str, list[str]] = {"left": [], "right": []}
    target: str | None = None
    for line in text.splitlines()[1:]:
        if line.strip() == "}}":
            break
        side = SPLIT_SIDE_RE.match(line)
        if side:
            target = side.group(1).lower()
        elif target:
            sides[target].append(line)
    return {
        "type": "split",
        "raw": text,
        "left": describe_blocks(split_blocks("\n".join(sides["left"]))),
        "right": describe_blocks(split_blocks("\n".join(sides["right"]))),
    }


def parse_work(text: str) -> dict:
    items: list[dict] = []
    current: dict = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "}}":
            break
        if not line.strip():
            if current:
                items.append(current)
                current = {}
            continue
        pair = re.match(r"^([A-Za-z_]+)\s*:\s*(.+)$", line.strip())
        if pair:
            current[pair.group(1).lower()] = pair.group(2).strip()
    if current:
        items.append(current)
    return {"type": "work", "raw": text, "items": items}


def parse_awards(text: str) -> dict:
    rows: list[list[str]] = []
    for line in text.splitlines()[1:]:
        if line.strip() == "}}":
            break
        if line.strip():
            rows.append([part.strip() for part in line.split("|", 2)])
    return {"type": "awards", "raw": text, "rows": rows}


def describe_block(text: str) -> dict:
    m = IMG_BLOCK_RE.match(text.strip())
    if m:
        return {
            "type": "image",
            "width": m.group("w") or "inline",
            "src": m.group("src"),
            "caption": m.group("cap") or "",
        }
    m = VIDEO_BLOCK_RE.match(text.strip())
    if m:
        return {"type": "video", "url": m.group("url").strip(), "caption": m.group("cap") or ""}
    if text.strip() == "***":
        return {"type": "pause"}
    if text.strip() == "~~":
        return {"type": "tiny"}
    if text.strip() == "---":
        return {"type": "rule"}
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    kind = BLOCK_KIND_RE.match(first_line)
    if kind:
        parser = {"split": parse_split, "work": parse_work, "awards": parse_awards}[kind.group(1).lower()]
        return parser(text.strip())
    lede = LEDE_RE.match(text)
    if lede:
        return {"type": "text", "style": "lede", "text": text[lede.end():]}
    return {"type": "text", "style": text_style(text), "text": text}


def canonical_block(block: dict) -> str:
    kind = block.get("type")
    if kind == "split":
        def side(name: str, blocks: list) -> str:
            body = "\n\n".join(block_raw(b) for b in blocks)
            return f"{name}:\n{body}" if body else f"{name}:"
        return (
            "{{split\n"
            + side("left", block.get("left") or [])
            + "\n\n"
            + side("right", block.get("right") or [])
            + "\n}}"
        )
    if kind == "work":
        parts = []
        for item in block.get("items") or []:
            lines = [f"{k}: {item[k]}" for k in ("image", "title", "artist", "url") if item.get(k)]
            if lines:
                parts.append("\n".join(lines))
        return "{{work\n" + "\n\n".join(parts) + "\n}}"
    if kind == "awards":
        rows = [" | ".join(p for p in row).rstrip(" |") for row in block.get("rows") or []]
        return "{{awards\n" + "\n".join(rows) + "\n}}"
    return block.get("text", "")


def _strip_raw(node):
    if isinstance(node, dict):
        return {k: _strip_raw(v) for k, v in node.items() if k != "raw"}
    if isinstance(node, list):
        return [_strip_raw(v) for v in node]
    return node


def block_raw(block: dict) -> str:
    kind = block.get("type")
    if kind == "image":
        prefix = f"{block['width']}: " if block.get("width") in ("wide", "full") else ""
        raw = f"![]({prefix}{block.get('src', '')})"
        cap = (block.get("caption") or "").strip()
        if cap:
            raw += f"\n*{cap}*"
        return raw
    if kind == "video":
        raw = f"{{{{video: {block.get('url', '').strip()}}}}}"
        cap = (block.get("caption") or "").strip()
        if cap:
            raw += f"\n*{cap}*"
        return raw
    if kind == "rule":
        return "---"
    if kind == "pause":
        return "***"
    if kind == "tiny":
        return "~~"
    if kind in ("split", "work", "awards"):
        raw = block.get("raw") or ""
        if raw and _strip_raw(describe_block(raw)) == _strip_raw(block):
            return raw
        return canonical_block(block)
    if kind == "text" and block.get("style") == "lede":
        return "{{lede}}\n" + block.get("text", "")
    return block.get("text", "")


def load_treatment(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        meta = yaml.safe_load(parts[1]) or {}
        body = parts[2].lstrip("\n") if len(parts) > 2 else ""
    else:
        meta, body = {}, text
    return {
        "slug": path.stem,
        "meta": meta,
        "blocks": describe_blocks(split_blocks(body)),
    }


def save_treatment(slug: str, data: dict) -> None:
    meta = data.get("meta") or {}
    body = "\n\n".join(block_raw(b) for b in data.get("blocks") or [])
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000).strip()
    (CONTENT / "treatments" / f"{slug}.md").write_text(
        f"---\n{front}\n---\n\n{body}\n", encoding="utf-8"
    )


def load_state() -> dict:
    treatments = [
        load_treatment(p) for p in sorted((CONTENT / "treatments").glob("*.md"))
    ]
    projects = []
    for p in sorted((CONTENT / "projects").glob("*.yml")):
        doc = read_yaml(p, {}) or {}
        doc.setdefault("slug", p.stem)
        doc.setdefault("credits", [])
        projects.append(doc)
    return {
        "treatments": treatments,
        "projects": projects,
        "portfolio": read_yaml(CONTENT / "portfolio.yml", []),
        "press": read_yaml(CONTENT / "press.yml", []),
        "contact": read_yaml(CONTENT / "contact.yml", []),
    }


def fill_tile_sizes(tiles: list[dict]) -> list[dict]:
    for tile in tiles:
        if tile.get("width") and tile.get("height"):
            continue
        img = SITE / "assets" / "cargo" / str(tile.get("image", ""))
        if img.exists():
            try:
                with Image.open(img) as im:
                    tile["width"], tile["height"] = im.size
            except Exception:
                pass
    return tiles


# ------------------------------------------------------------------ uploads

def resolve_asset_name(directory: Path, stem: str) -> str | None:
    for ext in RESOLVE_EXTS:
        candidate = directory / f"{stem}{ext}"
        if candidate.exists():
            return candidate.name
    return None


def handle_upload(query: dict, payload: bytes) -> dict:
    dir_key = (query.get("dir") or ["treatments"])[0]
    sub = (query.get("sub") or [""])[0]
    name = SAFE_NAME_RE.sub("-", (query.get("name") or ["upload.bin"])[0]).lstrip(".")

    if dir_key == "treatments":
        directory = ASSET_DIRS["treatments"] / SAFE_NAME_RE.sub("-", sub)
    else:
        directory = ASSET_DIRS["cargo"]
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / name
    target.write_bytes(payload)

    # Browsers only reliably decode H.264/VP8/VP9 video. Transcode anything else
    # (HEVC, ProRes, mpeg4...) to H.264 and standardise containers on .mp4.
    suffix = target.suffix.lower()
    if suffix in VIDEO_EXTS and shutil.which("ffmpeg"):
        codec = _video_codec(target)
        converted = target.with_suffix(".mp4")
        if codec not in BROWSER_SAFE_CODECS:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(target),
                   "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                   "-c:a", "aac", "-pix_fmt", "yuv420p", str(converted)]
        elif suffix != ".mp4":
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(target), "-c", "copy", str(converted)]
        else:
            cmd = None
        if cmd:
            done = subprocess.run(cmd, capture_output=True, text=True)
            if done.returncode == 0 and converted.exists():
                target.unlink()
                target = converted
            elif converted != target and converted.exists():
                converted.unlink()

    result = subprocess.run(
        [sys.executable, str(ROOT / "optimize_images.py")],
        capture_output=True, text=True, cwd=ROOT,
    )

    final_name = resolve_asset_name(directory, target.stem) or name
    final_path = directory / final_name
    width = height = None
    if final_path.suffix.lower() not in {".mp4", ".webm", ".mov"}:
        try:
            with Image.open(final_path) as im:
                width, height = im.size
        except Exception:
            pass

    rel = f"assets/{'treatments/' + directory.name if dir_key == 'treatments' else 'cargo'}/{final_name}"
    return {
        "name": final_name,
        "ref": rel,
        "width": width,
        "height": height,
        "bytes": final_path.stat().st_size,
        "optimizer": result.stdout.strip(),
    }


def send_test_alert() -> dict:
    config = read_yaml(CONTENT / "config.yml", {}) or {}
    alerts = config.get("alerts") or {}
    token = str(alerts.get("telegram_token") or "").strip()
    chat = str(alerts.get("telegram_chat_id") or "").strip()
    if not token or not chat:
        return {"ok": False, "error": "no telegram_token / telegram_chat_id in content/config.yml"}
    payload = urlencode({
        "chat_id": chat,
        "text": "Test alert — the treatment alert pipe is alive. (Sent from Studio.)",
        "disable_web_page_preview": "true",
    })
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        if shutil.which("curl"):
            result = subprocess.run(
                ["curl", "-s", "--max-time", "10", "-X", "POST", "-d", payload, url],
                capture_output=True, text=True,
            )
            reply = json.loads(result.stdout or "{}")
        else:
            req = urllib.request.Request(url, data=payload.encode(), method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                reply = json.loads(resp.read())
        if reply.get("ok"):
            return {"ok": True}
        return {"ok": False, "error": str(reply.get("description") or reply)[:200]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def run_build() -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "build_static_site_v3.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    output = (result.stdout + result.stderr).strip()
    return {"ok": result.returncode == 0, "output": output}


# ------------------------------------------------------------------- server

class Studio(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep the console quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, target: Path, ctype: str) -> None:
        """Serve a file with byte-range support — Safari won't play video without it."""
        data = target.read_bytes()
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d*)-(\d*)", rng) if rng else None
        if m and (m.group(1) or m.group(2)):
            start = int(m.group(1) or 0)
            end = min(int(m.group(2) or len(data) - 1), len(data) - 1)
            chunk = data[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data).encode(), "application/json")

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            self._send(200, APP_HTML.encode(), "text/html; charset=utf-8")
            return
        if path == "/api/state":
            self._json(load_state())
            return
        if path.startswith("/asset/"):
            rel = path[len("/asset/"):]
            target = (SITE / rel).resolve()
            if SITE.resolve() not in target.parents or not target.is_file():
                self._send(404, b"not found", "text/plain")
                return
            ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
            self._send_file(target, ctype)
            return
        if path.startswith("/site/"):
            rel = path[len("/site/"):]
            target = (SITE / rel).resolve()
            if SITE.resolve() not in target.parents:
                self._send(404, b"not found", "text/plain")
                return
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                self._send(404, b"not found", "text/plain")
                return
            ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
            self._send_file(target, ctype)
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        url = urlparse(self.path)
        path = url.path
        query = parse_qs(url.query)
        payload = self._body()

        try:
            if path == "/api/upload":
                self._json(handle_upload(query, payload))
                return

            data = json.loads(payload) if payload else {}

            if path == "/api/save/treatment":
                slug = (query.get("slug") or [""])[0]
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
                    self._json({"error": "bad slug"}, 400)
                    return
                save_treatment(slug, data)
                self._json({"ok": True})
                return

            if path == "/api/save/project":
                slug = (query.get("slug") or [""])[0]
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
                    self._json({"error": "bad slug"}, 400)
                    return
                write_yaml(CONTENT / "projects" / f"{slug}.yml", data)
                self._json({"ok": True})
                return

            if path == "/api/save/portfolio":
                self._json({"ok": True, "tiles": fill_tile_sizes(data)})
                write_yaml(CONTENT / "portfolio.yml", fill_tile_sizes(data))
                return

            if path == "/api/save/press":
                write_yaml(CONTENT / "press.yml", data)
                self._json({"ok": True})
                return

            if path == "/api/save/contact":
                write_yaml(CONTENT / "contact.yml", data)
                self._json({"ok": True})
                return

            if path == "/api/delete/treatment":
                slug = (query.get("slug") or [""])[0]
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
                    self._json({"error": "bad slug"}, 400)
                    return
                (CONTENT / "treatments" / f"{slug}.md").unlink(missing_ok=True)
                assets_dir = SITE / "assets" / "treatments" / slug
                leftover = sorted(p.name for p in assets_dir.iterdir() if p.is_file()) if assets_dir.exists() else []
                self._json({"ok": True, "assets": leftover})
                return

            if path == "/api/new/treatment":
                slug = (query.get("slug") or [""])[0]
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
                    self._json({"error": "bad slug"}, 400)
                    return
                name = (query.get("name") or [""])[0] or slug
                path_md = CONTENT / "treatments" / f"{slug}.md"
                if not path_md.exists():
                    save_treatment(slug, {
                        "meta": {
                            "client": "", "track": name, "production": "",
                            "director": "Maxim Kelly", "date": "",
                            "version": "Treatment v1", "hero": "",
                        },
                        "blocks": [
                            {"type": "text", "style": "body", "text": "Opening line — one or two sentences on the idea."},
                            {"type": "text", "style": "section", "text": "## The idea"},
                            {"type": "text", "style": "body", "text": "What actually happens in the film."},
                        ],
                    })
                self._json(load_treatment(path_md))
                return

            if path == "/api/new/project":
                slug = (query.get("slug") or [""])[0]
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", slug):
                    self._json({"error": "bad slug"}, 400)
                    return
                path_yml = CONTENT / "projects" / f"{slug}.yml"
                if not path_yml.exists():
                    write_yaml(path_yml, {
                        "slug": slug, "title": "", "artist": "",
                        "vimeo": "", "credits": [],
                    })
                self._json(read_yaml(path_yml, {}))
                return

            if path == "/api/build":
                self._json(run_build())
                return

            if path == "/api/test-alert":
                self._json(send_test_alert())
                return

            self._json({"error": "unknown endpoint"}, 404)
        except Exception as exc:  # surface errors in the UI instead of a hang
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


STARTER_TREATMENT = """---
client:
track:
production:
director: Maxim Kelly
date:
version: Treatment v1
hero:
---

Opening line — one or two sentences on the idea.

## The idea

What actually happens in the film.
"""


# --------------------------------------------------------------------- app

APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Studio</title>
<style>
  :root{--bg:#141412;--panel:#1d1d1a;--card:#232320;--line:#33332e;--fg:#e9e6df;
        --muted:#a19d94;--dim:#767268;--accent:#c9a227;--ok:#7fa86b;--bad:#c96b5b}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  header{display:flex;align-items:center;gap:16px;padding:10px 18px;
         border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
  header h1{font-size:15px;letter-spacing:.14em;text-transform:uppercase;margin:0;color:var(--muted)}
  nav{display:flex;gap:4px}
  nav button{background:none;border:1px solid transparent;color:var(--muted);
             padding:6px 12px;border-radius:6px;cursor:pointer;font-size:14px}
  nav button.on{background:var(--card);color:var(--fg);border-color:var(--line)}
  .spacer{flex:1}
  .btn{background:var(--card);border:1px solid var(--line);color:var(--fg);
       padding:7px 14px;border-radius:6px;cursor:pointer;font-size:14px}
  .btn:hover{border-color:var(--dim)}
  .btn.primary{background:var(--accent);border-color:var(--accent);color:#1a1a16;font-weight:600}
  .btn.small{padding:3px 9px;font-size:12px}
  .dirty{color:var(--accent);font-size:12px;letter-spacing:.08em;text-transform:uppercase}
  main{padding:22px;max-width:1100px;margin:0 auto}
  .layout{display:grid;grid-template-columns:230px 1fr;gap:22px}
  .side{position:sticky;top:64px;align-self:start}
  .side .item{padding:8px 10px;border:1px solid var(--line);border-radius:6px;
              margin-bottom:6px;cursor:pointer;background:var(--panel);font-size:13px}
  .side .item.on{border-color:var(--accent)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:8px;
        padding:14px;margin-bottom:12px}
  .card.dragging{opacity:.4}
  .card.over{border-color:var(--accent)}
  .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .grab{cursor:grab;color:var(--dim);user-select:none;font-size:16px;padding:0 4px}
  .tag{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim)}
  label{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
        color:var(--dim);margin:10px 0 4px}
  input,textarea,select{width:100%;background:var(--panel);border:1px solid var(--line);
        color:var(--fg);border-radius:6px;padding:8px 10px;font:inherit}
  textarea{resize:vertical;min-height:88px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 14px}
  .thumb{width:150px;aspect-ratio:16/9;object-fit:cover;border-radius:6px;
         background:#000;display:block}
  .drop{border:1px dashed var(--dim);border-radius:8px;padding:10px;text-align:center;
        color:var(--dim);font-size:12px;cursor:pointer}
  .drop.hot{border-color:var(--accent);color:var(--accent)}
  .widths{display:flex;gap:6px}
  .widths button{flex:1;background:var(--panel);border:1px solid var(--line);
                 color:var(--muted);border-radius:6px;padding:6px;cursor:pointer;font-size:12px}
  .widths button.on{border-color:var(--accent);color:var(--fg)}
  .sub{background:var(--panel);border:1px solid var(--line);border-radius:8px;
       padding:12px;margin:10px 0}
  .x{margin-left:auto;color:var(--dim);cursor:pointer;font-size:16px;padding:2px 8px}
  .x:hover{color:var(--bad)}
  .ins{display:flex;justify-content:center;align-items:center;min-height:16px;position:relative}
  .ins-plus{width:22px;height:22px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--dim);cursor:pointer;font-size:14px;line-height:1;opacity:.4;transition:opacity .15s}
  .ins:hover .ins-plus,.ins-plus:focus{opacity:1}
  .ins-empty{min-height:38px}
  .ins-empty .ins-plus{opacity:1;width:auto;padding:7px 16px;border-radius:6px;font-size:12px;letter-spacing:.06em}
  .ins-menu{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin:6px 0}
  [hidden]{display:none!important}
  .out{white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace;color:var(--muted);
       background:#0f0f0d;border-radius:8px;padding:12px;margin-top:14px}
  .hint{color:var(--dim);font-size:12px;margin:4px 0 14px}
  .hero-prev{width:100%;max-height:260px;object-fit:cover;border-radius:8px}
</style>
</head>
<body>
<header>
  <h1>Studio</h1>
  <nav id="tabs"></nav>
  <div class="spacer"></div>
  <span class="dirty" id="dirty" hidden>unsaved</span>
  <button class="btn" onclick="undo()" title="Cmd+Z">Undo</button>
  <button class="btn" id="save">Save</button>
  <button class="btn primary" id="build">Build &amp; preview</button>
  <button class="btn" onclick="testAlert()" title="Send a test Telegram alert">Test alert</button>
</header>
<main id="main"></main>
<script>
const TABS = ['Treatments','Films','Portfolio','Press','Contact'];
let S = null, tab = 'Treatments', current = null;

const $ = (s, el=document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const api = async (path, body) => {
  const opts = body === undefined ? {} : {method:'POST', body: typeof body === 'string' || body instanceof Blob ? body : JSON.stringify(body)};
  const r = await fetch(path, opts);
  return r.json();
};
let dirty = false;
const dirtyTabs = new Set();
let saveTimer = null;
const markDirty = () => {
  dirty = true; $('#dirty').hidden = false;
  dirtyTabs.add(tab);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => save(), 1500);
};
const markClean = () => { dirty = false; $('#dirty').hidden = true; };

/* ---------- drag reorder ---------- */
function sortable(container, cls, onReorder) {
  let dragged = null;
  container.addEventListener('dragstart', e => {
    const card = e.target.closest(cls);
    if (!card) return;
    dragged = card; card.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
  });
  container.addEventListener('dragover', e => {
    e.preventDefault();
    const card = e.target.closest(cls);
    if (!card || card === dragged || !dragged) return;
    const rect = card.getBoundingClientRect();
    const after = (e.clientY - rect.top) > rect.height / 2;
    card.parentNode.insertBefore(dragged, after ? card.nextSibling : card);
  });
  container.addEventListener('dragend', () => {
    if (!dragged) return;
    dragged.classList.remove('dragging');
    dragged = null;
    onReorder();
    markDirty();
  });
}

/* ---------- file drop ---------- */
function pickFile(onFile) {
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = 'image/*,video/*,.gif';
  inp.style.display = 'none';
  document.body.appendChild(inp);   // detached inputs lose their change event in WebKit
  window._pickInput = inp;          // hard reference until the dialog closes
  inp.addEventListener('change', () => {
    const f = inp.files && inp.files[0];
    inp.remove();
    if (window._pickInput === inp) window._pickInput = null;
    if (!f) return;
    try {
      const r = onFile(f);
      if (r && r.catch) r.catch(err => alert('Upload failed: ' + err.message));
    } catch (err) {
      alert('Upload failed: ' + err.message);
    }
  });
  inp.click();
}

function dropzone(el, onFile) {
  const dz = el.closest('.card, .sub') || el;
  dz.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('hot'); });
  dz.addEventListener('dragleave', e => { if (!dz.contains(e.relatedTarget)) el.classList.remove('hot'); });
  dz.addEventListener('drop', e => {
    e.preventDefault(); e.stopPropagation(); el.classList.remove('hot');
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!f) { alert('No file came through with that drop — drag it straight from a Finder window.'); return; }
    onFile(f);
  });
  el.addEventListener('click', () => pickFile(onFile));
}
async function upload(file, dir, sub) {
  const q = new URLSearchParams({dir, name: file.name});
  if (sub) q.set('sub', sub);
  const r = await api('/api/upload?' + q, file);
  if (r && r.error) throw new Error(r.error);
  return r;
}

/* ---------- tabs ---------- */
function renderTabs() {
  $('#tabs').innerHTML = TABS.map(t =>
    `<button class="${t === tab ? 'on' : ''}" onclick="switchTab('${t}')">${t}</button>`).join('');
}
function switchTab(t) { save(); tab = t; current = null; renderTabs(); render(); }

/* ---------- treatments ---------- */
function renderTreatments() {
  const list = S.treatments;
  if (!current) current = list[0] || null;
  const side = `
    <div class="side">
      ${list.map(t => `<div class="item ${current && t.slug === current.slug ? 'on' : ''}"
        onclick="pickTreatment('${t.slug}')">${esc(t.meta.track || t.slug)}</div>`).join('')}
      <button class="btn small" style="width:100%;margin-top:8px" onclick="newTreatment()">+ New treatment</button>
    </div>`;
  if (!current) return side + '<div><p class="hint">No treatments yet.</p></div>';

  const m = current.meta;
  const heroPath = String(m.hero || '');
  const heroIsVid = /\.(mp4|webm|mov)$/i.test(heroPath);
  const heroRef = heroPath ? '/asset/' + heroPath : '';
  const blocks = blockList(current.blocks, 'current.blocks');

  return side + `<div>
    <p class="hint">Drag cards to reorder. Hover between cards and use + to insert at that spot. Drop media straight onto a slot — naming and optimising happen automatically.</p>
    <details style="margin:0 0 14px">
      <summary class="tag" style="cursor:pointer">Text formatting — click for the cheat sheet</summary>
      <div class="card" style="margin-top:8px">
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">## Title</td><td class="hint" style="margin:0">Section divider — small tracked caps (Performance, Look…)</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">### Title</td><td class="hint" style="margin:0">Subheading — the big text (e.g. “The turn”)</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">plain text</td><td class="hint" style="margin:0">Body paragraph</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">&gt; text</td><td class="hint" style="margin:0">Pull quote — the largest text. Keep it on ONE line</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">**bold** *it*</td><td class="hint" style="margin:0">Bold / italic</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">- item</td><td class="hint" style="margin:0">Bullet list</td></tr>
          <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">---</td><td class="hint" style="margin:0">Page break — new page in the printed PDF, bigger divider on screen</td></tr>
                    <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">Enter</td><td class="hint" style="margin:0">New paragraph. Shift+Enter = soft line break</td></tr>
                              <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">***</td><td class="hint" style="margin:0">Half break — a soft pause between beats. Use the “Break here” button</td></tr>
                                        <tr><td style="padding:4px 10px 4px 0;color:var(--accent)">~~</td><td class="hint" style="margin:0">Tiny break — just a little air between two blocks</td></tr>
        </table>
      </div>
    </details>
    <div class="card">
      <div class="tag">Front matter</div>
      <div class="grid3">
        <div><label>Client</label><input value="${esc(m.client)}" oninput="setMeta('client',this.value)"></div>
        <div><label>Track</label><input value="${esc(m.track)}" oninput="setMeta('track',this.value)"></div>
        <div><label>Production</label><input value="${esc(m.production)}" oninput="setMeta('production',this.value)"></div>
        <div><label>Director</label><input value="${esc(m.director)}" oninput="setMeta('director',this.value)"></div>
        <div><label>Date</label><input value="${esc(m.date)}" oninput="setMeta('date',this.value)"></div>
        <div><label>Version</label><input value="${esc(m.version)}" oninput="setMeta('version',this.value)"></div>
        <div><label>Hero text</label>
          <select onchange="setMeta('hero_text',this.value)">
            ${['full','meta','off'].map(v => `<option value="${v}" ${(m.hero_text || 'full') === v ? 'selected' : ''}>${v === 'full' ? 'Full — title over hero' : v === 'meta' ? 'Meta only — credit line' : 'None — artwork only'}</option>`).join('')}
          </select></div>
      </div>
      <label>Hero</label>
      <div class="row" style="align-items:flex-start">
        ${heroRef ? (heroIsVid
          ? `<video class="hero-prev" style="max-width:340px" src="${heroRef}" autoplay muted loop playsinline></video>`
          : `<img class="hero-prev" style="max-width:340px" src="${heroRef}">`) : ''}
        <div class="drop" id="hero-drop" style="flex:1">Drop hero image or video here, or click</div>
      </div>
      ${heroIsVid ? `<label>Video framing</label>
      <div class="widths" style="max-width:260px">
        <button class="${(m.hero_fit || 'contain') === 'contain' ? 'on' : ''}" onclick="setMeta('hero_fit','contain')">contain</button>
        <button class="${(m.hero_fit || 'contain') === 'cover' ? 'on' : ''}" onclick="setMeta('hero_fit','cover')">cover</button>
      </div>` : ''}
    </div>
    <div id="blocks" data-arr="current.blocks">${blocks}</div>
    <div class="row" style="margin-top:14px">
      <button class="btn" onclick="buildNow('t/${current.slug}/')">Preview treatment</button>
      <button class="btn" style="color:var(--bad)" onclick="delTreatment()">Delete treatment</button>
    </div>
  </div>`;
}
async function delTreatment() {
  if (!current) return;
  const name = current.meta.track || current.slug;
  if (!confirm('Delete treatment "' + name + '"? The page and its markdown go away; dropped images stay in assets.')) return;
  const r = await api('/api/delete/treatment?slug=' + current.slug, {});
  S.treatments = S.treatments.filter(t => t.slug !== current.slug);
  current = S.treatments[0] || null;
  render();
  if (r.assets && r.assets.length) alert('Deleted. Images left in assets: ' + r.assets.join(', '));
}

async function pickTreatment(slug) {
  await save();
  current = S.treatments.find(t => t.slug === slug);
  render();
}
async function newTreatment() {
  const name = prompt('Treatment name (e.g. Sugababes Modern Love):');
  if (!name || !name.trim()) return;
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  if (!slug) { alert('Could not make a file name from that.'); return; }
  const doc = await api('/api/new/treatment?slug=' + encodeURIComponent(slug) + '&name=' + encodeURIComponent(name.trim()), {});
  if (!doc || doc.error) { alert('Could not create: ' + ((doc && doc.error) || 'unknown error')); return; }
  const i = S.treatments.findIndex(t => t.slug === slug);
  if (i >= 0) S.treatments[i] = doc; else S.treatments.push(doc);
  current = doc;
  render();
}
function setMeta(k, v) { coalescedSnap(); current.meta[k] = v; markDirty(); }
const G = p => eval(p);

/* ---------- undo history ---------- */
const history = [];
let lastSnapAt = 0;
function snap() {
  history.push(JSON.stringify({s: S, tab, slug: current && current.slug}));
  if (history.length > 50) history.shift();
  lastSnapAt = Date.now();
}
function coalescedSnap() {
  if (Date.now() - lastSnapAt > 1200) snap();
}
function undo() {
  const last = history.pop();
  if (!last) return;
  const st = JSON.parse(last);
  S = st.s;
  current = st.slug ? (S.treatments.find(t => t.slug === st.slug) || S.projects.find(p => p.slug === st.slug)) : null;
  markDirty();
  render();
}

function setB(p, k, v) { coalescedSnap(); G(p)[k] = v; markDirty(); }
function delAt(arrPath, idx) { snap(); G(arrPath).splice(idx, 1); markDirty(); render(); }
function specKind(kind) {
  return {
    text:    {type:'text', style:'body', text:''},
    heading: {type:'text', style:'section', text:'## Section'},
    image:   {type:'image', width:'inline', src:'', caption:''},
    video:   {type:'video', url:'', caption:''},
    quote:   {type:'text', style:'quote', text:'> The line you want them to leave with'},
    list:    {type:'text', style:'list', text:'- First item'},
    pause:   {type:'pause'},
    tiny:    {type:'tiny'},
    split:   {type:'split', left:[], right:[]},
    work:    {type:'work', items:[{image:'',title:'',artist:'',url:''}]},
    awards:  {type:'awards', rows:[['','','']]},
    rule:    {type:'rule'},
  }[kind];
}
function addAt(arrPath, kind) {
  snap();
  G(arrPath).push((typeof kind === 'object') ? kind : specKind(kind));
  markDirty(); render();
}
function insertAt(arrPath, idx, kind) {
  snap();
  G(arrPath).splice(idx, 0, (typeof kind === 'object') ? kind : specKind(kind));
  markDirty(); render();
}
function setStyleP(p, style) {
  const b = G(p);
  if (b.style === 'raw') return;
  snap();
  let t = (b.text || '')
    .replace(/^(?:\{\{\s*lede\s*\}\}\s*)+/i, '')
    .replace(/^#{2,3}\s+/, '')
    .replace(/^>\s?/, '')
    .replace(/^- /gm, '');
  if (style === 'section') t = '## ' + t.trimStart();
  else if (style === 'subheading') t = '### ' + t.trimStart();
  else if (style === 'quote') t = '> ' + t.replace(/\s*\n\s*/g, ' ').trim();
  else if (style === 'lede') t = '{{lede}}\n' + t.trimStart();
  else if (style === 'list') t = t.split('\n').filter(l => l.trim()).map(l => '- ' + l.trim()).join('\n');
  else t = t.trimStart();
  b.text = t; b.style = style;
  markDirty(); render();
}
function wrapSelP(p, mark) {
  const ta = document.querySelector(`textarea[data-ta="${p}"]`);
  if (!ta) return;
  snap();
  const s = ta.selectionStart, e = ta.selectionEnd;
  const sel = ta.value.slice(s, e) || 'text';
  ta.value = ta.value.slice(0, s) + mark + sel + mark + ta.value.slice(e);
  G(p).text = ta.value;
  ta.focus();
  ta.setSelectionRange(s + mark.length, s + mark.length + sel.length);
  markDirty();
}
function breakAt(p) {
  const ta = document.querySelector(`textarea[data-ta="${p}"]`);
  if (!ta) return;
  snap();
  const c = (ta.selectionStart === null || ta.selectionStart === undefined) ? ta.value.length : ta.selectionStart;
  const before = ta.value.slice(0, c).replace(/\s*$/, '');
  const after = ta.value.slice(c).replace(/^\s*/, '');
  ta.value = before + '\n\n***\n\n' + after;
  G(p).text = ta.value;
  const pos = before.length + 6;
  ta.focus();
  ta.setSelectionRange(pos, pos);
  markDirty();
}
function setCell(p, j, c, v) {
  const row = G(p).rows[j];
  coalescedSnap();
  while (row.length <= c) row.push('');
  row[c] = v; markDirty();
}

/* ---------- block cards (recursive — panes use these too) ---------- */
const STYLES = [['lede','Lede — big intro'],['body','Body text'],['section','## Section'],['subheading','### Subheading'],['quote','> Pull quote'],['list','- List']];
const ADD_LABELS = {text:'Paragraph', heading:'Heading', image:'Image / video', quote:'Quote', list:'List', tiny:'Tiny break', pause:'Half break', video:'Vimeo', split:'Split', work:'Work grid', awards:'Awards', rule:'Page break'};

function insStrip(arrPath, idx) {
  return `<div class="ins"><button class="ins-plus" onclick="toggleIns(this,'${arrPath}',${idx})" title="Insert here">+</button><div class="ins-menu" hidden></div></div>`;
}
function toggleIns(btn, arrPath, idx) {
  const menu = btn.parentNode.querySelector('.ins-menu');
  if (!menu.hidden) { menu.hidden = true; return; }
  menu.innerHTML = ['text','heading','image','video','quote','list','tiny','pause','split','work','awards','rule'].map(k =>
    `<button class="btn small" onclick="insertAt('${arrPath}',${idx},'${k}')">${ADD_LABELS[k]}</button>`).join('');
  menu.hidden = false;
}
function blockList(blocks, arrPath) {
  const list = blocks || [];
  if (!list.length) {
    return `<div class="ins ins-empty"><button class="ins-plus" onclick="toggleIns(this,'${arrPath}',0)">+ add here</button><div class="ins-menu" hidden></div></div>`;
  }
  let out = insStrip(arrPath, 0);
  list.forEach((b, j) => {
    out += blockCard(b, `${arrPath}[${j}]`, arrPath, j) + insStrip(arrPath, j + 1);
  });
  return out;
}

function cardHead(tag, arrPath, idx, extra) {
  return `<div class="card" draggable="true" data-idx="${idx}">
    <div class="row"><span class="grab">⠿</span>${tag ? `<span class="tag">${tag}</span>` : ''}${extra || ''}
    <span class="x" onclick="delAt('${arrPath}',${idx})">✕</span></div>`;
}

function blockCard(b, p, arrPath, idx) {
  if (b.type === 'image') return cardHead('Image / GIF / video', arrPath, idx) + `
    <div class="row" style="align-items:flex-start">
      ${/\.(mp4|webm|mov|gif)$/i.test(b.src || '') ? `<video class="thumb" src="/asset/${esc(b.src || '')}" autoplay muted loop playsinline></video>` : `<img class="thumb" src="/asset/${esc(b.src || '')}" onerror="this.style.opacity=.2">`}
      <div style="flex:1;min-width:220px">
        <div class="drop" data-drop="${p}" data-updir="treatments">Drop image, GIF or video here, or click</div>
        <label>Caption</label>
        <input value="${esc(b.caption || '')}" oninput="setB('${p}','caption',this.value)">
        <label>Width</label>
        <div class="widths">
          ${['inline','wide','full'].map(w =>
            `<button class="${b.width === w ? 'on' : ''}" onclick="snap();setB('${p}','width','${w}');render()">${w}</button>`).join('')}
        </div>
      </div>
    </div></div>`;
  if (b.type === 'video') return cardHead('Vimeo', arrPath, idx) + `
    <label>Vimeo URL</label>
    <input value="${esc(b.url || '')}" oninput="setB('${p}','url',this.value)">
    <label>Caption</label>
    <input value="${esc(b.caption || '')}" oninput="setB('${p}','caption',this.value)"></div>`;
  if (b.type === 'rule') return cardHead('section break', arrPath, idx) + '</div>';
  if (b.type === 'pause') return cardHead('half break', arrPath, idx) + '</div>';
  if (b.type === 'tiny') return cardHead('tiny break', arrPath, idx) + '</div>';
  if (b.type === 'split') return splitCard(b, p, arrPath, idx);
  if (b.type === 'work') return workCard(b, p, arrPath, idx);
  if (b.type === 'awards') return awardsCard(b, p, arrPath, idx);
  const isRaw = b.style === 'raw';
  return cardHead(isRaw ? 'special block — raw' : '', arrPath, idx, isRaw ? '' : `
    <select style="max-width:170px" onchange="setStyleP('${p}',this.value)">
      ${STYLES.map(([v, l]) => `<option value="${v}" ${b.style === v ? 'selected' : ''}>${l}</option>`).join('')}
    </select>
    <button class="btn small" title="bold" onclick="wrapSelP('${p}','**')"><b>B</b></button>
    <button class="btn small" title="italic" onclick="wrapSelP('${p}','*')"><i>I</i></button>
    <button class="btn small" title="half break at the cursor" onclick="breakAt('${p}')">Break here</button>`) + `
    <textarea data-ta="${p}" oninput="setB('${p}','text',this.value)">${esc(b.text || '')}</textarea></div>`;
}

function splitCard(b, p, arrPath, idx) {
  const pane = side => `
    <div class="tag">${side} pane</div>
    <div data-arr="${p}.${side}">${blockList(b[side], `${p}.${side}`)}</div>`;
  return cardHead('Split — two panes', arrPath, idx) + `
    <div class="row" style="align-items:flex-start;gap:14px">
      <div style="flex:1;min-width:250px">${pane('left')}</div>
      <div style="flex:1;min-width:250px">${pane('right')}</div>
    </div></div>`;
}

function workCard(b, p, arrPath, idx) {
  const items = (b.items || []).map((it, j) => `
    <div class="sub" draggable="true" data-idx="${j}">
      <div class="row"><span class="grab">⠿</span><span class="tag">Item ${j + 1}</span>
        <span class="x" onclick="delAt('${p}.items',${j})">✕</span></div>
      <div class="row" style="align-items:flex-start">
        <img class="thumb" src="/asset/${esc(it.image || '')}" onerror="this.style.opacity=.2">
        <div style="flex:1;min-width:220px">
          <div class="drop" data-drop="${p}.items[${j}]" data-updir="cargo" data-k="image">Drop still here, or click</div>
          <label>Image</label>
          <input value="${esc(it.image || '')}" oninput="setB('${p}.items[${j}]','image',this.value)">
          <label>Title</label>
          <input value="${esc(it.title || '')}" oninput="setB('${p}.items[${j}]','title',this.value)">
          <label>Artist</label>
          <input value="${esc(it.artist || '')}" oninput="setB('${p}.items[${j}]','artist',this.value)">
          <label>Link URL</label>
          <input value="${esc(it.url || '')}" oninput="setB('${p}.items[${j}]','url',this.value)">
        </div>
      </div>
    </div>`).join('');
  return cardHead('Work grid', arrPath, idx) + `<div data-arr="${p}.items">${items}</div>
    <button class="btn small" style="margin-top:8px" onclick="addAt('${p}.items',{image:'',title:'',artist:'',url:''})">+ Add item</button></div>`;
}

function awardsCard(b, p, arrPath, idx) {
  const rows = (b.rows || []).map((r, j) => `
    <div class="sub" draggable="true" data-idx="${j}">
      <div class="row"><span class="grab">⠿</span>
        <input style="max-width:90px" placeholder="Year" value="${esc(r[0] || '')}" oninput="setCell('${p}',${j},0,this.value)">
        <input style="max-width:230px" placeholder="Award" value="${esc(r[1] || '')}" oninput="setCell('${p}',${j},1,this.value)">
        <input placeholder="Result" value="${esc(r[2] || '')}" oninput="setCell('${p}',${j},2,this.value)">
        <span class="x" onclick="delAt('${p}.rows',${j})">✕</span></div>
    </div>`).join('');
  return cardHead('Awards', arrPath, idx) + `<div data-arr="${p}.rows">${rows}</div>
    <button class="btn small" style="margin-top:8px" onclick="addAt('${p}.rows',['','',''])">+ Add row</button></div>`;
}

/* ---------- films ---------- */
function renderFilms() {
  const side = `
    <div class="side">
      ${S.projects.map(p => `<div class="item ${current && p.slug === current.slug ? 'on' : ''}"
        onclick="pickProject('${p.slug}')">${esc(p.title || p.slug)}</div>`).join('')}
      <button class="btn small" style="width:100%;margin-top:8px" onclick="newProject()">+ New film</button>
    </div>`;
  if (!current) current = S.projects[0] || null;
  if (!current) return side + '<div><p class="hint">No films yet.</p></div>';

  const credits = (current.credits || []).map((c, i) => `
    <div class="sub" draggable="true" data-ci="${i}">
      <div class="row"><span class="grab">⠿</span><span class="tag">Award / credit</span>
        <span class="x" onclick="delCredit(${i})">✕</span></div>
      <div class="grid2">
        <div><label>Label</label><input value="${esc(c.label)}" oninput="setCredit(${i},'label',this.value)"></div>
        <div><label>Value</label><input value="${esc(c.value)}" oninput="setCredit(${i},'value',this.value)"></div>
      </div>
    </div>`).join('');

  return side + `<div>
    <p class="hint">Add an award by adding a credit. Drag to reorder.</p>
    <div class="card">
      <div class="grid2">
        <div><label>Slug</label><input value="${esc(current.slug)}" disabled></div>
        <div><label>Title</label><input value="${esc(current.title)}" oninput="setProject('title',this.value)"></div>
        <div><label>Artist</label><input value="${esc(current.artist)}" oninput="setProject('artist',this.value)"></div>
        <div><label>Vimeo embed URL</label><input value="${esc(current.vimeo)}" oninput="setProject('vimeo',this.value)"></div>
      </div>
    </div>
    <div id="credits">${credits}</div>
    <button class="btn small" onclick="addCredit()">+ Add credit</button>
    <div class="row" style="margin-top:14px">
      <button class="btn" onclick="buildNow('${current.slug}.html')">Preview film page</button>
    </div>
  </div>`;
}
async function pickProject(slug) { await save(); current = S.projects.find(p => p.slug === slug); render(); }
async function newProject() {
  const name = prompt('Film name (e.g. Sugababes Modern Love):');
  if (!name || !name.trim()) return;
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  if (!slug) { alert('Could not make a file name from that.'); return; }
  const doc = await api('/api/new/project?slug=' + encodeURIComponent(slug), {});
  if (!doc || doc.error) { alert('Could not create: ' + ((doc && doc.error) || 'unknown error')); return; }
  const i = S.projects.findIndex(p => p.slug === slug);
  if (i >= 0) S.projects[i] = doc; else S.projects.push(doc);
  current = doc;
  render();
}
function setProject(k, v) { coalescedSnap(); current[k] = v; markDirty(); }
function setCredit(i, k, v) { coalescedSnap(); current.credits[i][k] = v; markDirty(); }
function delCredit(i) { snap(); current.credits.splice(i, 1); markDirty(); render(); }
function addCredit() {
  snap();
  current.credits = current.credits || [];
  current.credits.push({label: '', value: ''});
  markDirty(); render();
}

/* ---------- portfolio ---------- */
function renderPortfolio() {
  const tiles = S.portfolio.map((t, i) => `
    <div class="card" draggable="true" data-ti="${i}">
      <div class="row"><span class="grab">⠿</span><span class="tag">Tile ${i + 1}</span>
        <span class="x" onclick="delTile(${i})">✕</span></div>
      <div class="row" style="align-items:flex-start">
        <img class="thumb" src="/asset/assets/cargo/${esc(t.image)}" onerror="this.style.opacity=.2">
        <div style="flex:1;min-width:240px">
          <div class="drop" data-tile="${i}">Drop still here, or click</div>
          <label>Image file</label>
          <input value="${esc(t.image)}" oninput="setTile(${i},'image',this.value)">
          <label>Caption</label>
          <input value="${esc(t.caption)}" oninput="setTile(${i},'caption',this.value)">
          <label>Links to film</label>
          <select onchange="setTile(${i},'slug',this.value)">
            ${S.projects.map(p => `<option ${p.slug === t.slug ? 'selected' : ''}>${esc(p.slug)}</option>`).join('')}
          </select>
        </div>
      </div>
    </div>`).join('');
  return `<div style="width:100%">
    <p class="hint">Drag tiles to reorder the portfolio. Width/height fill themselves in on save.</p>
    ${tiles}
    <button class="btn small" onclick="addTile()">+ Add tile</button>
    <div class="row" style="margin-top:14px">
      <button class="btn" onclick="buildNow('portfolio.html')">Preview portfolio</button>
    </div>
  </div>`;
}
function setTile(i, k, v) { coalescedSnap(); S.portfolio[i][k] = v; markDirty(); }
function delTile(i) { snap(); S.portfolio.splice(i, 1); markDirty(); render(); }
function addTile() {
  snap();
  S.portfolio.push({slug: S.projects[0]?.slug || '', image: '', caption: '', width: null, height: null});
  markDirty(); render();
}

/* ---------- press ---------- */
function renderPress() {
  const outlets = S.press.map((o, oi) => `
    <div class="card" draggable="true" data-oi="${oi}">
      <div class="row"><span class="grab">⠿</span>
        <input style="max-width:320px;font-weight:600" value="${esc(o.outlet)}"
          oninput="setOutlet(${oi},'outlet',this.value)">
        <span class="x" onclick="delOutlet(${oi})">✕</span></div>
      ${(o.groups || []).map((g, gi) => `
        <div class="sub" draggable="true" data-gi="${gi}" data-goi="${oi}">
          <div class="row"><span class="grab">⠿</span>
            <input style="max-width:320px" value="${esc(g.label)}"
              oninput="setGroup(${oi},${gi},'label',this.value)">
            <span class="x" onclick="delGroup(${oi},${gi})">✕</span></div>
          ${(g.items || []).map((it, ii) => `
            <div class="row" style="margin:6px 0">
              <input value="${esc(it)}" oninput="setItem(${oi},${gi},${ii},this.value)">
              <span class="x" onclick="delItem(${oi},${gi},${ii})">✕</span>
            </div>`).join('')}
          <button class="btn small" onclick="addItem(${oi},${gi})">+ Item</button>
        </div>`).join('')}
      <button class="btn small" onclick="addGroup(${oi})">+ Group</button>
    </div>`).join('');
  return `<div style="width:100%">
    <p class="hint">Outlet → group → item. Items accept [text](url) markdown. Drag to reorder.</p>
    ${outlets}
    <button class="btn small" onclick="addOutlet()">+ Add outlet</button>
  </div>`;
}
function setOutlet(i, k, v) { coalescedSnap(); S.press[i][k] = v; markDirty(); }
function delOutlet(i) { snap(); S.press.splice(i, 1); markDirty(); render(); }
function addOutlet() { snap(); S.press.push({outlet: '', groups: []}); markDirty(); render(); }
function setGroup(oi, gi, k, v) { coalescedSnap(); S.press[oi].groups[gi][k] = v; markDirty(); }
function delGroup(oi, gi) { snap(); S.press[oi].groups.splice(gi, 1); markDirty(); render(); }
function addGroup(oi) { snap(); S.press[oi].groups.push({label: '', items: []}); markDirty(); render(); }
function setItem(oi, gi, ii, v) { coalescedSnap(); S.press[oi].groups[gi].items[ii] = v; markDirty(); }
function delItem(oi, gi, ii) { snap(); S.press[oi].groups[gi].items.splice(ii, 1); markDirty(); render(); }
function addItem(oi, gi) { snap(); S.press[oi].groups[gi].items.push(''); markDirty(); render(); }

/* ---------- contact ---------- */
function renderContact() {
  const rows = S.contact.map((c, i) => `
    <div class="card" draggable="true" data-ki="${i}">
      <div class="row"><span class="grab">⠿</span><span class="tag">Row ${i + 1}</span>
        <span class="x" onclick="delContact(${i})">✕</span></div>
      <div class="grid3">
        <div><label>Region</label><input value="${esc(c.region)}" oninput="setContact(${i},'region',this.value)"></div>
        <div><label>Person</label><input value="${esc(c.person)}" oninput="setContact(${i},'person',this.value)"></div>
        <div><label>Email</label><input value="${esc(c.email)}" oninput="setContact(${i},'email',this.value)"></div>
        <div><label>Organisation</label><input value="${esc(c.org)}" oninput="setContact(${i},'org',this.value)"></div>
        <div><label>Org URL</label><input value="${esc(c.org_url)}" oninput="setContact(${i},'org_url',this.value)"></div>
        <div><label>Instagram</label><input value="${esc(c.instagram)}" oninput="setContact(${i},'instagram',this.value)"></div>
      </div>
    </div>`).join('');
  return `<div style="width:100%">
    <p class="hint">Drag to reorder rows.</p>
    ${rows}
    <button class="btn small" onclick="addContact()">+ Add row</button>
  </div>`;
}
function setContact(i, k, v) { coalescedSnap(); S.contact[i][k] = v; markDirty(); }
function delContact(i) { snap(); S.contact.splice(i, 1); markDirty(); render(); }
function addContact() {
  snap();
  S.contact.push({region: '', person: '', email: '', org: '', org_url: '', instagram: ''});
  markDirty(); render();
}

/* ---------- render + wiring ---------- */
function render() {
  const views = {
    Treatments: renderTreatments, Films: renderFilms,
    Portfolio: renderPortfolio, Press: renderPress, Contact: renderContact,
  };
  $('#main').innerHTML = `<div class="layout" style="${tab === 'Treatments' || tab === 'Films' ? '' : 'grid-template-columns:1fr'}">
    ${views[tab]()}</div>`;
  wire();
}

function wireSortables(root) {
  root.querySelectorAll('[data-arr]').forEach(container => {
    let dragged = null;
    container.addEventListener('dragstart', e => {
      const card = e.target.closest('[data-idx]');
      if (!card || card.closest('[data-arr]') !== container) return;
      dragged = card; card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    container.addEventListener('dragover', e => {
      if (!dragged) return;
      e.preventDefault();
      const card = e.target.closest('[data-idx]');
      if (!card || card === dragged || card.closest('[data-arr]') !== container) return;
      const rect = card.getBoundingClientRect();
      const after = (e.clientY - rect.top) > rect.height / 2;
      container.insertBefore(dragged, after ? card.nextSibling : card);
    });
    container.addEventListener('dragend', () => {
      if (!dragged) return;
      dragged.classList.remove('dragging');
      dragged = null;
      snap();
      const arr = G(container.dataset.arr);
      const order = [...container.children]
        .filter(el => el.dataset.idx !== undefined)
        .map(el => +el.dataset.idx);
      const reordered = order.map(i => arr[i]);
      reordered.forEach((v, k) => arr[k] = v);
      markDirty(); render();
    });
  });
}

function wireDrops(root) {
  root.querySelectorAll('[data-drop]').forEach(el =>
    dropzone(el, async f => {
      const p = el.dataset.drop, k = el.dataset.k || 'src';
      const dir = el.dataset.updir || 'cargo';
      el.textContent = 'Uploading…';
      try {
        const r = await upload(f, dir, dir === 'treatments' ? current.slug : undefined);
        snap();
        const b = G(p);
        if (k === 'tile') {
          if (!r || !r.name) throw new Error((r && r.error) || 'no file came back from the server');
          b.image = r.name; b.width = r.width; b.height = r.height;
        } else {
          if (!r || !r.ref) throw new Error((r && r.error) || 'no file came back from the server');
          b[k] = r.ref;
        }
        markDirty(); render();
      } catch (err) {
        el.textContent = 'Upload failed — ' + err.message + '. Drop to retry.';
      }
    }));
}

function wire() {
  const main = $('#main');

  if (tab === 'Treatments' && current) {
    wireSortables(main);
    wireDrops(main);
    main.querySelectorAll('textarea[data-ta]').forEach(ta => {
      const b = G(ta.dataset.ta);
      if (!b || b.style === 'raw') return;
      ta.addEventListener('keydown', e => {
        if (e.key !== 'Enter' || e.shiftKey) return;
        e.preventDefault();
        const s = ta.selectionStart, en = ta.selectionEnd;
        const insert = b.style === 'list' ? '\n- ' : '\n\n';
        ta.value = ta.value.slice(0, s) + insert + ta.value.slice(en);
        const pos = s + insert.length;
        ta.focus();
        ta.setSelectionRange(pos, pos);
        setB(ta.dataset.ta, 'text', ta.value);
      });
    });
    const hero = $('#hero-drop');
    if (hero) dropzone(hero, async f => {
      hero.textContent = 'Uploading…';
      try {
        const r = await upload(f, 'treatments', current.slug);
        snap();
        current.meta.hero = r.ref;
        markDirty(); render();
      } catch (err) {
        hero.textContent = 'Upload failed — ' + err.message + '. Drop to retry.';
      }
    });
    return;
  }

  if (tab === 'Films' && current) {
    sortable($('#credits'), '.sub', () => {
      const order = [...$('#credits').children].map(el => +el.dataset.ci);
      current.credits = order.map(i => current.credits[i]);
    });
  }

  if (tab === 'Portfolio') {
    sortable(main, '.card', () => {
      const order = [...main.querySelectorAll('.card')].map(el => +el.dataset.ti);
      S.portfolio = order.map(i => S.portfolio[i]);
    });
    main.querySelectorAll('[data-tile]').forEach(el =>
      dropzone(el, async f => {
        const i = +el.dataset.tile;
        el.textContent = 'Uploading…';
        try {
          const r = await upload(f, 'cargo');
          S.portfolio[i].image = r.name;
          S.portfolio[i].width = r.width;
          S.portfolio[i].height = r.height;
          markDirty(); render();
        } catch (err) {
          el.textContent = 'Upload failed — ' + err.message + '. Drop to retry.';
        }
      }));
  }

  if (tab === 'Press') {
    sortable(main, '.card', () => {
      const order = [...main.querySelectorAll('.card')].map(el => +el.dataset.oi);
      S.press = order.map(i => S.press[i]);
    });
  }

  if (tab === 'Contact') {
    sortable(main, '.card', () => {
      const order = [...main.querySelectorAll('.card')].map(el => +el.dataset.ki);
      S.contact = order.map(i => S.contact[i]);
    });
  }
}

async function saveTab(t) {
  if (t === 'Treatments' && current) await api('/api/save/treatment?slug=' + current.slug, current);
  else if (t === 'Films' && current) await api('/api/save/project?slug=' + current.slug, current);
  else if (t === 'Portfolio') S.portfolio = (await api('/api/save/portfolio', S.portfolio)).tiles || S.portfolio;
  else if (t === 'Press') await api('/api/save/press', S.press);
  else if (t === 'Contact') await api('/api/save/contact', S.contact);
}
async function save() {
  const tabs = [...dirtyTabs];
  dirtyTabs.clear();
  for (const t of tabs) await saveTab(t);
  markClean();
}

function preview(path) { window.open('/site/' + path + '?v=' + Date.now(), '_blank'); }

async function testAlert() {
  const r = await api('/api/test-alert', {});
  alert(r.ok ? 'Test alert sent — check Telegram.' : 'Alert failed: ' + (r.error || 'unknown error'));
}

async function buildNow(target) {
  await save();
  const r = await api('/api/build', {});
  const old = $('.out'); if (old) old.remove();
  const div = document.createElement('div');
  div.className = 'out';
  div.textContent = (r.ok ? 'BUILD OK\n\n' : 'BUILD FAILED\n\n') + (r.output || '');
  $('#main').appendChild(div);
  if (r.ok) preview(target || (tab === 'Treatments' && current ? 't/' + current.slug + '/' : 'index.html'));
}

$('#save').onclick = save;
$('#build').onclick = () => buildNow();

(async () => {
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => e.preventDefault());
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
      const t = e.target;
      if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.tagName === 'SELECT')) return;
      e.preventDefault();
      undo();
    }
  });
  S = await api('/api/state');
  renderTabs();
  render();
})();
</script>
</body>
</html>
"""


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Studio)
    url = f"http://localhost:{PORT}/"
    print(f"studio running at {url}  (ctrl-c to stop)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()