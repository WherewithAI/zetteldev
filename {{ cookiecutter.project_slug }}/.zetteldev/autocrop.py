"""Autocrop whitespace from rendered images (e.g. great_tables output).

Supports raster formats (PNG/JPEG) via PIL and vector SVG via a
rasterize-then-map-back-to-viewBox trick (cairosvg renders the SVG at a
known DPI, we find the content bbox in pixel space, and translate that
back to user units in the SVG's viewBox).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
from PIL import Image


_LENGTH_RE = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*$")


def autocrop(path: Path, padding: int = 20, bg_threshold: int = 250) -> None:
    """Crop whitespace from an image or SVG in-place.

    Args:
        path: Path to the image file (overwritten).
        padding: Pixels of padding to keep around content.
        bg_threshold: RGB values above this are considered background.
    """
    if path.suffix.lower() == ".svg":
        _autocrop_svg(path, padding=padding, bg_threshold=bg_threshold)
    else:
        _autocrop_raster(path, padding=padding, bg_threshold=bg_threshold)


def _autocrop_raster(path: Path, *, padding: int, bg_threshold: int) -> None:
    img = Image.open(path)
    arr = np.array(img.convert("RGB"))

    bbox = _content_bbox(arr, bg_threshold=bg_threshold)
    if bbox is None:
        return

    top, bottom, left, right = _padded_bbox(bbox, arr.shape[:2], padding=padding)
    img.crop((left, top, right, bottom)).save(path)


def _autocrop_svg(path: Path, *, padding: int, bg_threshold: int) -> None:
    """Tighten an SVG's viewBox to its content bounding box.

    Rasterizes the SVG with cairosvg at a chosen pixel width, finds the
    non-white bounding box with PIL+numpy, and rewrites the SVG's
    viewBox plus width/height so that the content fills the frame.
    Re-renders losslessly — the underlying vector paths are untouched,
    only the top-level attributes move.
    """
    try:
        import cairosvg  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "SVG autocrop requires `cairosvg`. Install with: uv add cairosvg"
        ) from exc

    svg_text = path.read_text()

    view_box = _parse_view_box(svg_text)
    width_attr = _parse_length_attr(svg_text, "width")
    height_attr = _parse_length_attr(svg_text, "height")
    if view_box is None and (width_attr is None or height_attr is None):
        raise ValueError(
            f"SVG at {path} has no viewBox and incomplete width/height — cannot crop."
        )
    if view_box is None:
        assert width_attr is not None and height_attr is not None
        view_box = (0.0, 0.0, width_attr[0], height_attr[0])

    vx, vy, vw, vh = view_box

    # Rasterize at a reasonable width so the bbox detection is precise.
    render_px_w = 1600
    png_bytes = cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"), output_width=render_px_w
    )
    img = Image.open(io.BytesIO(png_bytes))
    # Composite onto white so transparent pixels (which dominate
    # SVG renders) don't read as black "content" in the bbox pass.
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    arr = np.array(img.convert("RGB"))
    raster_h, raster_w = arr.shape[:2]

    bbox = _content_bbox(arr, bg_threshold=bg_threshold)
    if bbox is None:
        return

    # Convert padding (specified in raster pixels) into viewBox units,
    # then apply around the raster bbox.
    px_per_user_x = raster_w / vw
    px_per_user_y = raster_h / vh
    px_padding_x = padding
    px_padding_y = padding
    top = max(0, bbox[0] - px_padding_y)
    bottom = min(raster_h, bbox[1] + px_padding_y)
    left = max(0, bbox[2] - px_padding_x)
    right = min(raster_w, bbox[3] + px_padding_x)

    new_vx = vx + left / px_per_user_x
    new_vy = vy + top / px_per_user_y
    new_vw = (right - left) / px_per_user_x
    new_vh = (bottom - top) / px_per_user_y

    svg_text = _set_view_box(svg_text, (new_vx, new_vy, new_vw, new_vh))

    # If explicit width/height were set, scale them proportionally so
    # the rendered size matches the new aspect ratio.
    if width_attr is not None:
        old_val, unit = width_attr
        svg_text = _set_length_attr(svg_text, "width", old_val * (new_vw / vw), unit)
    if height_attr is not None:
        old_val, unit = height_attr
        svg_text = _set_length_attr(svg_text, "height", old_val * (new_vh / vh), unit)

    path.write_text(svg_text)


def _content_bbox(
    arr: np.ndarray, *, bg_threshold: int
) -> tuple[int, int, int, int] | None:
    """Return (top, bottom, left, right) pixel indices of non-background content."""
    not_bg = (arr < bg_threshold).any(axis=2)
    rows = not_bg.any(axis=1)
    cols = not_bg.any(axis=0)
    if not rows.any():
        return None
    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))
    return top, bottom, left, right


def _padded_bbox(
    bbox: tuple[int, int, int, int], shape_hw: tuple[int, int], *, padding: int
) -> tuple[int, int, int, int]:
    top, bottom, left, right = bbox
    h, w = shape_hw
    return (
        max(0, top - padding),
        min(h, bottom + padding),
        max(0, left - padding),
        min(w, right + padding),
    )


def _parse_view_box(svg_text: str) -> tuple[float, float, float, float] | None:
    m = re.search(r'viewBox\s*=\s*"([^"]+)"', svg_text)
    if not m:
        return None
    parts = m.group(1).replace(",", " ").split()
    if len(parts) != 4:
        return None
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _set_view_box(svg_text: str, vb: tuple[float, float, float, float]) -> str:
    new = f'viewBox="{vb[0]:g} {vb[1]:g} {vb[2]:g} {vb[3]:g}"'
    if re.search(r'viewBox\s*=\s*"[^"]+"', svg_text):
        return re.sub(r'viewBox\s*=\s*"[^"]+"', new, svg_text, count=1)
    # No viewBox — insert it on the <svg> root tag.
    return re.sub(r"<svg\b", f"<svg {new}", svg_text, count=1)


def _parse_length_attr(svg_text: str, name: str) -> tuple[float, str] | None:
    m = re.search(rf'<svg\b[^>]*\b{name}\s*=\s*"([^"]+)"', svg_text)
    if not m:
        return None
    v = _LENGTH_RE.match(m.group(1))
    if not v:
        return None
    return float(v.group(1)), v.group(2) or ""


def _set_length_attr(svg_text: str, name: str, value: float, unit: str) -> str:
    replacement = f'{name}="{value:g}{unit}"'
    pattern = rf'(<svg\b[^>]*\b){name}\s*=\s*"[^"]+"'
    return re.sub(pattern, rf"\1{replacement}", svg_text, count=1)
