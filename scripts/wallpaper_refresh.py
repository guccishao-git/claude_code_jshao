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
KEEP_LAST_WEEKS = 5
CATEGORIES = ["nature", "architecture", "abstract", "city"]
STAMP_FILE = Path.home() / ".wallpaper_last_run"
SCREEN_COUNT = 3


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


def fetch_distinct_image_urls(category: str, count: int) -> list[tuple[str, str]]:
    seen_urls = set()
    picks = []
    # Unsplash's random endpoint can repeat a photo across calls; retry until
    # we have `count` distinct ones so each monitor gets a different image.
    while len(picks) < count:
        image_url, author = fetch_random_image_url(category)
        if image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        picks.append((image_url, author))
    return picks


def download_image(image_url: str, dest: Path) -> None:
    req = urllib.request.Request(image_url, headers={"User-Agent": "WallpaperRefresh/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def set_wallpaper(path: Path, screen: str) -> None:
    # osascript + killall WallpaperAgent doesn't reliably refresh the visible
    # desktop when run from launchd on macOS 14+. The `wallpaper` CLI talks to
    # the modern WallpaperKit store and works in both contexts.
    subprocess.run(["/opt/homebrew/bin/wallpaper", "set", str(path), "--screen", screen], check=True)


def cleanup_old_wallpapers(directory: Path, keep_files: int) -> None:
    files = sorted(directory.glob("wallpaper_*.jpg"), key=lambda p: p.stat().st_mtime)
    for old in files[:-keep_files]:
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

    picks = fetch_distinct_image_urls(category, SCREEN_COUNT)

    # Include H%M%S so reruns within a day get a unique path — WallpaperKit
    # dedupes by path and won't refresh if the filename is unchanged.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    for screen_index, (image_url, author) in enumerate(picks):
        print(f"Photo by: {author}")
        dest = WALLPAPER_DIR / f"wallpaper_{stamp}_screen{screen_index}.jpg"

        print(f"Downloading to {dest} ...")
        download_image(image_url, dest)

        print(f"Setting wallpaper on screen {screen_index}...")
        set_wallpaper(dest, str(screen_index))

    cleanup_old_wallpapers(WALLPAPER_DIR, KEEP_LAST_WEEKS * SCREEN_COUNT)
    record_run()
    print("Done.")


if __name__ == "__main__":
    main()
