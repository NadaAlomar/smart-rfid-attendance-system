import tkinter as tk
from tkinter import ttk
from ui.theme import COLORS, FONTS


class TimePicker(tk.Frame):
    def __init__(self, parent, **kw):
        c = COLORS
        super().__init__(parent, bg=c["bg_dark"], **kw)

        self._hour_var = tk.StringVar(value="08")
        self._min_var = tk.StringVar(value="00")
        self._ampm_var = tk.StringVar(value="AM")
        self._format = "12h"

        hour_spin = tk.Spinbox(self, from_=1, to=12, width=3,
                               textvariable=self._hour_var,
                               font=FONTS["body"], justify="center",
                               bg=c["input_bg"], fg=c["text_primary"],
                               buttonbackground=c["bg_medium"])
        hour_spin.pack(side=tk.LEFT, padx=(0, 2))

        tk.Label(self, text=":", font=FONTS["body_bold"],
                 bg=c["bg_dark"], fg=c["text_primary"]).pack(side=tk.LEFT)

        min_spin = tk.Spinbox(self, from_=0, to=59, width=3,
                              textvariable=self._min_var,
                              font=FONTS["body"], justify="center",
                              format="%02.0f",
                              bg=c["input_bg"], fg=c["text_primary"],
                              buttonbackground=c["bg_medium"])
        min_spin.pack(side=tk.LEFT, padx=(2, 4))

        self._ampm_combo = ttk.Combobox(self, textvariable=self._ampm_var,
                                         values=["AM", "PM"], width=4,
                                         state="readonly")
        self._ampm_combo.pack(side=tk.LEFT)

    def get(self):
        try:
            h = int(self._hour_var.get())
            m = int(self._min_var.get())
            if self._format == "24h":
                return f"{h:02d}:{m:02d}"
            ampm = self._ampm_var.get()
            if ampm == "PM" and h != 12:
                h += 12
            elif ampm == "AM" and h == 12:
                h = 0
            return f"{h:02d}:{m:02d}"
        except (ValueError, tk.TclError):
            return "08:00"

    def set(self, time_str):
        try:
            parts = time_str.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0

            if self._format == "24h":
                self._hour_var.set(f"{h:02d}")
            else:
                ampm = "AM" if h < 12 else "PM"
                h12 = h % 12
                if h12 == 0:
                    h12 = 12
                self._hour_var.set(f"{h12:02d}")
                self._ampm_var.set(ampm)
            self._min_var.set(f"{m:02d}")
        except (ValueError, IndexError):
            pass

    def set_format(self, fmt):
        current_24 = self.get()
        self._format = fmt
        if fmt == "24h":
            self._ampm_combo.pack_forget()
            self._hour_var.set("")
            self.children[next(k for k in self.children if isinstance(self.children[k], tk.Spinbox))].configure(from_=0, to=23)
        else:
            self._ampm_combo.pack(side=tk.LEFT)
            self.children[next(k for k in self.children if isinstance(self.children[k], tk.Spinbox))].configure(from_=1, to=12)
        self.set(current_24)
