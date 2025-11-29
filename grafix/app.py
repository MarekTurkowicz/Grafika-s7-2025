import tkinter as tk
from tkinter import ttk, messagebox
import math
import colorsys

from .constants import APP_TITLE, APP_SIZE, COL_PREV
from .utils import parts
from .selection import Selection
from .shapes import Line, Rect, Circle, shape_from_dict
from .io import save_scene, load_scene, scene_to_dict
from .render import CanvasSurface

from tkinter.filedialog import asksaveasfilename, askopenfilename
from .io.jpeg_io import read_jpeg, write_jpeg
from .image_ops import linear_color_scale


from .rgbcube.cube_points import RGBCubePointsWindow
from .rgbcube.cube_sliced import RGBCubeSliceWindow
from .hsvcone.hsv_cone_window import HSVConeWindow
from .hsvcone.cone_points import HSVConePointsWindow

from .image_ops import linear_color_scale
from .image_ops import (
    add_constant,
    mul_constant,
    div_constant,
    change_brightness,
    to_grayscale_avg,
    to_grayscale_luma,
)
from .filters import (
    filter_box_blur,
    filter_median,
    filter_sobel,
    filter_sharpen,
    filter_gaussian,
    filter_custom,
)
from .histogram import compute_histogram, histogram_stretch, histogram_equalize
from .thresholds import (
    threshold_manual,
    threshold_percent_black,
    threshold_mean_iterative,
    threshold_entropy,
)
from .bezier.editor import BezierEditorWindow


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.minsize(1600, 1200)

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
        self._in_color_update = False

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

        self.point_add_var = tk.IntVar(value=0)
        self.point_mul_var = tk.DoubleVar(value=1.0)
        self.point_div_var = tk.DoubleVar(value=1.0)
        self.brightness_var = tk.IntVar(value=0)

        # --- (HISTOGRAM / BINARYZACJA) ---
        self.thresh_manual_var = tk.IntVar(value=128)
        self.thresh_percent_var = tk.DoubleVar(value=50.0)  # Percent Black (%)

        # --- Bezier Editor ---
        self.bezier_editor_win = None
        self.polygon_editor_win = None  # okno do zadania 7 (wielokąty)

        # --- Analiza koloru / terenów zielonych ---
        self.color_h_min_var = tk.DoubleVar(
            value=70.0
        )  # początek zakresu H (stopnie) – zieleń ~70°
        self.color_h_max_var = tk.DoubleVar(
            value=160.0
        )  # koniec zakresu H – zieleń ~160°
        self.color_s_min_var = tk.DoubleVar(value=0.2)  # minimalne nasycenie
        self.color_v_min_var = tk.DoubleVar(value=0.2)  # minimalna jasność
        self.green_result_var = tk.StringVar(value="Brak obliczeń.")

        self._build_ui()
        self._bind_canvas()

        # powierzchnia rysująca (Canvas)
        self.surface = CanvasSurface(self.canvas)
        # hook – selection używa cv._surface
        self.canvas._surface = self.surface

        self._push_history("Start")

    def _build_ui(self):
        # --- Główny układ 3 kolumn ---
        self.columnconfigure(0, weight=1)  # canvas
        self.columnconfigure(1, weight=0)  # panel 1 – zad. 1–3 + 4a
        self.columnconfigure(2, weight=0)  # panel 2 – zad. 4b + 5 + 6
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        # ===== LEWA STRONA: CANVAS =====
        self.canvas = tk.Canvas(
            self, bg="white", highlightthickness=1, highlightbackground="#ccc"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        panel1 = ttk.Frame(self, padding=8)
        panel1.grid(row=0, column=1, sticky="ns", padx=4, pady=8)
        panel1.columnconfigure(0, weight=1)

        # --- Rysowanie (zad. 1) ---
        ttk.Label(panel1, text="Rysowanie", font=("", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        modebar = ttk.Frame(panel1)
        modebar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        for text, value in [
            ("Select", "select"),
            ("Line", "line"),
            ("Rect", "rect"),
            ("Circle", "circle"),
        ]:
            ttk.Radiobutton(
                modebar,
                text=text,
                value=value,
                variable=self.mode,
                command=self._on_mode_change,
            ).pack(side="left", padx=2)

        self.params_label = ttk.Label(panel1, text="Parametry:")
        self.params_label.grid(row=2, column=0, sticky="w")
        self.params = ttk.Entry(panel1)
        self.params.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        rbtns = ttk.Frame(panel1)
        rbtns.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(rbtns, text="Rysuj", command=self.draw_from_fields).pack(side="left")
        ttk.Button(rbtns, text="Zastosuj", command=self.apply_to_selected).pack(
            side="left", padx=4
        )
        ttk.Button(rbtns, text="Wyczyść", command=self.clear_all).pack(
            side="left", padx=4
        )

        # --- Pliki sceny (JSON) (zad. 1) ---
        jsonrow = ttk.Frame(panel1)
        jsonrow.grid(row=5, column=0, sticky="ew")
        ttk.Button(jsonrow, text="Zapisz JSON", command=self.save_json).pack(
            side="left"
        )
        ttk.Button(jsonrow, text="Wczytaj JSON", command=self.load_json).pack(
            side="left", padx=4
        )

        # --- PPM / JPEG (zad. 2) ---
        ttk.Button(panel1, text="Wczytaj PPM (P3/P6)", command=self.load_ppm_auto).grid(
            row=6, column=0, sticky="ew", pady=(8, 0)
        )

        jpgrow = ttk.Frame(panel1)
        jpgrow.grid(row=7, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(jpgrow, text="Wczytaj JPEG", command=self.load_jpeg).pack(
            side="left"
        )
        ttk.Button(jpgrow, text="Zapisz JPEG", command=self.save_as_jpeg).pack(
            side="left", padx=4
        )

        # --- Levels (zad. 2 – liniowe skalowanie kolorów) ---
        levels = ttk.Frame(panel1)
        levels.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(levels, text="Levels (min,max):").pack(side="left")
        self.levels_entry = ttk.Entry(levels, width=10)
        self.levels_entry.insert(0, "0,255")
        self.levels_entry.pack(side="left", padx=4)
        ttk.Button(levels, text="OK", command=self.apply_levels).pack(side="left")

        # --- Zoom (zad. 2 – powiększanie) ---
        zoom = ttk.Frame(panel1)
        zoom.grid(row=9, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(zoom, text="Zoom:").pack(side="left")
        ttk.Button(zoom, text="−", width=3, command=lambda: self.change_zoom(-1)).pack(
            side="left"
        )
        ttk.Button(zoom, text="+", width=3, command=lambda: self.change_zoom(+1)).pack(
            side="left", padx=4
        )

        # --- Konwerter RGB/CMYK (zad. 3a) ---
        self._build_color_converter_panel(panel1, row=10)

        # --- Kostki RGB 3D (zad. 3b) ---
        cube = ttk.LabelFrame(panel1, text="Kostki RGB 3D")
        cube.grid(row=11, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(cube, text="Kropki", command=self.open_rgb_cube_points).pack(
            side="left", padx=4, pady=2
        )
        ttk.Button(cube, text="Pełna (cięcia)", command=self.open_rgb_cube_slice).pack(
            side="left", padx=4, pady=2
        )

        # --- Stożki HSV 3D (zad. 3c) ---
        hsv = ttk.LabelFrame(panel1, text="Stożki HSV 3D")
        hsv.grid(row=12, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(hsv, text="Punkty", command=self.open_hsv_cone_points).pack(
            side="left", padx=4, pady=2
        )
        ttk.Button(hsv, text="Pełny", command=self.open_hsv_cone_full).pack(
            side="left", padx=4, pady=2
        )

        # --- Przekształcenia punktowe (zad. 4a) ---
        pt = ttk.LabelFrame(panel1, text="Przekształcenia punktowe (4a)")
        pt.grid(row=13, column=0, sticky="ew", pady=(6, 0))

        ttk.Label(pt, text="Dodaj/odejmij:").grid(row=0, column=0)
        ttk.Entry(pt, textvariable=self.point_add_var, width=8).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(pt, text="OK", command=self.apply_point_add).grid(
            row=0, column=2, padx=4
        )

        ttk.Label(pt, text="Mnożenie ×:").grid(row=1, column=0)
        ttk.Entry(pt, textvariable=self.point_mul_var, width=8).grid(
            row=1, column=1, padx=4
        )
        ttk.Button(pt, text="OK", command=self.apply_point_mul).grid(
            row=1, column=2, padx=4
        )

        ttk.Label(pt, text="Dzielenie ÷:").grid(row=2, column=0)
        ttk.Entry(pt, textvariable=self.point_div_var, width=8).grid(
            row=2, column=1, padx=4
        )
        ttk.Button(pt, text="OK", command=self.apply_point_div).grid(
            row=2, column=2, padx=4
        )

        ttk.Label(pt, text="Jasność:").grid(row=3, column=0)
        ttk.Entry(pt, textvariable=self.brightness_var, width=8).grid(
            row=3, column=1, padx=4
        )
        ttk.Button(pt, text="OK", command=self.apply_brightness).grid(
            row=3, column=2, padx=4
        )

        gray = ttk.Frame(pt)
        gray.grid(row=4, column=0, columnspan=3, pady=(4, 0))
        ttk.Button(gray, text="Szarość (średnia)", command=self.apply_gray_avg).pack(
            side="left", padx=4
        )
        ttk.Button(gray, text="Szarość (luma)", command=self.apply_gray_luma).pack(
            side="left", padx=4
        )

        # ======================================================================
        # == PANEL 2 (kolumna 2): Zadanie 4b (filtry) + zadanie 5 + 6 (Bézier)
        # ======================================================================
        panel2 = ttk.Frame(self, padding=8)
        panel2.grid(row=0, column=2, sticky="ns", padx=(4, 8), pady=8)
        panel2.columnconfigure(0, weight=1)

        # --- Filtry (zad. 4b) ---
        filt = ttk.LabelFrame(panel2, text="Filtry (4b)")
        filt.grid(row=0, column=0, sticky="ew")

        ttk.Button(filt, text="Uśredniający", command=self.apply_filter_box).pack(
            fill="x", pady=1
        )
        ttk.Button(filt, text="Medianowy", command=self.apply_filter_median).pack(
            fill="x", pady=1
        )
        ttk.Button(
            filt, text="Sobel (krawędzie)", command=self.apply_filter_sobel
        ).pack(fill="x", pady=1)
        ttk.Button(filt, text="Wyostrzający", command=self.apply_filter_sharpen).pack(
            fill="x", pady=1
        )
        ttk.Button(
            filt, text="Gauss (rozmycie)", command=self.apply_filter_gaussian
        ).pack(fill="x", pady=1)

        ttk.Label(filt, text="Maska własna:").pack(fill="x", pady=(6, 0))
        self.custom_kernel_text = tk.Text(filt, height=4, width=24)
        self.custom_kernel_text.pack(fill="x", pady=2)
        self.custom_kernel_text.insert("1.0", "0 -1 0\n-1 5 -1\n0 -1 0")
        ttk.Button(
            filt, text="Zastosuj maskę własną", command=self.apply_filter_custom
        ).pack(fill="x", pady=(2, 2))

        # --- Histogram / Binaryzacja (zad. 5) ---
        hist = ttk.LabelFrame(panel2, text="Histogram / Binaryzacja (5)")
        hist.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        hist.columnconfigure(1, weight=1)

        # Histogram – 3 przyciski
        hrow = ttk.Frame(hist)
        hrow.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(2, 4))
        ttk.Button(hrow, text="Pokaż", command=self.show_histogram).pack(
            side="left", padx=2
        )
        ttk.Button(hrow, text="Rozszerz", command=self.apply_hist_stretch).pack(
            side="left", padx=2
        )
        ttk.Button(hrow, text="Equalizacja", command=self.apply_hist_equalize).pack(
            side="left", padx=2
        )

        # Binaryzacja ręczna
        brow1 = ttk.Frame(hist)
        brow1.grid(row=1, column=0, columnspan=3, sticky="ew", pady=1)
        ttk.Label(brow1, text="Próg ręczny:").pack(side="left")
        ttk.Entry(brow1, textvariable=self.thresh_manual_var, width=6).pack(
            side="left", padx=4
        )
        ttk.Button(brow1, text="OK", command=self.apply_threshold_manual).pack(
            side="left"
        )

        # Percent Black
        brow2 = ttk.Frame(hist)
        brow2.grid(row=2, column=0, columnspan=3, sticky="ew", pady=1)
        ttk.Label(brow2, text="% Black:").pack(side="left")
        ttk.Entry(brow2, textvariable=self.thresh_percent_var, width=6).pack(
            side="left", padx=4
        )
        ttk.Button(brow2, text="OK", command=self.apply_threshold_percent_black).pack(
            side="left"
        )

        # Automatyczne progi
        ttk.Button(
            hist,
            text="Mean Iterative",
            command=self.apply_threshold_mean_iterative,
        ).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2))

        ttk.Button(
            hist,
            text="Entropy",
            command=self.apply_threshold_entropy,
        ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(2, 4))

        # --- Krzywa Béziera (zadanie 6) ---
        bez = ttk.LabelFrame(panel2, text="Krzywa Béziera (6)")
        bez.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(
            bez,
            text="Edytor krzywej Béziera",
            command=self.open_bezier_editor,
        ).pack(side="left", padx=4, pady=4)

        # === Zadanie 7: wielokąty ===
        poly_frame = ttk.LabelFrame(panel2, text="Wielokąty (zad. 7)")
        poly_frame.grid(
            row=3, column=0, sticky="ew", pady=(8, 0)
        )  # K daj większe niż poprzedni wiersz
        ttk.Button(
            poly_frame,
            text="Edytor wielokątów (zad. 7)",
            command=self.open_polygon_editor,
        ).pack(fill="x", padx=2, pady=4)
        # --- Overlay pikseli ---
        self._pix_overlay_on = True

        # --- Status bar ---
        self.status = tk.StringVar(value="Gotowe.")
        ttk.Label(self, textvariable=self.status, anchor="w", padding=(8, 4)).grid(
            row=1, column=0, columnspan=3, sticky="ew"
        )

        self._set_params_hint()

        # === ZADANIE 8: Morfologia (operacje na obrazach binarnych) ===
        morph = ttk.LabelFrame(panel2, text="Morfologia (8)")
        morph.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        ttk.Label(
            morph,
            text="Element strukturyzujący (0/1, opcj. -1 = tło dla hit-or-miss):",
        ).pack(anchor="w")

        self.morph_se_text = tk.Text(morph, height=4, width=28)
        self.morph_se_text.pack(fill="x", pady=2)
        # domyślnie krzyż 3x3
        self.morph_se_text.insert("1.0", "0 1 0\n1 1 1\n0 1 0")

        mrow1 = ttk.Frame(morph)
        mrow1.pack(fill="x", pady=(4, 0))
        ttk.Button(mrow1, text="Dylatacja", command=self.apply_morph_dilate).pack(
            side="left", padx=2
        )
        ttk.Button(mrow1, text="Erozja", command=self.apply_morph_erode).pack(
            side="left", padx=2
        )

        mrow2 = ttk.Frame(morph)
        mrow2.pack(fill="x", pady=(2, 0))
        ttk.Button(mrow2, text="Otwarcie", command=self.apply_morph_open).pack(
            side="left", padx=2
        )
        ttk.Button(mrow2, text="Domknięcie", command=self.apply_morph_close).pack(
            side="left", padx=2
        )

        mrow3 = ttk.Frame(morph)
        mrow3.pack(fill="x", pady=(2, 2))
        ttk.Button(
            mrow3,
            text="Hit-or-miss (cienienie)",
            command=self.apply_morph_thin,
        ).pack(side="left", padx=2)
        ttk.Button(
            mrow3,
            text="Hit-or-miss (pogrubianie)",
            command=self.apply_morph_thicken,
        ).pack(side="left", padx=2)

        # === ZADANIE 9: Analiza koloru (np. terenów zielonych) ===
        color_an = ttk.LabelFrame(panel2, text="Analiza koloru (9)")
        color_an.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        color_an.columnconfigure(1, weight=1)

        # Zakres barwy H w stopniach (0..360)
        ttk.Label(color_an, text="Zakres H [°]:").grid(row=0, column=0, sticky="w")
        hfrm = ttk.Frame(color_an)
        hfrm.grid(row=0, column=1, sticky="ew")
        ttk.Entry(hfrm, textvariable=self.color_h_min_var, width=5).pack(side="left")
        ttk.Label(hfrm, text="–").pack(side="left")
        ttk.Entry(hfrm, textvariable=self.color_h_max_var, width=5).pack(side="left")

        # Minimalne S i V (nasycenie, jasność)
        ttk.Label(color_an, text="Min S, Min V:").grid(row=1, column=0, sticky="w")
        svfrm = ttk.Frame(color_an)
        svfrm.grid(row=1, column=1, sticky="ew")
        ttk.Entry(svfrm, textvariable=self.color_s_min_var, width=5).pack(side="left")
        ttk.Entry(svfrm, textvariable=self.color_v_min_var, width=5).pack(
            side="left", padx=(4, 0)
        )

        # Przycisk obliczania
        ttk.Button(
            color_an,
            text="Policz pokrycie kolorem",
            command=self.compute_color_coverage,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 2))

        # Etykieta z wynikiem
        ttk.Label(
            color_an,
            textvariable=self.green_result_var,
            foreground="darkgreen",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))

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
        self.rgb_r_scale.grid(row=0, column=1, sticky="ew", padx=6)

        self.rgb_r_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_r_entry.insert(0, str(self.rgb_r_var.get()))
        self.rgb_r_entry.grid(row=0, column=2)
        self.rgb_r_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("R"))
        self.rgb_r_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("R"))

        # dopiero TERAZ ustawiamy pozycję suwaka (po stworzeniu entry)
        self.rgb_r_scale.set(self.rgb_r_var.get())

        # G
        ttk.Label(self.rgb_inputs_frame, text="G:").grid(row=1, column=0, sticky="e")
        self.rgb_g_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("G", v),
        )
        self.rgb_g_scale.grid(row=1, column=1, sticky="ew", padx=6)

        self.rgb_g_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_g_entry.insert(0, str(self.rgb_g_var.get()))
        self.rgb_g_entry.grid(row=1, column=2)
        self.rgb_g_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("G"))
        self.rgb_g_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("G"))

        self.rgb_g_scale.set(self.rgb_g_var.get())

        # B
        ttk.Label(self.rgb_inputs_frame, text="B:").grid(row=2, column=0, sticky="e")
        self.rgb_b_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("B", v),
        )
        self.rgb_b_scale.grid(row=2, column=1, sticky="ew", padx=6)

        self.rgb_b_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_b_entry.insert(0, str(self.rgb_b_var.get()))
        self.rgb_b_entry.grid(row=2, column=2)
        self.rgb_b_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("B"))
        self.rgb_b_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("B"))

        self.rgb_b_scale.set(self.rgb_b_var.get())

        self.rgb_inputs_frame.columnconfigure(1, weight=1)

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
        self.rgb_r_scale.grid(row=0, column=1, sticky="ew", padx=6)

        self.rgb_r_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_r_entry.insert(0, str(self.rgb_r_var.get()))
        self.rgb_r_entry.grid(row=0, column=2)
        self.rgb_r_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("R"))
        self.rgb_r_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("R"))

        # dopiero teraz ustawiamy pozycję suwaka (po utworzeniu entry)
        self.rgb_r_scale.set(self.rgb_r_var.get())

        # G
        ttk.Label(self.rgb_inputs_frame, text="G:").grid(row=1, column=0, sticky="e")
        self.rgb_g_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("G", v),
        )
        self.rgb_g_scale.grid(row=1, column=1, sticky="ew", padx=6)

        self.rgb_g_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_g_entry.insert(0, str(self.rgb_g_var.get()))
        self.rgb_g_entry.grid(row=1, column=2)
        self.rgb_g_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("G"))
        self.rgb_g_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("G"))

        self.rgb_g_scale.set(self.rgb_g_var.get())

        # B
        ttk.Label(self.rgb_inputs_frame, text="B:").grid(row=2, column=0, sticky="e")
        self.rgb_b_scale = ttk.Scale(
            self.rgb_inputs_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=lambda v: self._on_rgb_slider_changed("B", v),
        )
        self.rgb_b_scale.grid(row=2, column=1, sticky="ew", padx=6)

        self.rgb_b_entry = ttk.Entry(self.rgb_inputs_frame, width=5)
        self.rgb_b_entry.insert(0, str(self.rgb_b_var.get()))
        self.rgb_b_entry.grid(row=2, column=2)
        self.rgb_b_entry.bind("<Return>", lambda e: self._on_rgb_entry_changed("B"))
        self.rgb_b_entry.bind("<FocusOut>", lambda e: self._on_rgb_entry_changed("B"))

        self.rgb_b_scale.set(self.rgb_b_var.get())

        self.rgb_inputs_frame.columnconfigure(1, weight=1)

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
        self.cmyk_c_scale.grid(row=0, column=1, sticky="ew", padx=6)

        self.cmyk_c_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_c_entry.insert(0, f"{self.cmyk_c_var.get():.1f}")
        self.cmyk_c_entry.grid(row=0, column=2)
        self.cmyk_c_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("C"))
        self.cmyk_c_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("C"))

        self.cmyk_c_scale.set(self.cmyk_c_var.get())

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
        self.cmyk_m_scale.grid(row=1, column=1, sticky="ew", padx=6)

        self.cmyk_m_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_m_entry.insert(0, f"{self.cmyk_m_var.get():.1f}")
        self.cmyk_m_entry.grid(row=1, column=2)
        self.cmyk_m_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("M"))
        self.cmyk_m_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("M"))

        self.cmyk_m_scale.set(self.cmyk_m_var.get())

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
        self.cmyk_y_scale.grid(row=2, column=1, sticky="ew", padx=6)

        self.cmyk_y_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_y_entry.insert(0, f"{self.cmyk_y_var.get():.1f}")
        self.cmyk_y_entry.grid(row=2, column=2)
        self.cmyk_y_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("Y"))
        self.cmyk_y_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("Y"))

        self.cmyk_y_scale.set(self.cmyk_y_var.get())

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
        self.cmyk_k_scale.grid(row=3, column=1, sticky="ew", padx=6)

        self.cmyk_k_entry = ttk.Entry(self.cmyk_inputs_frame, width=5)
        self.cmyk_k_entry.insert(0, f"{self.cmyk_k_var.get():.1f}")
        self.cmyk_k_entry.grid(row=3, column=2)
        self.cmyk_k_entry.bind("<Return>", lambda e: self._on_cmyk_entry_changed("K"))
        self.cmyk_k_entry.bind("<FocusOut>", lambda e: self._on_cmyk_entry_changed("K"))

        self.cmyk_k_scale.set(self.cmyk_k_var.get())

        self.cmyk_inputs_frame.columnconfigure(1, weight=1)

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

        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.color_preview.delete("all")
        self.color_preview.create_rectangle(0, 0, 68, 44, fill=hex_color, outline="")

    def _on_color_mode_changed(self):
        """Przełączanie trybu wejściowego RGB/CMYK."""
        mode = self.color_mode.get()

        # Jeżeli UI nie jest jeszcze gotowe (np. podczas budowy panelu) – po prostu wyjdź.
        if not hasattr(self, "rgb_r_var") or not hasattr(self, "cmyk_c_var"):
            return

        if mode == "RGB":
            # Chcemy, żeby suwaki/pola RGB pokazywały to, co teraz jest w CMYK
            self._update_ui_from_cmyk()
            self._show_rgb_inputs()
        else:
            # Chcemy, żeby suwaki/pola CMYK pokazywały aktualne RGB
            self._update_ui_from_rgb()
            self._show_cmyk_inputs()

        self._update_color_conversion()

    def _on_rgb_slider_changed(self, channel: str, value: str):
        """Callback suwaków RGB."""
        # Jeżeli aktualizujemy programowo inne kontrolki, to ignorujemy callback,
        # żeby nie zrobić pętli.
        if getattr(self, "_in_color_update", False):
            return

        self._in_color_update = True
        try:
            v = int(float(value))
            v = max(0, min(255, v))

            if channel == "R":
                self.rgb_r_var.set(v)
                if hasattr(self, "rgb_r_entry"):
                    self.rgb_r_entry.delete(0, "end")
                    self.rgb_r_entry.insert(0, str(v))
            elif channel == "G":
                self.rgb_g_var.set(v)
                if hasattr(self, "rgb_g_entry"):
                    self.rgb_g_entry.delete(0, "end")
                    self.rgb_g_entry.insert(0, str(v))
            elif channel == "B":
                self.rgb_b_var.set(v)
                if hasattr(self, "rgb_b_entry"):
                    self.rgb_b_entry.delete(0, "end")
                    self.rgb_b_entry.insert(0, str(v))

            # Po zmianie RGB – przelicz CMYK i zaktualizuj całą resztę UI
            self._update_ui_from_rgb()
        finally:
            self._in_color_update = False

        self._update_color_conversion()

    def _on_rgb_entry_changed(self, channel):
        """Zmiana wartości w polach tekstowych RGB."""
        entry = {
            "R": self.rgb_r_entry,
            "G": self.rgb_g_entry,
            "B": self.rgb_b_entry,
        }[channel]

        try:
            v = int(entry.get())
        except Exception:
            v = 0

        v = max(0, min(255, v))
        entry.delete(0, "end")
        entry.insert(0, str(v))

        if channel == "R":
            self.rgb_r_var.set(v)
            if hasattr(self, "rgb_r_scale"):
                self.rgb_r_scale.set(v)
        elif channel == "G":
            self.rgb_g_var.set(v)
            if hasattr(self, "rgb_g_scale"):
                self.rgb_g_scale.set(v)
        else:
            self.rgb_b_var.set(v)
            if hasattr(self, "rgb_b_scale"):
                self.rgb_b_scale.set(v)

        # Pole tekstowe traktujemy jak wejście użytkownika – więc normalnie przeliczamy
        self._update_ui_from_rgb()
        self._update_color_conversion()

    def _on_cmyk_slider_changed(self, channel: str, value: str):
        """Callback suwaków CMYK (wartości w %)."""
        if getattr(self, "_in_color_update", False):
            return

        self._in_color_update = True
        try:
            v = float(value)
            v = max(0.0, min(100.0, v))

            if channel == "C":
                self.cmyk_c_var.set(v)
                if hasattr(self, "cmyk_c_entry"):
                    self.cmyk_c_entry.delete(0, "end")
                    self.cmyk_c_entry.insert(0, f"{v:.1f}")
            elif channel == "M":
                self.cmyk_m_var.set(v)
                if hasattr(self, "cmyk_m_entry"):
                    self.cmyk_m_entry.delete(0, "end")
                    self.cmyk_m_entry.insert(0, f"{v:.1f}")
            elif channel == "Y":
                self.cmyk_y_var.set(v)
                if hasattr(self, "cmyk_y_entry"):
                    self.cmyk_y_entry.delete(0, "end")
                    self.cmyk_y_entry.insert(0, f"{v:.1f}")
            else:  # "K"
                self.cmyk_k_var.set(v)
                if hasattr(self, "cmyk_k_entry"):
                    self.cmyk_k_entry.delete(0, "end")
                    self.cmyk_k_entry.insert(0, f"{v:.1f}")

            # Po zmianie CMYK – przelicz RGB i zaktualizuj UI
            self._update_ui_from_cmyk()
        finally:
            self._in_color_update = False

        self._update_color_conversion()

    def _on_cmyk_entry_changed(self, channel):
        """Zmiana wartości w polach tekstowych CMYK (%)."""
        entry = {
            "C": self.cmyk_c_entry,
            "M": self.cmyk_m_entry,
            "Y": self.cmyk_y_entry,
            "K": self.cmyk_k_entry,
        }[channel]

        try:
            v = float(entry.get().replace(",", "."))
        except Exception:
            v = 0.0

        v = max(0.0, min(100.0, v))
        entry.delete(0, "end")
        entry.insert(0, f"{v:.1f}")

        if channel == "C":
            self.cmyk_c_var.set(v)
            if hasattr(self, "cmyk_c_scale"):
                self.cmyk_c_scale.set(v)
        elif channel == "M":
            self.cmyk_m_var.set(v)
            if hasattr(self, "cmyk_m_scale"):
                self.cmyk_m_scale.set(v)
        elif channel == "Y":
            self.cmyk_y_var.set(v)
            if hasattr(self, "cmyk_y_scale"):
                self.cmyk_y_scale.set(v)
        else:
            self.cmyk_k_var.set(v)
            if hasattr(self, "cmyk_k_scale"):
                self.cmyk_k_scale.set(v)

        self._update_ui_from_cmyk()
        self._update_color_conversion()

    def _update_ui_from_rgb(self):
        """Konwersja RGB -> CMYK i aktualizacja suwaków/pól CMYK (bez zapętlania)."""
        from .color_models import rgb_to_cmyk

        r = self.rgb_r_var.get()
        g = self.rgb_g_var.get()
        b = self.rgb_b_var.get()

        c, m, y, k = rgb_to_cmyk(r, g, b)
        c_p = c * 100.0
        m_p = m * 100.0
        y_p = y * 100.0
        k_p = k * 100.0

        self.cmyk_c_var.set(c_p)
        self.cmyk_m_var.set(m_p)
        self.cmyk_y_var.set(y_p)
        self.cmyk_k_var.set(k_p)

        # suwaki
        if hasattr(self, "cmyk_c_scale"):
            self.cmyk_c_scale.set(c_p)
        if hasattr(self, "cmyk_m_scale"):
            self.cmyk_m_scale.set(m_p)
        if hasattr(self, "cmyk_y_scale"):
            self.cmyk_y_scale.set(y_p)
        if hasattr(self, "cmyk_k_scale"):
            self.cmyk_k_scale.set(k_p)

        # pola tekstowe
        if hasattr(self, "cmyk_c_entry"):
            self.cmyk_c_entry.delete(0, "end")
            self.cmyk_c_entry.insert(0, f"{c_p:.1f}")
        if hasattr(self, "cmyk_m_entry"):
            self.cmyk_m_entry.delete(0, "end")
            self.cmyk_m_entry.insert(0, f"{m_p:.1f}")
        if hasattr(self, "cmyk_y_entry"):
            self.cmyk_y_entry.delete(0, "end")
            self.cmyk_y_entry.insert(0, f"{y_p:.1f}")
        if hasattr(self, "cmyk_k_entry"):
            self.cmyk_k_entry.delete(0, "end")
            self.cmyk_k_entry.insert(0, f"{k_p:.1f}")

    def _update_ui_from_cmyk(self):
        """Konwersja CMYK -> RGB i aktualizacja suwaków/pól RGB (bez zapętlania)."""
        from .color_models import cmyk_to_rgb

        c = self.cmyk_c_var.get() / 100.0
        m = self.cmyk_m_var.get() / 100.0
        y = self.cmyk_y_var.get() / 100.0
        k = self.cmyk_k_var.get() / 100.0

        r, g, b = cmyk_to_rgb(c, m, y, k)

        self.rgb_r_var.set(r)
        self.rgb_g_var.set(g)
        self.rgb_b_var.set(b)

        # suwaki
        if hasattr(self, "rgb_r_scale"):
            self.rgb_r_scale.set(r)
        if hasattr(self, "rgb_g_scale"):
            self.rgb_g_scale.set(g)
        if hasattr(self, "rgb_b_scale"):
            self.rgb_b_scale.set(b)

        # pola tekstowe
        if hasattr(self, "rgb_r_entry"):
            self.rgb_r_entry.delete(0, "end")
            self.rgb_r_entry.insert(0, str(r))
        if hasattr(self, "rgb_g_entry"):
            self.rgb_g_entry.delete(0, "end")
            self.rgb_g_entry.insert(0, str(g))
        if hasattr(self, "rgb_b_entry"):
            self.rgb_b_entry.delete(0, "end")
            self.rgb_b_entry.insert(0, str(b))

    def _update_color_conversion(self):
        """Aktualizacja napisów + preview na podstawie aktualnego trybu."""
        # Jeśli UI jeszcze nie jest gotowe – nic nie rób.
        if not hasattr(self, "result_label_1") or not hasattr(self, "result_label_2"):
            return

        mode = self.color_mode.get()
        if mode == "RGB":
            r = self.rgb_r_var.get()
            g = self.rgb_g_var.get()
            b = self.rgb_b_var.get()
            from .color_models import rgb_to_cmyk

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
            from .color_models import cmyk_to_rgb

            r, g, b = cmyk_to_rgb(c, m, y, k)
            self._update_color_preview(r, g, b)
            self.result_label_1.config(text=f"RGB: {r}, {g}, {b}")
            self.result_label_2.config(
                text=(
                    f"CMYK: {self.cmyk_c_var.get():.1f}%, "
                    f"{self.cmyk_m_var.get():.1f}%, "
                    f"{self.cmyk_y_var.get():.1f}%, "
                    f"{self.cmyk_k_var.get():.1f}%"
                )
            )

    def _update_color_preview(self, r, g, b):
        """Aktualizacja prostokąta podglądu koloru."""
        if not hasattr(self, "color_preview"):
            return

        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        self.color_preview.delete("all")
        self.color_preview.create_rectangle(0, 0, 68, 44, fill=hex_color, outline="")

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

    # --- Przekształcenia punktowe ---

    def _require_raster_image(self):
        """Pomocniczo: weź zaznaczony obraz rastrowy lub pokaż komunikat."""
        if not self.sel.obj:
            messagebox.showinfo("Obraz", "Zaznacz obraz PPM/JPEG.")
            return None
        from .shapes.image import RasterImage

        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            messagebox.showinfo("Obraz", "Zaznacz obraz PPM/JPEG.")
            return None
        return obj

    def apply_point_add(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            val = int(self.point_add_var.get())
        except Exception:
            messagebox.showerror("Dodawanie", "Podaj liczbę całkowitą.")
            return
        try:
            obj.src_pixels = add_constant(obj.src_pixels, val)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Dodawanie stałej")
        except Exception as e:
            messagebox.showerror("Dodawanie", f"Błąd:\n{e}")

    def apply_point_mul(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            val = float(self.point_mul_var.get())
        except Exception:
            messagebox.showerror("Mnożenie", "Podaj liczbę (float).")
            return
        try:
            obj.src_pixels = mul_constant(obj.src_pixels, val)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Mnożenie stałej")
        except Exception as e:
            messagebox.showerror("Mnożenie", f"Błąd:\n{e}")

    def apply_point_div(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            val = float(self.point_div_var.get())
        except Exception:
            messagebox.showerror("Dzielenie", "Podaj liczbę (float).")
            return
        try:
            obj.src_pixels = div_constant(obj.src_pixels, val)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Dzielenie stałej")
        except Exception as e:
            messagebox.showerror("Dzielenie", f"Błąd:\n{e}")

    def apply_brightness(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            delta = int(self.brightness_var.get())
        except Exception:
            messagebox.showerror("Jasność", "Podaj liczbę całkowitą.")
            return
        try:
            obj.src_pixels = change_brightness(obj.src_pixels, delta)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Zmiana jasności")
        except Exception as e:
            messagebox.showerror("Jasność", f"Błąd:\n{e}")

    def apply_gray_avg(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            obj.src_pixels = to_grayscale_avg(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Skala szarości (średnia)")
        except Exception as e:
            messagebox.showerror("Skala szarości", f"Błąd:\n{e}")

    def apply_gray_luma(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            obj.src_pixels = to_grayscale_luma(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Skala szarości (luma)")
        except Exception as e:
            messagebox.showerror("Skala szarości", f"Błąd:\n{e}")

    # --- Filtry ---
    def _require_raster_with_size(self):
        obj = self._require_raster_image()
        if obj is None:
            return None, None, None
        # zakładamy, że RasterImage ma src_w, src_h, src_pixels
        w = obj.src_w
        h = obj.src_h
        return obj, w, h

    def _apply_filter_and_update(self, func, label):
        obj, w, h = self._require_raster_with_size()
        if obj is None:
            return
        try:
            new_pixels = func(obj.src_pixels, w, h)
            obj.src_pixels = new_pixels
            obj.update_canvas(self.surface, self.canvas)
            self._push_history(label)
        except Exception as e:
            messagebox.showerror("Filtr", f"Błąd filtra ({label}):\n{e}")

    def apply_filter_box(self):
        self._apply_filter_and_update(
            lambda pixels, w, h: filter_box_blur(pixels, w, h, size=3),
            "Filtr wygładzający (box blur)",
        )

    def apply_filter_median(self):
        self._apply_filter_and_update(
            lambda pixels, w, h: filter_median(pixels, w, h, size=3),
            "Filtr medianowy",
        )

    def apply_filter_sobel(self):
        self._apply_filter_and_update(
            lambda pixels, w, h: filter_sobel(pixels, w, h),
            "Filtr Sobela",
        )

    def apply_filter_sharpen(self):
        self._apply_filter_and_update(
            lambda pixels, w, h: filter_sharpen(pixels, w, h),
            "Filtr wyostrzający",
        )

    def apply_filter_gaussian(self):

        self._apply_filter_and_update(
            lambda pixels, w, h: filter_gaussian(pixels, w, h),
            "Filtr Gaussa",
        )

    def apply_filter_custom(self):
        obj, w, h = self._require_raster_with_size()
        if obj is None:
            return

        # Odczyt tekstu z pola
        raw = self.custom_kernel_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showerror(
                "Maska własna", "Podaj maskę (co najmniej jeden wiersz)."
            )
            return

        try:
            kernel = []
            # każdy wiersz = jeden rząd maski, liczby oddzielone spacjami
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                row = [float(x) for x in line.replace(",", ".").split()]
                kernel.append(row)

            if not kernel:
                raise ValueError("Pusta maska.")

            # sprawdzenie, że maska jest prostokątna
            width0 = len(kernel[0])
            if width0 == 0:
                raise ValueError("Maska musi mieć co najmniej jedną kolumnę.")
            for r in kernel:
                if len(r) != width0:
                    raise ValueError(
                        "Wszystkie wiersze maski muszą mieć tyle samo elementów."
                    )

            # można, ale nie trzeba, wymusić nieparzysty rozmiar:
            if width0 % 2 == 0 or len(kernel) % 2 == 0:
                # pozwalamy, ale ostrzegamy
                # messagebox.showwarning("Maska", "Uwaga: najlepiej używać masek o nieparzystym rozmiarze.")
                pass

            new_pixels = filter_custom(obj.src_pixels, w, h, kernel)
            obj.src_pixels = new_pixels
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Filtr: maska własna")
        except Exception as e:
            messagebox.showerror("Maska własna", f"Błąd parsowania / splotu:\n{e}")

    # --- Zadanie 5a: Histogram ---

    def show_histogram(self):
        """Otwiera okno z histogramem jasności (luminancja)."""
        from .shapes.image import RasterImage

        if not self.sel.obj:
            messagebox.showinfo("Histogram", "Zaznacz obraz PPM/JPEG.")
            return
        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            messagebox.showinfo("Histogram", "Histogram działa na obrazach PPM/JPEG.")
            return

        hist = compute_histogram(obj.src_pixels)
        total = sum(hist) or 1
        max_count = max(hist) or 1

        top = tk.Toplevel(self)
        top.title("Histogram jasności (luminancja)")
        cv = tk.Canvas(top, width=512, height=200, bg="white")
        cv.pack(fill="both", expand=True)

        # oś X: 0..255 (rozciągnięte na szerokość 512 px, czyli 2 px na bin)
        w = 512
        h = 200
        for i, count in enumerate(hist):
            x0 = i * 2
            x1 = x0 + 2
            # wysokość słupka proporcjonalna do max_count
            bar_h = int(count / max_count * (h - 20))
            y0 = h - bar_h
            y1 = h
            cv.create_rectangle(x0, y0, x1, y1, fill="#444", outline="")

        cv.create_line(0, h - 1, w, h - 1, fill="black")
        cv.create_text(10, 10, anchor="nw", text=f"N = {total}", fill="black")

    def apply_hist_stretch(self):
        """Rozszerzenie histogramu dla zaznaczonego obrazu."""
        from .shapes.image import RasterImage

        if not self.sel.obj:
            messagebox.showinfo("Histogram", "Zaznacz obraz PPM/JPEG.")
            return
        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            messagebox.showinfo("Histogram", "Histogram działa na obrazach PPM/JPEG.")
            return

        try:
            obj.src_pixels = histogram_stretch(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Histogram – rozszerzenie")
        except Exception as e:
            messagebox.showerror("Histogram", f"Błąd rozszerzania histogramu:\n{e}")

    def apply_hist_equalize(self):
        """Equalizacja histogramu dla zaznaczonego obrazu."""
        from .shapes.image import RasterImage

        if not self.sel.obj:
            messagebox.showinfo("Histogram", "Zaznacz obraz PPM/JPEG.")
            return
        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            messagebox.showinfo("Histogram", "Histogram działa na obrazach PPM/JPEG.")
            return

        try:
            obj.src_pixels = histogram_equalize(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Histogram – equalizacja")
        except Exception as e:
            messagebox.showerror("Histogram", f"Błąd equalizacji histogramu:\n{e}")

    # --- Zadanie 5b: Binaryzacja ---

    def _require_raster_image(self):
        """Pomocniczo: pobierz zaznaczony obraz rastrowy."""
        from .shapes.image import RasterImage

        if not self.sel.obj:
            messagebox.showinfo("Binaryzacja", "Zaznacz obraz PPM/JPEG.")
            return None
        obj = self.sel.obj
        if not isinstance(obj, RasterImage):
            messagebox.showinfo(
                "Binaryzacja", "Operacje działają na obrazach PPM/JPEG."
            )
            return None
        return obj

    def apply_threshold_manual(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            T = int(self.thresh_manual_var.get())
        except Exception:
            messagebox.showerror("Binaryzacja", "Podaj próg 0..255.")
            return
        try:
            obj.src_pixels = threshold_manual(obj.src_pixels, T)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history(f"Binaryzacja ręczna T={T}")
        except Exception as e:
            messagebox.showerror("Binaryzacja", f"Błąd binaryzacji ręcznej:\n{e}")

    def apply_threshold_percent_black(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            p = float(self.thresh_percent_var.get())
        except Exception:
            messagebox.showerror("Binaryzacja", "Podaj procent czarnego (0..100).")
            return
        try:
            obj.src_pixels = threshold_percent_black(obj.src_pixels, p)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history(f"Binaryzacja Percent Black ({p:.1f}%)")
        except Exception as e:
            messagebox.showerror("Binaryzacja", f"Błąd Percent Black:\n{e}")

    def apply_threshold_mean_iterative(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            obj.src_pixels = threshold_mean_iterative(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Binaryzacja Mean Iterative")
        except Exception as e:
            messagebox.showerror("Binaryzacja", f"Błąd Mean Iterative:\n{e}")

    def apply_threshold_entropy(self):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            obj.src_pixels = threshold_entropy(obj.src_pixels)
            obj.update_canvas(self.surface, self.canvas)
            self._push_history("Binaryzacja Entropy")
        except Exception as e:
            messagebox.showerror("Binaryzacja", f"Błąd Entropy:\n{e}")

    def open_bezier_editor(self):
        """Otwiera (lub fokusuje) okno edytora krzywej Béziera."""
        if getattr(self, "bezier_editor_win", None) is not None:
            try:
                self.bezier_editor_win.lift()
                return
            except Exception:
                self.bezier_editor_win = None

        self.bezier_editor_win = BezierEditorWindow(self)

    def open_polygon_editor(self):
        """Otwiera okno edytora wielokątów (zadanie 7)."""
        try:
            from .polygons.editor import PolygonEditorWindow
        except Exception:
            # awaryjnie, gdy projekt odpalany bez pakietu
            from polygons.editor import PolygonEditorWindow  # type: ignore

        if (
            getattr(self, "polygon_editor_win", None) is not None
            and self.polygon_editor_win.winfo_exists()
        ):
            self.polygon_editor_win.lift()
            self.polygon_editor_win.focus_set()
            return

        self.polygon_editor_win = PolygonEditorWindow(self)
        self.polygon_editor_win.transient(self)

    # --- Zadanie 8: Morfologia obrazów binarnych ---

    def _parse_structuring_element(self):
        """
        Parsuje element strukturyzujący z pola tekstowego.
        Każdy wiersz = linia, wartości oddzielone spacjami.
        Dozwolone: 0, 1 oraz -1 (tło dla hit-or-miss).
        Zwraca listę list int.
        """
        if not hasattr(self, "morph_se_text") or self.morph_se_text is None:
            raise ValueError("Brak pola z elementem strukturyzującym w UI.")

        raw = self.morph_se_text.get("1.0", "end").strip()
        if not raw:
            raise ValueError("Element strukturyzujący jest pusty.")

        rows = []
        width = None
        for line in raw.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            try:
                row = [int(p) for p in parts]
            except ValueError:
                raise ValueError(
                    "Element strukturyzujący może zawierać tylko liczby całkowite "
                    "(0, 1 oraz opcjonalnie -1)."
                )
            if width is None:
                width = len(row)
            elif len(row) != width:
                raise ValueError(
                    "Wszystkie wiersze elementu strukturyzującego muszą mieć tę samą długość."
                )
            rows.append(row)

        if not rows or width is None:
            raise ValueError("Nie udało się odczytać elementu strukturyzującego.")

        return rows

    def _pixels_to_binary(self, pixels):
        """Zamienia listę pikseli RGB na obraz binarny 0/1."""
        bin_img = []
        for r, g, b in pixels:
            if (r + g + b) / 3 >= 128:
                bin_img.append(1)
            else:
                bin_img.append(0)
        return bin_img

    def _binary_to_pixels(self, bin_img):
        """Zamienia obraz binarny 0/1 na piksele (0 lub 255, RGB)."""
        pixels = []
        for v in bin_img:
            val = 255 if v else 0
            pixels.append((val, val, val))
        return pixels

    def _morph_dilate(self, bin_img, w, h, se):
        kh = len(se)
        kw = len(se[0])
        cy = kh // 2
        cx = kw // 2
        out = [0] * (w * h)

        for y in range(h):
            for x in range(w):
                val = 0
                for j in range(kh):
                    for i in range(kw):
                        if se[j][i] != 1:
                            continue
                        xx = x + i - cx
                        yy = y + j - cy
                        if 0 <= xx < w and 0 <= yy < h:
                            if bin_img[yy * w + xx] == 1:
                                val = 1
                                break
                    if val:
                        break
                out[y * w + x] = val
        return out

    def _morph_erode(self, bin_img, w, h, se):
        kh = len(se)
        kw = len(se[0])
        cy = kh // 2
        cx = kw // 2
        out = [0] * (w * h)

        for y in range(h):
            for x in range(w):
                val = 1
                for j in range(kh):
                    for i in range(kw):
                        if se[j][i] != 1:
                            continue
                        xx = x + i - cx
                        yy = y + j - cy
                        if not (0 <= xx < w and 0 <= yy < h):
                            val = 0
                            break
                        if bin_img[yy * w + xx] == 0:
                            val = 0
                            break
                    if val == 0:
                        break
                out[y * w + x] = val
        return out

    def _morph_hit_or_miss(self, bin_img, w, h, se):
        """Hit-or-miss z użyciem wartości 1 (obiekt), -1 (tło), 0 (don't care)."""
        kh = len(se)
        kw = len(se[0])
        cy = kh // 2
        cx = kw // 2
        out = [0] * (w * h)

        for y in range(h):
            for x in range(w):
                match = True
                for j in range(kh):
                    for i in range(kw):
                        v = se[j][i]
                        if v == 0:
                            continue
                        xx = x + i - cx
                        yy = y + j - cy

                        if v == 1:
                            # musi trafić w 1
                            if not (0 <= xx < w and 0 <= yy < h):
                                match = False
                                break
                            if bin_img[yy * w + xx] != 1:
                                match = False
                                break
                        elif v == -1:
                            # musi trafić w tło (0); poza obrazem też traktujemy jako tło
                            if 0 <= xx < w and 0 <= yy < h:
                                if bin_img[yy * w + xx] != 0:
                                    match = False
                                    break
                    if not match:
                        break
                out[y * w + x] = 1 if match else 0
        return out

    def _apply_morph(self, mode, label):
        obj = self._require_raster_image()
        if obj is None:
            return
        try:
            se = self._parse_structuring_element()
        except ValueError as e:
            messagebox.showerror("Morfologia", str(e))
            return

        w = obj.src_w
        h = obj.src_h
        bin_img = self._pixels_to_binary(obj.src_pixels)

        if mode == "dilate":
            out = self._morph_dilate(bin_img, w, h, se)
        elif mode == "erode":
            out = self._morph_erode(bin_img, w, h, se)
        elif mode == "open":
            tmp = self._morph_erode(bin_img, w, h, se)
            out = self._morph_dilate(tmp, w, h, se)
        elif mode == "close":
            tmp = self._morph_dilate(bin_img, w, h, se)
            out = self._morph_erode(tmp, w, h, se)
        elif mode == "thin":
            hm = self._morph_hit_or_miss(bin_img, w, h, se)
            out = [
                1 if (bin_img[i] == 1 and hm[i] == 0) else 0
                for i in range(len(bin_img))
            ]
        elif mode == "thicken":
            hm = self._morph_hit_or_miss(bin_img, w, h, se)
            out = [
                1 if (bin_img[i] == 1 or hm[i] == 1) else 0 for i in range(len(bin_img))
            ]
        else:
            messagebox.showerror("Morfologia", f"Nieznany tryb morfologii: {mode}")
            return

        obj.src_pixels = self._binary_to_pixels(out)
        obj.update_canvas(self.surface, self.canvas)
        self._push_history(label)

    def apply_morph_dilate(self):
        self._apply_morph("dilate", "Morfologia – dylatacja")

    def apply_morph_erode(self):
        self._apply_morph("erode", "Morfologia – erozja")

    def apply_morph_open(self):
        self._apply_morph("open", "Morfologia – otwarcie")

    def apply_morph_close(self):
        self._apply_morph("close", "Morfologia – domknięcie")

    def apply_morph_thin(self):
        self._apply_morph("thin", "Morfologia – hit-or-miss (cienienie)")

    def apply_morph_thicken(self):
        self._apply_morph("thicken", "Morfologia – hit-or-miss (pogrubianie)")

    def compute_color_coverage(self):
        """Liczy, jaki procent obrazu spełnia warunki koloru (domyślnie zieleń)."""
        obj = self._require_raster_image()
        if obj is None:
            return

        try:
            h_min = float(self.color_h_min_var.get())
            h_max = float(self.color_h_max_var.get())
            s_min = float(self.color_s_min_var.get())
            v_min = float(self.color_v_min_var.get())
        except Exception:
            messagebox.showerror(
                "Analiza koloru",
                "Podaj poprawne wartości liczbowe dla zakresu H, S i V.",
            )
            return

        # normalizacja zakresu H do [0, 360] i upewnienie się, że min <= max
        h_min = max(0.0, min(360.0, h_min))
        h_max = max(0.0, min(360.0, h_max))
        if h_max < h_min:
            h_min, h_max = h_max, h_min

        pixels = obj.src_pixels
        total = len(pixels)
        if total == 0:
            messagebox.showinfo("Analiza koloru", "Obraz jest pusty.")
            return

        count = 0
        # Pętla po pikselach – konwersja RGB -> HSV (stdlib: colorsys)
        for r, g, b in pixels:
            rn = r / 255.0
            gn = g / 255.0
            bn = b / 255.0
            h, s, v = colorsys.rgb_to_hsv(rn, gn, bn)
            h_deg = h * 360.0

            if h_min <= h_deg <= h_max and s >= s_min and v >= v_min:
                count += 1

        percent = 100.0 * count / total
        text = (
            f"Pokrycie kolorem (H∈[{h_min:.1f}°, {h_max:.1f}°], "
            f"S≥{s_min:.2f}, V≥{v_min:.2f}): {percent:.2f}%"
        )
        self.green_result_var.set(text)
        self._set_status(text)
