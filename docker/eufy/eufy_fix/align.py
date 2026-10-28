"""Line a backed-up map up with the robot's current one.

After a remap the robot starts a new coordinate frame from wherever it left
the dock, so the same house comes out turned by a few degrees and shifted.
``align`` finds that turn and shift by maximising the overlap of floor cells
(coarse search on 20 cm cells, then refined on full cells), and the resulting
``Alignment`` carries points (zones, walls, zone-clean areas) and room labels
from one map to the other.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageChops

from .mapdata import CELL_CARPET, CELL_FREE, Grid, Snapshot, _count, _iou, _mask

_FLOOR = (CELL_FREE, CELL_CARPET)
_COARSE = 4  # coarse search on 4x4-cell blocks


@dataclass
class Alignment:
    """other = R(angle) * (ref - pivot) + pivot + shift, in world cm."""

    angle_deg: float  # counter-clockwise, as seen in map.png
    pivot: tuple[float, float]
    shift: tuple[float, float]
    overlap: float  # floor intersection-over-union once aligned
    overlap_before: float  # ... and as the two maps stand

    def to_other(self, x: float, y: float) -> tuple[float, float]:
        a = math.radians(self.angle_deg)
        dx, dy = x - self.pivot[0], y - self.pivot[1]
        return (self.pivot[0] + self.shift[0] + dx * math.cos(a) - dy * math.sin(a),
                self.pivot[1] + self.shift[1] + dx * math.sin(a) + dy * math.cos(a))

    def to_ref(self, x: float, y: float) -> tuple[float, float]:
        a = -math.radians(self.angle_deg)
        dx, dy = x - self.pivot[0] - self.shift[0], y - self.pivot[1] - self.shift[1]
        return (self.pivot[0] + dx * math.cos(a) - dy * math.sin(a),
                self.pivot[1] + dx * math.sin(a) + dy * math.cos(a))

    def describe(self) -> str:
        return (f"turned {self.angle_deg:+.2f}°, shifted ({self.shift[0]:+.0f}, "
                f"{self.shift[1]:+.0f}) cm; floor overlap {self.overlap:.0%} "
                f"(unaligned {self.overlap_before:.0%})")


def _threshold(img: Image.Image) -> Image.Image:
    # A block counts as floor when at least a quarter of its cells are.
    return img.point([0] * 64 + [255] * 192).convert("1", dither=Image.Dither.NONE)


def _centroid(img: Image.Image) -> tuple[float, float]:
    w = img.width
    sx = sy = n = 0
    for i, v in enumerate(img.convert("L").tobytes()):
        if v:
            sx += i % w
            sy += i // w
            n += 1
    return (sx / n + 0.5, sy / n + 0.5) if n else (w / 2, img.height / 2)


def _search(ref: Image.Image, other: Image.Image, pivot: tuple[float, float],
            angles: list[float], shifts: list[tuple[int, int]]) -> tuple[float, float, int, int]:
    best = (-1.0, 0.0, 0, 0)
    for angle in angles:
        turned = ref.rotate(angle, resample=Image.Resampling.NEAREST, center=pivot)
        for dx, dy in shifts:
            iou = _iou(ImageChops.offset(turned, dx, dy), other)
            if iou > best[0]:
                best = (iou, angle, dx, dy)
    return best


def align(ref: Snapshot, other: Snapshot, max_angle: float = 15.0,
          max_shift_cm: float = 300.0) -> Alignment:
    ga, gb = ref.grid(), other.grid()
    if ga.resolution != gb.resolution:
        raise ValueError(f"resolutions differ: {ga.resolution} vs {gb.resolution} cm")
    res = ga.resolution
    xs = [round(g.origin_x / res) for g in (ga, gb)]
    ys = [round(g.origin_y / res) for g in (ga, gb)]
    margin = int(max_shift_cm / res) + max(ga.width, ga.height, gb.width, gb.height) // 4
    left, top = min(xs) - margin, min(ys) - margin
    right = max(xs[0] + ga.width, xs[1] + gb.width) + margin
    bottom = max(ys[0] + ga.height, ys[1] + gb.height) + margin
    # A multiple of the coarse block, so coarse shifts scale back exactly.
    w = (right - left + _COARSE - 1) // _COARSE * _COARSE
    h = (bottom - top + _COARSE - 1) // _COARSE * _COARSE
    fa = _mask(ga, _FLOOR, left, top, (w, h), res)
    fb = _mask(gb, _FLOOR, left, top, (w, h), res)
    if not _count(fa) or not _count(fb):
        raise ValueError("a map has no floor cells")
    before = _iou(fa, fb)

    # Coarse: whole degrees, shifts of one block around the centroid offset.
    ca, cb = _centroid(fa), _centroid(fb)
    sa, sb = (_threshold(f.convert("L").reduce(_COARSE)) for f in (fa, fb))
    pivot_small = (ca[0] / _COARSE, ca[1] / _COARSE)
    guess = (round((cb[0] - ca[0]) / _COARSE), round((cb[1] - ca[1]) / _COARSE))
    reach = int(max_shift_cm / (res * _COARSE))
    shifts = [(guess[0] + dx, guess[1] + dy)
              for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)]
    angles = sorted(range(-int(max_angle), int(max_angle) + 1), key=abs)
    _, angle, dx, dy = _search(sa, sb, pivot_small, [float(a) for a in angles], shifts)

    # Fine: quarter degrees and single cells around the coarse best.
    angles_fine = [angle + k * 0.25 for k in sorted(range(-4, 5), key=abs)]
    shifts = [(dx * _COARSE + i, dy * _COARSE + j)
              for i in range(-_COARSE - 1, _COARSE + 2) for j in range(-_COARSE - 1, _COARSE + 2)]
    overlap, angle, dx, dy = _search(fa, fb, ca, angles_fine, shifts)

    # Image -> world: x = (u + left) * res, y = (h + top - v) * res. Image y
    # points down, so PIL's counter-clockwise turn is counter-clockwise in the
    # world too, and an image shift of +dy is -dy in world y.
    pivot = ((ca[0] + left) * res, (h + top - ca[1]) * res)
    return Alignment(angle, pivot, (dx * res, -dy * res), overlap, before)


def ref_rooms_on(other: Grid, ref: Grid, al: Alignment) -> list[int]:
    """For every cell of *other*, the *ref* room id found there (0 = none / not floor)."""
    out = [0] * (other.width * other.height)
    if ref.rooms is None:
        return out
    res = other.resolution
    a = -math.radians(al.angle_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    px, py = al.pivot
    sx, sy = al.shift
    for i, cell in enumerate(other.cells):
        if cell not in _FLOOR:
            continue
        x = other.origin_x + (i % other.width + 0.5) * res - px - sx
        y = other.origin_y + (i // other.width + 0.5) * res - py - sy
        rx = int((px + x * cos_a - y * sin_a - ref.origin_x) // ref.resolution)
        ry = int((py + x * sin_a + y * cos_a - ref.origin_y) // ref.resolution)
        if 0 <= rx < ref.width and 0 <= ry < ref.height:
            j = ry * ref.width + rx
            if ref.cells[j] in _FLOOR:
                out[i] = ref.room_at(j)
    return out
