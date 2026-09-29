from __future__ import annotations

import math

from PIL import Image

Color = tuple[int, int, int]
Point = tuple[int, int]
Plot = tuple[int, int, float]


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[Point]:
    points: list[Point] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * err
        if doubled >= dy:
            err += dy
            x0 += sx
        if doubled <= dx:
            err += dx
            y0 += sy
    return points


def wu_line(x0: int, y0: int, x1: int, y1: int) -> list[Plot]:
    origin = (x0, y0, x1, y1)
    coverage: dict[Point, float] = {}
    steep = abs(y1 - y0) > abs(x1 - x0)
    if steep:
        x0, y0 = y0, x0
        x1, y1 = y1, x1
    if x0 > x1:
        x0, x1 = x1, x0
        y0, y1 = y1, y0

    def mark(ax: int, ay: int, amount: float) -> None:
        if amount <= 0.0:
            return
        px, py = (ay, ax) if steep else (ax, ay)
        key = (px, py)
        total = coverage.get(key, 0.0) + amount
        coverage[key] = 1.0 if total > 1.0 else total

    dx = x1 - x0
    dy = y1 - y0
    gradient = dy / dx if dx != 0 else 1.0

    def endpoint(px: float, py: float, from_start: bool) -> tuple[int, float]:
        xend = _round(px)
        yend = py + gradient * (xend - px)
        gap = _rfpart(px + 0.5) if from_start else _fpart(px + 0.5)
        iy = _ipart(yend)
        mark(xend, iy, _rfpart(yend) * gap)
        mark(xend, iy + 1, _fpart(yend) * gap)
        return xend, yend

    x_start, y_end = endpoint(float(x0), float(y0), True)
    intery = y_end + gradient
    x_stop, _ = endpoint(float(x1), float(y1), False)
    for x in range(x_start + 1, x_stop):
        iy = _ipart(intery)
        mark(x, iy, _rfpart(intery))
        mark(x, iy + 1, _fpart(intery))
        intery += gradient

    plots = [(px, py, value) for (px, py), value in coverage.items()]
    ox0, oy0, ox1, oy1 = origin
    reverse = (oy1 < oy0) if steep else (ox1 < ox0)
    plots.sort(key=(lambda item: (item[1], item[0])) if steep else (lambda item: (item[0], item[1])))
    if reverse:
        plots.reverse()
    return plots


def draw_bresenham(image: Image.Image, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    pixels = image.load()
    width, height = image.size
    for x, y in bresenham_line(x0, y0, x1, y1):
        if 0 <= x < width and 0 <= y < height:
            pixels[x, y] = color


def draw_wu(image: Image.Image, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    pixels = image.load()
    width, height = image.size
    for x, y, coverage in wu_line(x0, y0, x1, y1):
        if not (0 <= x < width and 0 <= y < height):
            continue
        pixels[x, y] = _mix(pixels[x, y], color, coverage)


def _ipart(value: float) -> int:
    return math.floor(value)


def _round(value: float) -> int:
    return math.floor(value + 0.5)


def _fpart(value: float) -> float:
    return value - math.floor(value)


def _rfpart(value: float) -> float:
    return 1.0 - _fpart(value)


def _mix(base: Color, color: Color, coverage: float) -> Color:
    keep = 1.0 - coverage
    mixed = (
        int(color[0] * coverage + base[0] * keep + 0.5),
        int(color[1] * coverage + base[1] * keep + 0.5),
        int(color[2] * coverage + base[2] * keep + 0.5),
    )
    return tuple(min(255, max(0, channel)) for channel in mixed)
