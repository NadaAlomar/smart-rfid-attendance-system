"""
Theme system مع دعم الوضعين الفاتح والداكن
"""
import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path

# ─── ملف حفظ الإعدادات ───
_PREFS_FILE = Path(__file__).resolve().parent.parent / "data" / "ui_prefs.json"


# ══════════════════════════════════════════════════════════════
#  لوحات الألوان
# ══════════════════════════════════════════════════════════════

DARK_COLORS = {
    "bg_dark":        "#0f0a1e",
    "bg_medium":      "#1a1035",
    "bg_light":       "#251848",
    "bg_card":        "#1e1540",
    "bg_card2":       "#2a1d56",
    "primary":        "#7c3aed",
    "primary_light":  "#9f67ff",
    "primary_dark":   "#5b21b6",
    "accent":         "#c084fc",
    "accent2":        "#e879f9",
    "success":        "#22c55e",
    "error":          "#ef4444",
    "warning":        "#f59e0b",
    "info":           "#38bdf8",
    "text_primary":   "#f5f3ff",
    "text_secondary": "#c4b5fd",
    "text_muted":     "#9384c2",
    "border":         "#4c1d95",
    "border_light":   "#6d28d9",
    "sidebar_bg":     "#080514",
    "input_bg":       "#1a1035",
    "hover":          "#6d28d9",
    "gold":           "#fbbf24",
    "sidebar_text":   "#c4b5fd",
    "sidebar_muted":  "#9384c2",
    "sidebar_active": "#ffffff",
    "present_bg":     "#dcfce7",
    "absent_bg":      "#fee2e2",
    "late_bg":        "#fef3c7",
    "justified_bg":   "#dbeafe",
    "online":         "#10b981",
    "offline":        "#6b7280",
    "pending":        "#f59e0b",
    "sidebar_text":   "#c4b5fd",
    "sidebar_sec":    "#9384c2",
    "sidebar_active":  "#7c3aed",
}

LIGHT_COLORS = {
    "bg_dark":        "#f3f4f6",
    "bg_medium":      "#ffffff",
    "bg_light":       "#e5e7eb",
    "bg_card":        "#ffffff",
    "bg_card2":       "#f9fafb",
    "primary":        "#7c3aed",
    "primary_light":  "#9f67ff",
    "primary_dark":   "#5b21b6",
    "accent":         "#7c3aed",
    "accent2":        "#a855f7",
    "success":        "#16a34a",
    "error":          "#dc2626",
    "warning":        "#d97706",
    "info":           "#0284c7",
    "text_primary":   "#111827",
    "text_secondary": "#374151",
    "text_muted":     "#6b7280",
    "border":         "#d1d5db",
    "border_light":   "#9ca3af",
    "sidebar_bg":     "#4c1d95",
    "sidebar_text":   "#ede9fe",
    "sidebar_muted":  "#c4b5fd",
    "sidebar_active": "#ffffff",
    "sidebar_sec":    "#c4b5fd",
    "input_bg":       "#f9fafb",
    "hover":          "#e5e7eb",
    "gold":           "#d97706",
}

# الـ COLORS الحالية (تتغير حسب الوضع)
COLORS = dict(DARK_COLORS)


# ══════════════════════════════════════════════════════════════
#  الخطوط
# ══════════════════════════════════════════════════════════════

FONT_FAMILIES = {
    "ar": {"primary": "Tahoma", "secondary": "Segoe UI", "mono": "Consolas"},
    "en": {"primary": "Segoe UI", "secondary": "Segoe UI", "mono": "Consolas"},
}

FONT_SIZES = {
    "hero":        (24, "bold"),
    "title":       (18, "bold"),
    "subtitle":    (14, "bold"),
    "section":     (13, "bold"),
    "body":        (11, "normal"),
    "body_bold":   (11, "bold"),
    "small":       (10, "normal"),
    "small_bold":  (10, "bold"),
    "mono":        (12, "normal"),
    "mono_large":  (16, "bold"),
    "stat_value":  (28, "bold"),
    "stat_label":  (11, "normal"),
    "sidebar_sec": (9, "bold"),
    "sidebar_btn": (11, "normal"),
}

FONT_SCALE = 1.0

_current_theme = "dark"
_current_lang = "ar"


def _build_fonts():
    lang = _current_lang
    fam = FONT_FAMILIES.get(lang, FONT_FAMILIES["en"])["primary"]
    result = {}
    for key, (size, weight) in FONT_SIZES.items():
        scaled = max(8, int(size * FONT_SCALE))
        if weight == "normal":
            result[key] = (fam, scaled)
        else:
            result[key] = (fam, scaled, weight)
    return result


FONTS = _build_fonts()


def reload_fonts():
    global FONTS
    new = _build_fonts()
    FONTS.clear()
    FONTS.update(new)


# ══════════════════════════════════════════════════════════════
#  إدارة الإعدادات
# ══════════════════════════════════════════════════════════════

_theme_listeners = []


def get_prefs():
    global _current_theme, _current_lang
    try:
        if _PREFS_FILE.exists():
            with open(_PREFS_FILE, "r", encoding="utf-8") as f:
                p = json.load(f)
                _current_theme = p.get("theme", "dark")
                _current_lang = p.get("lang", "ar")
    except Exception:
        pass
    return {"theme": _current_theme, "lang": _current_lang}


def save_prefs(theme=None, lang=None):
    global _current_theme, _current_lang
    if theme:
        _current_theme = theme
    if lang:
        _current_lang = lang
    try:
        _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": _current_theme, "lang": _current_lang}, f)
    except Exception:
        pass


def get_theme():
    return _current_theme


def get_lang():
    return _current_lang


def set_theme(theme):
    """ثبّت الوضع: 'light' أو 'dark'"""
    global COLORS
    new_colors = LIGHT_COLORS if theme == "light" else DARK_COLORS
    COLORS.clear()
    COLORS.update(new_colors)
    save_prefs(theme=theme)


def register_theme_listener(callback):
    if callback not in _theme_listeners:
        _theme_listeners.append(callback)


def notify_theme_change():
    for cb in _theme_listeners:
        try:
            cb()
        except Exception:
            pass


# تحميل الإعدادات عند الاستيراد
get_prefs()
set_theme(_current_theme)


# ══════════════════════════════════════════════════════════════
#  تطبيق الـ Theme على Tkinter
# ══════════════════════════════════════════════════════════════

_style = None


def apply_theme(root):
    """يطبّق الـ theme الحالي على نافذة معيّنة وعلى الـ ttk styles"""
    global _style
    root.configure(bg=COLORS["bg_dark"])

    style = ttk.Style()
    _style = style
    try:
        style.theme_use("clam")
    except Exception:
        pass

    c = COLORS

    # عام
    style.configure(".",
        background=c["bg_dark"],
        foreground=c["text_primary"],
        fieldbackground=c["input_bg"],
        bordercolor=c["border"],
        focuscolor=c["primary_light"],
        troughcolor=c["bg_medium"],
        selectbackground=c["primary"],
        selectforeground=c["text_primary"],
        font=FONTS["body"],
    )

    # Frames
    style.configure("TFrame", background=c["bg_dark"])
    style.configure("Card.TFrame", background=c["bg_card"])
    style.configure("Sidebar.TFrame", background=c["sidebar_bg"])

    # Labels
    style.configure("TLabel",
        background=c["bg_dark"],
        foreground=c["text_primary"],
        font=FONTS["body"])

    # Buttons
    style.configure("TButton",
        background=c["primary"],
        foreground="#ffffff",
        padding=(14, 8),
        font=FONTS["body_bold"],
        borderwidth=0,
        relief="flat")
    style.map("TButton",
        background=[("active", c["primary_light"]),
                    ("pressed", c["primary_dark"])])

    # Entries
    style.configure("TEntry",
        fieldbackground=c["input_bg"],
        foreground=c["text_primary"],
        insertcolor=c["accent"],
        bordercolor=c["border_light"],
        focuscolor=c["primary_light"],
        padding=(8, 6),
        font=FONTS["body"])
    style.map("TEntry",
        fieldbackground=[("focus", c["bg_card2"])],
        bordercolor=[("focus", c["primary_light"])])

    # Combobox
    style.configure("TCombobox",
        fieldbackground=c["input_bg"],
        foreground=c["text_primary"],
        selectbackground=c["primary"],
        selectforeground="#ffffff",
        bordercolor=c["border_light"],
        padding=(8, 6),
        font=FONTS["body"])
    style.map("TCombobox",
        fieldbackground=[("readonly", c["input_bg"])],
        foreground=[("readonly", c["text_primary"])])

    # خلفية القائمة المنسدلة
    root.option_add("*TCombobox*Listbox.background", c["bg_card"])
    root.option_add("*TCombobox*Listbox.foreground", c["text_primary"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])

    # Checkbutton / Radiobutton
    style.configure("TCheckbutton",
        background=c["bg_dark"],
        foreground=c["text_secondary"],
        font=FONTS["body"])
    style.map("TCheckbutton",
        background=[("active", c["bg_light"])],
        foreground=[("active", c["accent"])])

    style.configure("TRadiobutton",
        background=c["bg_dark"],
        foreground=c["text_secondary"],
        font=FONTS["body"])
    style.map("TRadiobutton",
        background=[("active", c["bg_light"])],
        foreground=[("active", c["accent"])])

    # LabelFrame
    style.configure("TLabelframe",
        background=c["bg_dark"],
        foreground=c["accent"],
        bordercolor=c["border_light"],
        font=FONTS["section"],
        relief="solid",
        borderwidth=1)
    style.configure("TLabelframe.Label",
        background=c["bg_dark"],
        foreground=c["accent"],
        font=FONTS["section"])

    # Treeview
    style.configure("Treeview",
        background=c["bg_card"],
        foreground=c["text_primary"],
        fieldbackground=c["bg_card"],
        bordercolor=c["border"],
        font=FONTS["body"],
        rowheight=32)
    style.configure("Treeview.Heading",
        background=c["bg_medium"],
        foreground=c["accent"],
        font=FONTS["body_bold"],
        bordercolor=c["border"],
        relief="flat",
        padding=(8, 6))
    style.map("Treeview",
        background=[("selected", c["primary"])],
        foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading",
        background=[("active", c["bg_light"])])

    # Scrollbar
    style.configure("Vertical.TScrollbar",
        background=c["bg_medium"],
        troughcolor=c["bg_dark"],
        bordercolor=c["border"],
        arrowsize=14)
    style.map("Vertical.TScrollbar",
        background=[("active", c["primary"])])

    # Progressbar
    style.configure("TProgressbar",
        background=c["primary_light"],
        troughcolor=c["bg_medium"],
        bordercolor=c["border"],
        thickness=8)

    # Notebook
    style.configure("TNotebook",
        background=c["bg_dark"],
        borderwidth=0,
        tabmargins=0)
    style.configure("TNotebook.Tab",
        background=c["bg_medium"],
        foreground=c["text_muted"],
        padding=(18, 8),
        font=FONTS["body_bold"])
    style.map("TNotebook.Tab",
        background=[("selected", c["primary"])],
        foreground=[("selected", "#ffffff")])

    # Separator
    style.configure("TSeparator", background=c["border"])


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def create_styled_treeview(parent, columns, show="headings", height=None, selectmode=None):
    kw = dict(columns=columns, show=show)
    if height is not None:
        kw["height"] = height
    if selectmode is not None:
        kw["selectmode"] = selectmode
    return ttk.Treeview(parent, **kw)


def create_styled_label_frame(parent, text="", padding=None):
    kw = dict(text=text)
    if padding is not None:
        kw["padding"] = padding
    return ttk.LabelFrame(parent, **kw)


def create_styled_entry(parent, **kw):
    return ttk.Entry(parent, **kw)


def create_themed_checkbutton(parent, text="", variable=None, command=None, **kw):
    c = COLORS
    try:
        bg = parent.cget("bg")
    except Exception:
        bg = c["bg_card"]
    return tk.Checkbutton(
        parent,
        text=text,
        variable=variable,
        command=command,
        bg=bg,
        fg=c["text_primary"],
        selectcolor=c["bg_dark"],
        activebackground=bg,
        activeforeground=c["accent"],
        font=FONTS["body"],
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        **kw,
    )


def themed_frame(parent, bg_key="bg_dark"):
    return tk.Frame(parent, bg=COLORS[bg_key])


def themed_label(parent, text, font_key="body", color_key="text_primary", **kw):
    c = COLORS
    return tk.Label(parent, text=text,
                    font=FONTS.get(font_key, FONTS["body"]),
                    bg=c["bg_dark"],
                    fg=c.get(color_key, c["text_primary"]), **kw)


def create_stat_card(parent, value, label, color):
    c = COLORS
    outer = tk.Frame(parent, bg=color, padx=2, pady=2)
    inner = tk.Frame(outer, bg=c["bg_card"], padx=22, pady=18)
    inner.pack(fill=tk.BOTH, expand=True)
    tk.Frame(inner, bg=color, height=4).pack(fill=tk.X, pady=(0, 10))
    val_lbl = tk.Label(inner, text=str(value), font=FONTS["stat_value"],
                       bg=c["bg_card"], fg=color)
    val_lbl.pack()
    tk.Label(inner, text=label, font=FONTS["stat_label"],
             bg=c["bg_card"], fg=c["text_secondary"]).pack(pady=(4, 0))
    return outer, val_lbl


def create_header_bar(parent, title, subtitle=""):
    c = COLORS
    bar = tk.Frame(parent, bg=c["bg_medium"])
    left = tk.Frame(bar, bg=c["bg_medium"])
    left.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=12)
    tk.Label(left, text=title, font=FONTS["hero"],
             bg=c["bg_medium"], fg=c["accent"]).pack(anchor="w")
    if subtitle:
        tk.Label(left, text=subtitle, font=FONTS["small"],
                 bg=c["bg_medium"], fg=c["text_muted"]).pack(anchor="w")
    tk.Frame(bar, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)
    return bar


def create_styled_button(parent, text="", command=None, width=None, **kw):
    c = COLORS
    btn = tk.Button(parent, text=text, command=command,
                    bg=c["primary"], fg="#ffffff",
                    activebackground=c["primary_light"],
                    activeforeground="#ffffff",
                    relief="flat", font=FONTS["sidebar_btn"],
                    cursor="hand2", bd=0, padx=10, pady=6, **kw)
    if width is not None:
        btn.configure(width=width)
    return btn


def safe_after(widget, delay_ms, callback):
    """Schedule callback after delay_ms, but skip if widget was destroyed.

    Use this instead of widget.after() for any recurring UI refresh
    to prevent TclError when the widget's parent page is closed.
    """
    def _wrapped():
        try:
            if widget.winfo_exists():
                callback()
        except (tk.TclError, AttributeError):
            pass
    try:
        return widget.after(delay_ms, _wrapped)
    except (tk.TclError, AttributeError):
        return None
