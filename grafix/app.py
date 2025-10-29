import tkinter as tk
from tkinter import ttk, messagebox
import math

from .constants import APP_TITLE, APP_SIZE, COL_PREV
from .utils import parts
from .selection import Selection
from .shapes import Line, Rect, Circle, shape_from_dict
from .io import save_scene, load_scene, scene_to_dict
from .render import CanvasSurface


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
        label = "x1,y1,x2,y2" if t in ("line", "rect") else "cx,cy,r"
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
