import tkinter as tk
from ui.theme import COLORS, FONTS
from ui.i18n import t


ROLE_COLORS = {
    "dean": {"bg": "#8b5cf6", "fg": "#ffffff"},
    "dean_assistant": {"bg": "#a78bfa", "fg": "#ffffff"},
    "secretary": {"bg": "#3b82f6", "fg": "#ffffff"},
    "doctor": {"bg": "#22c55e", "fg": "#ffffff"},
}


class RoleBadge(tk.Label):
    def __init__(self, parent, role="", **kw):
        colors = ROLE_COLORS.get(role, {"bg": COLORS["text_muted"], "fg": "#ffffff"})
        label = t(f"role.{role}") if role else "—"
        super().__init__(
            parent, text=f" {label} ",
            bg=colors["bg"], fg=colors["fg"],
            font=FONTS.get("small_bold", ("Segoe UI", 9, "bold")),
            padx=8, pady=2, **kw,
        )