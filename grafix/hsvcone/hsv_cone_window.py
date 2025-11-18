import tkinter as tk
from tkinter import ttk
import math
import colorsys


class HSVConeWindow(tk.Toplevel):
    """
    Stożek HSV w 3D – wersja pełna:
    - stożek w 3D z kolorami HSV->RGB,
    - obrót wokół osi X/Y/Z,
    - kliknięcie w stożek wybiera wysokość V,
    - po prawej rysowany jest przekrój (dysk HSV dla stałego V).
    """

    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Stożek HSV 3D (pełny)")
        self.resizable(False, False)

        # Gęstość próbkowania
        self.steps_v = 14  # V (wysokość)
        self.steps_s = 12  # S (promień)
        self.steps_h = 48  # H (kąt)

        # Kąty obrotu
        self.angle_x = tk.DoubleVar(value=30.0)
        self.angle_y = tk.DoubleVar(value=-30.0)
        self.angle_z = tk.DoubleVar(value=0.0)

        # Lista punktów po rzutowaniu: (sx, sy, vi)
        self._points = []

        self._build_ui()
        self._redraw_cone()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if hasattr(self.master_app, "hsv_cone_win"):
            self.master_app.hsv_cone_win = None
        self.destroy()

    # ---------------- UI ----------------

    def _build_ui(self):
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        # LEWA: stożek 3D
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.canvas_cone = tk.Canvas(
            left,
            width=380,
            height=380,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.canvas_cone.pack(fill="both", expand=True)

        rot = ttk.Frame(left)
        rot.pack(fill="x", pady=(4, 0))

        ttk.Label(rot, text="Rot X:").grid(row=0, column=0, sticky="w")
        ttk.Scale(
            rot,
            from_=-180,
            to=180,
            variable=self.angle_x,
            command=lambda v: self._redraw_cone(),
        ).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(rot, text="Rot Y:").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Scale(
            rot,
            from_=-180,
            to=180,
            variable=self.angle_y,
            command=lambda v: self._redraw_cone(),
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=(2, 0))

        ttk.Label(rot, text="Rot Z:").grid(row=2, column=0, sticky="w", pady=(2, 0))
        ttk.Scale(
            rot,
            from_=-180,
            to=180,
            variable=self.angle_z,
            command=lambda v: self._redraw_cone(),
        ).grid(row=2, column=1, sticky="ew", padx=4, pady=(2, 0))

        rot.columnconfigure(1, weight=1)

        # klik w stożek -> przekrój
        self.canvas_cone.bind("<Button-1>", self._on_click_cone)

        # PRAWA: przekrój
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")

        self.slice_info = ttk.Label(
            right,
            text="Przekrój: kliknij w stożek, aby wybrać V",
            anchor="w",
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

    # ---------------- 3D obrót ----------------

    def _rotate_point(self, x, y, z, ax, ay, az):
        # X
        cosx, sinx = math.cos(ax), math.sin(ax)
        y1 = y * cosx - z * sinx
        z1 = y * sinx + z * cosx
        x1 = x

        # Y
        cosy, siny = math.cos(ay), math.sin(ay)
        x2 = x1 * cosy + z1 * siny
        z2 = -x1 * siny + z1 * cosy
        y2 = y1

        # Z
        cosz, sinz = math.cos(az), math.sin(az)
        x3 = x2 * cosz - y2 * sinz
        y3 = x2 * sinz + y2 * cosz
        z3 = z2

        return x3, y3, z3

    def _hsv_to_rgb_hex(self, h, s, v):
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    # ---------------- Stożek 3D ----------------

    def _redraw_cone(self):
        self.canvas_cone.delete("all")
        self._points.clear()

        w = int(self.canvas_cone["width"])
        h = int(self.canvas_cone["height"])
        cx, cy = w / 2, h / 2
        scale = min(w, h) * 0.48

        ax = math.radians(self.angle_x.get())
        ay = math.radians(self.angle_y.get())
        az = math.radians(self.angle_z.get())

        voxels = []

        for vi in range(self.steps_v):
            v = vi / (self.steps_v - 1) if self.steps_v > 1 else 0.0
            z = v - 0.5  # przesuwamy tak, żeby stożek był wyśrodkowany na osi Z

            for si in range(self.steps_s):
                s = si / (self.steps_s - 1) if self.steps_s > 1 else 0.0

                # promień stożka rośnie z S i maleje z V -> klasyczny stożek
                r_cone = s * v

                for hi in range(self.steps_h):
                    h_norm = hi / self.steps_h
                    angle = 2 * math.pi * h_norm

                    x = r_cone * math.cos(angle)
                    y = r_cone * math.sin(angle)

                    xr, yr, zr = self._rotate_point(x, y, z, ax, ay, az)
                    sx = cx + xr * scale
                    sy = cy - yr * scale

                    color = self._hsv_to_rgb_hex(h_norm, s, v)
                    voxels.append((zr, sx, sy, vi, color))

        # sort po głębi (Z), żeby pseudo-3D się zgadzało
        voxels.sort(key=lambda t: t[0])

        base_size = scale / max(self.steps_v, self.steps_s, 1)
        size_pt = max(
            4, base_size * 1.8
        )  # trochę większe kwadraty, żeby nie było dziur

        for zr, sx, sy, vi, color in voxels:
            self.canvas_cone.create_rectangle(
                sx - size_pt / 2,
                sy - size_pt / 2,
                sx + size_pt / 2,
                sy + size_pt / 2,
                fill=color,
                outline="",
            )
            # zapisujemy tylko vi (indeks V) do przekroju
            self._points.append((sx, sy, vi))

    # ---------------- Klik + przekrój ----------------

    def _on_click_cone(self, event):
        """Znajdź najbliższy punkt stożka i narysuj przekrój dla jego V."""
        if not self._points:
            return

        ex, ey = event.x, event.y
        best_vi = None
        best_d2 = 1e9

        for sx, sy, vi in self._points:
            d2 = (sx - ex) ** 2 + (sy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_vi = vi

        if best_vi is not None:
            self._draw_slice(best_vi)

    def _draw_slice(self, vi):
        """Przekrój stożka dla stałego V – dysk H×S (tarcza HSV)."""
        self.canvas_slice.delete("all")

        v = vi / (self.steps_v - 1) if self.steps_v > 1 else 0.0
        self.slice_info.config(text=f"Przekrój dla V = {v:.2f} (0–1)")

        w = int(self.canvas_slice["width"])
        h = int(self.canvas_slice["height"])
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 10

        samples_s = self.steps_s * 2
        samples_h = self.steps_h * 2

        for si in range(samples_s):
            s = si / (samples_s - 1)
            for hi in range(samples_h):
                h_norm = hi / samples_h
                angle = 2 * math.pi * h_norm
                r = s * radius

                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)

                color = self._hsv_to_rgb_hex(h_norm, s, v)
                self.canvas_slice.create_rectangle(
                    x - 2,
                    y - 2,
                    x + 2,
                    y + 2,
                    fill=color,
                    outline="",
                )

        # obrys koła
        self.canvas_slice.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            outline="#444",
        )
