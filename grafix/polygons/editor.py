import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.filedialog import asksaveasfilename, askopenfilename
import json
import math


class PolygonEditorWindow(tk.Toplevel):
    """
    Prosty edytor wielokątów do zadania 7.
    - Definiowanie wielokątów myszą i z pól tekstowych.
    - Transformacje w współrzędnych jednorodnych: przesunięcie, obrót, skalowanie.
    - Transformacje zarówno z myszą, jak i z pól tekstowych.
    - Zapis / odczyt figur do pliku JSON.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Wielokąty – zadanie 7")
        self.geometry("960x640")

        # lista figur: każdy element = dict(points=[(x,y),...], closed=True)
        self.polygons = []
        self.selected_index = None

        # bieżący wielokąt w trakcie rysowania (indeks w self.polygons albo None)
        self.current_poly_index = None

        # tryb pracy: "draw", "move", "rotate", "scale"
        self.mode = tk.StringVar(value="draw")

        # pivot (środek obrotu / skalowania)
        self.pivot = None  # (x,y)

        # dane do przeciągania w danym trybie
        self.drag_start = None  # (x, y) po naciśnięciu
        self.orig_points = None  # kopia punktów z chwili naciśnięcia
        self.start_angle = None  # kąt początkowy dla obrotu
        self.start_dist = None  # odległość dla skalowania

        # zmienne tekstowe (transformacje z pól tekstowych)
        self.trans_dx = tk.DoubleVar(value=0.0)
        self.trans_dy = tk.DoubleVar(value=0.0)

        self.rot_cx = tk.DoubleVar(value=0.0)
        self.rot_cy = tk.DoubleVar(value=0.0)
        self.rot_angle = tk.DoubleVar(value=0.0)

        self.scale_cx = tk.DoubleVar(value=0.0)
        self.scale_cy = tk.DoubleVar(value=0.0)
        self.scale_k = tk.DoubleVar(value=1.0)

        # pole tekstowe na wierzchołki zaznaczonej figury
        self.vertices_text = None

        self._build_ui()
        self._bind_canvas()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)

        # Canvas z lewej
        self.canvas = tk.Canvas(
            self, bg="white", highlightthickness=1, highlightbackground="#ccc"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        # Panel sterowania z prawej
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        panel.columnconfigure(0, weight=1)

        ttk.Label(panel, text="Wielokąty (zad. 7)", font=("", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        # --- tryb pracy (mysz) ---
        mode_frame = ttk.LabelFrame(panel, text="Tryb myszy")
        mode_frame.grid(row=1, column=0, sticky="ew")
        for text, value in [
            ("Rysowanie", "draw"),
            ("Przesuwanie", "move"),
            ("Obrót", "rotate"),
            ("Skalowanie", "scale"),
        ]:
            ttk.Radiobutton(
                mode_frame,
                text=text,
                value=value,
                variable=self.mode,
            ).pack(anchor="w")

        # --- wierzchołki (z tekstu) ---
        verts_frame = ttk.LabelFrame(panel, text="Wierzchołki zaznaczonego wielokąta")
        verts_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            verts_frame,
            text="Format: x1,y1; x2,y2; ... lub każda para w osobnym wierszu",
            wraplength=260,
        ).pack(anchor="w")
        self.vertices_text = tk.Text(verts_frame, width=32, height=5)
        self.vertices_text.pack(fill="x", pady=4)
        ttk.Button(
            verts_frame,
            text="Zastosuj wierzchołki",
            command=self._apply_vertices_from_text,
        ).pack(anchor="e", pady=(0, 4))

        # --- Transformacje z pól tekstowych ---
        transf_frame = ttk.LabelFrame(panel, text="Transformacje (pola tekstowe)")
        transf_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        # Przesunięcie
        row = ttk.Frame(transf_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Przesuń dx, dy:").pack(side="left")
        ttk.Entry(row, textvariable=self.trans_dx, width=6).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=self.trans_dy, width=6).pack(side="left", padx=2)
        ttk.Button(row, text="OK", command=self._translate_from_entries).pack(
            side="left", padx=4
        )

        # Obrót
        row = ttk.Frame(transf_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Punkt obrotu cx,cy:").pack(side="left")
        ttk.Entry(row, textvariable=self.rot_cx, width=6).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=self.rot_cy, width=6).pack(side="left", padx=2)

        row2 = ttk.Frame(transf_frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Kąt (deg):").pack(side="left")
        ttk.Entry(row2, textvariable=self.rot_angle, width=6).pack(side="left", padx=2)
        ttk.Button(row2, text="Obróć", command=self._rotate_from_entries).pack(
            side="left", padx=4
        )

        # Skalowanie
        row = ttk.Frame(transf_frame)
        row.pack(fill="x", pady=(6, 2))
        ttk.Label(row, text="Punkt skal. cx,cy:").pack(side="left")
        ttk.Entry(row, textvariable=self.scale_cx, width=6).pack(side="left", padx=2)
        ttk.Entry(row, textvariable=self.scale_cy, width=6).pack(side="left", padx=2)

        row2 = ttk.Frame(transf_frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Skala k:").pack(side="left")
        ttk.Entry(row2, textvariable=self.scale_k, width=6).pack(side="left", padx=2)
        ttk.Button(row2, text="Skaluj", command=self._scale_from_entries).pack(
            side="left", padx=4
        )

        # --- Zapis / odczyt ---
        io_frame = ttk.LabelFrame(panel, text="Zapis / odczyt figur")
        io_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(io_frame, text="Zapisz JSON", command=self._save_json).pack(
            fill="x", pady=2
        )
        ttk.Button(io_frame, text="Wczytaj JSON", command=self._load_json).pack(
            fill="x", pady=2
        )

    def _bind_canvas(self):
        self.canvas.bind("<Button-1>", self._on_down)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)

    # ---------------------------------------------------------- RYSOWANIE ---
    def _ensure_current_polygon(self):
        """Upewnia się, że istnieje „bieżący” wielokąt w trakcie rysowania."""
        if self.current_poly_index is None:
            self.polygons.append({"points": [], "closed": False})
            self.current_poly_index = len(self.polygons) - 1
        return self.polygons[self.current_poly_index]

    def _add_point_to_current(self, x, y):
        poly = self._ensure_current_polygon()
        poly["points"].append((x, y))
        self.selected_index = self.current_poly_index
        self._sync_vertices_to_text()
        self._redraw()

    def _close_current_polygon(self):
        if self.current_poly_index is None:
            return
        poly = self.polygons[self.current_poly_index]
        if len(poly["points"]) < 3:
            messagebox.showinfo("Wielokąt", "Potrzeba co najmniej 3 punktów.")
            return
        poly["closed"] = True
        self.current_poly_index = None
        self._redraw()

    # -------------------------------------------------- MYSZ: on_down/drag ---
    def _on_down(self, e):
        mode = self.mode.get()
        x, y = e.x, e.y

        if mode == "draw":
            # dodawanie wierzchołków
            self._add_point_to_current(x, y)
            return

        # pozostałe tryby wymagają wybrania figury / pivotu
        if mode == "move":
            idx = self._hit_test_polygon(x, y)
            if idx is not None:
                self.selected_index = idx
                self._sync_vertices_to_text()
                self.drag_start = (x, y)
                self.orig_points = list(self.polygons[idx]["points"])
            else:
                self.selected_index = None
                self.drag_start = None
                self.orig_points = None
            self._redraw()
            return

        if mode == "rotate":
            # jeśli nie ma pivotu albo klik jest z wciśniętym Shift – ustaw pivot
            if self.pivot is None or (e.state & 0x0001):  # Shift
                self.pivot = (x, y)
                self.rot_cx.set(x)
                self.rot_cy.set(y)
                self._redraw()
                return
            # w przeciwnym wypadku – próbujemy złapać wielokąt
            idx = self._hit_test_polygon(x, y)
            if idx is not None:
                self.selected_index = idx
                self._sync_vertices_to_text()
                self.drag_start = (x, y)
                self.orig_points = list(self.polygons[idx]["points"])
                self.start_angle = math.atan2(y - self.pivot[1], x - self.pivot[0])
            else:
                self.selected_index = None
                self.drag_start = None
                self.orig_points = None
                self.start_angle = None
            self._redraw()
            return

        if mode == "scale":
            # ustawianie pivotu (z Shiftem albo jeśli brak)
            if self.pivot is None or (e.state & 0x0001):
                self.pivot = (x, y)
                self.scale_cx.set(x)
                self.scale_cy.set(y)
                self._redraw()
                return
            idx = self._hit_test_polygon(x, y)
            if idx is not None:
                self.selected_index = idx
                self._sync_vertices_to_text()
                self.drag_start = (x, y)
                self.orig_points = list(self.polygons[idx]["points"])
                self.start_dist = math.hypot(x - self.pivot[0], y - self.pivot[1])
                if self.start_dist == 0:
                    self.start_dist = 1.0
            else:
                self.selected_index = None
                self.drag_start = None
                self.orig_points = None
                self.start_dist = None
            self._redraw()
            return

    def _on_double_click(self, e):
        # dwuklik w trybie rysowania zamyka wielokąt
        if self.mode.get() == "draw":
            self._close_current_polygon()

    def _on_drag(self, e):
        if self.drag_start is None or self.selected_index is None:
            return
        mode = self.mode.get()
        x, y = e.x, e.y

        if mode == "move":
            dx = x - self.drag_start[0]
            dy = y - self.drag_start[1]
            M = self._matrix_translate(dx, dy)
            self.polygons[self.selected_index]["points"] = self._apply_matrix_to_points(
                self.orig_points, M
            )
            self._redraw()
            return

        if mode == "rotate" and self.pivot is not None and self.start_angle is not None:
            ang_now = math.atan2(y - self.pivot[1], x - self.pivot[0])
            delta = ang_now - self.start_angle
            M = self._matrix_rotate(self.pivot[0], self.pivot[1], delta)
            self.polygons[self.selected_index]["points"] = self._apply_matrix_to_points(
                self.orig_points, M
            )
            self.rot_angle.set(math.degrees(delta))
            self._redraw()
            return

        if mode == "scale" and self.pivot is not None and self.start_dist is not None:
            d_now = math.hypot(x - self.pivot[0], y - self.pivot[1])
            if self.start_dist == 0:
                k = 1.0
            else:
                k = d_now / self.start_dist
            M = self._matrix_scale(self.pivot[0], self.pivot[1], k)
            self.polygons[self.selected_index]["points"] = self._apply_matrix_to_points(
                self.orig_points, M
            )
            self.scale_k.set(k)
            self._redraw()
            return

    def _on_up(self, e):
        # po puszczeniu myszy kończymy operację; punkty już są zaktualizowane
        self.drag_start = None
        self.orig_points = None
        self.start_angle = None
        self.start_dist = None
        self._sync_vertices_to_text()

    # ---------------------------------------------------------- HIT TEST ----
    def _hit_test_polygon(self, x, y):
        """Zwraca indeks wielokąta, którego wnętrze zawiera punkt (x,y),
        albo None jeśli nie znaleziono.
        """
        pt = (x, y)
        for i in reversed(range(len(self.polygons))):
            poly = self.polygons[i]
            if len(poly["points"]) < 3:
                continue
            if self._point_in_polygon(pt, poly["points"]):
                return i
        return None

    @staticmethod
    def _point_in_polygon(pt, points):
        """Klasyczny algorytm „ray casting” – punkt w wielokącie."""
        x, y = pt
        inside = False
        n = len(points)
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            # sprawdzamy przecięcie z półprostą w prawo
            if ((y1 > y) != (y2 > y)) and (
                x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            ):
                inside = not inside
        return inside

    # ---------------------------------------------------------- RYSOWANIE ---
    def _redraw(self):
        self.canvas.delete("all")
        # rysuj wszystkie wielokąty
        for idx, poly in enumerate(self.polygons):
            pts = poly["points"]
            if len(pts) < 2:
                # pojedyncze punkty jako małe kółka
                for x, y in pts:
                    self.canvas.create_oval(
                        x - 2, y - 2, x + 2, y + 2, fill="#000", outline=""
                    )
                continue

            # kolor zależny od zaznaczenia
            outline = "#f00" if idx == self.selected_index else "#000"
            fill = ""  # bez wypełnienia
            flat = [coord for p in pts for coord in p]

            if poly.get("closed", False) and len(pts) >= 3:
                self.canvas.create_polygon(
                    *flat,
                    outline=outline,
                    fill=fill,
                    width=2,
                )
            else:
                self.canvas.create_line(
                    *flat,
                    fill=outline,
                    width=2,
                )

            # wierzchołki jako małe kółka
            for x, y in pts:
                self.canvas.create_oval(
                    x - 3, y - 3, x + 3, y + 3, fill=outline, outline=""
                )

        # pivot (jeśli jest)
        if self.pivot is not None:
            x, y = self.pivot
            self.canvas.create_line(x - 6, y, x + 6, y, fill="#00A", width=2)
            self.canvas.create_line(x, y - 6, x, y + 6, fill="#00A", width=2)
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, outline="#00A")

    # -------------------------------------------------- VERTEX TEXT <-> DATA -
    def _sync_vertices_to_text(self):
        if self.vertices_text is None:
            return
        self.vertices_text.delete("1.0", "end")
        if self.selected_index is None:
            return
        pts = self.polygons[self.selected_index]["points"]
        lines = [f"{x:.1f},{y:.1f}" for (x, y) in pts]
        self.vertices_text.insert("1.0", "\n".join(lines))

    def _apply_vertices_from_text(self):
        if self.selected_index is None:
            messagebox.showinfo(
                "Wierzchołki", "Najpierw zaznacz wielokąt (kliknij w niego)."
            )
            return
        raw = self.vertices_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showerror("Wierzchołki", "Pole jest puste.")
            return
        pts = []
        try:
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                # dopuszczamy format: "x,y" albo "x y"
                if ";" in line:
                    # ktoś wkleił w jednym wierszu – rozbij
                    parts = line.split(";")
                else:
                    parts = [line]
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    part = part.replace(";", "").replace("(", "").replace(")", "")
                    part = part.replace("[", "").replace("]", "")
                    part = part.replace(" ", ",")
                    xs, ys = [s for s in part.split(",") if s]
                    x = float(xs)
                    y = float(ys)
                    pts.append((x, y))
        except Exception as e:
            messagebox.showerror("Wierzchołki", f"Błąd parsowania wierzchołków:\n{e}")
            return

        if len(pts) < 3:
            messagebox.showerror("Wierzchołki", "Potrzeba co najmniej 3 punkty.")
            return

        poly = self.polygons[self.selected_index]
        poly["points"] = pts
        # jeśli był „bieżący” wielokąt w trakcie rysowania, przełączamy go na ten
        self.current_poly_index = None
        self._redraw()

    # ----------------------------------------------------- TRANSFORMACJE ----
    #   Wszystkie transformacje działają przez współrzędne jednorodne 2D.
    #   Punkt (x, y) reprezentujemy jako wektor [x, y, 1]^T i mnożymy przez macierz 3x3.
    # ------------------------------------------------------------------------
    @staticmethod
    def _apply_matrix_to_points(points, M):
        """Zwraca nową listę punktów po przekształceniu macierzą 3x3."""
        res = []
        for x, y in points:
            vx = M[0][0] * x + M[0][1] * y + M[0][2] * 1.0
            vy = M[1][0] * x + M[1][1] * y + M[1][2] * 1.0
            vw = M[2][0] * x + M[2][1] * y + M[2][2] * 1.0
            if abs(vw) < 1e-9:
                vw = 1.0
            res.append((vx / vw, vy / vw))
        return res

    @staticmethod
    def _matrix_translate(dx, dy):
        return [
            [1.0, 0.0, dx],
            [0.0, 1.0, dy],
            [0.0, 0.0, 1.0],
        ]

    @staticmethod
    def _matrix_rotate(cx, cy, angle_rad):
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        # T(cx,cy) * R * T(-cx,-cy)
        return [
            [c, -s, cx - c * cx + s * cy],
            [s, c, cy - s * cx - c * cy],
            [0, 0, 1],
        ]

    @staticmethod
    def _matrix_scale(cx, cy, k):
        # T(cx,cy) * S(k,k) * T(-cx,-cy)
        return [
            [k, 0, cx - k * cx],
            [0, k, cy - k * cy],
            [0, 0, 1],
        ]

    # --- transformacje z pól tekstowych -------------------------------------
    def _get_selected_poly_or_warn(self):
        if self.selected_index is None:
            messagebox.showinfo(
                "Transformacja", "Najpierw zaznacz wielokąt (klikając w niego)."
            )
            return None
        return self.polygons[self.selected_index]

    def _translate_from_entries(self):
        poly = self._get_selected_poly_or_warn()
        if poly is None:
            return
        dx = float(self.trans_dx.get())
        dy = float(self.trans_dy.get())
        M = self._matrix_translate(dx, dy)
        poly["points"] = self._apply_matrix_to_points(poly["points"], M)
        self._redraw()
        self._sync_vertices_to_text()

    def _rotate_from_entries(self):
        poly = self._get_selected_poly_or_warn()
        if poly is None:
            return
        cx = float(self.rot_cx.get())
        cy = float(self.rot_cy.get())
        ang_deg = float(self.rot_angle.get())
        ang_rad = math.radians(ang_deg)
        self.pivot = (cx, cy)
        M = self._matrix_rotate(cx, cy, ang_rad)
        poly["points"] = self._apply_matrix_to_points(poly["points"], M)
        self._redraw()
        self._sync_vertices_to_text()

    def _scale_from_entries(self):
        poly = self._get_selected_poly_or_warn()
        if poly is None:
            return
        cx = float(self.scale_cx.get())
        cy = float(self.scale_cy.get())
        k = float(self.scale_k.get())
        self.pivot = (cx, cy)
        M = self._matrix_scale(cx, cy, k)
        poly["points"] = self._apply_matrix_to_points(poly["points"], M)
        self._redraw()
        self._sync_vertices_to_text()

    # ------------------------------------------------------- ZAPIS / ODCZYT --
    def _save_json(self):
        path = asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Zapisz wielokąty (zad. 7)",
        )
        if not path:
            return
        data = {
            "polygons": [
                {
                    "points": [[float(x), float(y)] for (x, y) in poly["points"]],
                    "closed": bool(poly.get("closed", True)),
                }
                for poly in self.polygons
            ]
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo(
                "Zapis", f"Zapisano {len(self.polygons)} wielokąt(ów).\n{path}"
            )
        except Exception as e:
            messagebox.showerror("Zapis", f"Błąd zapisu JSON:\n{e}")

    def _load_json(self):
        path = askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Wczytaj wielokąty (zad. 7)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.polygons.clear()
            for item in data.get("polygons", []):
                pts = item.get("points", [])
                pts = [(float(x), float(y)) for (x, y) in pts]
                closed = bool(item.get("closed", True))
                if pts:
                    self.polygons.append({"points": pts, "closed": closed})
            self.selected_index = 0 if self.polygons else None
            self.current_poly_index = None
            self.pivot = None
            self._redraw()
            self._sync_vertices_to_text()
            messagebox.showinfo(
                "Wczytano",
                f"Wczytano {len(self.polygons)} wielokąt(ów).\n{path}",
            )
        except Exception as e:
            messagebox.showerror("Wczytywanie", f"Błąd odczytu JSON:\n{e}")
