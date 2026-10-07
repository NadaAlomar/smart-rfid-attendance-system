import tkinter as tk
from tkinter import messagebox
from ui.theme import COLORS, FONTS


def themed_message(parent, title, message, variant="info"):
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=COLORS["bg_card"])
    top.resizable(False, False)
    top.transient(parent)
    top.grab_set()

    color_map = {
        "info": COLORS["primary"],
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
    }
    color = color_map.get(variant, COLORS["primary"])

    icon_map = {
        "info": "\u2139\ufe0f",
        "success": "\u2705",
        "warning": "\u26a0\ufe0f",
        "error": "\u274c",
    }
    icon = icon_map.get(variant, "\u2139\ufe0f")

    tk.Frame(top, bg=color, height=4).pack(fill=tk.X)

    body = tk.Frame(top, bg=COLORS["bg_card"], padx=30, pady=24)
    body.pack()

    tk.Label(body, text=icon, font=("Segoe UI Emoji", 28),
             bg=COLORS["bg_card"], fg=color).pack(pady=(0, 12))
    tk.Label(body, text=title, font=FONTS["subtitle"],
             bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack()
    tk.Label(body, text=message, font=FONTS["body"],
             bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
             wraplength=350, justify="center").pack(pady=(8, 16))

    tk.Button(body, text="OK", command=top.destroy,
              bg=color, fg="#ffffff", font=FONTS["body_bold"],
              relief="flat", cursor="hand2", padx=24, pady=6, bd=0).pack()

    top.update_idletasks()
    x = parent.winfo_rootx() + parent.winfo_width() // 2 - top.winfo_width() // 2
    y = parent.winfo_rooty() + parent.winfo_height() // 2 - top.winfo_height() // 2
    top.geometry(f"+{x}+{y}")

    top.wait_window()
