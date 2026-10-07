"""Attendance Logs panel: filter, view, and export scan logs (success + failures)."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui import http_client
import threading
import csv
from datetime import datetime
from ui.theme import COLORS, FONTS, create_styled_treeview, create_themed_checkbutton, safe_after
from ui.rtl_helper import side_start, side_end, text_justify, anchor_start, pad_x
from ui.i18n import t
from ui import client_time



SCAN_TYPES = [
    ("all", "attendance_logs.all"),
    ("doctor_open", "attendance_logs.type_doctor_open"),
    ("doctor_close", "attendance_logs.type_doctor_close"),
    ("student_in", "attendance_logs.type_student_in"),
    ("unknown_card", "attendance_logs.type_unknown_card"),
    ("wrong_hall", "attendance_logs.type_wrong_hall"),
    ("no_session", "attendance_logs.type_no_session"),
    ("expired_card", "attendance_logs.type_expired_card"),
]


class AttendanceLogsPanel:
    def __init__(self, parent):
        self.parent = parent
        self._halls = []
        self._scan_type_labels = []
        self._page = 1
        self._per_page = 100
        self._auto_refresh_job = None
        self._auto_refresh = tk.BooleanVar(value=False)
        self._build()
        self._load_halls()
        self.refresh()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── Filter bar (two rows) ──
        filt = tk.Frame(wrap, bg=c["bg_dark"])
        filt.pack(fill=tk.X, pady=(0, 8))

        # Row 1
        row1 = tk.Frame(filt, bg=c["bg_dark"])
        row1.pack(fill=tk.X, pady=2)

        tk.Label(row1, text=t("attendance_logs.filter_search"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.search_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.search_var,
                  font=FONTS["body"], bg=c["input_bg"],
                  fg=c["text_primary"], insertbackground=c["accent"],
                  relief="flat", bd=0, width=20,
                  justify=text_justify()).pack(side=side_start(), ipady=5, padx=pad_x(0, 12))

        tk.Label(row1, text=t("attendance_logs.filter_hall"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.hall_var = tk.StringVar()
        self.hall_combo = ttk.Combobox(row1, textvariable=self.hall_var,
                                        values=[t("attendance_logs.all")], width=14,
                                        state="readonly")
        self.hall_combo.current(0)
        self.hall_combo.pack(side=side_start(), padx=pad_x(0, 12))

        tk.Label(row1, text=t("attendance_logs.filter_type"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.type_var = tk.StringVar()
        self._scan_type_labels = [t(k) for _, k in SCAN_TYPES]
        self.type_combo = ttk.Combobox(row1, textvariable=self.type_var,
                                        values=self._scan_type_labels, width=18,
                                        state="readonly")
        self.type_combo.current(0)
        self.type_combo.pack(side=side_start(), padx=pad_x(0, 12))

        tk.Label(row1, text=t("attendance_logs.filter_status"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(row1, textvariable=self.status_var,
                                          values=[t("attendance_logs.all"),
                                                   t("attendance_logs.success"),
                                                   t("attendance_logs.failure")],
                                          width=10, state="readonly")
        self.status_combo.current(0)
        self.status_combo.pack(side=side_start())

        # Row 2 (dates + buttons)
        row2 = tk.Frame(filt, bg=c["bg_dark"])
        row2.pack(fill=tk.X, pady=4)

        tk.Label(row2, text=t("attendance_logs.filter_date_from"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.date_from_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.date_from_var,
                  font=FONTS["body"], bg=c["input_bg"],
                  fg=c["text_primary"], insertbackground=c["accent"],
                  relief="flat", bd=0, width=12,
                  justify=text_justify()).pack(side=side_start(), ipady=5, padx=pad_x(0, 4))

        tk.Label(row2, text=t("attendance_logs.filter_date_to"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(0, 4))
        self.date_to_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.date_to_var,
                  font=FONTS["body"], bg=c["input_bg"],
                  fg=c["text_primary"], insertbackground=c["accent"],
                  relief="flat", bd=0, width=12,
                  justify=text_justify()).pack(side=side_start(), ipady=5, padx=pad_x(0, 12))

        tk.Button(row2, text=f"🔍 {t('attendance_logs.search_btn')}",
                  command=self.refresh,
                  bg=c["primary"], fg="#ffffff",
                  font=FONTS["small_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 6))

        tk.Button(row2, text=t("attendance_logs.clear_filters"),
                  command=self._clear_filters,
                  bg=c["bg_light"], fg=c["text_primary"],
                  font=FONTS["small_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 6))

        tk.Button(row2, text=f"⬇ {t('attendance_logs.export_csv')}",
                  command=self._export_csv,
                  bg=c["info"], fg="#ffffff",
                  font=FONTS["small_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 6))

        tk.Button(row2, text=f"🗑 {t('attendance_logs.delete_logs')}",
                  command=self._delete_logs,
                  bg=c["error"], fg="#ffffff",
                  font=FONTS["small_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 6))

        create_themed_checkbutton(row2, text=t("attendance_logs.auto_refresh"),
                                  variable=self._auto_refresh,
                                  command=self._toggle_auto_refresh).pack(side=side_end())

        # ── Today summary cards ──
        self.summary_frame = tk.Frame(wrap, bg=c["bg_dark"])
        self.summary_frame.pack(fill=tk.X, pady=(0, 8))

        # ── Main tree ──
        tree_wrap = tk.Frame(wrap, bg=c["bg_dark"])
        tree_wrap.pack(fill=tk.BOTH, expand=True)

        cols = ("time", "hall", "device", "type", "status", "name", "uid", "reason")
        self.tree = create_styled_treeview(tree_wrap, columns=cols,
                                            show="headings", selectmode="browse")
        hdrs = {
            "time":   (t("attendance_logs.col_time"),   140),
            "hall":   (t("attendance_logs.col_hall"),   110),
            "device": (t("attendance_logs.col_device"), 110),
            "type":   (t("attendance_logs.col_type"),   140),
            "status": (t("attendance_logs.col_status"),  60),
            "name":   (t("attendance_logs.col_name"),   200),
            "uid":    (t("attendance_logs.col_uid"),     80),
            "reason": (t("attendance_logs.col_reason"), 180),
        }
        for col, (h, w) in hdrs.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center", minwidth=40)

        vsb = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=self.tree.yview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.tag_configure("ok", background=c["bg_card"], foreground=c["success"])
        self.tree.tag_configure("fail", background="#3d1f1f", foreground=c["error"])

        # Status bar
        bar = tk.Frame(wrap, bg=c["bg_dark"])
        bar.pack(fill=tk.X, pady=(6, 0))
        self.status_lbl = tk.Label(bar, text="", font=FONTS["small"],
                                    bg=c["bg_dark"], fg=c["text_muted"])
        self.status_lbl.pack(side=side_start())

        self._latest_logs = []

    def _clear_filters(self):
        self.search_var.set("")
        self.hall_combo.current(0)
        self.type_combo.current(0)
        self.status_combo.current(0)
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.refresh()

    def _load_halls(self):
        def do():
            try:
                r = http_client.api_get("/api/halls").json()
                self._halls = r.get("halls", [])
                values = [t("attendance_logs.all")] + [h["hall_name"] for h in self._halls]
                self.parent.after(0, lambda: self.hall_combo.configure(values=values))
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _selected_scan_type(self):
        idx = self.type_combo.current()
        if idx <= 0 or idx >= len(SCAN_TYPES):
            return None
        return SCAN_TYPES[idx][0]

    def _selected_hall_id(self):
        idx = self.hall_combo.current()
        if idx <= 0 or idx - 1 >= len(self._halls):
            return None
        return self._halls[idx - 1]["id"]

    def _selected_success_filter(self):
        idx = self.status_combo.current()
        if idx == 1:
            return "true"
        if idx == 2:
            return "false"
        return None

    def refresh(self):
        try:
            if not self.tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return

        # Clear tree
        for r in self.tree.get_children():
            self.tree.delete(r)

        params = {
            "page": self._page,
            "per_page": self._per_page,
        }
        if self.search_var.get().strip():
            params["q"] = self.search_var.get().strip()
        hall_id = self._selected_hall_id()
        if hall_id:
            params["hall_id"] = hall_id
        scan_type = self._selected_scan_type()
        if scan_type:
            params["scan_type"] = scan_type
        success = self._selected_success_filter()
        if success:
            params["success"] = success
        if self.date_from_var.get().strip():
            params["from"] = self.date_from_var.get().strip()
        if self.date_to_var.get().strip():
            params["to"] = self.date_to_var.get().strip()

        def do():
            try:
                r = http_client.api_get("/api/scan-logs", **params).json()
                if not r.get("success"):
                    return
                logs = r.get("logs", [])
                self._latest_logs = logs
                total = r.get("total", 0)

                def update():
                    try:
                        if not self.tree.winfo_exists():
                            return
                    except (tk.TclError, AttributeError):
                        return
                    for lg in logs:
                        ts = lg.get("timestamp") or ""
                        ts_short = ""
                        if ts:
                            try:
                                ts_short = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                ts_short = ts[:19]
                        name = lg.get("student_name") or lg.get("doctor_name") or t("attendance_logs.no_card")
                        type_key = f"attendance_logs.type_{lg['scan_type']}"
                        type_label = t(type_key) if type_key in (t(k) for _, k in SCAN_TYPES) else lg["scan_type"]
                        # better fallback
                        type_label = t(type_key)
                        status_icon = "✓" if lg.get("success") else "✗"
                        tag = "ok" if lg.get("success") else "fail"
                        self.tree.insert("", tk.END, values=(
                            ts_short,
                            lg.get("hall_name") or "—",
                            lg.get("device_id") or "—",
                            type_label,
                            status_icon,
                            name,
                            lg.get("raw_uid_hint") or "—",
                            lg.get("error_reason") or "—",
                        ), tags=(tag,))
                    self.status_lbl.config(
                        text=f"{len(logs)} / {total}"
                    )

                safe_after(self.parent, 0, update)
                safe_after(self.parent, 0, self._load_today_summary)
            except Exception as e:
                safe_after(self.parent, 0, lambda: self.status_lbl.config(text=f"{t('error')}: {e}"))
        threading.Thread(target=do, daemon=True).start()

    def _load_today_summary(self):
        def do():
            try:
                r = http_client.api_get("/api/scan-logs/halls-today").json()
                halls = r.get("halls", [])

                def update():
                    try:
                        if not self.summary_frame.winfo_exists():
                            return
                    except (tk.TclError, AttributeError):
                        return
                    for child in self.summary_frame.winfo_children():
                        child.destroy()
                    tk.Label(self.summary_frame, text=t("attendance_logs.today_summary"),
                             font=FONTS["small_bold"], bg=COLORS["bg_dark"],
                             fg=COLORS["accent"]).pack(side=side_start(), padx=pad_x(0, 12))
                    for h in halls:
                        if h["success"] == 0 and h["failure"] == 0:
                            continue
                        card = tk.Frame(self.summary_frame, bg=COLORS["bg_card"],
                                         padx=8, pady=4)
                        card.pack(side=side_start(), padx=4)
                        tk.Label(card, text=h["hall_name"], font=FONTS["small_bold"],
                                 bg=COLORS["bg_card"], fg=COLORS["accent"]).pack()
                        sub = tk.Frame(card, bg=COLORS["bg_card"])
                        sub.pack()
                        tk.Label(sub, text=f"✓ {h['success']}", font=FONTS["small"],
                                 bg=COLORS["bg_card"], fg=COLORS["success"]).pack(side=side_start())
                        tk.Label(sub, text=" / ", font=FONTS["small"],
                                 bg=COLORS["bg_card"], fg=COLORS["text_muted"]).pack(side=side_start())
                        tk.Label(sub, text=f"✗ {h['failure']}", font=FONTS["small"],
                                 bg=COLORS["bg_card"], fg=COLORS["error"]).pack(side=side_start())
                        # click to filter
                        def _filter_this(hid=h["hall_id"]):
                            for i, hh in enumerate(self._halls):
                                if hh["id"] == hid:
                                    self.hall_combo.current(i + 1)
                                    break
                            self.refresh()
                        for w in [card] + list(card.winfo_children()):
                            w.bind("<Button-1>", lambda e, fn=_filter_this: fn())
                            try:
                                w.configure(cursor="hand2")
                            except Exception:
                                pass

                safe_after(self.parent, 0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _delete_logs(self):
        if not messagebox.askyesno(t("attendance_logs.delete_confirm_title"),
                                   t("attendance_logs.delete_confirm_msg"),
                                   icon="warning"):
            return

        def do():
            try:
                r = http_client.api_delete("/api/scan-logs")
                data = r.json()
                if data.get("success"):
                    deleted = data.get("deleted", 0)
                    safe_after(self.parent, 0, lambda: (
                        messagebox.showinfo(t("attendance_logs.delete_done_title"),
                                            t("attendance_logs.delete_done_msg").format(n=deleted)),
                        self.refresh(),
                    ))
                else:
                    err = data.get("error", "unknown")
                    safe_after(self.parent, 0, lambda: messagebox.showerror(
                        t("attendance_logs.error"), err))
            except Exception as e:
                safe_after(self.parent, 0, lambda: messagebox.showerror(
                    t("attendance_logs.error"), str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _export_csv(self):
        if not self._latest_logs:
            messagebox.showinfo(t("attendance_logs.no_results"),
                                 t("attendance_logs.no_results"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"scan_logs_{client_time.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "scan_type", "success", "hall",
                            "device_id", "name", "academic_id", "uid_hint",
                            "error_reason"])
                for lg in self._latest_logs:
                    w.writerow([
                        lg.get("timestamp", ""),
                        lg.get("scan_type", ""),
                        "1" if lg.get("success") else "0",
                        lg.get("hall_name", ""),
                        lg.get("device_id", ""),
                        lg.get("student_name") or lg.get("doctor_name") or "",
                        lg.get("academic_id", ""),
                        lg.get("raw_uid_hint", ""),
                        lg.get("error_reason", ""),
                    ])
            messagebox.showinfo(t("ok"), f"{t('attendance_logs.export_csv')}: {path}")
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def _toggle_auto_refresh(self):
        if self._auto_refresh.get():
            self._schedule_auto_refresh()
        else:
            if self._auto_refresh_job:
                try:
                    self.parent.after_cancel(self._auto_refresh_job)
                except Exception:
                    pass
                self._auto_refresh_job = None

    def _schedule_auto_refresh(self):
        try:
            if not self.tree.winfo_exists():
                return
        except (tk.TclError, AttributeError):
            return
        if not self._auto_refresh.get():
            return
        self.refresh()
        self._auto_refresh_job = safe_after(self.parent, 5000, self._schedule_auto_refresh)
