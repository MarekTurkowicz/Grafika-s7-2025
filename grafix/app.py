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
