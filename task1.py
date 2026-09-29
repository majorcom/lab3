from __future__ import annotations

import sys
from collections.abc import Callable
from typing import NamedTuple

from PIL import Image, ImageDraw

Color = tuple[int, int, int]
Point = tuple[int, int]
PaintFn = Callable[[int, int], Color]

_DIRS: tuple[Point, ...] = (
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (1, -1),
)
_DIR_INDEX = {step: index for index, step in enumerate(_DIRS)}


def solid_paint(color: Color) -> PaintFn:
    def paint(_x: int, _y: int) -> Color:
        return color

    return paint


class _PatternPaint:
    def __init__(self, pattern: Image.Image, repeat: bool) -> None:
        self.image = pattern.convert("RGB")
        self.pixels = self.image.load()
        self.repeat = repeat
        self.width, self.height = self.image.size
        if self.width <= 0 or self.height <= 0:
            raise ValueError("пустой рисунок")

    def __call__(self, x: int, y: int) -> Color:
        if self.repeat:
            return self.pixels[x % self.width, y % self.height]
        sx = x if x < self.width else self.width - 1
        sy = y if y < self.height else self.height - 1
        if sx < 0:
            sx = 0
        if sy < 0:
            sy = 0
        return self.pixels[sx, sy]


def pattern_paint(pattern: Image.Image, repeat: bool) -> PaintFn:
    return _PatternPaint(pattern, repeat)


def span_fill(image: Image.Image, x: int, y: int, paint: PaintFn) -> int:
    if image.mode != "RGB":
        raise ValueError("ожидается RGB-изображение")
    width, height = image.size
    if not (0 <= x < width and 0 <= y < height):
        return 0

    pixels = image.load()
    target = pixels[x, y]
    visited = bytearray(width * height)
    filled = 0

    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous_limit, height * 4 + 1000))

    def fill_span(px: int, py: int) -> None:
        nonlocal filled

        left = px
        while left > 0 and _can_fill(left - 1, py):
            left -= 1

        right = left
        row = py * width
        while right < width and not visited[row + right] and pixels[right, py] == target:
            visited[row + right] = 1
            pixels[right, py] = paint(right, py)
            filled += 1
            right += 1
        right -= 1

        for ny in (py - 1, py + 1):
            if ny < 0 or ny >= height:
                continue
            i = left
            while i <= right:
                if _can_fill(i, ny):
                    fill_span(i, ny)
                i += 1

    def _can_fill(px: int, py: int) -> bool:
        if px < 0 or py < 0 or px >= width or py >= height:
            return False
        if visited[py * width + px]:
            return False
        return pixels[px, py] == target

    try:
        fill_span(x, y)
    finally:
        sys.setrecursionlimit(previous_limit)
    return filled


class TraceResult(NamedTuple):
    points: list[Point]
    closed: bool


_OUTSIDE_FIRST = (4, 6, 0, 2, 5, 7, 3, 1)


def trace_boundary(image: Image.Image, x: int, y: int) -> TraceResult:
    if image.mode != "RGB":
        raise ValueError("ожидается RGB-изображение")
    width, height = image.size
    if not (0 <= x < width and 0 <= y < height):
        return TraceResult([], False)

    pixels = image.load()
    color = pixels[x, y]

    def is_boundary(px: int, py: int) -> bool:
        return 0 <= px < width and 0 <= py < height and pixels[px, py] == color

    if all(is_boundary(x + dx, y + dy) for dx, dy in _DIRS):
        while x > 0 and is_boundary(x - 1, y):
            x -= 1

    back_dir = _outside_direction(x, y, is_boundary)
    if back_dir is None:
        return TraceResult([(x, y)], True)

    start = (x, y)
    points = [start]
    seen = {(x, y, back_dir)}
    cx, cy = x, y
    limit = width * height * 4 + 8

    for _ in range(limit):
        found = _step_clockwise(cx, cy, back_dir, is_boundary)
        if found is None:
            return TraceResult(points, len(points) == 1)
        nx, ny, back_dir = found
        state = (nx, ny, back_dir)
        if state in seen:
            closed = points[-1] == start
            if closed and len(points) > 1:
                points.pop()
            return TraceResult(points, closed)
        seen.add(state)
        points.append((nx, ny))
        cx, cy = nx, ny

    return TraceResult(points, False)


def render_contour(image: Image.Image, points: list[Point]) -> Image.Image:
    result = image.copy()
    if not points:
        return result
    pixels = result.load()
    width, height = result.size
    last = max(len(points) - 1, 1)
    for index, (px, py) in enumerate(points):
        if not (0 <= px < width and 0 <= py < height):
            continue
        t = index / last
        pixels[px, py] = (int(255 * t), 30, int(255 * (1.0 - t)))

    sx, sy = points[0]
    yellow = (255, 210, 0)
    if 0 <= sx < width and 0 <= sy < height:
        pixels[sx, sy] = yellow
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if max(abs(dx), abs(dy)) != 2:
                continue
            mx, my = sx + dx, sy + dy
            if 0 <= mx < width and 0 <= my < height:
                pixels[mx, my] = yellow
    return result


def draw_stroke(
    image: Image.Image,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    radius: int,
    color: Color,
) -> None:
    centers = four_connected_line(x0, y0, x1, y1)
    if radius <= 0:
        pixels = image.load()
        width, height = image.size
        for x, y in centers:
            if 0 <= x < width and 0 <= y < height:
                pixels[x, y] = color
        return

    draw = ImageDraw.Draw(image)
    for x, y in centers:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def four_connected_line(x0: int, y0: int, x1: int, y1: int) -> list[Point]:
    points: list[Point] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * err
        step_x = False
        step_y = False
        if doubled > -dy:
            err -= dy
            x0 += sx
            step_x = True
        if doubled < dx:
            err += dx
            y0 += sy
            step_y = True
        if step_x and step_y:
            points.append((x0, y0 - sy))
    return points


def _outside_direction(x: int, y: int, is_boundary: Callable[[int, int], bool]) -> int | None:
    for index in _OUTSIDE_FIRST:
        dx, dy = _DIRS[index]
        if not is_boundary(x + dx, y + dy):
            return index
    return None


def _step_clockwise(
    x: int,
    y: int,
    back_dir: int,
    is_boundary: Callable[[int, int], bool],
) -> tuple[int, int, int] | None:
    for turn in range(1, 9):
        direction = (back_dir + turn) % 8
        dx, dy = _DIRS[direction]
        nx, ny = x + dx, y + dy
        if is_boundary(nx, ny):
            arrived = _DIR_INDEX[(-dx, -dy)]
            return nx, ny, arrived
    return None
