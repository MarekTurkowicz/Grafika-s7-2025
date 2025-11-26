# grafix/bezier/editor.py
import tkinter as tk
from tkinter import ttk
import math


class BezierEditorWindow(tk.Toplevel):
    """
    Edytor krzywej Béziera:
    - stopień podany przez użytkownika (spinbox),
    - punkty kontrolne można przesuwać myszą,
    - punkty można edytować w polach tekstowych,
    - krzywa przeliczana i rysowana w czasie rzeczywistym.
    """

    def __init__(self, master_app):
        super().__init__(master_app)
        self.master_app = master_app
        self.title("Krzywa Béziera")
        self.resizable(False, False)

        # stopień krzywej: n → liczba punktów kontrolnych = n+1
        self.degree_var = tk.IntVar(value=3)

        # lista punktów kontrolnych [(x,y), ...]
        # startowo cztery punkty na przekątnej
        self.control_points = [
            (80, 250),
            (180, 80),
            (320, 80),
            (420, 250),
        ]

        # obiekty Entry dla X,Y każdego punktu
        self.cp_entries = []

        # indeks aktualnie przeciąganego punktu (albo None)
        self._drag_index = None

        self._build_ui()
        self._rebuild_cp_entries()
        self._redraw_all()

        # przy zamknięciu okna wyczyść wskaźnik w App
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)

        # górny panel: stopień + przycisk "Zastosuj z pól"
        top = ttk.Frame(main)
        top.pack(fill="x", pady=(0, 6))

        ttk.Label(top, text="Stopień n:").pack(side="left")
        deg_spin = ttk.Spinbox(
            top,
            from_=1,
            to=10,
            width=4,
            textvariable=self.degree_var,
            command=self._on_degree_changed,
        )
        deg_spin.pack(side="left", padx=4)

        ttk.Button(
            top, text="Zastosuj punkty z pól", command=self._apply_from_entries
        ).pack(side="left", padx=8)

        # Środkowy panel: canvas na krzywą + punkty kontrolne
        self.canvas = tk.Canvas(
            main,
            width=500,
            height=320,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.canvas.pack(fill="both", expand=True, pady=(0, 6))

        self.canvas.bind("<Button-1>", self._on_canvas_down)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_up)

        # Dolny panel: pola tekstowe z punktami
        self.points_frame = ttk.LabelFrame(main, text="Punkty kontrolne (x, y)")
        self.points_frame.pack(fill="x")

    def _on_close(self):
        # żeby App wiedział, że okno już nie istnieje
        if hasattr(self.master_app, "bezier_editor_win"):
            self.master_app.bezier_editor_win = None
        self.destroy()

    # -------------------------------------------------- punkty / stopień --

    def _on_degree_changed(self):
        """
        Użytkownik zmienił stopień n → liczba punktów = n+1.
        Ucinamy lub dodajemy punkty.
        """
        try:
            n = int(self.degree_var.get())
        except Exception:
            n = 3
        if n < 1:
            n = 1
        if n > 10:
            n = 10
        self.degree_var.set(n)

        needed = n + 1
        current = len(self.control_points)

        if current > needed:
            # utnij nadmiar
            self.control_points = self.control_points[:needed]
        elif current < needed:
            # dodaj brakujące punkty mniej więcej równomiernie na linii
            w = 500
            h = 320
            for i in range(current, needed):
                t = i / max(1, needed - 1)
                x = 50 + t * (w - 100)
                y = h / 2
                self.control_points.append((x, y))

        self._rebuild_cp_entries()
        self._redraw_all()

    def _rebuild_cp_entries(self):
        """Buduje od nowa pola tekstowe dla punktów kontrolnych."""
        # usuń stare widżety
        for w in self.points_frame.winfo_children():
            w.destroy()
        self.cp_entries.clear()

        for idx, (x, y) in enumerate(self.control_points):
            row = ttk.Frame(self.points_frame)
            row.pack(fill="x", pady=1)

            ttk.Label(row, text=f"P{idx}:").pack(side="left")

            ex = ttk.Entry(row, width=6)
            ex.insert(0, str(int(round(x))))
            ex.pack(side="left", padx=(4, 2))

            ey = ttk.Entry(row, width=6)
            ey.insert(0, str(int(round(y))))
            ey.pack(side="left", padx=(2, 4))

            self.cp_entries.append((ex, ey))

    def _apply_from_entries(self):
        """
        Przepisuje współrzędne punktów z pól tekstowych do listy control_points.
        """
        new_points = []
        try:
            for ex, ey in self.cp_entries:
                x = float(ex.get().strip())
                y = float(ey.get().strip())
                new_points.append((x, y))
        except Exception as e:
            tk.messagebox.showerror(
                "Bézier", f"Niepoprawne współrzędne w polach tekstowych:\n{e}"
            )
            return

        if len(new_points) < 2:
            tk.messagebox.showinfo(
                "Bézier", "Potrzeba co najmniej 2 punktów kontrolnych."
            )
            return

        self.control_points = new_points
        # zaktualizuj stopień = liczba punktów - 1
        n = len(self.control_points) - 1
        if n < 1:
            n = 1
        if n > 10:
            n = 10
        self.degree_var.set(n)
        self._rebuild_cp_entries()
        self._redraw_all()

    def _update_entries_from_points(self):
        """Aktualizuje tekst w Entry na podstawie aktualnych control_points."""
        for (ex, ey), (x, y) in zip(self.cp_entries, self.control_points):
            ex.delete(0, "end")
            ex.insert(0, str(int(round(x))))
            ey.delete(0, "end")
            ey.insert(0, str(int(round(y))))

    # -------------------------------------------------- obsługa myszy ----

    def _on_canvas_down(self, event):
        """
        Kliknięcie:
        - jeśli blisko jakiegoś punktu kontrolnego → zaczynamy go przeciągać.
        """
        x, y = event.x, event.y
        idx = self._find_point_near(x, y, radius=10)
        self._drag_index = idx

    def _on_canvas_drag(self, event):
        if self._drag_index is None:
            return
        x, y = event.x, event.y
        # ogranicz lekko do obszaru canvasa
        x = max(0, min(x, int(self.canvas["width"])))
        y = max(0, min(y, int(self.canvas["height"])))
        pts = list(self.control_points)
        pts[self._drag_index] = (x, y)
        self.control_points = pts
        # aktualizacja pól tekstowych i rysunku w czasie rzeczywistym
        self._update_entries_from_points()
        self._redraw_all()

    def _on_canvas_up(self, event):
        self._drag_index = None

    def _find_point_near(self, x, y, radius=10):
        """
        Zwraca indeks punktu kontrolnego, który jest najbliżej (x,y),
        jeśli odległość <= radius; w przeciwnym razie None.
        """
        best = None
        best_d2 = radius * radius
        for i, (px, py) in enumerate(self.control_points):
            dx = px - x
            dy = py - y
            d2 = dx * dx + dy * dy
            if d2 <= best_d2:
                best_d2 = d2
                best = i
        return best

    # ---------------------------------------------------- rysowanie -----

    def _redraw_all(self):
        self.canvas.delete("all")

        if len(self.control_points) < 2:
            return

        # rysuj wielokąt kontrolny (łączący punkty)
        for i in range(len(self.control_points) - 1):
            x1, y1 = self.control_points[i]
            x2, y2 = self.control_points[i + 1]
            self.canvas.create_line(x1, y1, x2, y2, fill="#cccccc", dash=(4, 2))

        # rysuj krzywą Béziera (De Casteljau)
        curve_points = self._compute_bezier_points(self.control_points, steps=200)
        if len(curve_points) >= 2:
            for i in range(len(curve_points) - 1):
                x1, y1 = curve_points[i]
                x2, y2 = curve_points[i + 1]
                self.canvas.create_line(x1, y1, x2, y2, fill="#0040ff", width=2)

        # rysuj punkty kontrolne
        for idx, (x, y) in enumerate(self.control_points):
            r = 5
            self.canvas.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                fill="#ff0000",
                outline="black",
            )
            self.canvas.create_text(
                x + 12, y, text=f"P{idx}", anchor="w", fill="#000000", font=("", 8)
            )

    def _compute_bezier_points(self, points, steps=200):
        """Zwraca listę punktów (x,y) na krzywej Béziera."""
        n = len(points)
        if n < 2:
            return []

        res = []
        for i in range(steps + 1):
            t = i / steps
            x, y = self._de_casteljau(points, t)
            res.append((x, y))
        return res

    def _de_casteljau(self, points, t):
        """Algorytm de Casteljau dla zadanych punktów kontrolnych."""
        pts = [(float(x), float(y)) for (x, y) in points]
        m = len(pts)
        for r in range(1, m):
            for i in range(m - r):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                x = (1 - t) * x1 + t * x2
                y = (1 - t) * y1 + t * y2
                pts[i] = (x, y)
        return pts[0]
