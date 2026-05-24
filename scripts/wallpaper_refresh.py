#!/usr/bin/env python3
"""Weekly wallpaper refresh using Unsplash API."""

import json
import os
import random
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
WALLPAPER_DIR = Path.home() / "Pictures" / "Wallpapers"
KEEP_LAST_N = 5
CATEGORIES = ["nature", "architecture", "abstract", "city"]
STAMP_FILE = Path.home() / ".wallpaper_last_run"


def already_ran_this_week() -> bool:
    if not STAMP_FILE.exists():
        return False
    last = datetime.fromisoformat(STAMP_FILE.read_text().strip())
    return last.isocalendar()[:2] == datetime.now().isocalendar()[:2]


def record_run() -> None:
    STAMP_FILE.write_text(datetime.now().isoformat())


def fetch_random_image_url(category: str) -> tuple[str, str]:
    url = (
        f"https://api.unsplash.com/photos/random"
        f"?query={category}&orientation=landscape&content_filter=high"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    image_url = data["urls"]["full"]
    author = data["user"]["name"]
    return image_url, author


def download_image(image_url: str, dest: Path) -> None:
    req = urllib.request.Request(image_url, headers={"User-Agent": "WallpaperRefresh/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def set_wallpaper(path: Path) -> None:
    # osascript + killall WallpaperAgent doesn't reliably refresh the visible
    # desktop when run from launchd on macOS 14+. The `wallpaper` CLI talks to
    # the modern WallpaperKit store and works in both contexts.
    subprocess.run(["/opt/homebrew/bin/wallpaper", "set", str(path)], check=True)


def cleanup_old_wallpapers(directory: Path, keep: int) -> None:
    files = sorted(directory.glob("wallpaper_*.jpg"), key=lambda p: p.stat().st_mtime)
    for old in files[:-keep]:
        old.unlink()
        print(f"Removed old wallpaper: {old.name}")


def main() -> None:
    if already_ran_this_week():
        print("Already ran this week, skipping.")
        return

    if not UNSPLASH_ACCESS_KEY:
        raise RuntimeError("UNSPLASH_ACCESS_KEY not set. Add it to ~/.zshrc and reload.")

    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)

    category = random.choice(CATEGORIES)
    print(f"Category: {category}")

    image_url, author = fetch_random_image_url(category)
    print(f"Photo by: {author}")

    # Include H%M%S so reruns within a day get a unique path — WallpaperKit
    # dedupes by path and won't refresh if the filename is unchanged.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = WALLPAPER_DIR / f"wallpaper_{stamp}.jpg"

    print(f"Downloading to {dest} ...")
    download_image(image_url, dest)

    print("Setting wallpaper...")
    set_wallpaper(dest)

    cleanup_old_wallpapers(WALLPAPER_DIR, KEEP_LAST_N)
    record_run()
    print("Done.")


if __name__ == "__main__":
    main()
