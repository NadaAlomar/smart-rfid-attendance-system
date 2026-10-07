import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import csv
from datetime import datetime
from ui import http_client
from ui.theme import COLORS, FONTS, safe_after
from ui.i18n import t
from ui.widgets.date_picker import DatePicker
from ui.rtl_helper import side_start, side_end, anchor_start


class AuditLogPanel:
    ACTIONS = ("create", "update", "delete")
    ENTITIES = ("student", "doctor", "course", "schedule", "enrollment",
                "justification", "hall", "holiday", "account", "user", "backup")

    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._build()

    def _btn(self, parent, text, cmd, bg, fg="#ffffff"):
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg, activebackground=COLORS["primary_light"],
                         activeforeground="#ffffff", font=FONTS["small_bold"],
                         relief="flat", cursor="hand2", padx=12, pady=6, bd=0)

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        filters = tk.Frame(wrap, bg=c["bg_dark"])
        filters.pack(fill=tk.X, pady=(0, 10))

        tk.Label(filters, text=t("audit.filter_from"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(0, 4))
        self.from_var = tk.StringVar()
        DatePicker(filters, variable=self.from_var
                   ).pack(side=side_start(), padx=(0, 12))

        tk.Label(filters, text=t("audit.filter_to"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(0, 4))
        self.to_var = tk.StringVar()
        DatePicker(filters, variable=self.to_var
                   ).pack(side=side_start(), padx=(0, 12))

        tk.Label(filters, text=t("audit.filter_action"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(0, 4))
        self.action_var = tk.StringVar(value=t("audit.filter_all"))
        action_combo = ttk.Combobox(filters, textvariable=self.action_var,
                                     values=[t("audit.filter_all")] +
                                            [t(f"audit.action_{a}") for a in self.ACTIONS],
                                     state="readonly", width=12)
        action_combo.pack(side=side_start(), padx=(0, 12))

        self._btn(filters, t("refresh"), self._load, c["primary"]).pack(side=side_end(), padx=(0, 6))
        self._btn(filters, t("audit.export_csv"), self._export_csv, c["info"]).pack(side=side_end())

        cols = ("time", "user", "role", "action", "entity", "label")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=20)
        col_defs = {
            "time": (t("audit.col_time"), 160, "center"),
            "user": (t("audit.col_user"), 120, "center"),
            "role": (t("audit.col_role"), 100, "center"),
            "action": (t("audit.col_action"), 80, "center"),
            "entity": (t("audit.col_entity"), 100, "center"),
            "label": (t("audit.col_label"), 250, anchor_start()),
        }
        for col, (h, w, anch) in col_defs.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self._load()

    def _load(self):
        params = {}
        from_date = self.from_var.get().strip()
        to_date = self.to_var.get().strip()
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        action_text = self.action_var.get()
        for a in self.ACTIONS:
            if action_text == t(f"audit.action_{a}"):
                params["action"] = a
                break

        def do():
            try:
                r = http_client.api_get("/api/audit-logs", **params)
                data = r.json()
                logs = data.get("logs", [])
                self.parent.after(0, lambda: self._populate(logs))
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _populate(self, logs):
        for r in self.tree.get_children():
            self.tree.delete(r)
        if not logs:
            self.tree.insert("", tk.END, values=(t("audit.no_logs"), "", "", "", "", ""))
            return
        for log in logs:
            self.tree.insert("", tk.END, values=(
                log.get("timestamp", "")[:19].replace("T", " "),
                log.get("username", ""),
                log.get("role", ""),
                t(f"audit.action_{log.get('action', '')}", log.get("action", "")),
                log.get("entity_type", ""),
                log.get("entity_label", ""),
            ))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        params = {}
        from_date = self.from_var.get().strip()
        to_date = self.to_var.get().strip()
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        def do():
            try:
                r = http_client.api_get("/api/audit-logs", **params)
                data = r.json()
                logs = data.get("logs", [])
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["timestamp", "username", "role", "action",
                                "entity_type", "entity_id", "entity_label"])
                    for log in logs:
                        w.writerow([
                            log.get("timestamp", ""),
                            log.get("username", ""),
                            log.get("role", ""),
                            log.get("action", ""),
                            log.get("entity_type", ""),
                            log.get("entity_id", ""),
                            log.get("entity_label", ""),
                        ])
                self.parent.after(0, lambda: messagebox.showinfo(t("ok"), f"Exported {len(logs)} rows"))
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(t("error"), str(e)))
        threading.Thread(target=do, daemon=True).start()