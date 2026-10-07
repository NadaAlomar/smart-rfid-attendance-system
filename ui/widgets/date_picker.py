import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import calendar
from ui.theme import COLORS, FONTS
from ui.i18n import t
from ui.rtl_helper import side_start, side_end, anchor_start


_MONTH_NAMES = [
    "01", "02", "03", "04", "05", "06",
    "07", "08", "09", "10", "11", "12",
]


class DatePicker(tk.Frame):
    """Three-combobox date picker: Year / Month / Day.

    Reads/writes ISO date (YYYY-MM-DD) via the bound StringVar.
    """

    def __init__(self, parent, variable=None, **kw):
        bg = kw.pop("bg", COLORS["bg_dark"])
        super().__init__(parent, bg=bg, **kw)
        self._var = variable or tk.StringVar()
        self._bg = bg
        self._guard = False
        self._build()
        self._sync_from_var()
        self._var.trace_add("write", lambda *_: self._sync_from_var())

    def _years_list(self):
        today = date.today()
        return [str(y) for y in range(today.year - 5, today.year + 11)]

    def _days_for(self, year, month):
        try:
            last = calendar.monthrange(int(year), int(month))[1]
        except Exception:
            last = 31
        return [f"{d:02d}" for d in range(1, last + 1)]

    def _build(self):
        c = COLORS
        row = tk.Frame(self, bg=self._bg)
        row.pack(fill=tk.X)

        self._year_var = tk.StringVar()
        self._month_var = tk.StringVar()
        self._day_var = tk.StringVar()

        self._year_cb = ttk.Combobox(row, textvariable=self._year_var,
                                      values=self._years_list(),
                                      state="readonly", width=6,
                                      font=FONTS["body"])
        self._month_cb = ttk.Combobox(row, textvariable=self._month_var,
                                       values=_MONTH_NAMES,
                                       state="readonly", width=4,
                                       font=FONTS["body"])
        self._day_cb = ttk.Combobox(row, textvariable=self._day_var,
                                     values=self._days_for(date.today().year,
                                                            date.today().month),
                                     state="readonly", width=4,
                                     font=FONTS["body"])
        # RTL order: Day | Month | Year reads naturally right-to-left
        self._year_cb.pack(side=side_start(), padx=(0, 2))
        self._month_cb.pack(side=side_start(), padx=(0, 2))
        self._day_cb.pack(side=side_start())

        self._year_cb.bind("<<ComboboxSelected>>", lambda e: self._on_change())
        self._month_cb.bind("<<ComboboxSelected>>", lambda e: self._on_change())
        self._day_cb.bind("<<ComboboxSelected>>", lambda e: self._on_change())

    def _sync_from_var(self):
        if self._guard:
            return
        self._guard = True
        try:
            val = (self._var.get() or "").strip()
            d = None
            if val:
                try:
                    d = datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    d = None
            if d is None:
                d = date.today()
            self._year_var.set(str(d.year))
            self._month_var.set(f"{d.month:02d}")
            self._day_cb["values"] = self._days_for(d.year, d.month)
            self._day_var.set(f"{d.day:02d}")
        finally:
            self._guard = False

    def _on_change(self):
        if self._guard:
            return
        self._guard = True
        try:
            try:
                y = int(self._year_var.get())
                m = int(self._month_var.get())
            except ValueError:
                return
            self._day_cb["values"] = self._days_for(y, m)
            try:
                day_str = self._day_var.get() or "01"
                d = max(1, min(int(day_str), len(self._day_cb["values"])))
            except ValueError:
                d = 1
            self._day_var.set(f"{d:02d}")
            self._var.set(f"{y:04d}-{m:02d}-{d:02d}")
        finally:
            self._guard = False

    def set_enabled(self, enabled: bool):
        state = "readonly" if enabled else "disabled"
        for cb in (self._year_cb, self._month_cb, self._day_cb):
            cb.config(state=state)

    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(value)
