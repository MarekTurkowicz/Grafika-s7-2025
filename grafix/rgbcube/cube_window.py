import tkinter as tk
from tkinter import ttk
import math


class RGBCubeWindow(tk.Toplevel):
    """
    Okno z trójwymiarową kostką RGB.
    - Kostka rysowana jako chmura punktów (voxelki) w 3D, rzutowana na 2D.
    - Dwa suwaki obracają kostkę (kąt X i Y).
    - Kliknięcie w kostkę pokazuje przekrój dla danego R (stałe R, zmienne G,B).
    """

    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Kostka RGB 3D")
        self.resizable(False, False)

        # rozdzielczość kostki (liczba próbek na kanał)
        self.steps = 8  # 8^3 = 512 punktów – lekko i wystarczająco gęsto

        # kąty obrotu (w stopniach)
        self.angle_x = tk.DoubleVar(value=30.0)  # obrót wokół osi X (pitch)
        self.angle_y = tk.DoubleVar(value=-30.0)  # obrót wokół osi Y (yaw)

        # lista voxelów po rzutowaniu: (sx, sy, i, j, k)
        self._points = []

        self._build_ui()
        self._redraw_cube()

        # gdy okno się zamyka – wyzeruj referencję w App
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if self.master_app is not None:
            self.master_app.rgb_cube_win = None
        self.destroy()

    def _build_ui(self):
        from tkinter import ttk

        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        # Siatka 2 kolumny: lewa – kostka, prawa – przekrój
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # --- LEWA: kostka 3D ---
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.canvas_cube = tk.Canvas(
            left,
            width=360,
            height=360,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.canvas_cube.pack(fill="both", expand=True)

        # obracanie – dwa suwaki
        rot = ttk.Frame(left)
        rot.pack(fill="x", pady=(6, 0))

        ttk.Label(rot, text="Rot X:").grid(row=0, column=0, sticky="w")
        ttk.Scale(
            rot,
            from_=-180,
            to=180,
            variable=self.angle_x,
            command=lambda v: self._redraw_cube(),
        ).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(rot, text="Rot Y:").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Scale(
            rot,
            from_=-180,
            to=180,
            variable=self.angle_y,
            command=lambda v: self._redraw_cube(),
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=(2, 0))

        rot.columnconfigure(1, weight=1)

        # kliknięcie w kostkę → przekrój
        self.canvas_cube.bind("<Button-1>", self._on_click_cube)

        # --- PRAWA: przekrój ---
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")

        self.slice_info = ttk.Label(
            right, text="Przekrój: kliknij w kostkę, aby wybrać R", anchor="w"
        )
        self.slice_info.pack(fill="x", pady=(0, 4))

        self.canvas_slice = tk.Canvas(
            right,
            width=320,
            height=320,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.canvas_slice.pack(fill="both", expand=True)

    # --- Logika rysowania kostki ---

    def _rotate_point(self, x, y, z, ax, ay):
        """Obrót punktu (x,y,z) wokół osi X i Y o kąty ax, ay (radiany)."""
        # obrót wokół X
        cosx = math.cos(ax)
        sinx = math.sin(ax)
        y1 = y * cosx - z * sinx
        z1 = y * sinx + z * cosx

        # obrót wokół Y
        cosy = math.cos(ay)
        siny = math.sin(ay)
        x2 = x * cosy + z1 * siny
        z2 = -x * siny + z1 * cosy

        return x2, y1, z2

    def _redraw_cube(self):
        """Przelicza i rysuje kostkę RGB dla aktualnych kątów."""
        self.canvas_cube.delete("all")
        self._points.clear()

        w = int(self.canvas_cube["width"])
        h = int(self.canvas_cube["height"])
        cx = w / 2
        cy = h / 2
        scale = min(w, h) * 0.4  # skala dla 3D → 2D

        ax = math.radians(self.angle_x.get())
        ay = math.radians(self.angle_y.get())

        voxels = []

        # Generujemy wszystkie punkty (R,G,B)
        for i in range(self.steps):
            r = int(round(i / (self.steps - 1) * 255))
            x = i / (self.steps - 1) - 0.5  # -0.5..0.5

            for j in range(self.steps):
                g = int(round(j / (self.steps - 1) * 255))
                y = j / (self.steps - 1) - 0.5

                for k in range(self.steps):
                    b = int(round(k / (self.steps - 1) * 255))
                    z = k / (self.steps - 1) - 0.5

                    xr, yr, zr = self._rotate_point(x, y, z, ax, ay)
                    sx = cx + xr * scale
                    sy = cy - yr * scale
                    color = f"#{r:02x}{g:02x}{b:02x}"
                    voxels.append((zr, sx, sy, i, j, k, color))

        # Sortujemy po głębi (zr) – od najdalszych do najbliższych
        voxels.sort(key=lambda t: t[0])

        size_pt = 5  # wielkość „punktu” (kwadracik)
        for zr, sx, sy, i, j, k, color in voxels:
            self.canvas_cube.create_rectangle(
                sx - size_pt / 2,
                sy - size_pt / 2,
                sx + size_pt / 2,
                sy + size_pt / 2,
                fill=color,
                outline="",
            )
            self._points.append((sx, sy, i, j, k))

    # --- Kliknięcie i przekrój ---

    def _on_click_cube(self, event):
        """Znajdź najbliższy voxel do kliknięcia i pokaż przekrój dla danego R (i)."""
        if not self._points:
            return

        ex, ey = event.x, event.y
        best = None
        best_d2 = 1e9

        for sx, sy, i, j, k in self._points:
            dx = sx - ex
            dy = sy - ey
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = (i, j, k)

        if best is None:
            return

        r_index = best[0]
        self._draw_slice(r_index)

    def _draw_slice(self, r_index):
        """Rysuje przekrój dla danego indeksu R (stałe R, płaszczyzna G×B)."""
        self.canvas_slice.delete("all")

        steps = self.steps
        w = int(self.canvas_slice["width"])
        h = int(self.canvas_slice["height"])
        size = min(w, h) - 20  # margines
        cell = size / steps
        offset_x = (w - size) / 2
        offset_y = (h - size) / 2

        # wartość R z indeksu
        r_val = int(round(r_index / (steps - 1) * 255))
        self.slice_info.config(text=f"Przekrój dla R = {r_val} (0–255)")

        for j in range(steps):  # G
            g_val = int(round(j / (steps - 1) * 255))
            for k in range(steps):  # B
                b_val = int(round(k / (steps - 1) * 255))

                x1 = offset_x + k * cell
                y1 = offset_y + j * cell
                x2 = x1 + cell
                y2 = y1 + cell

                color = f"#{r_val:02x}{g_val:02x}{b_val:02x}"
                self.canvas_slice.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=color,
                    outline="",
                )

        # delikatna ramka dookoła
        self.canvas_slice.create_rectangle(
            offset_x,
            offset_y,
            offset_x + size,
            offset_y + size,
            outline="#333",
        )
