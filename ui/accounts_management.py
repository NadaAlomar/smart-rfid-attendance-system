import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, pad_x, rtl_columns
from ui.i18n import t
from ui import http_client


class AccountsPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._build()
        self._load()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 8))

        tk.Button(toolbar, text=f"+ {t('accounts.create_btn')}",
                  command=self._create_dialog,
                  bg=c["primary"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 6))
        tk.Button(toolbar, text=t("refresh"), command=self._load,
                  bg=c["bg_light"], fg=c["text_primary"], font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start())
        tk.Button(toolbar, text=t("delete"), command=self._delete_selected,
                  bg=c["error"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start(), padx=pad_x(12, 0))

        cols = rtl_columns("username", "role", "doctor")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        for col, (h, w) in {
            "username": (t("accounts.username_label"), 200),
            "role":     (t("accounts.role_label"), 180),
            "doctor":   (t("doctor"), 250),
        }.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self.tree.tag_configure("dean", foreground=c["accent"])
        self.tree.tag_configure("dean_assistant", foreground=c["info"])
        self.tree.tag_configure("secretary", foreground=c["info"])
        self.tree.tag_configure("doctor", foreground=c["success"])

        if self.user and self.user.get("role") == "dean":
            self._build_role_labels(wrap)

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        def do():
            try:
                r = http_client.api_get("/api/auth/accounts")
                data = r.json()
                accounts = data.get("accounts", [])

                def update():
                    for a in accounts:
                        role_label = t(f"role.{a['role']}")
                        self.tree.insert("", tk.END, values=(
                            a.get("username", ""),
                            role_label,
                            a.get("doctor_name") or "—",
                        ), tags=(a.get("role", ""),), iid=str(a["id"]))
                self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _create_dialog(self):
        dlg = tk.Toplevel(self.parent)
        dlg.title(t("accounts.create_btn"))
        dlg.geometry("400x420")
        dlg.configure(bg=COLORS["bg_card"])
        dlg.transient(self.parent)
        dlg.grab_set()

        c = COLORS
        body = tk.Frame(dlg, bg=c["bg_card"], padx=24, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        username_var = tk.StringVar()
        password_var = tk.StringVar()
        role_var = tk.StringVar(value="secretary")
        doctor_var = tk.StringVar()

        for label_text, var, show in [
            (t("accounts.username_label"), username_var, ""),
            (t("accounts.password_label"), password_var, "●"),
        ]:
            tk.Label(body, text=label_text, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start(), pady=(8, 0))
            tk.Entry(body, textvariable=var, font=FONTS["body"], bg=c["input_bg"],
                     fg=c["text_primary"], insertbackground=c["accent"],
                     relief="flat", bd=0, show=show if show else ""
                     ).pack(fill=tk.X, ipady=7, pady=(2, 0))

        tk.Label(body, text=t("accounts.role_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start(), pady=(8, 0))
        roles = ["secretary", "dean", "dean_assistant", "doctor"]
        role_combo = ttk.Combobox(body, textvariable=role_var, values=roles,
                     state="readonly", width=16)
        role_combo.pack(fill=tk.X, pady=(2, 0))

        doctor_frame = tk.Frame(body, bg=c["bg_card"])
        doctor_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(doctor_frame, text=t("accounts.link_doctor"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start())
        self._doctor_combo = ttk.Combobox(doctor_frame, textvariable=doctor_var,
                                          state="readonly", width=30)
        self._doctor_combo.pack(fill=tk.X, pady=(2, 0))

        self._doctors_data = []

        def _on_role_change(*_):
            if role_var.get() == "doctor":
                doctor_frame.pack(fill=tk.X, pady=(8, 0))
                self._load_doctors()
            else:
                doctor_frame.pack_forget()

        role_var.trace_add("write", _on_role_change)
        _on_role_change()

        def submit():
            u = username_var.get().strip()
            p = password_var.get()
            r = role_var.get().strip()
            if not u or not p:
                return

            doc_id = None
            if r == "doctor" and doctor_var.get():
                idx = self._doctor_combo.current()
                if 0 <= idx < len(self._doctors_data):
                    doc_id = self._doctors_data[idx]["id"]

            def do():
                try:
                    payload = {"username": u, "password": p, "role": r}
                    if doc_id:
                        payload["doctor_id"] = doc_id
                    resp = http_client.api_post("/api/auth/accounts", payload)
                    data = resp.json()
                    if data.get("success"):
                        dlg.destroy()
                        self._load()
                    else:
                        dlg.after(0, lambda: messagebox.showerror(t("error"), data.get("error", "")))
                except Exception as e:
                    dlg.after(0, lambda: messagebox.showerror(t("error"), str(e)))
            threading.Thread(target=do, daemon=True).start()

        tk.Button(body, text=t("save"), command=submit,
                  bg=c["success"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(pady=(16, 0))

    def _load_doctors(self):
        def do():
            try:
                r = http_client.api_get("/api/doctors")
                data = r.json()
                doctors = data.get("doctors", [])
                unlinked = [d for d in doctors if not d.get("user_id")]
                names = [d["full_name"] for d in unlinked]
                self._doctors_data = unlinked

                def update():
                    self._doctor_combo["values"] = names
                    if names:
                        self._doctor_combo.current(0)
                self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        uid = sel[0]
        if not messagebox.askyesno(t("confirm_delete"), t("confirm_delete_msg")):
            return

        def do():
            try:
                http_client.api_delete(f"/api/auth/accounts/{uid}")
                self.parent.after(0, self._load)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _build_role_labels(self, parent):
        c = COLORS
        section = tk.LabelFrame(parent, text=f"  {t('accounts.role_labels_section')}  ",
                                font=FONTS["section"], bg=c["bg_dark"],
                                fg=c["accent"], padx=12, pady=10,
                                relief="groove", bd=1)
        section.pack(fill=tk.X, pady=(12, 0), padx=4)

        header_row = tk.Frame(section, bg=c["bg_dark"])
        header_row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(header_row, text=t("accounts.role_label"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_muted"], width=14,
                 anchor=anchor_start()).pack(side=side_start(), padx=pad_x(8, 0))
        tk.Label(header_row, text=t("accounts.label_ar"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_muted"], width=14,
                 anchor=anchor_start()).pack(side=side_start(), padx=pad_x(4, 0))
        tk.Label(header_row, text=t("accounts.label_en"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_muted"], width=14,
                 anchor=anchor_start()).pack(side=side_start(), padx=pad_x(4, 0))

        self._role_entries = {}
        for role_key in ["dean", "dean_assistant", "secretary", "doctor"]:
            row = tk.Frame(section, bg=c["bg_dark"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=t(f"role.{role_key}"), font=FONTS["body"],
                     bg=c["bg_dark"], fg=c["text_primary"], width=14,
                     anchor=anchor_start()).pack(side=side_start(), padx=pad_x(8, 0))
            ar_var = tk.StringVar()
            en_var = tk.StringVar()
            tk.Entry(row, textvariable=ar_var, font=FONTS["body"],
                     bg=c["input_bg"], fg=c["text_primary"],
                     insertbackground=c["accent"], relief="flat", bd=0,
                     width=14).pack(side=side_start(), padx=pad_x(4, 0), ipady=5)
            tk.Entry(row, textvariable=en_var, font=FONTS["body"],
                     bg=c["input_bg"], fg=c["text_primary"],
                     insertbackground=c["accent"], relief="flat", bd=0,
                     width=14).pack(side=side_start(), padx=pad_x(4, 0), ipady=5)
            self._role_entries[role_key] = {"ar": ar_var, "en": en_var}

        tk.Button(section, text=t("accounts.save_labels"),
                  command=self._save_role_labels,
                  bg=c["success"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=5, bd=0
                  ).pack(anchor=anchor_start(), pady=(8, 0), padx=pad_x(8, 0))

        self._load_role_labels()

    def _load_role_labels(self):
        def do():
            try:
                r = http_client.api_get("/api/role-labels")
                data = r.json()
                labels = data.get("labels", [])

                def update():
                    for lbl in labels:
                        key = lbl["role_key"]
                        if key in self._role_entries:
                            self._role_entries[key]["ar"].set(lbl.get("label_ar", ""))
                            self._role_entries[key]["en"].set(lbl.get("label_en", ""))
                self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _save_role_labels(self):
        for key, vars_ in self._role_entries.items():
            ar = vars_["ar"].get().strip()
            en = vars_["en"].get().strip()

            def do(k=key, a=ar, e=en):
                try:
                    http_client.api_put(f"/api/role-labels/{k}",
                                        json_body={"label_ar": a, "label_en": e})
                except Exception:
                    pass
            threading.Thread(target=do, daemon=True).start()
        messagebox.showinfo(t("success"), t("accounts.labels_saved"))
