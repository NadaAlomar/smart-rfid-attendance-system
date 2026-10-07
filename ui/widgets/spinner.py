import tkinter as tk
from ui.theme import COLORS, FONTS


class Spinner(tk.Frame):
    def __init__(self, parent, text="...", **kw):
        c = COLORS
        super().__init__(parent, bg=c["bg_dark"], **kw)
        self.label = tk.Label(self, text=text, font=FONTS["body"],
                              bg=c["bg_dark"], fg=c["primary"])
        self.label.pack(pady=20)
        self._running = False
        self._chars = ["\u2807", "\u2839", "\u2838", "\u2834",
                       "\u2826", "\u2807", "\u280f", "\u2819"]
        self._idx = 0

    def start(self, text=None):
        if text:
            self.label.config(text=text)
        self._running = True
        self._animate()

    def stop(self):
        self._running = False
        self.label.config(text="")

    def _animate(self):
        if not self._running:
            return
        char = self._chars[self._idx % len(self._chars)]
        current = self.label.cget("text")
        base = current.split(" ")[0] if " " in current else ""
        self.label.config(text=f"{base} {char}" if base else char)
        self._idx += 1
        self.after(200, self._animate)
