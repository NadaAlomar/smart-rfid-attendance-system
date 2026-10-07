import tkinter as tk
from tkinter import ttk
from ui.theme import COLORS


class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg_key="bg_dark", **kw):
        bg = kw.pop("bg", COLORS[bg_key])
        super().__init__(parent, bg=bg, **kw)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._vscroll = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                       command=self._canvas.yview)
        self._vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._canvas.configure(yscrollcommand=self._vscroll.set)
        self.inner = tk.Frame(self._canvas, bg=bg)
        self._win_id = self._canvas.create_window((0, 0), window=self.inner,
                                                    anchor="nw")
        self.inner.bind("<Configure>",
                         lambda e: self._canvas.configure(
                             scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self.bind("<Enter>", lambda e: self._bind_wheel())
        self.bind("<Leave>", lambda e: self._unbind_wheel())

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _on_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_wheel(self):
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self._canvas.unbind_all("<MouseWheel>")
