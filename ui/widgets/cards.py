import tkinter as tk
from ui.theme import COLORS, FONTS


class StatCard(tk.Frame):
    def __init__(self, parent, icon="", value="", label="", color=None, **kw):
        c = COLORS
        color = color or c["primary"]
        super().__init__(parent, bg=c["bg_card"], padx=2, pady=2, **kw)
        inner = tk.Frame(self, bg=c["bg_card"], padx=20, pady=14)
        inner.pack(fill=tk.BOTH, expand=True)
        tk.Frame(inner, bg=color, height=4).pack(fill=tk.X, pady=(0, 8))
        if icon:
            tk.Label(inner, text=icon, font=("Segoe UI Emoji", 18),
                     bg=c["bg_card"], fg=color).pack(anchor="e")
        self.val_lbl = tk.Label(inner, text=str(value), font=FONTS["stat_value"],
                                bg=c["bg_card"], fg=color)
        self.val_lbl.pack(anchor="e")
        tk.Label(inner, text=label, font=FONTS["stat_label"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor="e").pack(fill=tk.X)

    def set_value(self, val):
        self.val_lbl.config(text=str(val))


class ActionButton(tk.Frame):
    def __init__(self, parent, text="", command=None, variant="primary", **kw):
        c = COLORS
        colors = {
            "primary": (c["primary"], c["primary_light"]),
            "success": (c["success"], c["primary_light"]),
            "danger": (c["error"], c["primary_light"]),
            "warning": (c["warning"], c["gold"]),
            "ghost": (c["bg_light"], c["primary"]),
        }
        bg, active_bg = colors.get(variant, colors["primary"])
        fg = "#ffffff" if variant != "ghost" else c["text_primary"]
        super().__init__(parent, bg=c["bg_dark"], **kw)
        self.btn = tk.Button(self, text=text, command=command,
                             bg=bg, fg=fg, activebackground=active_bg,
                             activeforeground="#ffffff", relief="flat",
                             font=FONTS["body_bold"], cursor="hand2",
                             padx=14, pady=8, bd=0)
        self.btn.pack()

    def configure(self, **kw):
        self.btn.configure(**kw)


class StatusBadge(tk.Label):
    def __init__(self, parent, text="", status="info", **kw):
        c = COLORS
        color_map = {
            "present": c["success"],
            "absent": c["error"],
            "late": c["warning"],
            "justified": c["info"],
            "online": c["success"],
            "offline": c["text_muted"],
            "active": c["success"],
            "inactive": c["error"],
            "info": c["info"],
        }
        color = color_map.get(status, c["info"])
        super().__init__(parent, text=text, bg=color, fg="#ffffff",
                         font=FONTS["small_bold"], padx=8, pady=2, **kw)


class EmptyState(tk.Frame):
    def __init__(self, parent, icon="", message="", action_text="", action_cmd=None, **kw):
        c = COLORS
        super().__init__(parent, bg=c["bg_dark"], **kw)
        if icon:
            tk.Label(self, text=icon, font=("Segoe UI Emoji", 40),
                     bg=c["bg_dark"], fg=c["text_muted"]).pack(pady=(20, 8))
        tk.Label(self, text=message, font=FONTS["body"],
                 bg=c["bg_dark"], fg=c["text_muted"]).pack(pady=4)
        if action_text and action_cmd:
            tk.Button(self, text=action_text, command=action_cmd,
                      bg=c["primary"], fg="#ffffff",
                      font=FONTS["body_bold"], relief="flat",
                      cursor="hand2", padx=16, pady=6, bd=0).pack(pady=(8, 20))


class SectionHeader(tk.Frame):
    def __init__(self, parent, title="", subtitle="", **kw):
        c = COLORS
        super().__init__(parent, bg=c["bg_dark"], **kw)
        tk.Label(self, text=title, font=FONTS["section"],
                 bg=c["bg_dark"], fg=c["text_secondary"],
                 anchor="e").pack(fill=tk.X)
        if subtitle:
            tk.Label(self, text=subtitle, font=FONTS["small"],
                     bg=c["bg_dark"], fg=c["text_muted"],
                     anchor="e").pack(fill=tk.X)
