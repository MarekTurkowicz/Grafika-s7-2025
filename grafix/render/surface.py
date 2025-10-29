from typing import Tuple


class Surface:
    """Interfejs powierzchni rysującej pojedyncze piksele."""

    def plot(self, x: int, y: int, color: str, tags: Tuple[str, ...]):
        raise NotImplementedError

    def clear_tag(self, tag: str):
        raise NotImplementedError

    def flush(self):
        """Opcjonalny batch-flush."""
        pass
