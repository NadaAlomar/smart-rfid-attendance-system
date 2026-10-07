import tkinter as tk
from ui.theme import COLORS, FONTS
from ui.rtl_helper import side_start, anchor_start


class CustomCheck(tk.Frame):
    """Checkbox widget with proper RTL support and themed canvas indicator."""

    def __init__(self, parent, text="", variable=None, command=None,
                 fg=None, font_key="body", **kw):
        bg = kw.pop("bg", COLORS["bg_dark"])
        super().__init__(parent, bg=bg, **kw)

        self._variable = variable or tk.BooleanVar(value=False)
        self._command = command
        self._fg = fg or COLORS["text_secondary"]
        self._font = FONTS.get(font_key, FONTS["body"])
        self._bg = bg

        self._canvas = tk.Canvas(
            self, width=18, height=18,
            highlightthickness=0, bg=self._bg, cursor="hand2",
        )
        self._canvas.pack(side=side_start(), padx=(0, 6))

        self._label = tk.Label(
            self, text=text, font=self._font,
            fg=self._fg, bg=self._bg, cursor="hand2",
        )
        self._label.pack(side=side_start(), anchor=anchor_start())

        self._variable.trace_add("write", self._on_var_change)
        self._canvas.bind("<Button-1>", self._on_click)
        self._label.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)

        self._draw()

    def _draw(self):
        c = self._canvas
        c.delete("all")
        checked = self._variable.get()
        fill = COLORS["primary"] if checked else COLORS["bg_card"]
        outline = COLORS["primary"] if checked else COLORS["border"]

        c.create_rectangle(2, 2, 16, 16, fill=fill, outline=outline, width=1)

        if checked:
            c.create_line(5, 9, 8, 12, fill="#ffffff", width=2)
            c.create_line(8, 12, 13, 6, fill="#ffffff", width=2)

    def _on_var_change(self, *_args):
        self._draw()

    def _on_click(self, _event=None):
        current = self._variable.get()
        self._variable.set(not current)
        self.event_generate("<<CustomCheckChanged>>")
        if self._command:
            self._command()

    def get(self):
        return self._variable.get()

    def set(self, value):
        self._variable.set(value)

    def configure_widget(self, **kw):
        if "text" in kw:
            self._label.config(text=kw.pop("text"))
        if "fg" in kw:
            self._fg = kw.pop("fg")
            self._label.config(fg=self._fg)
        if "command" in kw:
            self._command = kw.pop("command")
        if "variable" in kw:
            self._variable = kw.pop("variable")
            self._variable.trace_add("write", self._on_var_change)
            self._draw()
        self.config(**kw)