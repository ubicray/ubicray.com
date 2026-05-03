#!/usr/bin/env python3
"""Regenerate Locket app icons from the source ubicray.com/icon.png.

The source icon is an iOS-style rendered tile (rounded corners + drop shadow)
sitting inside an off-white canvas. Google Play and Android adaptive launchers
require a full-bleed square asset with NO baked rounded corners and NO shadow.

This script produces:
  - 1024x1024 master, full-bleed teal background, no rounded corners       (icon.png)
  - 512x512  Play Store store-listing icon                                  (locket-play-store-icon.png)
  - 1024x1024 adaptive-icon foreground: transparent background, artwork
    constrained to inner safe zone                                          (adaptive-icon.png)

Inputs/outputs are absolute paths so this can be run from anywhere.
"""

from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path('/home/elmar/workspaces')
SRC = ROOT / 'ubicray.com' / 'icon.png'

# Sampled from the source teal area (top-left of the iOS tile body)
TEAL = (78, 139, 141)


def load_source():
    return Image.open(SRC).convert('RGB')


def to_hsv(arr_rgb_01):
    """Vectorised RGB->HSV. arr_rgb_01: HxWx3 in [0,1]. Returns h(deg), s, v."""
    r = arr_rgb_01[:, :, 0]
    g = arr_rgb_01[:, :, 1]
    b = arr_rgb_01[:, :, 2]
    mx = arr_rgb_01.max(axis=2)
    mn = arr_rgb_01.min(axis=2)
    diff = mx - mn
    safe = np.where(diff > 0, diff, 1)
    hr = ((g - b) / safe) % 6
    hg = ((b - r) / safe) + 2
    hb = ((r - g) / safe) + 4
    h = np.where(mx == r, hr, np.where(mx == g, hg, hb)) * 60.0
    h = np.where(diff > 0, h, 0.0)
    s = np.where(mx > 0, diff / np.where(mx > 0, mx, 1), 0.0)
    v = mx
    return h, s, v


def extract_artwork_mask(arr_rgb_255):
    """Mask of the gold speech-bubble + its dark warm outlines.

    Cool-hued (teal/grey) pixels — tile body, drop shadow, off-white bg — are False.
    """
    arr = arr_rgb_255.astype(np.float32) / 255.0
    h, s, v = to_hsv(arr)
    # Warm hues only: yellow/orange/brown band 15..75 deg, with enough saturation
    # to exclude grey-ish drop-shadow pixels (which are near-zero saturation).
    warm = (h >= 15) & (h <= 75) & (s > 0.18)
    return warm


def render_full_bleed(target_size: int) -> Image.Image:
    """Solid-teal canvas with the speech-bubble artwork composited on top."""
    src = load_source()
    arr = np.array(src)
    H, W = arr.shape[:2]

    mask = extract_artwork_mask(arr)
    # Find bounding box of artwork so we can centre + scale it
    ys, xs = np.where(mask)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    aw, ah = x1 - x0 + 1, y1 - y0 + 1

    # Crop artwork with a small alpha mask cutout (so anti-alias edges blend cleanly)
    art_rgb = arr[y0:y1+1, x0:x1+1, :3]
    art_alpha = mask[y0:y1+1, x0:x1+1].astype(np.uint8) * 255
    artwork = Image.fromarray(np.dstack([art_rgb, art_alpha]), mode='RGBA')

    # Match the proportions the artwork has on the source iOS tile (~62% of tile width).
    # Use that ratio against the full target canvas so the speech bubble fills the
    # adaptive-icon safe zone (~66%) without cropping.
    scale = 0.66 * target_size / max(aw, ah)
    new_w = int(round(aw * scale))
    new_h = int(round(ah * scale))
    artwork_resized = artwork.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new('RGBA', (target_size, target_size), TEAL + (255,))
    px = (target_size - new_w) // 2
    py = (target_size - new_h) // 2
    canvas.paste(artwork_resized, (px, py), artwork_resized)
    return canvas.convert('RGB')


def render_adaptive_foreground(target_size: int) -> Image.Image:
    """Transparent canvas with artwork centred inside the inner safe zone."""
    src = load_source()
    arr = np.array(src)
    mask = extract_artwork_mask(arr)
    ys, xs = np.where(mask)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    aw, ah = x1 - x0 + 1, y1 - y0 + 1
    art_rgb = arr[y0:y1+1, x0:x1+1, :3]
    art_alpha = mask[y0:y1+1, x0:x1+1].astype(np.uint8) * 255
    artwork = Image.fromarray(np.dstack([art_rgb, art_alpha]), mode='RGBA')
    # Adaptive icons: visible mask is the inner 72/108 ≈ 66.7% of canvas.
    # Keep artwork inside ~60% so any mask shape (circle, squircle, teardrop) preserves it.
    scale = 0.60 * target_size / max(aw, ah)
    new_w = int(round(aw * scale))
    new_h = int(round(ah * scale))
    artwork_resized = artwork.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    px = (target_size - new_w) // 2
    py = (target_size - new_h) // 2
    canvas.paste(artwork_resized, (px, py), artwork_resized)
    return canvas


def main():
    icon_1024 = render_full_bleed(1024)
    icon_512 = render_full_bleed(512)
    adaptive = render_adaptive_foreground(1024)
    favicon = icon_1024.resize((48, 48), Image.LANCZOS)

    targets = [
        (icon_1024, ROOT / 'ubicray.com' / 'icon.png'),
        (icon_1024, ROOT / 'ubicray.com' / 'locket' / 'icon.png'),
        (icon_512,  ROOT / 'ubicray.com' / 'locket-play-store-icon.png'),
        (icon_1024, ROOT / 'android' / 'locket_rn' / 'assets' / 'icon.png'),
        (adaptive,  ROOT / 'android' / 'locket_rn' / 'assets' / 'adaptive-icon.png'),
        (favicon,   ROOT / 'android' / 'locket_rn' / 'assets' / 'favicon.png'),
    ]
    for img, path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)
        print(f'wrote {path} ({img.size[0]}x{img.size[1]} {img.mode})')


if __name__ == '__main__':
    main()
