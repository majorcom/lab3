from __future__ import annotations

import math

from PIL import Image

Color = tuple[int, int, int]
Point = tuple[int, int]
_Rgb = tuple[float, float, float]
_Vert = tuple[float, float, _Rgb]


def draw_gradient_triangle(
    image: Image.Image,
    p0: Point,
    c0: Color,
    p1: Point,
    c1: Color,
    p2: Point,
    c2: Color,
) -> int:
    if image.mode != "RGB":
        raise ValueError("ожидается RGB-изображение")

    verts: list[_Vert] = [
        (float(p0[0]), float(p0[1]), (float(c0[0]), float(c0[1]), float(c0[2]))),
        (float(p1[0]), float(p1[1]), (float(c1[0]), float(c1[1]), float(c1[2]))),
        (float(p2[0]), float(p2[1]), (float(c2[0]), float(c2[1]), float(c2[2]))),
    ]
    verts.sort(key=lambda vert: (vert[1], vert[0]))
    (x0, y0, col0), (x1, y1, col1), (x2, y2, col2) = verts

    pixels = image.load()
    width, height = image.size
    painted = 0

    def paint_span(y: int, ax: float, ac: _Rgb, bx: float, bc: _Rgb) -> None:
        nonlocal painted
        if y < 0 or y >= height:
            return
        if ax > bx:
            ax, bx = bx, ax
            ac, bc = bc, ac
        left = math.floor(ax + 0.5)
        right = math.floor(bx + 0.5)
        span = right - left
        x_from = left if left > 0 else 0
        x_to = right if right < width else width - 1
        for x in range(x_from, x_to + 1):
            t = 0.0 if span == 0 else (x - left) / span
            pixels[x, y] = _pack(_lerp(ac, bc, t))
            painted += 1

    if y0 == y2:
        paint_span(int(y0), x0, col0, x1, col1)
        if x1 != x2:
            paint_span(int(y0), x1, col1, x2, col2)
        return painted

    total = y2 - y0
    for i in range(int(total) + 1):
        second = i > (y1 - y0) or y1 == y0
        segment = (y2 - y1) if second else (y1 - y0)
        alpha = i / total
        beta = (i - (y1 - y0)) / segment if second else i / segment
        ax = x0 + (x2 - x0) * alpha
        ac = _lerp(col0, col2, alpha)
        if second:
            bx = x1 + (x2 - x1) * beta
            bc = _lerp(col1, col2, beta)
        else:
            bx = x0 + (x1 - x0) * beta
            bc = _lerp(col0, col1, beta)
        paint_span(int(y0) + i, ax, ac, bx, bc)
    return painted


def _lerp(a: _Rgb, b: _Rgb, t: float) -> _Rgb:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _pack(color: _Rgb) -> Color:
    return (
        min(255, max(0, math.floor(color[0] + 0.5))),
        min(255, max(0, math.floor(color[1] + 0.5))),
        min(255, max(0, math.floor(color[2] + 0.5))),
    )
