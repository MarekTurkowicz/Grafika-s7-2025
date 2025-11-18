import tkinter as tk
from tkinter import ttk
import math
import colorsys


class HSVConePointsWindow(tk.Toplevel):
    """
    Prostsza wizualizacja stożka HSV:
    - stożek rysowany jako chmura punktów (HSV → RGB),
    - obrót wokół X/Y/Z,
    - kliknięcie pokazuje przekrój (stałe V) po prawej.
    """

    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("Stożek HSV 3D (punkty)")
        self.resizable(False, False)

        # Mniej próbek niż w wersji pełnej – lżejsze, bardziej „punktowe”
        self.steps_v = 8  # wysokość (V)
        self.steps_s = 6  # promień (S)
        self.steps_h = 24  # kąt (H)

        # Rotacja
        self.angle_x = tk.DoubleVar(value=30.0)
        self.angle_y = tk.DoubleVar(value=-30.0)
        self.angle_z = tk.DoubleVar(value=0.0)

        # Lista voxelowych punktów po rzutowaniu
        self._points = []  # (sx, sy, vi)

        self._build_ui()
        self._redraw_cone()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        # wyczyszczenie referencji w App
        if hasattr(self.master_app, "hsv_cone_points_win"):
            self.master_app.hsv_cone_points_win = None
        self.destroy()

    # --- UI ---

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
            width=360,
            height=360,
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

        # klik w stożek → przekrój
        self.canvas_cone.bind("<Button-1>", self._on_click_cone)

        # PRAWA: prosty przekrój
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")

        self.slice_info = ttk.Label(
            right, text="Przekrój (prosty): kliknij w stożek, aby wybrać V", anchor="w"
        )
        self.slice_info.pack(fill="x", pady=(0, 4))

        self.canvas_slice = tk.Canvas(
            right,
            width=300,
            height=300,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.canvas_slice.pack(fill="both", expand=True)

    # --- Obrót 3D ---

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

    def _hsv_to_hex(self, h, s, v):
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    # --- Stożek 3D (punkty) ---

    def _redraw_cone(self):
        self.canvas_cone.delete("all")
        self._points.clear()

        w = int(self.canvas_cone["width"])
        h = int(self.canvas_cone["height"])
        cx, cy = w / 2, h / 2
        scale = min(w, h) * 0.45

        ax = math.radians(self.angle_x.get())
        ay = math.radians(self.angle_y.get())
        az = math.radians(self.angle_z.get())

        voxels = []

        for vi in range(self.steps_v):
            v = vi / (self.steps_v - 1)
            z = v - 0.5

            for si in range(self.steps_s):
                s = si / (self.steps_s - 1)

                r = s * v

                for hi in range(self.steps_h):
                    hnorm = hi / self.steps_h
                    angle = 2 * math.pi * hnorm

                    x = r * math.cos(angle)
                    y = r * math.sin(angle)

                    xr, yr, zr = self._rotate_point(x, y, z, ax, ay, az)
                    sx = cx + xr * scale
                    sy = cy - yr * scale

                    color = self._hsv_to_hex(hnorm, s, v)
                    voxels.append((zr, sx, sy, vi, color))

        # sortowanie po głębi
        voxels.sort(key=lambda t: t[0])

        size = 5  # małe kwadraciki – efekt „z punktów”
        for zr, sx, sy, vi, color in voxels:
            self.canvas_cone.create_rectangle(
                sx - size / 2,
                sy - size / 2,
                sx + size / 2,
                sy + size / 2,
                fill=color,
                outline="",
            )
            self._points.append((sx, sy, vi))

    # --- Klik + prosty przekrój ---

    def _on_click_cone(self, event):
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
        """Prosty przekrój: krążek HSV dla stałego V."""
        self.canvas_slice.delete("all")

        v = vi / (self.steps_v - 1)
        self.slice_info.config(text=f"Przekrój (prosty) V = {v:.2f}")

        w = int(self.canvas_slice["width"])
        h = int(self.canvas_slice["height"])
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 10

        samples_s = self.steps_s * 2
        samples_h = self.steps_h * 2

        for si in range(samples_s):
            s = si / (samples_s - 1)
            for hi in range(samples_h):
                hnorm = hi / samples_h
                ang = 2 * math.pi * hnorm
                r = s * R

                x = cx + r * math.cos(ang)
                y = cy + r * math.sin(ang)

                col = self._hsv_to_hex(hnorm, s, v)
                self.canvas_slice.create_rectangle(
                    x - 2,
                    y - 2,
                    x + 2,
                    y + 2,
                    fill=col,
                    outline="",
                )

        self.canvas_slice.create_oval(
            cx - R,
            cy - R,
            cx + R,
            cy + R,
            outline="#444",
        )
