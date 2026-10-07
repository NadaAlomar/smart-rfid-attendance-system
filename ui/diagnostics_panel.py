import os
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ui import http_client

from ui.i18n import t
from ui.rtl_helper import side_start, side_end, anchor_start, pad_x
from ui.theme import COLORS, FONTS, safe_after



class DiagnosticsPanel:
    LOGS = (
        ("app", "diagnostics.tab_app"),
        ("errors", "diagnostics.tab_errors"),
        ("scan", "diagnostics.tab_scan"),
        ("missing_i18n", "diagnostics.tab_missing_i18n"),
    )

    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self.log_dir = Path(__file__).resolve().parent.parent / "data"
        self._texts = {}
        self._build()
        self.refresh()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        self._button(toolbar, t("diagnostics.refresh"), self.refresh, c["primary"])
        self._button(toolbar, t("diagnostics.clear"), self.clear_current, c["bg_light"], fg=c["text_primary"])
        self._button(toolbar, t("diagnostics.export"), self.export_current, c["info"])
        self._button(toolbar, t("diagnostics.open_folder"), self.open_log_folder, c["success"])

        self.status_lbl = tk.Label(toolbar, text=t("diagnostics.ready"),
                                   font=FONTS["small"], bg=c["bg_dark"],
                                   fg=c["text_muted"], anchor=anchor_start())
        self.status_lbl.pack(side=side_end(), padx=10)

        self.notebook = ttk.Notebook(wrap)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        for log_type, title_key in self.LOGS:
            tab = tk.Frame(self.notebook, bg=c["bg_dark"])
            self.notebook.add(tab, text=t(title_key))

            text_wrap = tk.Frame(tab, bg=c["bg_dark"])
            text_wrap.pack(fill=tk.BOTH, expand=True)

            ysb = ttk.Scrollbar(text_wrap, orient=tk.VERTICAL)
            xsb = ttk.Scrollbar(text_wrap, orient=tk.HORIZONTAL)
            text = tk.Text(
                text_wrap,
                bg=c["bg_card"], fg=c["text_primary"],
                insertbackground=c["accent"], selectbackground=c["primary"],
                relief="flat", bd=0, wrap="none", state=tk.DISABLED,
                font=FONTS["mono"], padx=10, pady=10,
                yscrollcommand=ysb.set, xscrollcommand=xsb.set,
            )
            ysb.configure(command=text.yview)
            xsb.configure(command=text.xview)
            ysb.pack(side=side_end(), fill=tk.Y)
            xsb.pack(side=tk.BOTTOM, fill=tk.X)
            text.pack(side=side_start(), fill=tk.BOTH, expand=True)
            self._texts[log_type] = text

        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self.refresh())

    def _button(self, parent, text, command, bg, fg="#ffffff"):
        btn = tk.Button(parent, text=text, command=command,
                        bg=bg, fg=fg, activebackground=COLORS["primary_light"],
                        activeforeground="#ffffff", font=FONTS["small_bold"],
                        relief="flat", cursor="hand2", padx=12, pady=6, bd=0)
        btn.pack(side=side_start(), padx=pad_x(0, 6))
        return btn

    def _current_log_type(self):
        try:
            idx = self.notebook.index(self.notebook.select())
            return self.LOGS[idx][0]
        except Exception:
            return "app"

    def _set_status(self, text):
        try:
            if self.status_lbl.winfo_exists():
                self.status_lbl.config(text=text)
        except tk.TclError:
            pass

    def _set_text(self, log_type, content):
        text = self._texts.get(log_type)
        if not text:
            return
        try:
            if not text.winfo_exists():
                return
            text.configure(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            text.insert("1.0", content or t("diagnostics.no_data"))
            text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass

    def _get_text(self, log_type):
        text = self._texts.get(log_type)
        if not text:
            return ""
        try:
            return text.get("1.0", tk.END).rstrip("\n")
        except tk.TclError:
            return ""

    def refresh(self, log_type=None):
        log_type = log_type or self._current_log_type()
        self._set_status(t("diagnostics.loading"))

        def do():
            try:
                resp = http_client.api_get("/api/diagnostics/log", type=log_type, lines=1000)
                data = resp.json()
                if not data.get("success"):
                    raise RuntimeError(data.get("error", t("diagnostics.load_failed")))
                content = data.get("content") or ""
                filename = data.get("filename", log_type)
                truncated = data.get("truncated", False)

                def update():
                    self._set_text(log_type, content)
                    suffix = "" if not truncated else " - truncated"
                    self._set_status(f"{t('diagnostics.loaded')}: {filename}{suffix}")

                safe_after(self.parent, 0, update)
            except Exception as ex:
                msg = str(ex)
                safe_after(self.parent, 0, lambda m=msg: self._set_status(
                    f"{t('diagnostics.load_failed')}: {m}"))

        threading.Thread(target=do, daemon=True).start()

    def clear_current(self):
        log_type = self._current_log_type()
        self._set_text(log_type, "")
        self._set_status(t("diagnostics.cleared"))

    def export_current(self):
        log_type = self._current_log_type()
        content = self._get_text(log_type)
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(content)
            messagebox.showinfo(t("ok"), f"{t('diagnostics.exported')}: {path}")
        except Exception as ex:
            messagebox.showerror(t("error"), f"{t('diagnostics.export_failed')}: {ex}")

    def open_log_folder(self):
        try:
            os.startfile(str(self.log_dir))
        except Exception as ex:
            messagebox.showerror(t("error"), f"{t('diagnostics.open_failed')}: {ex}")
