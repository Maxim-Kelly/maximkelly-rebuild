#!/usr/bin/env python3
import json, pathlib, re

root = pathlib.Path("raw")
outdir = pathlib.Path("extracted")
outdir.mkdir(exist_ok=True)

def grab(tag, text):
    m = re.search(rf'<script[^>]*{tag}[^>]*>(.*?)</script>', text, re.S)
    return m.group(1).strip() if m else None

summary = []

for f in sorted(root.rglob("index.html")):
    text = f.read_text(encoding="utf-8", errors="ignore")
    row = {
        "file": str(f),
        "has_setSite": bool(grab("data-setSite", text)),
        "has_scaffolding": bool(grab("data-setScaffoldingData", text)),
        "contentpartialhtml_hits": len(re.findall(r'contentpartialhtml', text)),
        "contentnohtml_hits": len(re.findall(r'contentnohtml', text)),
        "localcss_hits": len(re.findall(r'localcss', text)),
        "projecturl_hits": len(re.findall(r'projecturl', text)),
        "pinoptions_hits": len(re.findall(r'pinoptions', text)),
        "backdrop_hits": len(re.findall(r'datavideourl|backdrop', text)),
        "vimeo_hits": len(re.findall(r'player\.vimeo\.com', text)),
        "cargo_file_hits": len(re.findall(r'files\.cargocollective\.com|freight\.cargo\.site', text)),
    }
    summary.append(row)

(outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
