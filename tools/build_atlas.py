"""Deterministic atlas builder for the arlecchino-chibi pet.

Takes generated 4-pose panels (or single-pose images), chroma-keys them,
normalizes every figure to one shared scale + baseline, and composes the
8x11 / 192x208 v2 atlas.

Usage:
    python tools/build_atlas.py --spec tools/atlas_spec.json --out build/
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 11
KEY = np.array([0, 255, 0], dtype=np.float32)
TARGET_H = 176.0  # figure height inside the 208px cell
MAX_W = 182.0
BOTTOM_MARGIN = 12


# ---------------------------------------------------------------- chroma key
def key_to_rgba(im: Image.Image, low: float = 34.0, high: float = 92.0,
                despill: bool = True) -> Image.Image:
    """Key on green dominance, not exact key distance.

    The generator never returns a perfectly flat #00FF00: sampled background
    pixels land around (0-45, 180-240, 0-45). Green dominance (g - max(r,b))
    separates it cleanly from the pet's white / black / crimson palette.
    """
    a = np.array(im.convert("RGB")).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dominance = g - np.maximum(r, b)

    alpha = 1.0 - np.clip((dominance - low) / (high - low), 0.0, 1.0)
    rgb = a.copy()

    if despill:
        ceiling = np.maximum(r, b)
        fringe = (dominance > 0) & (g > ceiling)
        softened = ceiling + np.clip(g - ceiling, 0, None) * 0.15
        rgb[..., 1] = np.where(fringe & (alpha < 1.0), softened, g)

    a255 = alpha * 255.0
    # fully transparent pixels must not keep chroma-key RGB residue
    rgb[a255 < 1.0] = 0.0
    out = np.dstack([np.clip(rgb, 0, 255), a255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# ---------------------------------------------------------------- extraction
def content_mask(rgba: Image.Image) -> np.ndarray:
    return np.array(rgba)[..., 3] > 24


def cluster_groups(mask: np.ndarray, expected: int) -> list[tuple[int, int]]:
    """Split a panel into `expected` figure ranges.

    Figures are often only 2-10 px apart, so blank-gap detection is not reliable.
    Instead cut at the thinnest column near each expected boundary.
    """
    counts = mask.sum(axis=0).astype(np.float64)
    if not counts.any():
        raise SystemExit("panel has no visible content")
    w = mask.shape[1]
    step = w / float(expected)
    cuts = [0]
    for i in range(1, expected):
        center = int(round(i * step))
        half = int(step * 0.35)
        lo = max(cuts[-1] + 8, center - half)
        hi = min(w - 1, center + half)
        if hi <= lo:
            cuts.append(center)
            continue
        window = counts[lo:hi]
        cuts.append(lo + int(np.argmin(window)))
    cuts.append(w)

    groups = []
    for i in range(expected):
        x0, x1 = cuts[i], cuts[i + 1] - 1
        if x1 <= x0:
            raise SystemExit(f"degenerate split at figure {i + 1}")
        groups.append((x0, x1))
    return groups


def figures_from_panel(path: Path, expected: int, erase_corner: bool = True
                       ) -> list[dict]:
    """Return one dict per figure: cropped RGBA plus its offset above baseline."""
    im = Image.open(path).convert("RGB")
    if erase_corner:
        a = np.array(im)
        h, w, _ = a.shape
        # generator watermark lives in the extreme bottom-right corner
        a[int(h * 0.90):, int(w * 0.60):] = KEY.astype(np.uint8)
        im = Image.fromarray(a, "RGB")
    rgba = key_to_rgba(im)
    mask = content_mask(rgba)

    boxes = []
    for x0, x1 in cluster_groups(mask, expected):
        sub = mask[:, x0:x1 + 1]
        ys = np.where(sub.any(axis=1))[0]
        boxes.append((x0, x1, int(ys.min()), int(ys.max())))
    baseline = max(b[3] for b in boxes)

    out = []
    for x0, x1, y0, y1 in boxes:
        pad = 2
        crop = rgba.crop((max(0, x0 - pad), max(0, y0 - pad),
                          min(rgba.width, x1 + pad + 1),
                          min(rgba.height, y1 + pad + 1)))
        out.append({"img": crop, "lift": baseline - (y1 + pad)})
    return out


def normalize(fig: Image.Image, scale: float) -> Image.Image:
    w = max(1, int(round(fig.width * scale)))
    h = max(1, int(round(fig.height * scale)))
    return fig.resize((w, h), Image.LANCZOS)


def place(fig: Image.Image, lift: float) -> Image.Image:
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    x = (CELL_W - fig.width) // 2
    room = CELL_H - BOTTOM_MARGIN - fig.height
    # never let vertical motion push the sprite past the cell top
    y = CELL_H - BOTTOM_MARGIN - fig.height - int(round(min(lift, room)))
    cell.alpha_composite(fig, (max(0, x), max(0, y)))
    return cell


def scale_for(fig: Image.Image, target_h: float = TARGET_H) -> float:
    return min(target_h / fig.height, MAX_W / fig.width)


def finalize(sheet: Image.Image) -> Image.Image:
    """Zero RGB under transparency and hard-despill any surviving green fringe."""
    a = np.array(sheet).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    ceiling = np.maximum(r, b)
    greenish = (g > ceiling + 18) & (g > 90)
    rgb[..., 1] = np.where(greenish, ceiling, g)
    rgb[alpha < 1.0] = 0.0
    return Image.fromarray(
        np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- main build
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # state -> list of cell images
    cells: dict[str, list[Image.Image]] = {}
    for state in spec["states"]:
        if state.get("mirror_of"):
            src = state["mirror_of"]
            base_cells = cells[src][: state["frames"]]
            cells[state["state"]] = [
                c.transpose(Image.FLIP_LEFT_RIGHT) for c in base_cells
            ]
            print(f"{state['state']:14s} mirrored from {src} frames={len(base_cells)}")
            continue

        figs: list[dict] = []
        for panel in state["panels"]:
            figs.extend(figures_from_panel(Path(panel["path"]), panel["figures"],
                                           panel.get("erase_corner", True)))
        need = state["frames"]
        if len(figs) < need:
            raise SystemExit(f"{state['state']}: got {len(figs)} figures, need {need}")
        figs = figs[:need]
        target_h = float(state.get("target_h", TARGET_H))
        keep_lift = bool(state.get("preserve_lift", False))
        # panels differ in source resolution, so normalise per figure by height
        cells[state["state"]] = [
            place(normalize(f["img"], scale_for(f["img"], target_h)),
                  (f["lift"] if keep_lift else 0) * scale_for(f["img"], target_h))
            for f in figs
        ]
        print(f"{state['state']:14s} frames={len(figs)}")

    sheet = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    for state in spec["states"]:
        row = state["row"]
        for i, cell in enumerate(cells[state["state"]]):
            if i >= COLS:
                break
            sheet.alpha_composite(cell, (i * CELL_W, row * CELL_H))

    neutral = spec.get("neutral_cell")
    if neutral:
        src_cells = cells[neutral["state"]]
        sheet.alpha_composite(
            src_cells[int(neutral.get("index", 0))],
            (int(neutral["col"]) * CELL_W, int(neutral["row"]) * CELL_H))
        print(f"neutral cell -> row {neutral['row']} col {neutral['col']} from {neutral['state']}")

    sheet = finalize(sheet)

    png = out_dir / "spritesheet.png"
    webp = out_dir / "spritesheet.webp"
    sheet.save(png)
    sheet.save(webp, lossless=True, quality=100, method=6, exact=True)
    print(f"saved {png} {sheet.size}")
    print(f"saved {webp} {webp.stat().st_size} bytes")

    preview = out_dir / "cells_preview.png"
    scale = 2
    sheet.resize((sheet.width * scale // 2, sheet.height * scale // 2)).save(preview)
    print(f"preview {preview}")


if __name__ == "__main__":
    main()
