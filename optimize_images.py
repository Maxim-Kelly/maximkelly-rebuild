#!/usr/bin/env python3
"""Optimize the downloaded portfolio stills so the site loads quickly.

Large Cargo PNG exports (10-12MB each) are converted to JPEG at a sane
display size. Filenames keep their base name but get a .jpg extension, so
build_static_site_v3.py falls back across extensions when it resolves
`assets/cargo/...` references.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

CARGO = Path(__file__).resolve().parent / "site" / "assets" / "cargo"
MAX_EDGE = 1600
JPEG_QUALITY = 82
MIN_BYTES_TO_TOUCH = 400_000  # skip anything already small enough


def optimize(path: Path) -> Path | None:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    if path.stat().st_size < MIN_BYTES_TO_TOUCH:
        return None

    out_path = path.with_suffix(".jpg")
    if out_path == path:
        out_path = path  # recompress in place

    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

    if out_path != path and path.exists():
        path.unlink()

    return out_path


def main() -> int:
    if not CARGO.exists():
        print(f"missing {CARGO}", file=sys.stderr)
        return 1

    touched = 0
    for path in sorted(CARGO.iterdir()):
        result = optimize(path)
        if result is not None:
            size_kb = result.stat().st_size // 1024
            print(f"optimized {path.name} -> {result.name} ({size_kb}KB)")
            touched += 1

    total = sum(p.stat().st_size for p in CARGO.iterdir() if p.is_file())
    print(f"{touched} file(s) optimized, cargo assets now {total // (1024 * 1024)}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
