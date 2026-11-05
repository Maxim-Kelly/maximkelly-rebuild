#!/usr/bin/env python3
"""Optimize stills and GIFs used across the site.

- Photos are downscaled and re-encoded to JPEG.
- Screenshots keep their format so small type stays sharp.
- Animated GIFs become silent looping MP4s (roughly 10x smaller, better quality).

Scans site/assets/cargo and site/assets/treatments recursively. Safe to re-run:
anything already small is left alone.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
SCAN_DIRS = [SITE / "assets" / "cargo", SITE / "assets" / "treatments"]

MAX_EDGE = 2000
GIF_MAX_EDGE = 1280
JPEG_QUALITY = 82
MIN_BYTES_TO_TOUCH = 400_000
# A PNG this large is almost certainly a photo, not a screenshot.
PNG_PHOTO_THRESHOLD = 1_000_000


def image_paths() -> list[Path]:
    found: list[Path] = []
    for base in SCAN_DIRS:
        if base.exists():
            found.extend(p for p in sorted(base.rglob("*")) if p.is_file())
    return found


def resample(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    if max(width, height) <= MAX_EDGE:
        return size
    if width >= height:
        return MAX_EDGE, max(1, round(height * MAX_EDGE / width))
    return max(1, round(width * MAX_EDGE / height)), MAX_EDGE


def optimize_still(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None

    with Image.open(path) as img:
        size = img.size
        is_animated = bool(getattr(img, "is_animated", False))
    if is_animated:
        return None

    oversized = max(size) > MAX_EDGE
    big_file = path.stat().st_size >= MIN_BYTES_TO_TOUCH
    if not oversized and not big_file:
        return None

    out_path = path
    if suffix == ".png":
        if path.stat().st_size > PNG_PHOTO_THRESHOLD:
            out_path = path.with_suffix(".jpg")
        else:
            out_path = path
    else:
        out_path = path.with_suffix(".jpg")

    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        if out_path.suffix.lower() == ".png":
            img.save(out_path, "PNG", optimize=True)
        else:
            img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)

    if out_path != path and path.exists():
        path.unlink()
    return f"{path.name} -> {out_path.name} ({out_path.stat().st_size // 1024}KB)"


def gif_to_mp4(path: Path) -> str | None:
    if path.suffix.lower() != ".gif":
        return None
    if not shutil.which("ffmpeg"):
        return "ffmpeg not found - skipped"

    with Image.open(path) as img:
        width, height = img.size
        animated = bool(getattr(img, "is_animated", False))
    if not animated:
        return optimize_still(path.with_suffix(".png")) or None

    if width > GIF_MAX_EDGE:
        target_w = GIF_MAX_EDGE
        target_h = max(2, round(height * GIF_MAX_EDGE / width / 2) * 2)
    else:
        target_w = width if width % 2 == 0 else width - 1
        target_h = height if height % 2 == 0 else height - 1

    out_path = path.with_suffix(".mp4")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(path),
        "-vf", f"scale={target_w}:{target_h}",
        "-c:v", "libx264", "-crf", "24", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return f"ffmpeg failed on {path.name}: {result.stderr.strip()[:200]}"
    path.unlink()
    return f"{path.name} -> {out_path.name} ({out_path.stat().st_size // 1024}KB)"


def video_poster(path: Path) -> str | None:
    """Extract a first-frame poster for every video so heroes have a fallback."""
    if path.suffix.lower() not in {".mp4", ".webm", ".mov"}:
        return None
    if not shutil.which("ffmpeg"):
        return None
    out = path.with_name(path.stem + "-poster.jpg")
    if out.exists():
        return None
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(path), "-frames:v", "1", "-q:v", "3", str(out),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"poster failed for {path.name}"
    return f"{path.name} -> {out.name} ({out.stat().st_size // 1024}KB)"


def main() -> int:
    touched = 0
    for path in image_paths():
        if path.name.startswith("."):
            continue
        try:
            if path.suffix.lower() == ".gif":
                message = gif_to_mp4(path)
            else:
                message = optimize_still(path) or video_poster(path)
        except Exception as exc:  # keep going on a single bad file
            message = f"ERROR {path.name}: {exc}"
        if message:
            print(message)
            touched += 1

    total = sum(p.stat().st_size for base in SCAN_DIRS if base.exists() for p in base.rglob("*") if p.is_file())
    print(f"{touched} file(s) touched, optimized assets now {total // (1024 * 1024)}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
