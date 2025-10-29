import json
from tkinter.filedialog import asksaveasfilename, askopenfilename
from tkinter import messagebox
from ..shapes import shape_from_dict


def scene_to_dict(objects, selected_index=None):
    return {
        "version": 1,
        "objects": [o.to_dict() for o in objects],
        "selected_index": selected_index,
    }


def save_scene(objects):
    if not objects:
        messagebox.showinfo("Zapis", "Brak obiektów do zapisania.")
        return None
    data = {"version": 1, "objects": [o.to_dict() for o in objects]}
    path = asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON", "*.json")],
        title="Zapisz projekt",
    )
    if not path:
        return None
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path
    except Exception as e:
        messagebox.showerror("Zapis JSON", f"Nie udało się zapisać:\n{e}")
        return None


def load_scene():
    path = askopenfilename(filetypes=[("JSON", "*.json")], title="Wczytaj projekt")
    if not path:
        return None, []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        objs = [shape_from_dict(d) for d in data.get("objects", [])]
        return path, objs
    except Exception as e:
        messagebox.showerror("Wczytanie JSON", f"Nie udało się wczytać:\n{e}")
        return None, []
