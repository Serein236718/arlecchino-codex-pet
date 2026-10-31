"""Build the arlecchino-chibi-v2 atlas from ONE existing frame.

The prototype (frames_clean320/frame_00.png) is treated as read-only source
material: nothing is redrawn, nothing is written back to it. Every one of the
88 atlas cells is a deterministic affine derivation of that single image
(non-uniform scale, rotation about the feet, horizontal mirror).

Usage:
    python tools/build_from_frame.py --src <frame_00.png> --out v2_from_frame
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 11
TARGET_H = 176.0
MAX_W = 182.0
BOTTOM_MARGIN = 12


# ---------------------------------------------------------------- source prep
def largest_component(mask: np.ndarray) -> np.ndarray:
    """Flood fill the biggest blob so floating decoration specks get dropped."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys[::37], xs[::37]):
        if seen[sy, sx] or not mask[sy, sx]:
            continue
        stack = [(int(sy), int(sx))]
        blob = []
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            blob.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(blob) > len(best):
            best = blob
    out = np.zeros_like(mask, dtype=bool)
    if best:
        by, bx = zip(*best)
        out[np.array(by), np.array(bx)] = True
    return out


def dilate(mask: np.ndarray, r: int = 2) -> np.ndarray:
    out = mask.copy()
    for _ in range(r):
        shifted = out.copy()
        shifted[1:, :] |= out[:-1, :]
        shifted[:-1, :] |= out[1:, :]
        shifted[:, 1:] |= out[:, :-1]
        shifted[:, :-1] |= out[:, 1:]
        out = shifted
    return out


def load_master(path: Path) -> Image.Image:
    """Crop the prototype to the character only, keeping its original pixels."""
    im = Image.open(path)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    a = np.array(im)
    alpha = a[..., 3]

    blob = largest_component(alpha > 40)
    if not blob.any():
        raise SystemExit("no opaque content in prototype")
    keep = dilate(blob, 2)

    cleaned = a.copy()
    cleaned[..., 3] = np.where(keep, alpha, 0)
    cleaned[cleaned[..., 3] == 0] = 0

    ys, xs = np.where(cleaned[..., 3] > 8)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    out = Image.fromarray(cleaned, "RGBA").crop(box)
    return out


# ------------------------------------------------------- alpha-safe transforms
def premultiply(im: Image.Image) -> Image.Image:
    a = np.array(im).astype(np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return Image.fromarray((a * 255.0).round().astype(np.uint8), "RGBA")


def unpremultiply(im: Image.Image) -> Image.Image:
    a = np.array(im).astype(np.float32) / 255.0
    al = a[..., 3:4]
    a[..., :3] /= np.maximum(al, 1e-4)
    a[..., :3] = np.clip(a[..., :3], 0.0, 1.0)
    out = (a * 255.0).round().astype(np.uint8)
    out[out[..., 3] == 0] = 0
    return Image.fromarray(out, "RGBA")


def resize_rgba(im: Image.Image, w: int, h: int) -> Image.Image:
    w, h = max(1, w), max(1, h)
    return unpremultiply(premultiply(im).resize((w, h), Image.LANCZOS))


def crop_content(im: Image.Image, th: int = 8) -> Image.Image:
    al = np.array(im)[..., 3]
    ys, xs = np.where(al > th)
    if len(ys) == 0:
        return im
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def rotate_feet(im: Image.Image, deg: float) -> Image.Image:
    """Rotate around the feet (bottom centre) so the character stays grounded."""
    if abs(deg) < 1e-6:
        return im
    pad = int(max(im.width, im.height) * 0.7) + 8
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    canvas.alpha_composite(im, (pad, pad))
    pivot = (pad + im.width / 2.0, pad + im.height)
    rot = premultiply(canvas).rotate(deg, resample=Image.BICUBIC, center=pivot)
    return crop_content(unpremultiply(rot))


# ---------------------------------------------------------------- cell layout
def make_cell(master: Image.Image, *, sx: float = 1.0, sy: float = 1.0,
              ang: float = 0.0, lift: float = 0.0, dx: float = 0.0,
              mirror: bool = False, target_h: float = TARGET_H) -> Image.Image:
    base = master.transpose(Image.FLIP_LEFT_RIGHT) if mirror else master
    s = min(target_h / base.height, MAX_W / base.width)
    fig = resize_rgba(base, round(base.width * s * sx), round(base.height * s * sy))
    fig = rotate_feet(fig, ang)
    fig = crop_content(fig)

    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    x = (CELL_W - fig.width) // 2 + int(round(dx))
    y = CELL_H - BOTTOM_MARGIN - fig.height - int(round(lift))
    x = max(0, min(x, CELL_W - fig.width)) if fig.width <= CELL_W else 0
    y = max(0, min(y, CELL_H - fig.height)) if fig.height <= CELL_H else 0
    cell.alpha_composite(fig, (x, y))
    return cell


# ---------------------------------------------------------------- motion specs
def spec_idle(n: int) -> list[dict]:
    sy = [1.000, 1.008, 1.015, 1.012, 1.005, 1.000, 1.004, 1.008]
    ang = [0.0, 0.5, 0.8, 0.4, -0.3, 0.0, -0.4, -0.1]
    dx = [0.0, 0.5, 0.8, 0.4, -0.5, 0.0, -0.4, -0.1]
    lift = [0, 1, 2, 2, 1, 0, 1, 1]
    return [dict(sy=sy[i], ang=ang[i], dx=dx[i], lift=lift[i]) for i in range(n)]


def spec_run_right(n: int) -> list[dict]:
    ang = [-7.0, -7.6, -8.2, -7.4, -7.0, -7.6, -8.2, -7.4]
    lift = [0, 6, 11, 5, 0, 6, 11, 5]
    sy = [0.982, 1.010, 1.022, 1.000, 0.982, 1.010, 1.022, 1.000]
    dx = [0.0, 1.0, 2.0, 1.0, 0.0, 1.0, 2.0, 1.0]
    return [dict(sy=sy[i], ang=ang[i], dx=dx[i], lift=lift[i]) for i in range(n)]


def spec_waving(n: int) -> list[dict]:
    ang = [-1.5, -5.5, -3.5, -1.0, -4.0, -1.5, -3.0, -1.0]
    lift = [0, 2, 3, 1, 2, 1, 2, 0]
    sy = [1.000, 1.010, 1.006, 1.000, 1.008, 1.002, 1.005, 1.000]
    dx = [0.0, -2.0, -1.0, 0.0, -1.5, -0.5, -1.0, 0.0]
    return [dict(sy=sy[i], ang=ang[i], dx=dx[i], lift=lift[i]) for i in range(n)]


def spec_jumping(n: int) -> list[dict]:
    # crouch -> launch -> rise -> peak -> land
    sy = [0.930, 1.048, 1.018, 1.000, 0.950, 0.965, 1.000, 1.000]
    lift = [0, 9, 28, 38, 5, 0, 2, 0]
    ang = [0.0, -1.2, -2.0, -1.0, 0.4, 0.8, 0.2, 0.0]
    # a smaller row-local scale keeps the jump from popping the pet size
    return [dict(sy=sy[i], ang=ang[i], lift=lift[i], target_h=148.0)
            for i in range(n)]


def spec_failed(n: int) -> list[dict]:
    sy = [0.992, 0.972, 0.956, 0.946, 0.950, 0.960, 0.972, 0.984]
    lift = [0, -1, -2, -3, -2.5, -2, -1, -0.5]
    ang = [0.6, 1.4, 2.2, 2.8, 2.3, 1.7, 1.1, 0.7]
    return [dict(sy=sy[i], ang=ang[i], lift=lift[i]) for i in range(n)]


def spec_waiting(n: int) -> list[dict]:
    ang = [-1.4, -0.7, 0.0, 0.7, 1.4, 0.7, 0.0, -0.7]
    lift = [0, -1, -2, -2, -1, 0, 0, -0.5]
    sy = [1.000, 0.998, 0.995, 0.995, 0.998, 1.000, 1.000, 0.999]
    return [dict(sy=sy[i], ang=ang[i], lift=lift[i]) for i in range(n)]


def spec_running(n: int) -> list[dict]:
    ang = [-1.6, -0.5, 0.6, 1.6, 0.5, -0.6, -1.4, 0.0]
    lift = [0, 3, 5, 3, 0, 2, 4, 1]
    dx = [0.0, 1.0, -1.0, 1.0, 0.0, -1.0, 0.5, 0.0]
    return [dict(ang=ang[i], lift=lift[i], dx=dx[i]) for i in range(n)]


def spec_review(n: int) -> list[dict]:
    ang = [0.0, -1.6, -2.6, -2.0, -1.0, 0.0, 0.8, 0.4]
    lift = [0, 2, 4, 5, 3, 0, 1, 0]
    sy = [1.000, 1.008, 1.014, 1.012, 1.006, 1.000, 1.002, 1.000]
    return [dict(sy=sy[i], ang=ang[i], lift=lift[i]) for i in range(n)]


def spec_orientation(start_deg: float, count: int) -> list[dict]:
    """Fake a yaw turn with width compression plus a sideways weight shift.

    A single front-view bitmap cannot show the back of the head, so the turn is
    expressed as foreshortening: the silhouette narrows toward profile, widens
    back at the opposite front, and slides toward the side being faced.
    """
    out = []
    for i in range(count):
        deg = math.radians((start_deg + i * 22.5) % 360.0)
        s_, c_ = math.sin(deg), math.cos(deg)
        f = abs(s_)
        out.append(dict(
            sx=1.0 - 0.34 * f,
            sy=1.0 + 0.05 * f,
            dx=9.0 * s_,
            # lean a little into the turn: compression alone reads as a squeeze
            ang=-5.5 * s_,
            mirror=c_ < 0,
            lift=0.0,
        ))
    return out


STATES = [
    # frame counts are fixed by the v2 contract; spare columns must stay empty
    ("idle", 0, spec_idle(6)),
    ("running-right", 1, spec_run_right(8)),
    ("running-left", 2, None),  # mirrored from row 1
    ("waving", 3, spec_waving(4)),
    ("jumping", 4, spec_jumping(5)),
    ("failed", 5, spec_failed(8)),
    ("waiting", 6, spec_waiting(6)),
    ("running", 7, spec_running(6)),
    ("review", 8, spec_review(6)),
    ("look-a", 9, spec_orientation(0.0, 8)),
    ("look-b", 10, spec_orientation(180.0, 8)),
]

# the v2 contract needs a dead-ahead neutral frame at row 0 / col 6
NEUTRAL = ("idle", 0, 0, 6)


# ---------------------------------------------------------------- finalisation
def finalize(sheet: Image.Image) -> Image.Image:
    a = np.array(sheet).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    # no visible pixel may lean green, or the chroma-key check flags it
    ceiling = np.maximum(rgb[..., 0], rgb[..., 2])
    rgb[..., 1] = np.minimum(rgb[..., 1], ceiling)
    rgb[alpha < 1.0] = 0.0
    return Image.fromarray(
        np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8), "RGBA")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.src)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    master = load_master(src)
    print(f"prototype {src.name} -> master {master.width}x{master.height} "
          f"(source untouched)")

    sheet = Image.new("RGBA", (CELL_W * COLS, CELL_H * ROWS), (0, 0, 0, 0))
    cells: dict[str, list[Image.Image]] = {}

    for name, row, frames in STATES:
        if frames is None:
            src_cells = cells["running-right"]
            cells[name] = [c.transpose(Image.FLIP_LEFT_RIGHT) for c in src_cells]
        else:
            cells[name] = [make_cell(master, **kw) for kw in frames]
        for i, cell in enumerate(cells[name]):
            if i < COLS:
                sheet.alpha_composite(cell, (i * CELL_W, row * CELL_H))
        print(f"{name:14s} row={row:2d} frames={len(cells[name])}")

    sname, sidx, srow, scol = NEUTRAL
    sheet.alpha_composite(cells[sname][sidx], (scol * CELL_W, srow * CELL_H))
    print(f"neutral cell -> row {srow} col {scol} from {sname}[{sidx}]")

    sheet = finalize(sheet)
    png, webp = out_dir / "spritesheet.png", out_dir / "spritesheet.webp"
    sheet.save(png)
    sheet.save(webp, lossless=True, quality=100, method=6, exact=True)
    print(f"saved {png} {sheet.size}")
    print(f"saved {webp} {webp.stat().st_size} bytes")

    half = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    bg = Image.new("RGB", half.size, (24, 24, 28))
    bg.paste(half, (0, 0), half)
    bg.save(out_dir / "atlas_preview.png")
    print(f"preview {out_dir / 'atlas_preview.png'}")


if __name__ == "__main__":
    main()
