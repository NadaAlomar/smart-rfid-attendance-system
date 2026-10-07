import tkinter as tk
from ui.theme import COLORS, FONTS


class Toast(tk.Toplevel):
    def __init__(self, parent, message="", variant="info", duration=3000, **kw):
        super().__init__(parent, **kw)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        c = COLORS
        bg_map = {
            "success": c["success"],
            "error": c["error"],
            "warning": c["warning"],
            "info": c["primary"],
        }
        bg = bg_map.get(variant, c["primary"])

        frame = tk.Frame(self, bg=bg, padx=16, pady=10)
        frame.pack()
        tk.Label(frame, text=message, font=FONTS["body_bold"],
                 bg=bg, fg="#ffffff").pack()

        self.update_idletasks()
        x = parent.winfo_rootx() + parent.winfo_width() // 2 - self.winfo_width() // 2
        y = parent.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")

        self.after(duration, self.destroy)


def show_toast(parent, message, variant="info", duration=3000):
    if parent and parent.winfo_exists():
        Toast(parent, message=message, variant=variant, duration=duration)
