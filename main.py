from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageOps, ImageTk

from task1 import (
    Color,
    Point,
    draw_stroke,
    pattern_paint,
    render_contour,
    solid_paint,
    span_fill,
    trace_boundary,
)
from task2 import bresenham_line, draw_bresenham, draw_wu, wu_line
from task3 import draw_gradient_triangle

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
WHITE: Color = (255, 255, 255)
CANVAS_SIZE = (900, 600)
VIEW_MAX = (960, 640)

MODES = (
    ("draw", "Рисование области"),
    ("fill_color", "1а. Заливка цветом"),
    ("fill_pattern", "1б. Заливка рисунком"),
    ("boundary", "1в. Обход границы"),
    ("line_bresenham", "2. Отрезок Брезенхема"),
    ("line_wu", "2. Отрезок Ву"),
    ("triangle", "3. Градиент треугольника"),
)

LINE_MODES = ("line_bresenham", "line_wu")


def hex_color(color: Color) -> str:
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def load_rgb(path: str) -> Image.Image:
    with Image.open(path) as opened:
        oriented = ImageOps.exif_transpose(opened)
        return oriented.convert("RGB")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ЛР3 — растровые алгоритмы")
        self.image = Image.new("RGB", CANVAS_SIZE, WHITE)
        self.pattern: Image.Image | None = None
        self.pattern_name = ""
        self.contour: list[Point] | None = None
        self.border_color: Color = (0, 0, 0)
        self.fill_color: Color = (210, 40, 40)
        self.stroke_start: Point | None = None
        self.line_anchor: Point | None = None
        self.line_end: Point | None = None
        self.tri_points: list[Point] = []
        self.tri_preview: Point | None = None
        self.vertex_colors: list[Color] = [(220, 40, 40), (40, 180, 50), (40, 70, 210)]
        self.erasing = False
        self.photo: ImageTk.PhotoImage | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None

        self.mode = tk.StringVar(value="draw")
        self.pattern_mode = tk.StringVar(value="repeat")
        self.brush = tk.IntVar(value=1)
        self.status = tk.StringVar(value="Нарисуйте замкнутую область или загрузите изображение.")
        self.coords = tk.StringVar(value="")

        self._build()
        self._fit_viewport()
        self._refresh()
        self._on_mode()

    def _build(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        panel = ttk.Frame(self.root, padding=8)
        panel.grid(row=0, column=0, sticky="ns")
        workspace = ttk.Frame(self.root)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.columnconfigure(0, weight=1)

        self._build_modes(panel)
        self._build_colors(panel)
        self._build_vertices(panel)
        self._build_pattern(panel)
        self._build_image_tools(panel)

        canvas_wrap = ttk.Frame(workspace)
        canvas_wrap.grid(row=0, column=0, sticky="nw")
        workspace.rowconfigure(0, weight=0)
        workspace.rowconfigure(1, weight=1)
        self.canvas = tk.Canvas(
            canvas_wrap,
            width=CANVAS_SIZE[0],
            height=CANVAS_SIZE[1],
            bg="#d0d0d0",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.hbar = ttk.Scrollbar(canvas_wrap, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        points_box = ttk.LabelFrame(workspace, text="Список точек", padding=4)
        points_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.points_text = ScrolledText(
            points_box, height=7, font=("Consolas", 9), wrap="none"
        )
        self.points_text.pack(fill="both", expand=True)

        status_bar = ttk.Frame(self.root, padding=(8, 4))
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Label(status_bar, textvariable=self.status).pack(side="left")
        ttk.Label(status_bar, textvariable=self.coords).pack(side="right")

        self.canvas.bind("<ButtonPress-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        self.canvas.bind("<ButtonPress-3>", self._on_right_down)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_stroke_end)
        self.canvas.bind("<Motion>", self._on_move)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

    def _build_modes(self, panel: ttk.Frame) -> None:
        box = ttk.LabelFrame(panel, text="Режим", padding=6)
        box.pack(fill="x")
        for value, text in MODES:
            ttk.Radiobutton(
                box, text=text, value=value, variable=self.mode, command=self._on_mode
            ).pack(anchor="w")

    def _build_colors(self, panel: ttk.Frame) -> None:
        box = ttk.LabelFrame(panel, text="Кисть и цвета", padding=6)
        box.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Радиус").pack(side="left")
        ttk.Spinbox(row, from_=0, to=12, textvariable=self.brush, width=4).pack(side="left", padx=6)
        ttk.Label(row, text="0 — один пиксель").pack(side="left")

        self.border_swatch = self._color_row(box, "Граница", self.border_color, self._pick_border)
        self.fill_swatch = self._color_row(box, "Заливка", self.fill_color, self._pick_fill)

    def _build_vertices(self, panel: ttk.Frame) -> None:
        box = ttk.LabelFrame(panel, text="Вершины треугольника (3)", padding=6)
        box.pack(fill="x", pady=(8, 0))
        self.vertex_swatches: list[tk.Label] = []
        for index in range(3):
            swatch = self._color_row(
                box,
                f"Вершина {index + 1}",
                self.vertex_colors[index],
                lambda i=index: self._pick_vertex(i),
            )
            self.vertex_swatches.append(swatch)

    def _color_row(self, parent: ttk.Frame, title: str, color: Color, command) -> tk.Label:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=title, width=10).pack(side="left")
        swatch = tk.Label(row, width=3, bg=hex_color(color), relief="solid", borderwidth=1)
        swatch.pack(side="left")
        ttk.Button(row, text="Выбрать", command=command).pack(side="left", padx=6)
        return swatch

    def _build_pattern(self, panel: ttk.Frame) -> None:
        box = ttk.LabelFrame(panel, text="Рисунок для заливки (1б)", padding=6)
        box.pack(fill="x", pady=(8, 0))
        ttk.Button(box, text="Загрузить файл...", command=self._load_pattern).pack(anchor="w")
        samples = ttk.Frame(box)
        samples.pack(fill="x", pady=4)
        ttk.Button(samples, text="Маленький", command=lambda: self._load_sample_pattern(True)).pack(
            side="left"
        )
        ttk.Button(samples, text="Большой", command=lambda: self._load_sample_pattern(False)).pack(
            side="left", padx=4
        )
        self.preview = ttk.Label(box)
        self.preview.pack(anchor="w", pady=2)
        self.pattern_info = tk.StringVar(value="Файл не загружен")
        ttk.Label(box, textvariable=self.pattern_info, wraplength=280).pack(anchor="w")
        ttk.Radiobutton(
            box,
            text="Циклически (маленький файл)",
            value="repeat",
            variable=self.pattern_mode,
        ).pack(anchor="w")
        ttk.Radiobutton(
            box,
            text="Без повтора, 1:1 (большой файл)",
            value="once",
            variable=self.pattern_mode,
        ).pack(anchor="w")

    def _build_image_tools(self, panel: ttk.Frame) -> None:
        box = ttk.LabelFrame(panel, text="Холст и контур", padding=6)
        box.pack(fill="x", pady=(8, 0))
        ttk.Button(box, text="Загрузить изображение...", command=self._load_canvas).pack(
            anchor="w", pady=1
        )
        ttk.Button(box, text="Пример: фигура с отверстием", command=self._load_shape_sample).pack(
            anchor="w", pady=1
        )
        ttk.Button(box, text="Очистить холст", command=self._clear).pack(anchor="w", pady=1)
        ttk.Button(box, text="Скрыть контур", command=self._hide_contour).pack(anchor="w", pady=1)
        ttk.Button(box, text="Сохранить изображение...", command=self._save_image).pack(
            anchor="w", pady=1
        )
        ttk.Button(box, text="Сохранить точки контура...", command=self._save_points).pack(
            anchor="w", pady=1
        )

    def _on_mode(self) -> None:
        self.line_anchor = None
        self.line_end = None
        self.tri_points.clear()
        self.tri_preview = None
        self.stroke_start = None
        self.erasing = False
        mode = self.mode.get()
        hints = {
            "draw": "ЛКМ — граница области, ПКМ — стереть до белого.",
            "fill_color": "Щёлкните внутри области: это затравка заливки цветом.",
            "fill_pattern": "Щёлкните внутри области: заливка рисунком из файла.",
            "boundary": "Щёлкните по границе. Точки записываются по порядку обхода.",
            "line_bresenham": "Протяните отрезок левой кнопкой. Цвет берётся из поля «Граница».",
            "line_wu": "Протяните отрезок левой кнопкой. Цвет берётся из поля «Граница».",
            "triangle": "Три щелчка — вершины. Цвета задаются полями «Вершина 1», «Вершина 2» и «Вершина 3».",
        }
        self.status.set(hints[mode])
        self._refresh()

    def _on_move(self, event: tk.Event) -> None:
        point = self._image_xy(event, clamp=False)
        self.coords.set("" if point is None else f"x={point[0]}  y={point[1]}")
        self._move_triangle_preview(event)

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_left_down(self, event: tk.Event) -> None:
        mode = self.mode.get()
        if mode in LINE_MODES:
            point = self._image_xy(event, clamp=True)
            if point is None:
                return
            self.line_anchor = point
            self.line_end = point
            self.contour = None
            self.status.set("Протяните отрезок и отпустите кнопку.")
            self._refresh()
            return
        if mode == "triangle":
            return
        if mode != "draw":
            return
        point = self._image_xy(event, clamp=True)
        if point is None:
            return
        self.erasing = False
        self.contour = None
        self._clear_points_view()
        self._paint_stroke(point, point, self.border_color)
        self.stroke_start = point

    def _on_left_drag(self, event: tk.Event) -> None:
        if self.mode.get() == "triangle":
            self._move_triangle_preview(event)
            return
        if self.mode.get() in LINE_MODES:
            if self.line_anchor is None:
                return
            point = self._image_xy(event, clamp=True)
            if point is None:
                return
            self.line_end = point
            self._refresh()
            return
        if self.mode.get() != "draw" or self.stroke_start is None or self.erasing:
            return
        point = self._image_xy(event, clamp=True)
        if point is None:
            return
        self._paint_stroke(self.stroke_start, point, self.border_color)
        self.stroke_start = point

    def _on_left_up(self, event: tk.Event) -> None:
        mode = self.mode.get()
        if mode in LINE_MODES:
            start = self.line_anchor
            self.line_anchor = None
            self.line_end = None
            point = self._image_xy(event, clamp=True)
            if start is not None and point is not None:
                self._draw_segment(start, point)
            else:
                self._refresh()
            return
        if mode == "triangle":
            point = self._image_xy(event, clamp=True)
            self.tri_preview = None
            if point is None:
                self._refresh()
                return
            self.tri_points.append(point)
            if len(self.tri_points) == 3:
                self._draw_triangle()
                return
            left = 3 - len(self.tri_points)
            self.status.set(f"Вершина {len(self.tri_points)}: {point}. Осталось указать: {left}.")
            self._refresh()
            return
        point = self._image_xy(event, clamp=False)
        self.stroke_start = None
        self.erasing = False
        if point is None:
            return
        if mode == "fill_color":
            self._fill(point, pattern=False)
        elif mode == "fill_pattern":
            self._fill(point, pattern=True)
        elif mode == "boundary":
            self._trace(point)

    def _on_right_down(self, event: tk.Event) -> None:
        if self.mode.get() != "draw":
            return
        point = self._image_xy(event, clamp=True)
        if point is None:
            return
        self.erasing = True
        self.contour = None
        self._clear_points_view()
        self._paint_stroke(point, point, WHITE)
        self.stroke_start = point

    def _on_right_drag(self, event: tk.Event) -> None:
        if not self.erasing or self.stroke_start is None:
            return
        point = self._image_xy(event, clamp=True)
        if point is None:
            return
        self._paint_stroke(self.stroke_start, point, WHITE)
        self.stroke_start = point

    def _on_stroke_end(self, _event: tk.Event) -> None:
        self.stroke_start = None
        self.erasing = False

    def _draw_segment(self, start: Point, end: Point) -> None:
        x0, y0 = start
        x1, y1 = end
        if self.mode.get() == "line_wu":
            draw_wu(self.image, x0, y0, x1, y1, self.border_color)
            plots = wu_line(x0, y0, x1, y1)
            self._show_plots(plots, start, end, "Ву")
            self.status.set(f"Алгоритм Ву: {len(plots)} пикселов, {start} — {end}.")
        else:
            points = bresenham_line(x0, y0, x1, y1)
            draw_bresenham(self.image, x0, y0, x1, y1, self.border_color)
            self._show_plots([(x, y, 1.0) for x, y in points], start, end, "Брезенхем")
            self.status.set(f"Алгоритм Брезенхема: {len(points)} пикселов, {start} — {end}.")
        self._refresh()

    def _draw_triangle(self) -> None:
        points = list(self.tri_points)
        colors = [self.vertex_colors[0], self.vertex_colors[1], self.vertex_colors[2]]
        self.tri_points.clear()
        self.tri_preview = None
        self.contour = None
        count = draw_gradient_triangle(
            self.image,
            points[0],
            colors[0],
            points[1],
            colors[1],
            points[2],
            colors[2],
        )
        self._show_triangle(points, colors, count)
        self.status.set(f"Треугольник: {count} пикселов. Вершины {points[0]}, {points[1]}, {points[2]}.")
        self._refresh()

    def _show_triangle(self, points: list[Point], colors: list[Color], count: int) -> None:
        self.points_text.delete("1.0", "end")
        self.points_text.insert(
            "end",
            f"# Треугольник\n# Пикселов: {count}\n# вершина  x  y  r  g  b\n",
        )
        for index, ((x, y), (red, green, blue)) in enumerate(zip(points, colors), start=1):
            self.points_text.insert(
                "end",
                f"{index:5d}  {x:5d}  {y:5d}  {red:3d} {green:3d} {blue:3d}\n",
            )

    def _move_triangle_preview(self, event: tk.Event) -> None:
        if self.mode.get() != "triangle" or not self.tri_points:
            return
        preview = self._image_xy(event, clamp=True)
        if preview is None or preview == self.tri_preview:
            return
        self.tri_preview = preview
        self._refresh()

    def _paint_triangle_preview(self, image: Image.Image) -> None:
        points = self.tri_points
        colors = self.vertex_colors
        if len(points) >= 2 and self.tri_preview is not None:
            draw_gradient_triangle(
                image,
                points[0],
                colors[0],
                points[1],
                colors[1],
                self.tri_preview,
                colors[2],
            )
        elif len(points) == 2:
            draw_bresenham(
                image,
                points[0][0],
                points[0][1],
                points[1][0],
                points[1][1],
                colors[0],
            )
        elif len(points) == 1 and self.tri_preview is not None:
            draw_bresenham(
                image,
                points[0][0],
                points[0][1],
                self.tri_preview[0],
                self.tri_preview[1],
                colors[0],
            )
        marks = list(zip(points, colors))
        if self.tri_preview is not None and len(points) < 3:
            marks.append((self.tri_preview, colors[len(points)]))
        for point, color in marks:
            _mark_vertex(image, point, color)

    def _show_plots(
        self,
        plots: list[tuple[int, int, float]],
        start: Point,
        end: Point,
        name: str,
    ) -> None:
        self.points_text.delete("1.0", "end")
        header = (
            f"# {name}\n"
            f"# {start[0]} {start[1]} — {end[0]} {end[1]}\n"
            f"# Пикселов: {len(plots)}\n"
            "# номер  x  y  яркость\n"
        )
        self.points_text.insert("end", header)
        shown = plots if len(plots) <= 8000 else plots[:8000]
        body = "\n".join(
            f"{index:5d}  {x:5d}  {y:5d}  {coverage:4.2f}"
            for index, (x, y, coverage) in enumerate(shown, start=1)
        )
        if body:
            self.points_text.insert("end", body + "\n")
        if len(plots) > len(shown):
            self.points_text.insert("end", f"# ... ещё {len(plots) - len(shown)} пикселов\n")

    def _paint_stroke(self, start: Point, end: Point, color: Color) -> None:
        draw_stroke(self.image, start[0], start[1], end[0], end[1], self._radius(), color)
        self._refresh()

    def _radius(self) -> int:
        try:
            radius = int(self.brush.get())
        except (tk.TclError, ValueError):
            radius = 1
        return max(0, min(radius, 20))

    def _fill(self, seed: Point, pattern: bool) -> None:
        if pattern:
            if self.pattern is None:
                messagebox.showinfo(
                    "Заливка рисунком",
                    "Сначала загрузите графический файл с рисунком.",
                    parent=self.root,
                )
                return
            repeat = self.pattern_mode.get() == "repeat"
            paint = pattern_paint(self.pattern, repeat)
            how = "циклически" if repeat else "без повтора, 1:1"
        else:
            paint = solid_paint(self.fill_color)
            how = f"цветом {self.fill_color}"

        self.contour = None
        self._clear_points_view()
        backup = self.image.copy()
        self.status.set("Идёт заливка...")
        self.canvas.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            count = span_fill(self.image, seed[0], seed[1], paint)
        except RecursionError:
            self.image = backup
            messagebox.showerror(
                "Заливка",
                "Не хватило глубины рекурсии. Упростите область.",
                parent=self.root,
            )
            self.status.set("Заливка прервана.")
            return
        finally:
            self.canvas.configure(cursor="crosshair")
        self.status.set(f"Закрашено {count} пикселов ({how}). Затравка {seed}.")
        self._refresh()

    def _trace(self, seed: Point) -> None:
        self.status.set("Идёт обход границы...")
        self.canvas.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            result = trace_boundary(self.image, seed[0], seed[1])
        finally:
            self.canvas.configure(cursor="crosshair")
        self.contour = result.points
        self._show_points(result.points, result.closed, seed)
        self._refresh()
        if not result.points:
            self.status.set("Граница не найдена.")
            return
        start = result.points[0]
        where = "замкнут" if result.closed else "не замкнулся"
        moved = ""
        if start != seed:
            moved = f" Старт сдвинут к краю области: {start}."
        self.status.set(f"Контур: {len(result.points)} точек, обход {where}.{moved}")

    def _show_points(self, points: list[Point], closed: bool, seed: Point) -> None:
        self.points_text.delete("1.0", "end")
        header = (
            f"# Точек: {len(points)}\n"
            f"# Замкнут: {'да' if closed else 'нет'}\n"
            f"# Щелчок: {seed[0]} {seed[1]}\n"
            "# номер  x  y\n"
        )
        self.points_text.insert("end", header)
        shown = points if len(points) <= 8000 else points[:8000]
        body = "\n".join(f"{index:5d}  {x:5d}  {y:5d}" for index, (x, y) in enumerate(shown, start=1))
        if body:
            self.points_text.insert("end", body + "\n")
        if len(points) > len(shown):
            self.points_text.insert("end", f"# ... ещё {len(points) - len(shown)} точек\n")

    def _clear_points_view(self) -> None:
        self.points_text.delete("1.0", "end")

    def _hide_contour(self) -> None:
        self.contour = None
        self._clear_points_view()
        self._refresh()
        self.status.set("Контур скрыт. Исходное изображение не менялось.")

    def _pick_border(self) -> None:
        chosen = self._ask_color(self.border_color)
        if chosen is not None:
            self.border_color = chosen
            self.border_swatch.configure(bg=hex_color(chosen))

    def _pick_fill(self) -> None:
        chosen = self._ask_color(self.fill_color)
        if chosen is not None:
            self.fill_color = chosen
            self.fill_swatch.configure(bg=hex_color(chosen))

    def _pick_vertex(self, index: int) -> None:
        chosen = self._ask_color(self.vertex_colors[index])
        if chosen is None:
            return
        self.vertex_colors[index] = chosen
        self.vertex_swatches[index].configure(bg=hex_color(chosen))
        if self.tri_points:
            self._refresh()

    def _ask_color(self, current: Color) -> Color | None:
        rgb, _hex = colorchooser.askcolor(color=hex_color(current), parent=self.root)
        if rgb is None:
            return None
        red, green, blue = rgb
        return int(red), int(green), int(blue)

    def _load_pattern(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Рисунок для заливки",
            initialdir=str(SAMPLES if SAMPLES.exists() else ROOT),
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"),
                ("Все файлы", "*.*"),
            ],
        )
        if not path:
            return
        try:
            image = load_rgb(path)
        except OSError as error:
            messagebox.showerror("Рисунок", f"Не удалось открыть файл.\n{error}", parent=self.root)
            return
        self._set_pattern(image, Path(path).name)

    def _load_sample_pattern(self, small: bool) -> None:
        name = "pattern_small.png" if small else "pattern_large.png"
        path = SAMPLES / name
        if not path.exists():
            messagebox.showerror("Пример", f"Нет файла {path}", parent=self.root)
            return
        self._set_pattern(load_rgb(str(path)), name)

    def _set_pattern(self, image: Image.Image, name: str) -> None:
        self.pattern = image
        self.pattern_name = name
        thumb = image.copy()
        thumb.thumbnail((88, 88), Image.Resampling.NEAREST)
        self.preview_photo = ImageTk.PhotoImage(thumb)
        self.preview.configure(image=self.preview_photo)
        width, height = image.size
        canvas_w, canvas_h = self.image.size
        if width >= canvas_w and height >= canvas_h:
            self.pattern_mode.set("once")
            advice = "Рисунок не меньше холста: выбран режим 1:1, без повтора и без масштаба."
        else:
            self.pattern_mode.set("repeat")
            advice = "Рисунок меньше холста: выбран циклический повтор. Режим можно переключить."
        self.pattern_info.set(f"{name}: {width}×{height}. {advice}")
        self.status.set(advice)

    def _load_canvas(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Изображение для обхода границы",
            initialdir=str(SAMPLES if SAMPLES.exists() else ROOT),
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"),
                ("Все файлы", "*.*"),
            ],
        )
        if not path:
            return
        try:
            image = load_rgb(path)
        except OSError as error:
            messagebox.showerror("Изображение", f"Не удалось открыть файл.\n{error}", parent=self.root)
            return
        self._replace_canvas(image, Path(path).name)

    def _load_shape_sample(self) -> None:
        path = SAMPLES / "shape.png"
        if not path.exists():
            messagebox.showerror("Пример", f"Нет файла {path}", parent=self.root)
            return
        self._replace_canvas(load_rgb(str(path)), path.name)

    def _replace_canvas(self, image: Image.Image, name: str) -> None:
        self.image = image
        self.contour = None
        self.tri_points.clear()
        self.tri_preview = None
        self.line_anchor = None
        self.line_end = None
        self._clear_points_view()
        self.photo = None
        self._fit_viewport()
        self._refresh()
        width, height = image.size
        if width * height > 2_000_000:
            self.status.set(
                f"{name}: {width}×{height}. Файл большой, операции могут занять время. Масштаб не менялся."
            )
        else:
            self.status.set(f"Холст заменён: {name}, {width}×{height}. Масштаб не менялся.")

    def _clear(self) -> None:
        self.image = Image.new("RGB", CANVAS_SIZE, WHITE)
        self.contour = None
        self.tri_points.clear()
        self.tri_preview = None
        self.line_anchor = None
        self.line_end = None
        self.photo = None
        self._clear_points_view()
        self._fit_viewport()
        self._refresh()
        self.status.set("Холст очищен.")

    def _save_image(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Сохранить то, что на экране",
            defaultextension=".png",
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            return
        self._compose().save(path)
        self.status.set(f"Изображение сохранено: {path}")

    def _save_points(self) -> None:
        if not self.contour:
            messagebox.showinfo("Контур", "Сначала обойдите границу.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Сохранить точки контура",
            defaultextension=".txt",
            filetypes=[("Текст", "*.txt")],
        )
        if not path:
            return
        lines = [f"{x} {y}" for x, y in self.contour]
        header = f"# Точек: {len(self.contour)}\n# x y\n"
        Path(path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
        self.status.set(f"Список из {len(self.contour)} точек сохранён: {path}")

    def _compose(self) -> Image.Image:
        shown = render_contour(self.image, self.contour) if self.contour else self.image
        needs_line = self.line_anchor is not None and self.line_end is not None
        needs_triangle = self.mode.get() == "triangle" and bool(self.tri_points)
        if not needs_line and not needs_triangle:
            return shown
        shown = shown.copy()
        if needs_line and self.line_anchor is not None and self.line_end is not None:
            x0, y0 = self.line_anchor
            x1, y1 = self.line_end
            if self.mode.get() == "line_wu":
                draw_wu(shown, x0, y0, x1, y1, self.border_color)
            else:
                draw_bresenham(shown, x0, y0, x1, y1, self.border_color)
        if needs_triangle:
            self._paint_triangle_preview(shown)
        return shown


    def _fit_viewport(self) -> None:
        width, height = self.image.size
        view_w = min(width, VIEW_MAX[0])
        view_h = min(height, VIEW_MAX[1])
        self.canvas.configure(width=view_w, height=view_h, scrollregion=(0, 0, width, height))
        if width > view_w:
            self.hbar.grid(row=1, column=0, sticky="ew")
        else:
            self.hbar.grid_remove()
        if height > view_h:
            self.vbar.grid(row=0, column=1, sticky="ns")
        else:
            self.vbar.grid_remove()

    def _refresh(self) -> None:
        shown = self._compose()
        if (
            self.photo is None
            or self.photo.width() != shown.size[0]
            or self.photo.height() != shown.size[1]
        ):
            self.photo = ImageTk.PhotoImage(shown)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            self.canvas.configure(scrollregion=(0, 0, shown.size[0], shown.size[1]))
        else:
            self.photo.paste(shown)

    def _image_xy(self, event: tk.Event, clamp: bool) -> Point | None:
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        width, height = self.image.size
        if clamp:
            if width <= 0 or height <= 0:
                return None
            return min(max(x, 0), width - 1), min(max(y, 0), height - 1)
        if 0 <= x < width and 0 <= y < height:
            return x, y
        return None


def _mark_vertex(image: Image.Image, point: Point, color: Color) -> None:
    pixels = image.load()
    width, height = image.size
    x, y = point
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if max(abs(dx), abs(dy)) != 2:
                continue
            mx, my = x + dx, y + dy
            if 0 <= mx < width and 0 <= my < height:
                pixels[mx, my] = (0, 0, 0)
    if 0 <= x < width and 0 <= y < height:
        pixels[x, y] = color


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
