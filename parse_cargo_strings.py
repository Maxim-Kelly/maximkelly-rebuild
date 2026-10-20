#!/usr/bin/env python3
import re, json, pathlib

root = pathlib.Path("raw")
outdir = pathlib.Path("parsed")
outdir.mkdir(exist_ok=True)

def grab(pattern, text, flags=re.S):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else None

summary = []

for f in sorted(root.rglob("index.html")):
    text = f.read_text(encoding="utf-8", errors="ignore")

    page = {
        "file": str(f),
        "title": grab(r'typepage,title(.*?),titlenohtml', text),
        "projecturl": grab(r'projecturl([A-Za-z0-9\-_]+),directlinkhttps', text),
        "contentpartialhtml": grab(r'contentpartialhtml(.*?),thumb', text),
        "contentnohtml": grab(r'contentnohtml(.*?),contentpartialhtml', text),
        "localcss": grab(r'localcss(.*?),locallayoutoptions', text),
        "pinoptions": grab(r'pinoptions(.*?),innav', text),
        "datavideourl": grab(r'datavideourl(https[^,]+)', text),
        "vimeo": re.findall(r'https?://player\.vimeo\.com/video/[^"\s<]+', text),
    }

    outname = f.parent.name if f.parent.name != "raw" else "home"
    (outdir / f"{outname}.json").write_text(json.dumps(page, indent=2), encoding="utf-8")

    summary.append({
        "page": outname,
        "has_title": bool(page["title"]),
        "has_projecturl": bool(page["projecturl"]),
        "has_contentpartialhtml": bool(page["contentpartialhtml"]),
        "has_localcss": bool(page["localcss"]),
        "has_datavideourl": bool(page["datavideourl"]),
        "vimeo_count": len(page["vimeo"]),
    })

(outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
