#!/usr/bin/env python3
import json, re, html
from pathlib import Path

RAW = Path("raw")
OUT = Path("blocks")
OUT.mkdir(exist_ok=True)

SITE_ID_RE = re.compile(r'siteid(\d+),projecturl', re.I)

def read_text(path):
    return path.read_text(encoding="utf-8", errors="ignore")

def get_scaffolding_blob(text):
    m = re.search(
        r'<script[^>]+data-setScaffoldingData[^>]*>(.*?)</script>',
        text,
        re.I | re.S
    )
    return m.group(1) if m else ""

def normalize(s):
    return html.unescape((s or "").replace("\\/", "/").replace("\r", ""))

def extract_field(block, field, next_fields):
    stops = "|".join(re.escape(f) for f in next_fields)
    pat = re.compile(rf'{re.escape(field)}(.*?)(?=,(?:{stops})|$)', re.I | re.S)
    m = pat.search(block)
    return normalize(m.group(1).strip()) if m else ""

def split_blocks(blob):
    starts = list(re.finditer(r'(?:^|,)siteid\d+,projecturl', blob, re.I))
    if not starts:
        return []
    chunks = []
    for i, m in enumerate(starts):
        start = m.start()
        end = starts[i+1].start() if i + 1 < len(starts) else len(blob)
        chunks.append(blob[start:end].lstrip(","))
    return chunks

FIELD_ORDER = [
    "projecturl","directlink","type","title","titlenohtml","tags","display","pin",
    "pinoptions","innav","ishomepage","backdropenabled","isset","stack","excerpt",
    "content","contentnohtml","contentpartialhtml","thumb","thumbmeta","thumbisvisible",
    "sort","index","setid","pageoptionsusinglocalcss","localcss","locallayoutoptions",
    "splitlayout","splitresponsive","fullheight","advancedpaddingenabled","pagecontainerbgcolor",
    "showlocalthumbs","pagebgcolor","textalignment","mainmargin","mainmargintop","mainmarginright",
    "mainmarginbottom","mainmarginleft","contentwidth","contentposition","verticalposition",
    "thumbnailoptions","setopen","images","backdrop","id"
]

def parse_blocks(blob):
    results = []
    for raw_block in split_blocks(blob):
        b = {"raw": raw_block}
        for i, field in enumerate(FIELD_ORDER):
            b[field] = extract_field(raw_block, field, FIELD_ORDER[i+1:] + ["siteid"])
        b["vimeo"] = ""
        vm = re.search(r'player\.vimeo\.com/video/([0-9]+[^"\s,<]*)', raw_block, re.I)
        if vm:
            b["vimeo"] = "https://player.vimeo.com/video/" + vm.group(1)
        dv = re.search(r'(https?://[^,\s"]+\.(?:mp4|webm|mov)(?:\?[^,\s"]*)?)', raw_block, re.I)
        b["datavideourl"] = dv.group(1) if dv else ""
        if b.get("projecturl"):
            results.append({
                "projecturl": b.get("projecturl",""),
                "title": b.get("title",""),
                "pinoptions": b.get("pinoptions",""),
                "datavideourl": b.get("datavideourl",""),
                "vimeo": b.get("vimeo",""),
                "contentpartialhtml": b.get("contentpartialhtml",""),
                "contentnohtml": b.get("contentnohtml",""),
                "localcss": b.get("localcss",""),
                "backdrop": b.get("backdrop",""),
                "id": b.get("id","")
            })
    return results

summary = []

for html_file in sorted(RAW.glob("**/index.html")):
    rel = html_file.relative_to(RAW)
    page = "home" if str(rel) == "index.html" else rel.parts[0]
    text = read_text(html_file)
    blob = get_scaffolding_blob(text)

    blocks = parse_blocks(blob) if blob else []

    payload = {
        "page": page,
        "file": str(html_file),
        "block_count": len(blocks),
        "blocks": blocks
    }

    out_file = OUT / f"{page}.json"
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary.append({
        "page": page,
        "block_count": len(blocks),
        "projecturls": [b["projecturl"] for b in blocks[:12]],
        "has_contentpartialhtml": sum(1 for b in blocks if b["contentpartialhtml"]),
        "has_localcss": sum(1 for b in blocks if b["localcss"]),
        "has_datavideourl": sum(1 for b in blocks if b["datavideourl"] or b["vimeo"])
    })

(OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
