import tkinter as tk
from tkinter import ttk, messagebox
import math

from .constants import APP_TITLE, APP_SIZE, COL_PREV
from .utils import parts
from .selection import Selection
from .shapes import Line, Rect, Circle, shape_from_dict
from .io import save_scene, load_scene, scene_to_dict
from .render import CanvasSurface

from tkinter.filedialog import asksaveasfilename, askopenfilename
from .io.jpeg_io import read_jpeg, write_jpeg
from .image_ops import linear_color_scale

from .color_models import rgb_to_cmyk, cmyk_to_rgb

from .rgbcube.cube_points import RGBCubePointsWindow
from .rgbcube.cube_sliced import RGBCubeSliceWindow
from .hsvcone.hsv_cone_window import HSVConeWindow
from .hsvcone.cone_points import HSVConePointsWindow


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.minsize(900, 600)

        self.objects = []
        self.mode = tk.StringVar(value="select")
        self.preview_id = None
        self.mouse_start = None
        self.sel = Selection()
        self._pix_overlay_mode = "auto"
        self._pix_overlay_threshold = 8

        # Historia
        self.history = []
        self.history_i = -1
        self._suspend_history = False

        self.color_mode = tk.StringVar(value="RGB")
        # RGB wejściowe
        self.rgb_r_var = tk.IntVar(value=255)
        self.rgb_g_var = tk.IntVar(value=0)
        self.rgb_b_var = tk.IntVar(value=0)

        # CMYK wejściowe (w %)
        self.cmyk_c_var = tk.DoubleVar(value=0.0)
        self.cmyk_m_var = tk.DoubleVar(value=100.0)
        self.cmyk_y_var = tk.DoubleVar(value=100.0)
        self.cmyk_k_var = tk.DoubleVar(value=0.0)

        # okna z kostkami RGB
        self.rgb_cube_points_win = None  # prosta wersja
        self.rgb_cube_slice_win = None  # wersja z cięciami

        # okno z stożkiem
        self.hsv_cone_points_win = None
        self.hsv_cone_win = None

        self._build_ui()
        self._bind_canvas()

        # powierzchnia rysująca (Canvas)
        self.surface = CanvasSurface(self.canvas)
        # hook – selection używa cv._surface
        self.canvas._surface = self.surface

        self._push_history("Start")

    # --- UI ---
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.canvas = tk.Canvas(
            self, bg="white", highlightthickness=1, highlightbackground="#ccc"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        ttk.Label(panel, text="Panel sterowania", font=("", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        modebar = ttk.Frame(panel)
        modebar.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for text, value in [
            ("Select", "select"),
            ("Line", "line"),
            ("Rect", "rect"),
            ("Circle", "circle"),
        ]:
            rb = ttk.Radiobutton(
                modebar,
                text=text,
                value=value,
                variable=self.mode,
                command=self._on_mode_change,  # wywoła odświeżenie podpowiedzi i czyszczenie preview
            )
            rb.pack(side="left", padx=4)

        self.params_label = ttk.Label(panel, text="Parametry:")
        self.params_label.grid(row=3, column=0, sticky="w")
        self.params = ttk.Entry(panel)
        self.params.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        btnrow = ttk.Frame(panel)
        btnrow.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(btnrow, text="Rysuj z pól", command=self.draw_from_fields).pack(
            side="left"
        )
        ttk.Button(
            btnrow, text="Zastosuj do zaznaczonego", command=self.apply_to_selected
        ).pack(side="left", padx=6)
        ttk.Button(btnrow, text="Wyczyść", command=self.clear_all).pack(
            side="left", padx=6
        )

        filerow = ttk.Frame(panel)
        filerow.grid(row=6, column=0, sticky="ew")
        ttk.Button(filerow, text="Zapisz JSON", command=self.save_json).pack(
            side="left"
        )
        ttk.Button(filerow, text="Wczytaj JSON", command=self.load_json).pack(
            side="left", padx=6
        )

        ppmrow = ttk.Frame(panel)
        ppmrow.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(ppmrow, text="Wczytaj PPM (P3/P6)", command=self.load_ppm_auto).pack(
            side="left"
        )

        # --- JPEG ---
        jpegs = ttk.Frame(panel)
        jpegs.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(jpegs, text="Wczytaj JPEG", command=self.load_jpeg).pack(side="left")
        ttk.Button(jpegs, text="Zapisz jako JPEG…", command=self.save_as_jpeg).pack(
            side="left", padx=6
        )

        # --- Skala kolorów (poziomy) ---
        levels = ttk.Frame(panel)
        levels.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(levels, text="Levels in_min,in_max:").pack(side="left")
        self.levels_entry = ttk.Entry(levels, width=12)
        self.levels_entry.insert(0, "0,255")
        self.levels_entry.pack(side="left", padx=4)
        ttk.Button(levels, text="Zastosuj do obrazu", command=self.apply_levels).pack(
            side="left"
        )

        # --- Zoom / Pan ---
        zoomrow = ttk.Frame(panel)
        zoomrow.grid(row=10, column=0, sticky="ew", pady=(8, 0))

        ttk.Label(zoomrow, text="Zoom:").pack(side="left")
        ttk.Button(
            zoomrow, text="−", width=3, command=lambda: self.change_zoom(-1)
        ).pack(side="left")
        ttk.Button(
            zoomrow, text="+", width=3, command=lambda: self.change_zoom(+1)
        ).pack(side="left", padx=4)
        ttk.Label(
            zoomrow,
            text="(przy dużym powiększeniu: przesuwaj obraz PPM/JPEG przeciągając)",
        ).pack(side="left", padx=6)

        # --- Konwersja kolorów RGB / CMYK ---
        self._build_color_converter_panel(panel, row=11)

        # --- Kostki RGB 3D ---
        cube_row = ttk.LabelFrame(panel, text="Kostki RGB 3D")
        cube_row.grid(row=12, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(
            cube_row,
            text="Prosta (kropki)",
            command=self.open_rgb_cube_points,
        ).pack(side="left", padx=4, pady=2)

        ttk.Button(
            cube_row, text="Pełna kostka RGB (cięcia)", command=self.open_rgb_cube_slice
        ).pack(side="left", padx=4, pady=2)
        # --- Stożki HSV 3D ---
        hsv_row = ttk.LabelFrame(panel, text="Stożki HSV 3D")
        hsv_row.grid(row=13, column=0, sticky="ew", pady=(4, 0))

        ttk.Button(
            hsv_row,
            text="Stożek (punkty)",
            command=self.open_hsv_cone_points,
        ).pack(side="left", padx=4, pady=2)

        ttk.Button(
            hsv_row,
            text="Stożek (pełny)",
            command=self.open_hsv_cone_full,
        ).pack(side="left", padx=4, pady=2)

        # overlay RGB
        self._pix_overlay_on = True  # można zrobić przełącznik

        panel.grid_propagate(False)
        panel.configure(width=360)
        panel.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Gotowe.")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 4)).grid(
            row=1, column=0, columnspan=2, sticky="ew"
        )

        self._set_params_hint()

    def _bind_canvas(self):
        self.canvas.bind("<Button-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)
        self.canvas.bind(
            "<Motion>",
            lambda e: self._set_status(f"x={e.x}, y={e.y} | tryb: {self.mode.get()}"),
        )
        self.canvas.bind("<Motion>", self._on_motion)
        self.bind_all("<Control-z>", self.undo)
        self.bind_all("<Control-y>", self.redo)
        self.bind_all("<Control-Shift-Z>", self.redo)
        self.bind_all("<Delete>", self.on_delete)
        self.canvas.bind("<Delete>", self.on_delete)
        self.bind_all("<Control-d>", self.duplicate_selected)

    # --- Historia ----------
    def _scene_to_dict(self):
        sel_idx = None
        if self.sel.obj:
            for i, o in enumerate(self.objects):
                if o is self.sel.obj:
                    sel_idx = i
                    break
        return scene_to_dict(self.objects, sel_idx)

    def _load_scene_from_dict(self, data: dict):
        self.canvas.delete("all")
        self.objects.clear()
        self._clear_preview()
        self.sel.clear(self.canvas)
        # odtwórz scenę
        for d in data.get("objects", []):
            o = shape_from_dict(d)
            o.draw(self.surface, self.canvas)
            self.objects.append(o)
        idx = data.get("selected_index", None)
        if idx is not None and 0 <= idx < len(self.objects):
            self.sel.set(self.canvas, self.objects[idx])
            self._reflect_selected_to_ui()
        else:
            self._set_status("Gotowe.")

    def _push_history(self, label=""):
        if self._suspend_history:
            return
        state = self._scene_to_dict()
        if self.history_i < len(self.history) - 1:
            self.history = self.history[: self.history_i + 1]
        self.history.append(state)
        self.history_i = len(self.history) - 1
        MAX_HIST = 50
        if len(self.history) > MAX_HIST:
            self.history = self.history[-MAX_HIST:]
            self.history_i = len(self.history) - 1
        if label:
            self._set_status(f"{label} (hist: {self.history_i+1}/{len(self.history)})")

    def undo(self, e=None):
        if self.history_i <= 0:
            self._set_status("Brak wcześniejszego stanu.")
            return
        self.history_i -= 1
        self._suspend_history = True
        try:
            self._load_scene_from_dict(self.history[self.history_i])
        finally:
            self._suspend_history = False
        self._set_status("Cofnięto (Undo).")

    def redo(self, e=None):
        if self.history_i >= len(self.history) - 1:
            self._set_status("Brak następnego stanu.")
            return
        self.history_i += 1
        self._suspend_history = True
        try:
            self._load_scene_from_dict(self.history[self.history_i])
        finally:
            self._suspend_history = False
        self._set_status("Ponowiono (Redo).")

    # --- Helpers ---
    def _set_status(self, s):
        self.status.set(s)

    def _clear_preview(self):
        if self.preview_id:
            self.canvas.delete(self.preview_id)
            self.preview_id = None

    def _on_mode_change(self):
        self._clear_preview()
        self.mouse_start = None
        self.sel.clear(self.canvas)
        self._set_params_hint()

    def _set_params_hint(self):
        m = self.mode.get()
        if m in ("line", "rect"):
            self.params_label.config(text="Parametry (x1,y1,x2,y2)")
            self.params.delete(0, tk.END)
            self.params.insert(0, "100,100,300,200")
        elif m == "circle":
            self.params_label.config(text="Parametry (cx,cy,r)")
            self.params.delete(0, tk.END)
            self.params.insert(0, "250,220,80")
        else:
            self.params_label.config(text="Parametry:")
            self.params.delete(0, tk.END)

    def _add_object(self, obj):
        obj.draw(self.surface, self.canvas)
        self.objects.append(obj)

    def _reflect_selected_to_ui(self):
        if not self.sel.obj:
            return
        t = type(self.sel.obj).__name__.lower()
        if t in ("line", "rect"):
            label = "x1,y1,x2,y2"
        elif t in ("circle",):
            label = "cx,cy,r"
        elif t in ("rasterimage", "image"):
            label = "x,y,w,h"
        else:
            label = "Parametry"
        self.params_label.config(text=f"(wybór) {t}: {label}")
        self.params.delete(0, tk.END)
        self.params.insert(0, self.sel.obj.params_text())
        self._set_status(f"Select → {t}: {self.sel.obj.params_text()}")

    # --- Actions ---
    def draw_from_fields(self):
        try:
            m = self.mode.get()
            if m == "line":
                x1, y1, x2, y2 = map(int, parts(self.params.get(), 4))
                o = Line(x1, y1, x2, y2)
            elif m == "rect":
                x1, y1, x2, y2 = map(int, parts(self.params.get(), 4))
                o = Rect(x1, y1, x2, y2)
            elif m == "circle":
                cx, cy, r = map(int, parts(self.params.get(), 3))
                if r <= 0:
                    raise ValueError("Promień musi być > 0")
                o = Circle(cx, cy, r)
            else:
                messagebox.showwarning("Tryb", "Wybierz line/rect/circle")
                return
        except Exception as e:
            messagebox.showerror("Parametry", str(e))
            return
        self._add_object(o)
        self.sel.set(self.canvas, o)
        self._reflect_selected_to_ui()
        self._push_history("Rysuj z pól")

    def apply_to_selected(self):
        if not self.sel.obj:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz obiekt")
            return
        try:
            self.sel.obj.set_params_text(self.params.get())
        except Exception as e:
            messagebox.showerror("Parametry", str(e))
            return
        self.sel.obj.update_canvas(self.surface, self.canvas)
        self.sel._update_visual(self.canvas)
        self._reflect_selected_to_ui()
        self._push_history("Zastosuj parametry")

    def duplicate_selected(self, e=None):
        if not self.sel.obj:
            self._set_status("Brak zaznaczenia do duplikacji.")
            return
        o = self.sel.obj
        if isinstance(o, Line):
            dup = Line(o.x1 + 15, o.y1 + 15, o.x2 + 15, o.y2 + 15)
        elif isinstance(o, Rect):
            dup = Rect(o.x1 + 15, o.y1 + 15, o.x2 + 15, o.y2 + 15)
        else:
            dup = Circle(o.cx + 15, o.cy + 15, o.r)
        self._add_object(dup)
        self.sel.set(self.canvas, dup)
        self._reflect_selected_to_ui()
        self._push_history("Duplikacja")

    def on_delete(self, e=None):
        if not self.sel.obj:
            self._set_status("Brak zaznaczenia do usunięcia.")
            return
        # usuń wszystkie piksele z tagiem oid
        self.surface.clear_tag(self.sel.obj.oid)
        self.objects = [oo for oo in self.objects if oo is not self.sel.obj]
        self.sel.clear(self.canvas)
        self._push_history("Usuń")

    def clear_all(self):
        self.canvas.delete("all")
        self.objects.clear()
        self._clear_preview()
        self.sel.clear(self.canvas)
        # odtwórz surface (zniknął _surface po delete("all")):
        self.canvas._surface = self.surface = CanvasSurface(self.canvas)
        self._set_status("Wyczyszczono.")
        self._push_history("Wyczyszczono")

    # --- Plik JSON ---
    def save_json(self):
        path = save_scene(self.objects)
        if path:
            self._set_status(f"Zapisano: {path}")

    def load_json(self):
        path, objs = load_scene()
        if path is None:
            return
        self.canvas.delete("all")
        self.objects.clear()
        self._clear_preview()
        self.sel.clear(self.canvas)
        # odtwórz surface po czyszczeniu
        self.canvas._surface = self.surface = CanvasSurface(self.canvas)
        for o in objs:
            self._add_object(o)
        if objs:
            self.sel.set(self.canvas, objs[-1])
            self._reflect_selected_to_ui()
        self._set_status(f"Wczytano: {path}")
        self._push_history("Wczytano JSON")

    # --- Zdarzenia myszy ---
    def on_down(self, e):
        m = self.mode.get()
        if m in ("line", "rect", "circle"):
            self.mouse_start = (e.x, e.y)
            self._clear_preview()
            if m == "line":
                self.preview_id = self.canvas.create_line(
                    e.x,
                    e.y,
                    e.x,
                    e.y,
                    dash=(4, 2),
                    fill=COL_PREV,
                    width=1,
                    tags=("preview",),
                )
            elif m == "rect":
                self.preview_id = self.canvas.create_rectangle(
                    e.x,
                    e.y,
                    e.x,
                    e.y,
                    dash=(4, 2),
                    outline=COL_PREV,
                    width=1,
                    tags=("preview",),
                )
            else:
                self.preview_id = self.canvas.create_oval(
                    e.x,
                    e.y,
                    e.x,
                    e.y,
                    dash=(4, 2),
                    outline=COL_PREV,
                    width=1,
                    tags=("preview",),
                )
            return

        # uchwyt?
        item = self.canvas.find_withtag("current")
        if (
            item
            and self.sel.obj
            and self.sel.begin_resize_if_handle(self.canvas, item[0])
        ):
            return
        # piksel/kształt?
        if item:
            tags = self.canvas.gettags(item[0])
            if "shape" in tags:
                oid = next((t for t in tags if t.startswith("oid:")), None)
                if oid:
                    for o in self.objects:
                        if hasattr(o, "oid") and o.oid == oid:
                            self.sel.set(self.canvas, o)
                            self.sel.drag_last = (e.x, e.y)
                            self._reflect_selected_to_ui()
                            return
        self.sel.clear(self.canvas)

    def on_drag(self, e):
        # RESIZE
        if self.mode.get() == "select" and self.sel.resizing and self.sel.obj:
            self.sel.resize_to(self.canvas, e.x, e.y)
            self.params.delete(0, tk.END)
            self.params.insert(0, self.sel.obj.params_text())
            return
        # MOVE
        if self.mode.get() == "select" and self.sel.obj and self.sel.drag_last:
            dx = e.x - self.sel.drag_last[0]
            dy = e.y - self.sel.drag_last[1]
            if dx or dy:
                self.sel.move_by(self.canvas, dx, dy)
                self.sel.drag_last = (e.x, e.y)
                self._update_pixel_overlay()
                self.params.delete(0, tk.END)
                self.params.insert(0, self.sel.obj.params_text())
            return
        # PREVIEW
        if not (self.preview_id and self.mouse_start):
            return
        x0, y0 = self.mouse_start
        if self.mode.get() == "line":
            self.canvas.coords(self.preview_id, x0, y0, e.x, e.y)
        elif self.mode.get() == "rect":
            x1, y1, x2, y2 = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
            self.canvas.coords(self.preview_id, x1, y1, x2, y2)
        else:
            r = int(round(math.hypot(e.x - x0, e.y - y0)))
            x1, y1, x2, y2 = x0 - r, y0 - r, x0 + r, y0 + r
            self.canvas.coords(self.preview_id, x1, y1, x2, y2)

    def on_up(self, e):
        # end move
        if (
            self.mode.get() == "select"
            and self.sel.obj
            and self.sel.drag_last
            and not self.sel.resizing
        ):
            self.sel.drag_last = None
            self.sel._update_visual(self.canvas)
            self._reflect_selected_to_ui()
            self._push_history("Przesunięcie")
            return
        # end resize
        if self.mode.get() == "select" and self.sel.resizing:
            self.sel.end_resize(self.canvas)
            self._reflect_selected_to_ui()
            self._push_history("Zmiana rozmiaru")
            return
        self._update_pixel_overlay()
        # finalize draw
        if not self.mouse_start:
            return
        x0, y0 = self.mouse_start
        self._clear_preview()
        self.mouse_start = None
        m = self.mode.get()
        if m == "line":
            if (x0, y0) != (e.x, e.y):
                o = Line(x0, y0, e.x, e.y)
                self._add_object(o)
                self.sel.set(self.canvas, o)
                self._reflect_selected_to_ui()
                self._push_history("Rysunek myszą")
        elif m == "rect":
            x1, y1, x2, y2 = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
            if (x1, y1) != (x2, y2):
                o = Rect(x1, y1, x2, y2)
                self._add_object(o)
                self.sel.set(self.canvas, o)
                self._reflect_selected_to_ui()
                self._push_history("Rysunek myszą")
        elif m == "circle":
            r = int(round(math.hypot(e.x - x0, e.y - y0)))
            if r > 0:
                o = Circle(x0, y0, r)
                self._add_object(o)
                self.sel.set(self.canvas, o)
                self._reflect_selected_to_ui()
                self._push_history("Rysunek myszą")

    def _place_raster(self, w, h, pixels, src=None):
        from .shapes.image import RasterImage

        # domyślnie od (10,10)
        img = RasterImage(10, 10, w, h, pixels, src=src)
        self._add_object(img)
        self.sel.set(self.canvas, img)
        self._reflect_selected_to_ui()
        self._push_history("Wczytano PPM")

    def load_ppm_auto(self):
        from tkinter.filedialog import askopenfilename
        from tkinter import messagebox
        from .io.ppm import read_ppm_auto

        path = askopenfilename(
            filetypes=[("PPM", "*.ppm;*.pnm")], title="Wczytaj PPM (P3/P6)"
        )
        if not path:
            return
        try:
            w, h, pixels, fmt = read_ppm_auto(path)  # fmt: "P3" lub "P6"
        except Exception as e:
            messagebox.showerror("PPM", f"Nie udało się wczytać pliku PPM:\n{e}")
            return

        # wstaw obraz jako RasterImage (zachowujemy ścieżkę źródłową)
        self._place_raster(w, h, pixels, src=path)
        self._set_status(f"Wczytano {fmt}: {path}")

    def load_ppm_p3(self):
        from tkinter.filedialog import askopenfilename
        from .io.ppm import read_ppm_p3

        path = askopenfilename(
            filetypes=[("PPM P3", "*.ppm;*.pnm;*.pbm;*.pgm")], title="Wczytaj PPM P3"
        )
        if not path:
            return
        try:
            w, h, pixels = read_ppm_p3(path)
        except Exception as e:
            from tkinter import messagebox

            messagebox.showerror("PPM P3", f"Nie udało się wczytać:\n{e}")
            return
        self._place_raster(w, h, pixels, src=path)

    def load_ppm_p6(self):
        from tkinter.filedialog import askopenfilename
        from .io.ppm import read_ppm_p6

        path = askopenfilename(
            filetypes=[("PPM P6", "*.ppm;*.pnm")], title="Wczytaj PPM P6"
        )
        if not path:
            return
        try:
            w, h, pixels = read_ppm_p6(path)
        except Exception as e:
            from tkinter import messagebox

            messagebox.showerror("PPM P6", f"Nie udało się wczytać:\n{e}")
            return
        self._place_raster(w, h, pixels, src=path)

    # --- JPEG ---
    def load_jpeg(self):
        path = askopenfilename(
            filetypes=[("JPEG", "*.jpg;*.jpeg")], title="Wczytaj JPEG"
        )
        if not path:
            return
        try:
            w, h, pixels = read_jpeg(path)
        except Exception as e:
            messagebox.showerror("JPEG", f"Nie udało się wczytać JPEG:\n{e}")
            return
        from .shapes.image import RasterImage

        img = RasterImage(
            10, 10, src_w=w, src_h=h, src_pixels=pixels, w=w, h=h, src=path
        )
        self._add_object(img)
        self.sel.set(self.canvas, img)
        self._reflect_selected_to_ui()
        self._push_history("Wczytano JPEG")

    def save_as_jpeg(self):
        if not self.sel.obj:
            messagebox.showinfo("JPEG", "Zaznacz obraz (PPM/JPEG).")
            return
        obj = self.sel.obj
        t = type(obj).__name__.lower()
        if t not in ("rasterimage", "image"):
            messagebox.showinfo("JPEG", "Zaznacz obraz (PPM/JPEG).")
            return
        # wybór jakości
        top = tk.Toplevel(self)
        top.title("Zapis JPEG – jakość")
        ttk.Label(top, text="Jakość (1–100):").pack(padx=12, pady=(12, 4))
        qvar = tk.IntVar(value=90)
        qscale = ttk.Scale(
            top,
            from_=1,
            to=100,
            orient="horizontal",
            command=lambda v: qvar.set(int(float(v))),
        )
        qscale.set(90)
        qscale.pack(padx=12, pady=4, fill="x")
        btns = ttk.Frame(top)
        btns.pack(pady=8)

        def do_save():
            path = asksaveasfilename(
                defaultextension=".jpg",
                filetypes=[("JPEG", "*.jpg;*.jpeg")],
                title="Zapisz jako JPEG",
            )
            if not path:
                return
            try:
                # zapisujemy BIEŻĄCY widok (w,h) → przeskalowane piksele (nearest)
                # odtwarzamy piksele podstawowe i skalujemy do w,h:
                from .shapes.image import RasterImage

                if isinstance(obj, RasterImage):
                    if obj.w == obj.src_w and obj.h == obj.src_h:
                        pixels = obj.src_pixels
                        write_jpeg(
                            path, obj.src_w, obj.src_h, pixels, quality=qvar.get()
                        )
                    else:
                        # przeskaluj nearest do obj.w,obj.h
                        dst = obj._scale_nearest(obj.w, obj.h)
                        write_jpeg(path, obj.w, obj.h, dst, quality=qvar.get())
                else:
                    messagebox.showerror(
                        "JPEG", "Wybrany obiekt nie jest obrazem rastrowym."
                    )
                    return
                messagebox.showinfo("JPEG", f"Zapisano: {path}")
                top.destroy()
            except Exception as e:
                messagebox.showerror("JPEG", f"Nie udało się zapisać JPEG:\n{e}")

        ttk.Button(btns, text="Zapisz", command=do_save).pack(side="left", padx=6)
        ttk.Button(btns, text="Anuluj", command=top.destroy).pack(side="left", padx=6)

    # --- Levels (liniowe skalowanie kolorów) ---
    def apply_levels(self):
        if not self.sel.obj:
            messagebox.showinfo("Levels", "Zaznacz obraz.")
            return
        obj = self.sel.obj
        from .shapes.image import RasterImage

        if not isinstance(obj, RasterImage):
            messagebox.showinfo("Levels", "Zaznacz obraz PPM/JPEG.")
            return
        try:
            mins, maxs = self.levels_entry.get().replace(";", ",").split(",")
            in_min, in_max = int(mins.strip()), int(maxs.strip())
        except Exception:
            messagebox.showerror("Levels", "Podaj dwie liczby: in_min,in_max (0..255).")
            return
        try:
            obj.src_pixels = linear_color_scale(obj.src_pixels, in_min, in_max)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Levels")
        except Exception as e:
            messagebox.showerror("Levels", f"Błąd skalowania kolorów:\n{e}")

    # --- Okno kostki RGB 3D ---
    def open_rgb_cube_points(self):
        """Otwórz prostą kostkę RGB (kropki)."""
        if (
            self.rgb_cube_points_win is not None
            and self.rgb_cube_points_win.winfo_exists()
        ):
            self.rgb_cube_points_win.lift()
            self.rgb_cube_points_win.focus_set()
            return
        self.rgb_cube_points_win = RGBCubePointsWindow(self)

    def open_rgb_cube_slice(self):
        """Otwiera okno pełnej kostki RGB z cięciami."""
        if (
            self.rgb_cube_slice_win is not None
            and self.rgb_cube_slice_win.winfo_exists()
        ):
            self.rgb_cube_slice_win.lift()
            self.rgb_cube_slice_win.focus_set()
            return

        self.rgb_cube_slice_win = RGBCubeSliceWindow(self)

    def open_hsv_cone_points(self):
        """Otwórz prosty stożek HSV (punkty)."""
        if (
            self.hsv_cone_points_win is not None
            and self.hsv_cone_points_win.winfo_exists()
        ):
            self.hsv_cone_points_win.lift()
            self.hsv_cone_points_win.focus_set()
            return
        self.hsv_cone_points_win = HSVConePointsWindow(self)

    def open_hsv_cone_full(self):
        """Otwórz pełny stożek HSV (istniejący HSVConeWindow)."""
        if self.hsv_cone_win is not None and self.hsv_cone_win.winfo_exists():
            self.hsv_cone_win.lift()
            self.hsv_cone_win.focus_set()
            return
        self.hsv_cone_win = HSVConeWindow(self)

    # --- Panel konwersji kolorów RGB/CMYK ---

    def _build_color_converter_panel(self, parent, row=0):
        """Panel do konwersji RGB <-> CMYK (suwaki + pola tekstowe + podgląd).
        parent: ramka (u Ciebie to 'panel'), row: numer wiersza grid.
        """
        import tkinter as tk
        from tkinter import ttk

        frame = ttk.LabelFrame(parent, text="Konwersja kolorów RGB / CMYK")
        frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)

        # Tryb wejściowy: RGB / CMYK
        modebar = ttk.Frame(frame)
        modebar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        ttk.Label(modebar, text="Tryb wejściowy:").pack(side="left")
        ttk.Radiobutton(
            modebar,
            text="RGB",
            variable=self.color_mode,
            value="RGB",
            command=self._on_color_mode_changed,
        ).pack(side="left", padx=6)
        ttk.Radiobutton(
            modebar,
            text="CMYK",
            variable=self.color_mode,
            value="CMYK",
            command=self._on_color_mode_changed,
        ).pack(side="left", padx=6)

        # Ramka na wejścia (zamiennie RGB/CMYK)
        self.color_input_frame = ttk.Frame(frame)
        self.color_input_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        self.color_input_frame.columnconfigure(1, weight=1)

        # Zbuduj oba zestawy wejść
        self._build_rgb_inputs(self.color_input_frame)
        self._build_cmyk_inputs(self.color_input_frame)

        # Startowo pokaż RGB
        self._show_rgb_inputs()

        # Podgląd + wyniki konwersji
        preview = ttk.Frame(frame)
        preview.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))
        ttk.Label(preview, text="Podgląd:").grid(row=0, column=0, sticky="w")

        self.color_preview = tk.Canvas(
            preview, width=68, height=44, bd=1, relief="sunken"
        )
        self.color_preview.grid(row=0, column=1, rowspan=2, padx=6, pady=2, sticky="w")

        self.result_label_1 = ttk.Label(preview, text="RGB: -")
        self.result_label_1.grid(row=0, column=2, sticky="w", padx=6)

        self.result_label_2 = ttk.Label(preview, text="CMYK: -")
        self.result_label_2.grid(row=1, column=2, sticky="w", padx=6)

        # Pierwsze przeliczenie i odświeżenie podglądu
        self._update_color_conversion()

    def _build_rgb_inputs(self, parent):
        """Wejścia RGB: suwaki 0-255 + pola tekstowe."""
        from tkinter import ttk

        self.rgb_inputs_frame = ttk.Frame(parent)
        # R
        ttk.Label(self.rgb_inputs_frame, text="R:").grid(row=0, column=0, sticky="e")
        self.rgb_r_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("R", v),
        )
        self.rgb_r_scale.set(self.rgb_r_var.get())
        self.rgb_r_scale.grid(row=0, column=1, sticky="ew", padx=6)
        self.rgb_r_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_r_entry.insert(0, str(self.rgb_r_var.get()))
        self.rgb_r_entry.grid(row=0, column=2)
        self.rgb_r_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("R"))
        self.rgb_r_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("R"))

        # G
        ttk.Label(self.rgb_inputs_frame, text="G:").grid(row=1, column=0, sticky="e")
        self.rgb_g_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("G", v),
        )
        self.rgb_g_scale.set(self.rgb_g_var.get())
        self.rgb_g_scale.grid(row=1, column=1, sticky="ew", padx=6)
        self.rgb_g_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_g_entry.insert(0, str(self.rgb_g_var.get()))
        self.rgb_g_entry.grid(row=1, column=2)
        self.rgb_g_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("G"))
        self.rgb_g_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("G"))

        # B
        ttk.Label(self.rgb_inputs_frame, text="B:").grid(row=2, column=0, sticky="e")
        self.rgb_b_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("B", v),
        )
        self.rgb_b_scale.set(self.rgb_b_var.get())
        self.rgb_b_scale.grid(row=2, column=1, sticky="ew", padx=6)
        self.rgb_b_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_b_entry.insert(0, str(self.rgb_b_var.get()))
        self.rgb_b_entry.grid(row=2, column=2)
        self.rgb_b_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("B"))
        self.rgb_b_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("B"))

        self.rgb_inputs_frame.columnconfigure(1, weight=1)

    def _build_cmyk_inputs(self, parent):
        """Wejścia CMYK: suwaki 0-100% + pola tekstowe (wartości w %)."""
        from tkinter import ttk

        self.cmyk_inputs_frame = ttk.Frame(parent)

        # C
        ttk.Label(self.cmyk_inputs_frame, text="C (%):").grid(
            row=0, column=0, sticky="e"
        )
        self.cmyk_c_scale = ttk.Scale(
            self.cmyk_inputs_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda v: self._on_cmyk_slider_changed("C", v),
        )
        self.cmyk_c_scale.set(self.cmyk_c_var.get())
        self.cmyk_c_scale.grid(row=0, column=1, sticky="ew", padx=6)
        self.cmyk_c_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_c_entry.insert(0, f"{self.cmyk_c_var.get():.1f}")
        self.cmyk_c_entry.grid(row=0, column=2)
        self.cmyk_c_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("C"))
        self.cmyk_c_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("C"))

        # M
        ttk.Label(self.cmyk_inputs_frame, text="M (%):").grid(
            row=1, column=0, sticky="e"
        )
        self.cmyk_m_scale = ttk.Scale(
            self.cmyk_inputs_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda v: self._on_cmyk_slider_changed("M", v),
        )
        self.cmyk_m_scale.set(self.cmyk_m_var.get())
        self.cmyk_m_scale.grid(row=1, column=1, sticky="ew", padx=6)
        self.cmyk_m_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_m_entry.insert(0, f"{self.cmyk_m_var.get():.1f}")
        self.cmyk_m_entry.grid(row=1, column=2)
        self.cmyk_m_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("M"))
        self.cmyk_m_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("M"))

        # Y
        ttk.Label(self.cmyk_inputs_frame, text="Y (%):").grid(
            row=2, column=0, sticky="e"
        )
        self.cmyk_y_scale = ttk.Scale(
            self.cmyk_inputs_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda v: self._on_cmyk_slider_changed("Y", v),
        )
        self.cmyk_y_scale.set(self.cmyk_y_var.get())
        self.cmyk_y_scale.grid(row=2, column=1, sticky="ew", padx=6)
        self.cmyk_y_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_y_entry.insert(0, f"{self.cmyk_y_var.get():.1f}")
        self.cmyk_y_entry.grid(row=2, column=2)
        self.cmyk_y_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("Y"))
        self.cmyk_y_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("Y"))

        # K
        ttk.Label(self.cmyk_inputs_frame, text="K (%):").grid(
            row=3, column=0, sticky="e"
        )
        self.cmyk_k_scale = ttk.Scale(
            self.cmyk_inputs_frame,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda v: self._on_cmyk_slider_changed("K", v),
        )
        self.cmyk_k_scale.set(self.cmyk_k_var.get())
        self.cmyk_k_scale.grid(row=3, column=1, sticky="ew", padx=6)
        self.cmyk_k_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_k_entry.insert(0, f"{self.cmyk_k_var.get():.1f}")
        self.cmyk_k_entry.grid(row=3, column=2)
        self.cmyk_k_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("K"))
        self.cmyk_k_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("K"))

        self.cmyk_inputs_frame.columnconfigure(1, weight=1)

    # --- Przełączanie widoku wejść ---

    def _show_rgb_inputs(self):
        self.cmyk_inputs_frame.grid_forget()
        self.rgb_inputs_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

    def _show_cmyk_inputs(self):
        self.rgb_inputs_frame.grid_forget()
        self.cmyk_inputs_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

    def _on_color_mode_changed(self):
        mode = self.color_mode.get()
        if mode == "RGB":
            # przechodzimy z CMYK -> RGB, więc RGB ma odpowiadać aktualnemu CMYK
            self._sync_rgb_from_cmyk()
            self._show_rgb_inputs()
        else:
            # przechodzimy z RGB -> CMYK, więc CMYK ma odpowiadać aktualnemu RGB
            self._sync_cmyk_from_rgb()
            self._show_cmyk_inputs()

        # Po synchronizacji odświeżamy podgląd i etykiety
        self._update_color_conversion()

    # --- Handlery RGB ---

    def _on_rgb_slider_changed(self, channel, value):
        v = int(float(value))
        if channel == "R":
            self.rgb_r_var.set(v)
            self.rgb_r_entry.delete(0, "end")
            self.rgb_r_entry.insert(0, str(v))
        elif channel == "G":
            self.rgb_g_var.set(v)
            self.rgb_g_entry.delete(0, "end")
            self.rgb_g_entry.insert(0, str(v))
        else:
            self.rgb_b_var.set(v)
            self.rgb_b_entry.delete(0, "end")
            self.rgb_b_entry.insert(0, str(v))
        self._update_color_conversion()

    def _on_rgb_entry_changed(self, channel):
        entry = {"R": self.rgb_r_entry, "G": self.rgb_g_entry, "B": self.rgb_b_entry}[
            channel
        ]
        try:
            v = int(entry.get())
        except ValueError:
            v = 0
        v = max(0, min(255, v))
        entry.delete(0, "end")
        entry.insert(0, str(v))
        if channel == "R":
            self.rgb_r_var.set(v)
            self.rgb_r_scale.set(v)
        elif channel == "G":
            self.rgb_g_var.set(v)
            self.rgb_g_scale.set(v)
        else:
            self.rgb_b_var.set(v)
            self.rgb_b_scale.set(v)
        self._update_color_conversion()

    # --- Handlery CMYK ---

    def _on_cmyk_slider_changed(self, channel, value):
        v = max(0.0, min(100.0, float(value)))
        if channel == "C":
            self.cmyk_c_var.set(v)
            self.cmyk_c_entry.delete(0, "end")
            self.cmyk_c_entry.insert(0, f"{v:.1f}")
        elif channel == "M":
            self.cmyk_m_var.set(v)
            self.cmyk_m_entry.delete(0, "end")
            self.cmyk_m_entry.insert(0, f"{v:.1f}")
        elif channel == "Y":
            self.cmyk_y_var.set(v)
            self.cmyk_y_entry.delete(0, "end")
            self.cmyk_y_entry.insert(0, f"{v:.1f}")
        else:
            self.cmyk_k_var.set(v)
            self.cmyk_k_entry.delete(0, "end")
            self.cmyk_k_entry.insert(0, f"{v:.1f}")
        self._update_color_conversion()

    def _on_cmyk_entry_changed(self, channel):
        entry = {
            "C": self.cmyk_c_entry,
            "M": self.cmyk_m_entry,
            "Y": self.cmyk_y_entry,
            "K": self.cmyk_k_entry,
        }[channel]
        try:
            v = float(entry.get().replace(",", "."))
        except ValueError:
            v = 0.0
        v = max(0.0, min(100.0, v))
        entry.delete(0, "end")
        entry.insert(0, f"{v:.1f}")
        if channel == "C":
            self.cmyk_c_var.set(v)
            self.cmyk_c_scale.set(v)
        elif channel == "M":
            self.cmyk_m_var.set(v)
            self.cmyk_m_scale.set(v)
        elif channel == "Y":
            self.cmyk_y_var.set(v)
            self.cmyk_y_scale.set(v)
        else:
            self.cmyk_k_var.set(v)
            self.cmyk_k_scale.set(v)
        self._update_color_conversion()

    # --- Przeliczanie + podgląd ---

    def _update_color_conversion(self):
        mode = self.color_mode.get()
        if mode == "RGB":
            r, g, b = self.rgb_r_var.get(), self.rgb_g_var.get(), self.rgb_b_var.get()
            c, m, y, k = rgb_to_cmyk(r, g, b)
            self._update_color_preview(r, g, b)
            self.result_label_1.config(text=f"RGB: {r}, {g}, {b}")
            self.result_label_2.config(
                text=f"CMYK: {c*100:.1f}%, {m*100:.1f}%, {y*100:.1f}%, {k*100:.1f}%"
            )
        else:
            c = self.cmyk_c_var.get() / 100.0
            m = self.cmyk_m_var.get() / 100.0
            y = self.cmyk_y_var.get() / 100.0
            k = self.cmyk_k_var.get() / 100.0
            r, g, b = cmyk_to_rgb(c, m, y, k)
            self._update_color_preview(r, g, b)
            self.result_label_1.config(text=f"RGB: {r}, {g}, {b}")
            self.result_label_2.config(
                text=f"CMYK: {self.cmyk_c_var.get():.1f}%, {self.cmyk_m_var.get():.1f}%, {self.cmyk_y_var.get():.1f}%, {self.cmyk_k_var.get():.1f}%"
            )

    def _update_color_preview(self, r, g, b):
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.color_preview.delete("all")
        self.color_preview.create_rectangle(0, 0, 68, 44, fill=hex_color, outline="")

    def _sync_cmyk_from_rgb(self):
        """Ustaw CMYK tak, żeby odpowiadał aktualnemu RGB."""
        r = self.rgb_r_var.get()
        g = self.rgb_g_var.get()
        b = self.rgb_b_var.get()

        c, m, y, k = rgb_to_cmyk(r, g, b)

        # zapisujemy w % (0-100)
        c_p = c * 100.0
        m_p = m * 100.0
        y_p = y * 100.0
        k_p = k * 100.0

        self.cmyk_c_var.set(c_p)
        self.cmyk_m_var.set(m_p)
        self.cmyk_y_var.set(y_p)
        self.cmyk_k_var.set(k_p)

        # zsynchronizuj suwaki i pola tekstowe
        self.cmyk_c_scale.set(c_p)
        self.cmyk_m_scale.set(m_p)
        self.cmyk_y_scale.set(y_p)
        self.cmyk_k_scale.set(k_p)

        self.cmyk_c_entry.delete(0, "end")
        self.cmyk_c_entry.insert(0, f"{c_p:.1f}")
        self.cmyk_m_entry.delete(0, "end")
        self.cmyk_m_entry.insert(0, f"{m_p:.1f}")
        self.cmyk_y_entry.delete(0, "end")
        self.cmyk_y_entry.insert(0, f"{y_p:.1f}")
        self.cmyk_k_entry.delete(0, "end")
        self.cmyk_k_entry.insert(0, f"{k_p:.1f}")

    def _sync_rgb_from_cmyk(self):
        """Ustaw RGB tak, żeby odpowiadał aktualnemu CMYK."""
        c = self.cmyk_c_var.get() / 100.0
        m = self.cmyk_m_var.get() / 100.0
        y = self.cmyk_y_var.get() / 100.0
        k = self.cmyk_k_var.get() / 100.0

        r, g, b = cmyk_to_rgb(c, m, y, k)

        self.rgb_r_var.set(r)
        self.rgb_g_var.set(g)
        self.rgb_b_var.set(b)

        self.rgb_r_scale.set(r)
        self.rgb_g_scale.set(g)
        self.rgb_b_scale.set(b)

        self.rgb_r_entry.delete(0, "end")
        self.rgb_r_entry.insert(0, str(r))
        self.rgb_g_entry.delete(0, "end")
        self.rgb_g_entry.insert(0, str(g))
        self.rgb_b_entry.delete(0, "end")
        self.rgb_b_entry.insert(0, str(b))

    # --- Zoom / Pan ---
    def change_zoom(self, delta):
        # Zmieniamy rozmiar WYBRANEGO obrazu (RasterImage) – całkowity zoom o krok (±1) → x2 / x0.5?
        # Prościej: zoom krokowy o współczynnik 1.25 / 0.8 albo całkowity (1.0 → 2.0 → 4.0).
        # Tutaj zrobimy zoom całkowity: mnożnik 2 dla +, dzielnik 2 dla −.
        if not self.sel.obj:
            self._set_status("Zaznacz obraz, aby zmienić zoom.")
            return
        from .shapes.image import RasterImage

        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            self._set_status("Zoom działa na obrazach PPM/JPEG.")
            return
        if delta > 0:
            new_w = obj.w * 2
            new_h = obj.h * 2
        else:
            new_w = max(1, obj.w // 2)
            new_h = max(1, obj.h // 2)
        obj.w, obj.h = int(new_w), int(new_h)
        obj.update_canvas(self.surface, self.canvas)
        self.sel._update_visual(self.canvas)
        self._update_pixel_overlay()
        self._reflect_selected_to_ui()
        self._push_history("Zoom")

    def _on_motion(self, e):
        # status
        self._set_status(f"x={e.x}, y={e.y} | tryb: {self.mode.get()}")
        self._update_pixel_overlay(cursor=(e.x, e.y))
        # overlay RGB tylko dla obrazów
        if not self._pix_overlay_on:
            return
        if not self.sel.obj:
            self.canvas.delete("pixlbl")
            return
        obj = self.sel.obj
        t = type(obj).__name__.lower()
        if t not in ("rasterimage", "image"):
            self.canvas.delete("pixlbl")
            return
        px = obj.pixel_at_canvas(e.x, e.y)
        if px is None:
            self.canvas.delete("pixlbl")
            return
        # pokaż małą etykietę nad pikselem – i tylko przy sensownym zoomie (duża waga: <= tworzyć mało itemów)
        # Zamiast gęsto na całym obszarze, pokazujemy TYLKO pixel pod kursorem:
        self.canvas.delete("pixlbl")
        r, g, b = px
        txt = f"({r},{g},{b})"
        self.canvas.create_text(
            e.x + 30,
            e.y - 12,
            text=txt,
            anchor="w",
            font=("", 9, "bold"),
            tags=("pixlbl",),
            fill="#000",
        )
        # kropka w miejscu piksela
        self.canvas.create_oval(
            e.x - 1,
            e.y - 1,
            e.x + 1,
            e.y + 1,
            fill="#000",
            outline="",
            tags=("pixlbl",),
        )

    def _update_pixel_overlay(self, cursor=None):
        # czyścimy poprzedni overlay
        self.canvas.delete("pixlbl")

        if self._pix_overlay_mode == "off":
            return
        if not self.sel.obj:
            return

        obj = self.sel.obj
        t = type(obj).__name__.lower()
        if t not in ("rasterimage", "image"):
            return

        # rozmiar jednego wyświetlanego piksela
        if obj.w is None or obj.h is None or obj.w == 0 or obj.h == 0:
            return
        px_w = obj.w / obj.src_w
        px_h = obj.h / obj.src_h
        big_enough = (
            px_w >= self._pix_overlay_threshold and px_h >= self._pix_overlay_threshold
        )

        # 1) zawsze: RGB pod kursorem (jeśli jest)
        if cursor is not None:
            r = obj.pixel_at_canvas(*cursor)
            if r is not None:
                r0, g0, b0 = r
                self.canvas.create_text(
                    cursor[0] + 30,
                    cursor[1] - 12,
                    text=f"({r0},{g0},{b0})",
                    anchor="w",
                    font=("", 9, "bold"),
                    tags=("pixlbl",),
                    fill="#000",
                )
                self.canvas.create_oval(
                    cursor[0] - 1,
                    cursor[1] - 1,
                    cursor[0] + 1,
                    cursor[1] + 1,
                    fill="#000",
                    outline="",
                    tags=("pixlbl",),
                )

        # 2) przy dużym zoomie: etykieta na KAŻDYM widocznym pikselu
        if not big_enough:
            return

        # ograniczamy się do bboxu obrazu (widoczne piksele)
        x1, y1, x2, y2 = obj.bbox()
        # „snapping” do granic wyświetlanych pikseli (siatka)
        # iterujemy po pikselach źródłowych, mapując je na wyświetlane prostokąty o rozmiarze px_w x px_h
        # Aby nie przerysowywać całej sceny, robimy etykiety w obrębie widocznych pikseli (prostokąty mieszczące się w bbox).
        for sy in range(obj.src_h):
            # y-środek wyświetlanego piksela (w canvas coords)
            cy = int(obj.y + sy * px_h + px_h / 2)
            if cy < y1 or cy > y2:
                continue
            row_base = sy * obj.src_w
            for sx in range(obj.src_w):
                cx = int(obj.x + sx * px_w + px_w / 2)
                if cx < x1 or cx > x2:
                    continue
                rgb = obj.src_pixels[row_base + sx]
                self.canvas.create_text(
                    cx,
                    cy,
                    text=f"{rgb[0]},{rgb[1]},{rgb[2]}",
                    anchor="c",
                    font=("", 8),
                    tags=("pixlbl",),
                    fill="#000",
                )
