import tkinter as tk
from .constants import COL_SEL, HANDLE_S, H_OUTLINE, H_FILL


class Selection:
    def __init__(self):
        self.obj = None
        self.selbox_id = None
        self.handle_ids = []
        self.resizing = False
        self.handle_kind = None
        self.drag_last = None

    def clear(self, cv: tk.Canvas):
        self.obj = None
        if self.selbox_id:
            cv.delete(self.selbox_id)
            self.selbox_id = None
        for hid in self.handle_ids:
            try:
                cv.delete(hid)
            except:
                pass
        self.handle_ids.clear()
        self.resizing = False
        self.handle_kind = None
        self.drag_last = None

    def set(self, cv: tk.Canvas, obj):
        self.obj = obj
        self._update_visual(cv)

    def _update_visual(self, cv: tk.Canvas):
        if self.selbox_id:
            cv.delete(self.selbox_id)
            self.selbox_id = None
        if not self.obj:
            return
        x1, y1, x2, y2 = self.obj.bbox()
        self.selbox_id = cv.create_rectangle(
            x1, y1, x2, y2, outline=COL_SEL, dash=(4, 2), width=1, tags=("selbox",)
        )
        cv.tag_raise(self.selbox_id)
        self._draw_handles(cv)

    def _draw_handles(self, cv: tk.Canvas):
        for hid in self.handle_ids:
            try:
                cv.delete(hid)
            except:
                pass
        self.handle_ids.clear()
        if not self.obj:
            return
        for x, y, kind in self.obj.handles():
            hid = cv.create_rectangle(
                x - HANDLE_S,
                y - HANDLE_S,
                x + HANDLE_S,
                y + HANDLE_S,
                outline=H_OUTLINE,
                fill=H_FILL,
                tags=("handle", kind),
            )
            self.handle_ids.append(hid)

    def move_by(self, cv: tk.Canvas, dx: int, dy: int):
        if not self.obj:
            return
        self.obj.move(dx, dy)
        self.obj.update_canvas(surface=self._get_surface(cv), canvas=cv)
        if self.selbox_id:
            cv.move(self.selbox_id, dx, dy)
        for hid in self.handle_ids:
            cv.move(hid, dx, dy)

    def begin_resize_if_handle(self, cv: tk.Canvas, current_id: int) -> bool:
        if not self.obj:
            return False
        tags = cv.gettags(current_id)
        if "handle" in tags:
            hk = None
            for t in tags:
                if t in ("p1", "p2", "tl", "tr", "br", "bl", "center", "radius"):
                    hk = t
            self.resizing = True
            self.handle_kind = hk
            return True
        return False

    def resize_to(self, cv: tk.Canvas, x: int, y: int):
        if not (self.obj and self.resizing and self.handle_kind):
            return
        self.obj.apply_handle(self.handle_kind, x, y)
        self.obj.update_canvas(surface=self._get_surface(cv), canvas=cv)
        x1, y1, x2, y2 = self.obj.bbox()
        if self.selbox_id:
            cv.coords(self.selbox_id, x1, y1, x2, y2)
        self._draw_handles(cv)

    def end_resize(self, cv: tk.Canvas):
        self.resizing = False
        self.handle_kind = None
        self._update_visual(cv)

    # Surface podpinamy z atrybutu canvas: cv._surface (ustawiane w App)
    def _get_surface(self, cv: tk.Canvas):
        return getattr(cv, "_surface", None)
