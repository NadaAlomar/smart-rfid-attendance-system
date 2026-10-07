import tkinter as tk
from ui.theme import get_lang


def is_rtl():
    return get_lang() == "ar"


def side_start():
    return tk.RIGHT if is_rtl() else tk.LEFT


def side_end():
    return tk.LEFT if is_rtl() else tk.RIGHT


def anchor_start():
    return "e" if is_rtl() else "w"


def anchor_end():
    return "w" if is_rtl() else "e"


def text_justify():
    return "right" if is_rtl() else "left"


def grid_column_start(total_cols):
    return (total_cols - 1) if is_rtl() else 0


def reverse_columns(columns):
    if is_rtl():
        return list(reversed(columns))
    return list(columns)


def pad_x(start, end):
    """Return (left, right) padx tuple, swapping in RTL mode."""
    return (end, start) if is_rtl() else (start, end)


def rtl_columns(*cols):
    """Return reversed column tuple when RTL is active."""
    return tuple(reversed(cols)) if is_rtl() else tuple(cols)
