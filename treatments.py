"""Treatment pages: /t/<slug>/ — standalone presentation pages with no site chrome."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

# Treatment pages live at t/<slug>/index.html, so site assets sit two levels up.
ASSET_PREFIX = "../../"
ASSET_EXT = (".jpg", ".jpeg", ".webp", ".png", ".mp4", ".webm", ".gif")

TREATMENT_CSS = r"""
.treatment-page{--t-bg:#141412;--t-fg:#e9e6df;--t-muted:#a19d94;--t-dim:#767268;--t-rule:rgba(233,230,223,.15);--t-col:min(72ch,calc(100% - 2 * var(--pad)));--t-wide:min(1180px,calc(100% - 2 * var(--pad)));background:var(--t-bg);color:var(--t-fg);overflow-x:clip}
.treatment{width:100%}
.t-hero{position:relative;min-height:100vh;min-height:100dvh;display:flex;align-items:flex-end;padding:var(--pad);isolation:isolate}
.t-hero-media{position:absolute;inset:0;z-index:-2;background-position:center;background-size:cover}
.t-hero-video{position:absolute;inset:0;z-index:-2;width:100%;height:100%;object-fit:contain;background:#000}
.t-hero-video--cover{object-fit:cover}
@media (orientation:portrait){.t-hero-video{object-fit:cover}}
.t-hero-scrim{position:absolute;inset:0;z-index:-1;background:linear-gradient(to top,rgba(20,20,18,.94) 0%,rgba(20,20,18,.16) 52%,rgba(20,20,18,.52) 100%)}
.t-hero-inner{width:min(100%,960px)}
.t-kicker{margin:0 0 20px;font-size:var(--text-caption);letter-spacing:.32em;text-transform:uppercase;color:var(--t-muted)}
.t-title{margin:0;font-size:clamp(34px,6.4vw,104px);line-height:.92;letter-spacing:-.055em;font-weight:400;text-wrap:balance}
.t-meta{margin:26px 0 0;font-size:clamp(11px,1vw,13px);letter-spacing:.22em;text-transform:uppercase;color:var(--t-muted);line-height:1.8}
.t-body{padding:clamp(56px,9vw,120px) 0}
.t-section{margin:0 auto clamp(56px,9vw,112px)}
.t-section:last-child{margin-bottom:0}
.t-section-title{margin:0 auto clamp(28px,5vw,52px);width:var(--t-col);padding:0;font-size:clamp(11px,1vw,13px);letter-spacing:.3em;text-transform:uppercase;color:var(--t-dim);font-weight:400}
.t-block{margin:0 auto}
.t-block--col{width:var(--t-col)}
.t-block--col-wide{width:min(90ch,calc(100% - 2 * var(--pad)))}
.t-block--wide{width:var(--t-wide)}
.t-block--full{width:94vw;margin-left:calc(50% - 47vw)}
.t-h3{margin:0 0 .55em;font-size:clamp(20px,2.2vw,30px);line-height:1.18;letter-spacing:-.025em;font-weight:400}
.t-p{margin:0 0 1.35em;font-size:clamp(18px,1.4vw,23px);line-height:1.62;letter-spacing:-.004em;color:#dcd8d0}
.t-p:last-child{margin-bottom:0}
.t-list{margin:0 0 1.5em;padding-left:1.15em;font-size:clamp(18px,1.4vw,23px);line-height:1.62;color:#dcd8d0}
.t-list li{margin:.42em 0}
.t-cols-2{column-count:2;column-gap:clamp(28px,4vw,56px)}
.t-quote{margin:0;padding:0 0 0 clamp(18px,2.4vw,28px);border-left:1px solid var(--t-rule);font-size:clamp(22px,2.8vw,38px);line-height:1.22;letter-spacing:-.035em;color:var(--t-fg)}
.t-fig{margin:clamp(38px,6vw,72px) 0}
.t-fig img{display:block;width:100%;height:auto}
.t-fig figcaption{margin:12px 2px 0;font-size:clamp(11px,.95vw,13px);letter-spacing:.14em;text-transform:uppercase;color:var(--t-dim);line-height:1.55}
.t-block--full .t-fig{margin-inline:0}
.t-block--full figcaption{padding-inline:var(--pad)}
.t-video{position:relative;width:100%;aspect-ratio:16/9;background:#000}
.t-video iframe,.t-video video{position:absolute;inset:0;width:100%;height:100%;border:0;object-fit:cover}
.t-split{display:grid;grid-template-columns:1fr 1fr;gap:clamp(28px,4.5vw,64px);align-items:start;width:var(--t-wide);margin:clamp(38px,6vw,72px) auto}
.t-split>*{min-width:0}
.t-split .t-block{width:auto;margin:0}
.t-split .t-fig{margin:0}
.t-work{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:clamp(24px,3.5vw,48px);width:var(--t-wide);margin:clamp(38px,6vw,72px) auto}
.t-work-item{display:block;text-decoration:none}
.t-work-item .t-fig{margin:0}
.t-work-item img{transition:transform .6s cubic-bezier(.2,.7,.2,1),opacity .3s ease}
.t-work-item:hover img{transform:scale(1.03);opacity:.9}
.t-work-title{margin:14px 0 0;font-size:clamp(15px,1.4vw,19px);letter-spacing:-.015em;color:var(--t-fg)}
.t-work-artist{margin:4px 0 0;font-size:clamp(11px,.95vw,13px);letter-spacing:.16em;text-transform:uppercase;color:var(--t-dim)}
.t-awards{display:grid;grid-template-columns:auto 1fr;gap:14px clamp(18px,3vw,36px);margin:0;font-size:clamp(15px,1.3vw,19px)}
.t-awards dt{margin:0;letter-spacing:.12em;color:var(--t-dim);font-variant-numeric:tabular-nums}
.t-awards dd{margin:0}
.t-award-org{display:block;letter-spacing:-.01em;color:var(--t-fg)}
.t-award-detail{display:block;margin-top:4px;font-size:clamp(11px,.95vw,13px);letter-spacing:.14em;text-transform:uppercase;color:var(--t-dim)}
.t-break{width:100%;margin:clamp(56px,9vw,112px) 0;border:0;border-top:1px solid var(--t-rule)}
.t-credits{width:var(--t-wide);margin:0 auto;padding:clamp(48px,8vw,96px) 0 clamp(64px,10vw,120px);border-top:1px solid var(--t-rule);display:flex;justify-content:flex-end}
.t-credits-inner{width:min(460px,100%)}
.t-credits dl{display:grid;grid-template-columns:minmax(110px,.55fr) 1.45fr;gap:10px clamp(18px,3vw,32px);margin:0;font-size:clamp(12px,1vw,14px)}
.t-credits dt{margin:0;letter-spacing:.24em;text-transform:uppercase;color:var(--t-dim)}
.t-credits dd{margin:0;letter-spacing:.02em;color:var(--t-muted)}
.t-version{margin:34px 0 0;font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:var(--t-dim)}
.t-reveal{opacity:0;transform:translateY(22px);transition:opacity .95s cubic-bezier(.22,.61,.36,1),transform .95s cubic-bezier(.22,.61,.36,1)}
.t-reveal.is-in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.t-reveal{opacity:1!important;transform:none!important;transition:none!important}}
@media (max-width:720px){
  .t-hero{padding:var(--pad) 16px}
  .t-hero-video{object-fit:cover}
  .t-hero-inner{width:100%}
  .t-title{font-size:clamp(30px,9vw,52px)}
  .t-meta{margin-top:18px;line-height:1.7}
  .t-p,.t-list{font-size:clamp(17px,4.6vw,20px);line-height:1.6}
  .t-quote{font-size:clamp(20px,5.4vw,28px)}
  .t-cols-2{column-count:1}
  .t-work{grid-template-columns:1fr;width:calc(100% - 2 * var(--pad))}
  .t-awards{grid-template-columns:1fr;gap:2px}
  .t-awards dd{margin-bottom:18px}
  .t-split{grid-template-columns:1fr;gap:clamp(22px,5vw,36px);width:calc(100% - 2 * var(--pad))}
  .t-credits{padding-inline:var(--pad);justify-content:flex-start}
  .t-credits-inner{width:100%}
  .t-credits dl{grid-template-columns:1fr;gap:4px}
  .t-credits dd{margin-bottom:16px}
}
@media print{
  .treatment-page{background:#fff;color:#000}
  .t-hero{min-height:auto;padding:0 0 24pt}
  .t-hero-media,.t-hero-scrim{display:none}
  .t-kicker,.t-meta{color:#555}
  .t-title{font-size:30pt;letter-spacing:-.02em}
  .t-body{padding:18pt 0}
  .t-section{margin:0 0 18pt}
  .t-section-title{position:static;background:none;color:#555;padding:0 0 8pt}
  .t-block,.t-block--col,.t-block--col-wide,.t-block--wide,.t-block--full,.t-split,.t-credits{width:auto;margin-left:0;margin-right:0}
  .t-split{display:grid;grid-template-columns:1fr 1fr}
  .t-credits{display:block;border-top:1pt solid #999}
  .t-credits-inner{width:auto}
  .t-p,.t-list{color:#000;font-size:11pt}
  .t-quote{font-size:16pt;color:#000}
  .t-reveal{opacity:1!important;transform:none!important}
  .t-credits{border-top:1pt solid #999}
}
"""

TREATMENT_JS = r"""
(function(){
  var track = function(name, title){
    if (window.goatcounter && typeof window.goatcounter.count === 'function') {
      try { window.goatcounter.count({ path: name, title: title || name, event: true }); } catch (e) {}
    }
  };

  /* ---- push alert to you on the high-signal events ---- */
  var ALERT_ENDPOINT = '__ALERT_URL__';
  var ALERT_MODE = '__ALERT_MODE__';
  var ALERT_CHAT = '__ALERT_CHAT__';
  var ALERT_TITLE = '__ALERT_TITLE__';
  function alertNow(){
    if (!ALERT_ENDPOINT) return;
    try {
      if (ALERT_MODE === 'telegram') {
        fetch(ALERT_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: ALERT_CHAT, text: 'Treatment opened — ' + ALERT_TITLE + '\n' + window.location.href })
        }).catch(function(){});
      } else if (ALERT_MODE === 'json') {
        fetch(ALERT_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ treatment: ALERT_TITLE, url: window.location.href, time: new Date().toISOString() })
        }).catch(function(){});
      } else {
        var body = '_subject=' + encodeURIComponent('Treatment opened: ' + ALERT_TITLE)
          + '&event=treatment_open&page=' + encodeURIComponent(window.location.href);
        fetch(ALERT_ENDPOINT, {
          method: 'POST',
          mode: 'no-cors',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body
        }).catch(function(){});
      }
    } catch (e) {}
  }

  /* ---- engagement signals ---- */
  var key = 't-seen:' + location.pathname;
  var seen = false;
  try { seen = !!window.localStorage.getItem(key); window.localStorage.setItem(key, String(Date.now())); } catch (e) {}
  track(seen ? 'treatment_revisit' : 'treatment_open');
  alertNow();

  var printed = false;
  function notePrint(){ if (!printed) { printed = true; track('treatment_print'); } }
  window.addEventListener('beforeprint', notePrint);
  if (window.matchMedia) {
    try {
      var mq = window.matchMedia('print');
      if (mq.addEventListener) mq.addEventListener('change', function(e){ if (e.matches) notePrint(); });
    } catch (e) {}
  }

  var marks = [25, 50, 75, 100], reached = {};
  function depth(){
    var root = document.documentElement;
    var max = root.scrollHeight - window.innerHeight;
    var pct = max > 0 ? Math.round((window.pageYOffset / max) * 100) : 100;
    for (var i = 0; i < marks.length; i++) {
      var m = marks[i];
      if (pct >= m && !reached[m]) {
        reached[m] = true;
        track('scroll_depth_' + m);
      }
    }
  }

  var currentSection = null, sectionStart = 0;
  function flushSection(){
    if (currentSection && sectionStart) {
      var secs = Math.round((Date.now() - sectionStart) / 1000);
      if (secs >= 3) track('section_' + currentSection, currentSection + ' (' + secs + 's)');
    }
    currentSection = null; sectionStart = 0;
  }
  function enterSection(name){
    if (currentSection === name) return;
    flushSection();
    currentSection = name; sectionStart = Date.now();
  }
  window.addEventListener('pagehide', flushSection);

  document.querySelectorAll('.t-video').forEach(function(el){
    el.addEventListener('click', function(){ track('video_click'); }, { once: true });
  });

  /* ---- motion ---- */
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if ('IntersectionObserver' in window) {
    var sectionIo = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if (e.isIntersecting) enterSection(e.target.getAttribute('data-section') || 'intro');
      });
    }, { threshold: 0.2 });
    document.querySelectorAll('[data-section]').forEach(function(el){ sectionIo.observe(el); });

    if (!reduce) {
      var revealIo = new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if (e.isIntersecting) { e.target.classList.add('is-in'); revealIo.unobserve(e.target); }
        });
      }, { rootMargin: '0px 0px -8% 0px' });
      document.querySelectorAll('.t-reveal').forEach(function(el){ revealIo.observe(el); });
    }
  } else {
    document.querySelectorAll('.t-reveal').forEach(function(el){ el.classList.add('is-in'); });
  }

  window.addEventListener('scroll', depth, { passive: true });
  window.addEventListener('scroll', function(){
    if (reduce || ticking) return;
    ticking = true;
    window.requestAnimationFrame(parallax);
  }, { passive: true });

  var ticking = false;
  var parallaxItems = [];
  if (!reduce) {
    parallaxItems = Array.prototype.slice.call(document.querySelectorAll('.t-block--full'));
  }
  function parallax(){
    var vh = window.innerHeight;
    for (var i = 0; i < parallaxItems.length; i++) {
      var fig = parallaxItems[i], r = fig.getBoundingClientRect();
      if (r.bottom < -80 || r.top > vh + 80) continue;
      var progress = (r.top + r.height / 2 - vh / 2) / vh;
      fig.style.setProperty('--p', (-progress * 4).toFixed(2) + '%');
    }
    ticking = false;
  }

  depth();
  parallax();
})();
"""

IMAGE_LINE = re.compile(r"^!\[(.*?)\]\((?:(inline|wide|full):\s*)?([^)]+)\)\s*$")
VIDEO_LINE = re.compile(r"^\{\{\s*video:\s*(.+?)\s*\}\}\s*$")
CAPTION_LINE = re.compile(r"^\*([^*].*?)\*\s*$")
HEADING_LINE = re.compile(r"^(#{2,3})\s+(.*)$")
DIRECTIVE_LINE = re.compile(r"^\{\{\s*(wide|full|columns:\s*\d+)\s*\}\}\s*$", re.I)
SPLIT_OPEN = re.compile(r"^\{\{\s*split\s*$", re.I)
WORK_OPEN = re.compile(r"^\{\{\s*work\s*$", re.I)
AWARDS_OPEN = re.compile(r"^\{\{\s*awards\s*$", re.I)
SPLIT_SIDE = re.compile(r"^\s*(left|right)\s*:\s*$", re.I)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    import yaml

    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].lstrip("\n")


def _md_plain(value: str) -> str:
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", value)
    return value


def md_inline(value: str) -> str:
    out: list[str] = []
    pos = 0
    for match in LINK_RE.finditer(value):
        out.append(_md_plain(value[pos : match.start()]))
        out.append(
            f'<a href="{html.escape(match.group(2), quote=True)}" target="_blank" rel="noopener">'
            f"{_md_plain(match.group(1))}</a>"
        )
        pos = match.end()
    out.append(_md_plain(value[pos:]))
    return "".join(out)


def resolve_asset(site_root: Path, src: str) -> str:
    src = src.strip()
    if not src or src.startswith(("http://", "https://", "//", "data:")):
        return src
    name = src.lstrip("/")
    stem = Path(name).stem
    parent = Path(name).parent
    for ext in ASSET_EXT:
        candidate = parent / f"{stem}{ext}"
        if (site_root / candidate).exists():
            return ASSET_PREFIX + candidate.as_posix()
    return ASSET_PREFIX + name


def is_video(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".webm", ".mov"}


def vimeo_embed(url: str) -> str:
    url = html.unescape(url.strip())
    found = re.search(r"vimeo\.com/(?:video/)?([0-9]+)", url)
    return f"https://player.vimeo.com/video/{found.group(1)}" if found else url


def wrap(kind: str, inner: str, *, reveal: bool = True, extra: str = "") -> str:
    classes = f"t-block t-block--{kind}" + (" t-reveal" if reveal else "")
    if extra:
        classes += f" {extra}"
    return f'<div class="{classes}">{inner}</div>'


def render_work(site_root: Path, items: list[dict[str, str]]) -> str:
    cells: list[str] = []
    for item in items:
        src = resolve_asset(site_root, item.get("image", ""))
        title = md_inline(item.get("title", ""))
        artist = md_inline(item.get("artist", ""))
        url = item.get("url", "").strip()
        inner = (
            '<figure class="t-fig">'
            f'<img src="{html.escape(src, quote=True)}" '
            f'alt="{html.escape(_md_plain(item.get("title", "")), quote=True)}" loading="lazy">'
            "</figure>"
        )
        inner += f'<p class="t-work-title">{title}</p>'
        if artist:
            inner += f'<p class="t-work-artist">{artist}</p>'
        if url:
            cells.append(
                f'<a class="t-work-item t-reveal" href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noopener">{inner}</a>'
            )
        else:
            cells.append(f'<div class="t-work-item t-reveal">{inner}</div>')
    return f'<div class="t-work">{"".join(cells)}</div>'


def render_awards(rows: list[list[str]]) -> str:
    body: list[str] = []
    for row in rows:
        year = row[0] if len(row) > 0 else ""
        org = row[1] if len(row) > 1 else ""
        detail = row[2] if len(row) > 2 else ""
        body.append(
            f"<dt>{md_inline(year)}</dt><dd>"
            f'<span class="t-award-org">{md_inline(org)}</span>'
            + (f'<span class="t-award-detail">{md_inline(detail)}</span>' if detail else "")
            + "</dd>"
        )
    return (
        '<div class="t-block t-block--col t-reveal">'
        f'<dl class="t-awards">{"".join(body)}</dl></div>'
    )


def render_blocks(site_root: Path, body: str) -> str:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    lines = body.splitlines()
    out: list[str] = []
    section_open = False
    pending_width = ""
    pending_extra = ""
    i = 0
    total = len(lines)

    def close_section() -> None:
        nonlocal section_open
        if section_open:
            out.append("</section>")
            section_open = False

    def take_width() -> tuple[str, str]:
        nonlocal pending_width, pending_extra
        width, extra = pending_width, pending_extra
        pending_width = ""
        pending_extra = ""
        return width, extra

    while i < total:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        directive = DIRECTIVE_LINE.match(stripped)
        if directive:
            token = re.sub(r"\s+", "", directive.group(1)).lower()
            if token == "columns:2":
                pending_extra = "t-cols-2"
                pending_width = pending_width or "col"
            else:
                pending_width = token
            i += 1
            continue

        if SPLIT_OPEN.match(stripped):
            close_section()
            left: list[str] = []
            right: list[str] = []
            target: list[str] | None = None
            i += 1
            while i < total:
                line = lines[i].rstrip()
                if line.strip() == "}}":
                    i += 1
                    break
                side = SPLIT_SIDE.match(line)
                if side:
                    target = left if side.group(1).lower() == "left" else right
                elif target is not None:
                    target.append(line)
                i += 1
            left_html = render_blocks(site_root, "\n".join(left))
            right_html = render_blocks(site_root, "\n".join(right))
            out.append(f'<div class="t-split">{left_html}{right_html}</div>')
            continue

        if WORK_OPEN.match(stripped):
            close_section()
            i += 1
            items: list[dict[str, str]] = []
            current: dict[str, str] = {}
            while i < total:
                line = lines[i].strip()
                if line == "}}":
                    i += 1
                    break
                if not line:
                    if current:
                        items.append(current)
                        current = {}
                else:
                    pair = re.match(r"^([A-Za-z_]+)\s*:\s*(.+)$", line)
                    if pair:
                        current[pair.group(1).lower()] = pair.group(2).strip()
                i += 1
            if current:
                items.append(current)
            out.append(render_work(site_root, items))
            continue

        if AWARDS_OPEN.match(stripped):
            close_section()
            i += 1
            award_rows: list[list[str]] = []
            while i < total:
                line = lines[i].strip()
                if line == "}}":
                    i += 1
                    break
                if line:
                    award_rows.append([part.strip() for part in line.split("|", 2)])
                i += 1
            out.append(render_awards(award_rows))
            continue

        if stripped == "---":
            close_section()
            out.append('<hr class="t-break">')
            i += 1
            continue

        heading = HEADING_LINE.match(stripped)
        if heading:
            level = len(heading.group(1))
            text = md_inline(heading.group(2).strip())
            if level == 2:
                close_section()
                out.append(f'<section class="t-section" data-section="{html.escape(heading.group(2).strip(), quote=True)}">')
                section_open = True
                out.append(f'<h2 class="t-section-title">{text}</h2>')
            else:
                width, extra = take_width()
                out.append(wrap(width or "col", f'<h3 class="t-h3">{text}</h3>', extra=extra))
            i += 1
            continue

        image = IMAGE_LINE.match(stripped)
        if image:
            alt, width, src = image.group(1).strip(), image.group(2) or "inline", image.group(3).strip()
            resolved = resolve_asset(site_root, src)
            caption = ""
            if i + 1 < total:
                cap = CAPTION_LINE.match(lines[i + 1].strip())
                if cap:
                    caption = md_inline(cap.group(1).strip())
                    i += 1
            if is_video(resolved):
                media = (
                    '<div class="t-video">'
                    f'<video src="{html.escape(resolved, quote=True)}" autoplay muted loop playsinline></video>'
                    "</div>"
                )
            else:
                media = (
                    f'<img src="{html.escape(resolved, quote=True)}" '
                    f'alt="{html.escape(caption or alt, quote=True)}" loading="lazy">'
                )
            fig = f'<figure class="t-fig">{media}'
            if caption:
                fig += f"<figcaption>{caption}</figcaption>"
            fig += "</figure>"
            block_width, extra = take_width()
            out.append(wrap(block_width or ("col" if width == "inline" else width), fig, extra=extra))
            i += 1
            continue

        video = VIDEO_LINE.match(stripped)
        if video:
            embed = vimeo_embed(video.group(1))
            inner = (
                '<figure class="t-fig"><div class="t-video">'
                f'<iframe src="{html.escape(embed, quote=True)}" '
                'allow="autoplay; fullscreen; picture-in-picture" allowfullscreen loading="lazy"></iframe>'
                "</div></figure>"
            )
            block_width, extra = take_width()
            out.append(wrap(block_width or "wide", inner, extra=extra))
            i += 1
            continue

        if stripped.startswith(">"):
            quote = stripped.lstrip("> ").strip()
            block_width, extra = take_width()
            out.append(wrap(block_width or "col", f'<blockquote class="t-quote">{md_inline(quote)}</blockquote>', extra=extra))
            i += 1
            continue

        if stripped.startswith("- "):
            items = []
            while i < total and lines[i].strip().startswith("- "):
                items.append(f"<li>{md_inline(lines[i].strip()[2:].strip())}</li>")
                i += 1
            block_width, extra = take_width()
            out.append(wrap(block_width or "col", f'<ul class="t-list">{"".join(items)}</ul>', extra=extra))
            continue

        para = [stripped]
        i += 1
        while i < total:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith(("- ", ">"))
                or IMAGE_LINE.match(nxt)
                or VIDEO_LINE.match(nxt)
                or HEADING_LINE.match(nxt)
                or DIRECTIVE_LINE.match(nxt)
                or SPLIT_OPEN.match(nxt)
                or WORK_OPEN.match(nxt)
                or AWARDS_OPEN.match(nxt)
                or nxt == "---"
            ):
                break
            para.append(nxt)
            i += 1
        block_width, extra = take_width()
        out.append(wrap(block_width or "col", f'<p class="t-p">{md_inline(" ".join(para))}</p>', extra=extra))

    close_section()
    return "\n".join(out)


def render_treatment(
    meta: dict[str, Any],
    body: str,
    *,
    site_root: Path,
    stylesheet: str,
    slug: str,
    site_url: str,
    analytics_code: str = "",
    alert_endpoint: str = "",
    alert_mode: str = "form",
    alert_chat: str = "",
) -> str:
    track = str(meta.get("track") or slug).strip()
    client = str(meta.get("client") or "").strip()
    hero = str(meta.get("hero") or "").strip()
    hero_src = resolve_asset(site_root, hero) if hero else ""
    hero_poster_src = ""
    if meta.get("hero_poster"):
        hero_poster_src = resolve_asset(site_root, str(meta["hero_poster"]))
    elif hero and is_video(hero_src):
        stem = Path(hero).with_suffix("").as_posix()
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = f"{stem}-poster{ext}"
            if (site_root / candidate).exists():
                hero_poster_src = ASSET_PREFIX + candidate
                break
    hero_fit = str(meta.get("hero_fit") or "contain").strip().lower()
    hero_class = "t-hero-video t-hero-video--cover" if hero_fit == "cover" else "t-hero-video"

    og_image_src = hero_poster_src or (hero_src if hero_src and not is_video(hero_src) else "")
    og_image_url = ""
    if og_image_src.startswith(ASSET_PREFIX):
        og_image_url = f"{site_url}/{og_image_src[len(ASSET_PREFIX):]}"
    elif og_image_src.startswith(("http://", "https://")):
        og_image_url = og_image_src
    og_block = ""
    if og_image_url:
        og_block = (
            f'\n  <meta property="og:image" content="{html.escape(og_image_url, quote=True)}">'
            f'\n  <meta name="twitter:image" content="{html.escape(og_image_url, quote=True)}">'
        )

    meta_bits = []
    if meta.get("director"):
        meta_bits.append(f"Directed by {meta['director']}")
    if meta.get("production"):
        meta_bits.append(str(meta["production"]))
    if meta.get("date"):
        meta_bits.append(str(meta["date"]))
    meta_line = " · ".join(meta_bits)

    hero_markup = ""
    if hero_src and is_video(hero_src):
        poster_attr = (
            f' poster="{html.escape(hero_poster_src, quote=True)}"'
            if hero_poster_src
            else ""
        )
        hero_markup += (
            f'<video class="{hero_class}" autoplay muted loop playsinline preload="metadata" '
            f'aria-hidden="true"{poster_attr}>'
            f'<source src="{html.escape(hero_src, quote=True)}" type="video/mp4">'
            "</video>"
        )
    elif hero_src:
        hero_markup += (
            '<div class="t-hero-media" '
            f'style="background-image:url(\'{html.escape(hero_src, quote=True)}\')"></div>'
        )
    hero_markup += '<div class="t-hero-scrim"></div><div class="t-hero-inner">'
    if client:
        hero_markup += f'<p class="t-kicker">{html.escape(client)}</p>'
    hero_markup += f'<h1 class="t-title">{md_inline(track)}</h1>'
    if meta_line:
        hero_markup += f'<p class="t-meta">{html.escape(meta_line)}</p>'
    hero_markup += "</div>"

    credits = [
        ("Client", meta.get("client")),
        ("Track", meta.get("track")),
        ("Director", meta.get("director")),
        ("Production", meta.get("production")),
        ("Date", meta.get("date")),
    ]
    rows = "".join(
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(str(value))}</dd>"
        for label, value in credits
        if value
    )
    inner = f"<dl>{rows}</dl>" if rows else ""
    if meta.get("version"):
        inner += f'<p class="t-version">{html.escape(str(meta["version"]))}</p>'
    credits_markup = f'<footer class="t-credits"><div class="t-credits-inner">{inner}</div></footer>' if inner else ""

    description = html.escape(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()[:240], quote=True
    )
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "name": track,
        "description": description,
        "url": f"{site_url}/t/{slug}/",
    }
    if meta.get("director"):
        payload["creator"] = {"@type": "Person", "name": str(meta["director"])}

    analytics = ""
    if analytics_code:
        analytics = (
            f'\n  <script data-goatcounter="https://{html.escape(analytics_code, quote=True)}'
            '.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'
        )

    def js_safe(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

    treatment_js = (
        TREATMENT_JS.replace("__ALERT_URL__", js_safe(alert_endpoint))
        .replace("__ALERT_MODE__", js_safe(alert_mode))
        .replace("__ALERT_CHAT__", js_safe(alert_chat))
        .replace("__ALERT_TITLE__", js_safe(track))
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(track, quote=False)} — Treatment</title>
  <meta name="description" content="{description}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{html.escape(track, quote=True)} — Treatment">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{html.escape(site_url, quote=True)}/t/{html.escape(slug, quote=True)}/">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(track, quote=True)} — Treatment">
  <meta name="twitter:description" content="{description}">{og_block}
  <meta name="robots" content="noindex, nofollow">
  <link rel="canonical" href="{html.escape(site_url, quote=True)}/t/{html.escape(slug, quote=True)}/">
  <link rel="stylesheet" href="{stylesheet}">
  <script type="application/ld+json">{json.dumps(payload, ensure_ascii=False)}</script>{analytics}
</head>
<body class="treatment-page">
<article class="treatment">
  <header class="t-hero">{hero_markup}</header>
  <div class="t-body">
{render_blocks(site_root, body)}
  </div>
{credits_markup}
</article>
<script>{treatment_js}</script>
</body>
</html>
"""
