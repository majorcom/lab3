from __future__ import annotations

import unittest

from PIL import Image

from task1 import (
    draw_stroke,
    four_connected_line,
    pattern_paint,
    render_contour,
    solid_paint,
    span_fill,
    trace_boundary,
)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 20, 20)
BLUE = (0, 0, 180)


def component(image: Image.Image, x: int, y: int) -> set[tuple[int, int]]:
    pixels = image.load()
    width, height = image.size
    target = pixels[x, y]
    found: set[tuple[int, int]] = set()
    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if (cx, cy) in found or not (0 <= cx < width and 0 <= cy < height):
            continue
        if pixels[cx, cy] != target:
            continue
        found.add((cx, cy))
        stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
    return found


def rect_border(image: Image.Image, x0: int, y0: int, x1: int, y1: int, color=BLACK) -> None:
    pixels = image.load()
    for x in range(x0, x1 + 1):
        pixels[x, y0] = color
        pixels[x, y1] = color
    for y in range(y0, y1 + 1):
        pixels[x0, y] = color
        pixels[x1, y] = color


class LineTests(unittest.TestCase):
    def test_line_is_four_connected(self) -> None:
        samples = (
            (0, 0, 10, 3),
            (0, 0, 3, 10),
            (5, 5, 5, 8),
            (8, 1, 1, 1),
            (0, 0, 0, 0),
            (2, 9, 8, 1),
            (0, 0, 1, 1),
            (4, 0, 0, 7),
        )
        for x0, y0, x1, y1 in samples:
            points = four_connected_line(x0, y0, x1, y1)
            self.assertEqual(points[0], (x0, y0))
            self.assertEqual(points[-1], (x1, y1))
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                self.assertEqual(abs(ax - bx) + abs(ay - by), 1, points)


class FillTests(unittest.TestCase):
    def test_span_matches_four_connected_component(self) -> None:
        image = Image.new("RGB", (48, 36), WHITE)
        rect_border(image, 2, 2, 40, 30)
        rect_border(image, 10, 8, 20, 18)
        pixels = image.load()
        pixels[30, 10] = (0, 128, 0)
        pixels[31, 10] = (0, 128, 0)
        expected = component(image, 4, 4)
        self.assertNotIn((15, 13), expected)
        self.assertNotIn((30, 10), expected)
        self.assertIn((25, 10), expected)

        filled = span_fill(image, 4, 4, solid_paint(RED))
        self.assertEqual(filled, len(expected))
        pixels = image.load()
        for y in range(image.size[1]):
            for x in range(image.size[0]):
                if (x, y) in expected:
                    self.assertEqual(pixels[x, y], RED)
                else:
                    self.assertNotEqual(pixels[x, y], RED)

    def test_hole_stays_empty_and_outside_stays_empty(self) -> None:
        image = Image.new("RGB", (40, 40), WHITE)
        draw_stroke(image, 20, 4, 36, 20, 0, BLACK)
        draw_stroke(image, 36, 20, 20, 36, 0, BLACK)
        draw_stroke(image, 20, 36, 4, 20, 0, BLACK)
        draw_stroke(image, 4, 20, 20, 4, 0, BLACK)
        rect_border(image, 16, 16, 24, 24)

        span_fill(image, 20, 10, solid_paint(RED))
        pixels = image.load()
        self.assertEqual(pixels[20, 10], RED)
        self.assertEqual(pixels[20, 20], WHITE)
        self.assertEqual(pixels[0, 0], WHITE)
        self.assertEqual(pixels[20, 4], BLACK)
        self.assertEqual(pixels[16, 16], BLACK)

    def test_diagonal_neighbors_are_not_connected(self) -> None:
        image = Image.new("RGB", (3, 2), WHITE)
        pixels = image.load()
        pixels[1, 0] = BLACK
        pixels[2, 1] = BLACK
        span_fill(image, 1, 0, solid_paint(RED))
        self.assertEqual(image.load()[2, 1], BLACK)

    def test_pattern_repeats_when_small(self) -> None:
        image = Image.new("RGB", (12, 8), WHITE)
        rect_border(image, 0, 0, 11, 7)
        pattern = Image.new("RGB", (3, 2))
        pattern_pixels = pattern.load()
        for y in range(2):
            for x in range(3):
                pattern_pixels[x, y] = (x * 40, y * 60, 10)
        expected = component(image, 2, 2)
        before = image.copy()
        span_fill(image, 2, 2, pattern_paint(pattern, repeat=True))
        pixels = image.load()
        source = pattern.load()
        for x, y in expected:
            self.assertEqual(pixels[x, y], source[x % 3, y % 2])
        self.assertEqual(pixels[5, 3], source[5 % 3, 3 % 2])
        self.assertEqual(pixels[0, 0], before.load()[0, 0])

    def test_large_pattern_is_not_tiled(self) -> None:
        image = Image.new("RGB", (8, 4), WHITE)
        rect_border(image, 0, 0, 7, 3)
        pattern = Image.new("RGB", (3, 2))
        pattern_pixels = pattern.load()
        for y in range(2):
            for x in range(3):
                pattern_pixels[x, y] = (x * 40, y * 60, 7)
        span_fill(image, 1, 1, pattern_paint(pattern, repeat=False))
        pixels = image.load()
        self.assertEqual(pixels[4, 1], (2 * 40, 60, 7))
        self.assertNotEqual(pixels[4, 1], (1 * 40, 60, 7))
        self.assertEqual(pixels[1, 1], (1 * 40, 60, 7))

    def test_pattern_may_contain_the_background_color(self) -> None:
        image = Image.new("RGB", (8, 6), WHITE)
        rect_border(image, 1, 1, 6, 4)
        pattern = Image.new("RGB", (2, 2), WHITE)
        pattern.load()[0, 0] = RED
        filled = span_fill(image, 2, 2, pattern_paint(pattern, repeat=True))
        self.assertGreater(filled, 1)
        self.assertEqual(image.load()[0, 0], WHITE)


class BoundaryTests(unittest.TestCase):
    def test_rectangle_perimeter_in_order(self) -> None:
        image = Image.new("RGB", (9, 7), WHITE)
        pixels = image.load()
        for y in range(1, 6):
            for x in range(1, 8):
                pixels[x, y] = BLACK
        result = trace_boundary(image, 4, 3)
        perimeter = {
            (x, y)
            for y in range(1, 6)
            for x in range(1, 8)
            if x in (1, 7) or y in (1, 5)
        }
        self.assertTrue(result.closed)
        self.assertEqual(set(result.points), perimeter)
        self.assertNotIn((4, 3), result.points)
        self.assertEqual(result.points[0], (1, 3))
        self._assert_walk(result.points, closed=True)

    def test_click_on_outline_starts_there(self) -> None:
        image = Image.new("RGB", (11, 9), WHITE)
        rect_border(image, 2, 2, 8, 7, BLUE)
        result = trace_boundary(image, 5, 2)
        border = {
            (x, y)
            for y in range(2, 8)
            for x in range(2, 9)
            if x in (2, 8) or y in (2, 7)
        }
        self.assertEqual(result.points[0], (5, 2))
        self.assertTrue(result.closed)
        self.assertEqual(set(result.points), border)
        self._assert_walk(result.points, closed=True)

    def test_hole_outline_is_separate_from_outer(self) -> None:
        image = Image.new("RGB", (20, 16), WHITE)
        rect_border(image, 1, 1, 18, 14, BLUE)
        rect_border(image, 6, 5, 12, 11, BLUE)
        outer = trace_boundary(image, 1, 1)
        hole = trace_boundary(image, 6, 5)
        self.assertIn((1, 1), outer.points)
        self.assertNotIn((6, 5), outer.points)
        self.assertEqual(hole.points[0], (6, 5))
        self.assertNotIn((1, 1), hole.points)
        self.assertTrue(hole.closed)

    def test_other_color_is_not_followed(self) -> None:
        image = Image.new("RGB", (10, 8), WHITE)
        rect_border(image, 1, 1, 8, 6, BLUE)
        pixels = image.load()
        pixels[8, 3] = RED
        pixels[9, 3] = RED
        result = trace_boundary(image, 1, 1)
        colors = {image.load()[x, y] for x, y in result.points}
        self.assertEqual(colors, {BLUE})

    def test_overlay_does_not_change_source(self) -> None:
        image = Image.new("RGB", (6, 5), WHITE)
        rect_border(image, 1, 1, 4, 3)
        result = trace_boundary(image, 1, 1)
        before = image.copy()
        shown = render_contour(image, result.points)
        self.assertEqual(image.tobytes(), before.tobytes())
        self.assertEqual(shown.load()[result.points[0]], (255, 210, 0))
        self.assertNotEqual(shown.load()[result.points[1]], before.load()[result.points[1]])

    def _assert_walk(self, points: list[tuple[int, int]], closed: bool) -> None:
        sequence = points + ([points[0]] if closed else [])
        for (ax, ay), (bx, by) in zip(sequence, sequence[1:]):
            self.assertLessEqual(max(abs(ax - bx), abs(ay - by)), 1)
            self.assertNotEqual((ax, ay), (bx, by))


class AppSmokeTest(unittest.TestCase):
    def test_window_opens(self) -> None:
        import tkinter as tk

        from main import App

        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root)
            self.assertEqual(app.image.size, (900, 600))
            self.assertEqual(app.image.getpixel((10, 10)), (255, 255, 255))
            app._refresh()
            self.assertIsNotNone(app.photo)

            app._load_sample_pattern(True)
            self.assertEqual(app.pattern.size, (24, 24))
            self.assertEqual(app.pattern_mode.get(), "repeat")
            app._load_sample_pattern(False)
            self.assertEqual(app.pattern.size, (1100, 800))
            self.assertEqual(app.pattern_mode.get(), "once")

            app._load_shape_sample()
            self.assertEqual(app.image.size, (640, 420))
            app._trace((297, 35))
            self.assertGreater(len(app.contour), 100)
            self.assertIn(str(len(app.contour)), app.points_text.get("1.0", "2.0"))
            outside = app.image.getpixel((10, 400))
            app._fill((140, 200), pattern=False)
            self.assertNotEqual(app.image.getpixel((140, 200)), (255, 255, 255))
            self.assertEqual(app.image.getpixel((320, 220)), (255, 255, 255))
            self.assertEqual(app.image.getpixel((10, 400)), outside)
            root.update_idletasks()
            self.assertLess(
                root.winfo_reqheight(),
                1100,
                f"window {root.winfo_reqwidth()}x{root.winfo_reqheight()}",
            )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
