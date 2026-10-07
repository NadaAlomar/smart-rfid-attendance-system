import tkinter as tk
from tkinter import ttk, messagebox
from ui import http_client
import threading
from ui.theme import (
    COLORS, FONTS, apply_theme, create_styled_treeview,
    create_styled_label_frame, create_themed_checkbutton,
)
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t


def _btn(parent, text, cmd, color=None, **kw):
    c = COLORS
    color = color or c["primary"]
    fg = c["bg_dark"] if color in (c["success"], c["warning"], c["accent"], c["info"]) else c["text_primary"]
    return tk.Button(parent, text=text, command=cmd,
                     bg=color, fg=fg,
                     activebackground=c["primary_light"], activeforeground=c["text_primary"],
                     relief="flat", font=FONTS["body_bold"],
                     cursor="hand2", padx=14, pady=8, bd=0, **kw)


def _entry(parent, **kw):
    c = COLORS
    return tk.Entry(parent, font=FONTS["body"],
                    bg=c["input_bg"], fg=c["text_primary"],
                    insertbackground=c["accent"],
                    relief="flat", bd=0, justify=text_justify(), **kw)


class DoctorManagement:
    def __init__(self, parent):
        self.parent = parent
        self._build()
        self.refresh()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=20, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        # Segmented selector: theoretical doctors vs practical teachers
        tabs = tk.Frame(wrap, bg=c["bg_dark"])
        tabs.pack(fill=tk.X, pady=(0, 8))
        self._mode_var = tk.StringVar(value="theory")
        self._tab_btns = {}
        for mode_key, label_key in [("theory", "doctor.tab_theory"),
                                     ("practical", "doctor.tab_practical")]:
            btn = tk.Button(tabs, text=t(label_key),
                            command=lambda m=mode_key: self._set_mode(m),
                            bg=c["bg_light"], fg=c["text_secondary"],
                            activebackground=c["primary"], activeforeground="#ffffff",
                            font=FONTS["body_bold"], relief="flat",
                            cursor="hand2", padx=22, pady=8, bd=0)
            btn.pack(side=side_start(), padx=(0, 6))
            self._tab_btns[mode_key] = btn

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 12))

        _btn(toolbar, t("doctor.add_btn"), self._add_dialog,
             color=c["success"]).pack(side=side_start())

        tk.Label(toolbar, text=t("doctor.search_label"), font=FONTS["body"],
                 bg=c["bg_dark"], fg=c["text_muted"]).pack(
            side=side_start(), padx=(8, 6))
        self.search_var = tk.StringVar()
        se = tk.Entry(toolbar, textvariable=self.search_var,
                      font=FONTS["body"], bg=c["input_bg"],
                      fg=c["text_primary"], insertbackground=c["accent"],
                       relief="flat", bd=0, justify=text_justify(), width=22)
        se.pack(side=side_start(), ipady=7, padx=(0, 4))
        se.bind("<KeyRelease>", lambda e: self._filter_doctors())

        _btn(toolbar, t("doctor.edit_btn"), self._edit_dialog,
             color=c["warning"]).pack(side=side_end(), padx=(0, 6))
        _btn(toolbar, t("doctor.delete_btn"), self._delete,
             color=c["error"]).pack(side=side_end(), padx=(0, 6))
        _btn(toolbar, t("doctor.assign_course_btn"), self._assign_course_dialog,
             color=c["info"]).pack(side=side_end(), padx=(0, 6))
        _btn(toolbar, t("doctor.lectures_btn"), self._lectures_dialog,
             color=c["accent"]).pack(side=side_end())

        self.status = tk.Label(toolbar, text="",
                                font=FONTS["small"],
                                bg=c["bg_dark"], fg=c["text_muted"])
        self.status.pack(side=side_end(), padx=12)

        footer = tk.Frame(wrap, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        tk.Frame(wrap, bg=c["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        _btn(footer, t("doctor.refresh_btn"), self.refresh).pack(side=side_end(), padx=(0, 6))

        tree_frame = tk.Frame(wrap, bg=c["bg_dark"])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "full_name", "card", "courses", "teaching_type", "has_account")
        self.tree = create_styled_treeview(tree_frame, columns=cols,
                                            show="headings", selectmode="browse")
        hdrs = {
            "id":             (t("doctor.col_id"),              60,   "center"),
            "full_name":      (t("doctor.col_name"),            240,  anchor_start()),
            "card":           (t("doctor.col_card"),             110,  "center"),
            "courses":        (t("doctor.col_courses"),         60,   "center"),
            "teaching_type":  (t("doctor.col_teaching_type"),   100,  "center"),
            "has_account":    (t("doctor.col_account"),         90,   "center"),
        }
        for col, (h, w, anch) in hdrs.items():
            self.tree.heading(col, text=h, anchor=anch)
            self.tree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=self.tree.yview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda e: self._details_dialog())

        self._set_mode("theory")

    def _card_value(self, doctor):
        if doctor.get("is_placeholder_card") or not doctor.get("hashed_uid"):
            return t("doctor.no_card")
        return doctor.get("card_hint") or str(doctor.get("hashed_uid") or "")[-4:] or t("doctor.card_linked")

    def refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        self.status.config(text=t("doctor.loading"))

        def do():
            try:
                r = http_client.api_get("/api/doctors")
                data = r.json()
                if data.get("success"):
                    doctors = data["doctors"]
                    self._all_doctors = doctors

                    def update():
                        # apply current mode (theory/practical) + search filter
                        self._set_mode(self._mode_var.get())

                    self.parent.after(0, update)
                else:
                    self.parent.after(0, lambda: self.status.config(text=t("doctor.load_failed")))
            except Exception as e:
                msg = str(e)
                self.parent.after(0, lambda m=msg: self.status.config(text=f'{t("doctor.error_prefix")} {m}'))
        threading.Thread(target=do, daemon=True).start()

    def _set_mode(self, mode):
        self._mode_var.set(mode)
        c = COLORS
        for key, btn in self._tab_btns.items():
            if key == mode:
                btn.config(bg=c["primary"], fg="#ffffff")
            else:
                btn.config(bg=c["bg_light"], fg=c["text_secondary"])
        self._filter_doctors()

    def _filter_doctors(self):
        if not hasattr(self, "_all_doctors"):
            return
        q = self.search_var.get().strip().lower()
        mode = getattr(self, "_mode_var", None)
        mode = mode.get() if mode is not None else "theory"

        for r in self.tree.get_children():
            self.tree.delete(r)

        count = 0
        for d in self._all_doctors:
            dtype = d.get("doctor_type") or d.get("teaching_type") or "theory"
            if mode == "theory" and dtype != "theory":
                continue
            if mode == "practical" and dtype != "practical":
                continue
            name = d["full_name"].lower()
            if q and q not in name:
                continue
            n_courses = len(d.get("courses", []))
            dtype_display = t("doctor.theory") if dtype == "theory" else t("doctor.practical")
            self.tree.insert("", tk.END, values=(
                d["id"], d["full_name"], self._card_value(d), n_courses,
                dtype_display, "✔" if d["user_id"] else "—"))
            count += 1

        if q:
            self.status.config(text=f'{t("doctor.search_results")} {count}')
        else:
            self.status.config(text=f'{t("doctor.count_status")} {count}')

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("doctor.select_first"))
            return None
        return self.tree.item(sel[0])["values"][0]

    def _details_dialog(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        did = item["values"][0]

        def do():
            try:
                r = http_client.api_get(f"/api/doctors/{did}")
                data = r.json()
                if not data.get("success"):
                    return
                doctor = data["doctor"]
            except Exception:
                return

            def show():
                c = COLORS
                win = tk.Toplevel(self.parent)
                win.title(t("doctor.details_title"))
                win.geometry("480x520")
                win.minsize(440, 460)
                win.configure(bg=c["bg_dark"])
                win.resizable(False, False)
                win.grab_set()

                hdr = tk.Frame(win, bg=c["bg_medium"])
                hdr.pack(fill=tk.X)
                tk.Frame(hdr, bg=c["info"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
                tk.Label(hdr, text=t("doctor.details_header"),
                         font=FONTS["section"], bg=c["bg_medium"],
                         fg=c["accent"]).pack(side=side_start(), padx=16, pady=12)
                tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

                f = tk.Frame(win, bg=c["bg_card"], padx=24, pady=18)
                f.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

                def info_row(label_key, value, fg=None):
                    row_f = tk.Frame(f, bg=c["bg_card"])
                    row_f.pack(fill=tk.X, pady=3)
                    tk.Label(row_f, text=t(label_key), font=FONTS["small_bold"],
                             bg=c["bg_card"], fg=c["text_muted"],
                             anchor=anchor_start(), width=18).pack(side=side_start(), padx=(0, 8))
                    tk.Label(row_f, text=str(value), font=FONTS["body_bold"],
                             bg=c["bg_card"], fg=fg or c["text_primary"],
                             anchor=anchor_start()).pack(side=side_start(), fill=tk.X, expand=True)

                info_row("doctor.detail_id", doctor.get("id", ""))
                info_row("doctor.detail_full_name", doctor.get("full_name", ""))
                info_row("doctor.first_name", doctor.get("first_name", ""))
                info_row("doctor.last_name", doctor.get("last_name", ""))

                tk.Frame(f, bg=c["border"], height=1).pack(fill=tk.X, pady=8)

                if doctor.get("is_placeholder_card") or not doctor.get("hashed_uid"):
                    card_text = t("doctor.no_card")
                    card_fg = c["warning"]
                elif doctor.get("card_hint"):
                    card_text = f"{t('doctor.card_linked')} ({doctor['card_hint']})"
                    card_fg = c["success"]
                else:
                    card_text = t("doctor.card_linked")
                    card_fg = c["success"]
                info_row("doctor.detail_card", card_text, fg=card_fg)

                if doctor.get("username"):
                    info_row("doctor.detail_account", doctor["username"], fg=c["success"])
                else:
                    info_row("doctor.detail_account", t("doctor.no_user_account"), fg=c["text_muted"])

                tk.Frame(f, bg=c["border"], height=1).pack(fill=tk.X, pady=8)

                dtype = doctor.get("doctor_type") or doctor.get("teaching_type") or "theory"
                type_display = t("doctor.theory") if dtype == "theory" else t("doctor.practical")
                info_row("doctor.teaching_type", type_display)

                courses = doctor.get("courses", [])
                courses_label = tk.Frame(f, bg=c["bg_card"])
                courses_label.pack(fill=tk.X, pady=3, anchor=anchor_start())
                tk.Label(courses_label, text=t("doctor.col_courses"),
                         font=FONTS["small_bold"], bg=c["bg_card"],
                         fg=c["text_muted"], anchor=anchor_start(),
                         width=18).pack(side=side_start(), padx=(0, 8),
                                         anchor=anchor_start())
                courses_box = tk.Frame(f, bg=c["bg_card"])
                courses_box.pack(fill=tk.X, padx=(18, 0))
                if courses:
                    for cr in courses:
                        line = f"• {cr['course_code']} — {cr['course_name']}"
                        tk.Label(courses_box, text=line, font=FONTS["body"],
                                 bg=c["bg_card"], fg=c["text_primary"],
                                 anchor=anchor_start(),
                                 justify=text_justify()).pack(fill=tk.X, anchor=anchor_start())
                else:
                    tk.Label(courses_box, text=t("doctor.no_courses"),
                             font=FONTS["body"], bg=c["bg_card"],
                             fg=c["text_muted"],
                             anchor=anchor_start()).pack(fill=tk.X, anchor=anchor_start())

                btn_row = tk.Frame(f, bg=c["bg_card"])
                btn_row.pack(fill=tk.X, pady=(12, 0))
                _btn(btn_row, t("close"), win.destroy, color=c["bg_light"]).pack(side=side_end())
                _btn(btn_row, t("doctor.edit_btn"), lambda: [win.destroy(), self._edit_dialog()],
                     color=c["info"]).pack(side=side_end(), padx=(0, 8))

            self.parent.after(0, show)
        threading.Thread(target=do, daemon=True).start()

    def _add_dialog_with_uid(self, uid):
        self._add_dialog(prefill_uid=uid)

    def _add_dialog(self, prefill_uid=None):
        c = COLORS
        win = tk.Toplevel()
        win.title(t("doctor.add_title"))
        win.geometry("520x620")
        win.minsize(500, 500)
        win.resizable(True, True)
        win.configure(bg=c["bg_dark"])
        win.grab_set()
        apply_theme(win)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=t("doctor.add_header"),
                 font=FONTS["section"], bg=c["bg_medium"],
                  fg=c["accent"]).pack(side=side_start(), padx=16, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        card = tk.Frame(win, bg=c["bg_card"], padx=30, pady=20)
        card.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        card.columnconfigure(0, weight=1)

        def lbl(row, text):
            tk.Label(card, text=text, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"],
                      anchor=anchor_start()).grid(row=row, column=1, sticky="e",
                                      padx=(0, 10), pady=6)

        def sep(row):
            tk.Frame(card, bg=c["border"], height=1).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        lbl(0, t("doctor.first_name_req"))
        first_e = _entry(card)
        first_e.grid(row=0, column=0, sticky="ew", ipady=9, pady=6)
        sep(1)

        lbl(2, t("doctor.last_name_req"))
        last_e = _entry(card)
        last_e.grid(row=2, column=0, sticky="ew", ipady=9, pady=6)
        sep(3)

        lbl(4, t("doctor.uid_rfid_req"))
        uid_row = tk.Frame(card, bg=c["bg_card"])
        uid_row.grid(row=4, column=0, sticky="ew", pady=6)
        uid_row.columnconfigure(0, weight=1)

        uid_e = tk.Entry(uid_row, font=FONTS["mono"],
                         bg=c["input_bg"], fg=c["accent"],
                         insertbackground=c["accent"],
                         relief="flat", bd=0, justify=text_justify())
        uid_e.grid(row=0, column=0, sticky="ew", ipady=9)

        uid_ok = tk.Label(uid_row, text="", font=("Segoe UI", 16, "bold"),
                           bg=c["bg_card"], fg=c["success"])

        def _scan():
            from ui.rfid_scanner_dialog import RFIDScanDialog
            def on_uid(u):
                uid_e.delete(0, tk.END)
                uid_e.insert(0, u)
                uid_ok.config(text="✓")
            RFIDScanDialog(win, on_uid).show()

        tk.Button(uid_row, text=t("doctor.scan_btn"), command=_scan,
                  bg=c["info"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  activeforeground="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=8, bd=0).grid(
            row=0, column=1, padx=(8, 0))
        uid_ok.grid(row=0, column=2, padx=(6, 0))

        if prefill_uid:
            uid_e.insert(0, prefill_uid)
            uid_ok.config(text="✓")
        sep(5)

        lbl(6, t("doctor.teaching_type"))
        dtype_var = tk.StringVar(value="theory")
        type_nb = ttk.Notebook(card)
        type_nb.grid(row=6, column=0, sticky="ew", pady=6)
        theory_tab = tk.Frame(type_nb, bg=c["bg_card"], height=30)
        practical_tab = tk.Frame(type_nb, bg=c["bg_card"], height=30)
        type_nb.add(theory_tab, text=f"  {t('doctor.theory')}  ")
        type_nb.add(practical_tab, text=f"  {t('doctor.practical')}  ")

        def _on_tab_change(event):
            idx = type_nb.index(type_nb.select())
            dtype_var.set("theory" if idx == 0 else "practical")

        type_nb.bind("<<NotebookTabChanged>>", _on_tab_change)
        sep(7)

        create_acct = tk.BooleanVar()

        acct_frame = tk.Frame(card, bg=c["bg_card"])
        acct_frame.grid(row=11, column=0, columnspan=2, sticky="ew")
        acct_frame.columnconfigure(0, weight=1)

        tk.Label(acct_frame, text=t("doctor.username_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start()).grid(
            row=0, column=1, sticky="e", padx=(0, 10), pady=(0, 4))
        uname_e = tk.Entry(acct_frame, font=FONTS["body"],
                           bg=c["input_bg"], fg=c["text_primary"],
                           insertbackground=c["accent"],
                           relief="flat", bd=0, justify=text_justify())
        uname_e.grid(row=0, column=0, sticky="ew", ipady=8, pady=(0, 4))

        tk.Label(acct_frame, text=t("doctor.password_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start()).grid(
            row=1, column=1, sticky="e", padx=(0, 10), pady=(4, 0))
        pass_e = tk.Entry(acct_frame, font=FONTS["body"],
                          bg=c["input_bg"], fg=c["text_primary"],
                          insertbackground=c["accent"],
                          relief="flat", bd=0, show="●", justify=text_justify())
        pass_e.grid(row=1, column=0, sticky="ew", ipady=8, pady=(4, 0))

        tk.Label(acct_frame,
                 text=t("doctor.account_info"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start(), justify=text_justify()
                 ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        acct_frame.grid_remove()

        def _toggle_acct():
            if create_acct.get():
                acct_frame.grid()
                win.geometry("520x680")
            else:
                acct_frame.grid_remove()
                win.geometry("520x560")

        create_themed_checkbutton(card, text=t("doctor.create_account_checkbox"),
                                  variable=create_acct,
                                  command=_toggle_acct).grid(
            row=10, column=0, columnspan=2, sticky="e", pady=(8, 4))

        sep(12)

        btn_row = tk.Frame(card, bg=c["bg_card"])
        btn_row.grid(row=13, column=0, columnspan=2, sticky="e", pady=(8, 0))

        tk.Button(btn_row, text=t("cancel"), command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=16, pady=8, bd=0
                   ).pack(side=side_end(), padx=(0, 8))

        def save():
            first = first_e.get().strip()
            last = last_e.get().strip()
            uid = uid_e.get().strip()

            if not first or not last:
                messagebox.showerror(t("error"),
                    t("doctor.name_required"), parent=win)
                return
            if not uid:
                uid_e.config(bg=COLORS["error"], fg="white")
                uid_e.after(2000, lambda: uid_e.config(
                    bg=COLORS["input_bg"], fg=COLORS["text_primary"]))
                messagebox.showerror(t("error"), t("doctor.uid_required"), parent=win)
                return

            payload = {
                "first_name":  first,
                "last_name":   last,
                "uid":         uid,
                "doctor_type": dtype_var.get(),
                "create_user": create_acct.get(),
                "username":    uname_e.get().strip(),
                "password":    pass_e.get().strip(),
            }
            try:
                r = http_client.api_post("/api/doctors", json_body=payload)
                data = r.json()
                if data.get("success"):
                    messagebox.showinfo(t("success"),
                        t("doctor.added_success"), parent=win)
                    win.destroy()
                    self.refresh()
                else:
                    messagebox.showerror(t("error"),
                        data.get("error", t("doctor.operation_failed")), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        tk.Button(btn_row, text=t("doctor.save_btn"), command=save,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=8, bd=0
                   ).pack(side=side_end())

    def _edit_dialog(self):
        did = self._selected_id()
        if not did:
            return
        did_int = int(did)
        c = COLORS

        # Fetch full doctor record (first_name, last_name, card status, username)
        try:
            r = http_client.api_get(f"/api/doctors/{did}")
            data = r.json()
            if not data.get("success"):
                messagebox.showerror(t("error"), data.get("error", ""))
                return
            doctor = data["doctor"]
        except Exception as e:
            messagebox.showerror(t("error"), str(e))
            return

        win = tk.Toplevel(self.parent)
        win.title(t("doctor.edit_title"))
        win.geometry("560x680")
        win.minsize(520, 600)
        win.configure(bg=c["bg_dark"])
        win.resizable(True, True)
        win.grab_set()

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["warning"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'{t("doctor.edit_header")} {doctor["full_name"]}',
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=16, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        # Scroll container
        canvas = tk.Canvas(win, bg=c["bg_dark"], highlightthickness=0)
        vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        f = tk.Frame(canvas, bg=c["bg_dark"], padx=30, pady=20)
        wid = canvas.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        f.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        f.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        f.columnconfigure(0, weight=1)

        # ── name fields ──
        def _field_label(row, text_key):
            tk.Label(f, text=t(text_key), font=FONTS["small_bold"],
                     bg=c["bg_dark"], fg=c["text_muted"],
                     anchor=anchor_start()).grid(row=row, column=1, sticky="e",
                                                  padx=(0, 10), pady=6)

        _field_label(0, "doctor.first_name")
        first_e = _entry(f)
        first_e.insert(0, doctor.get("first_name") or "")
        first_e.grid(row=0, column=0, sticky="ew", ipady=7, pady=6)

        _field_label(1, "doctor.last_name")
        last_e = _entry(f)
        last_e.insert(0, doctor.get("last_name") or "")
        last_e.grid(row=1, column=0, sticky="ew", ipady=7, pady=6)

        _field_label(2, "doctor.full_name_label")
        name_e = _entry(f)
        name_e.insert(0, doctor["full_name"])
        name_e.grid(row=2, column=0, sticky="ew", ipady=7, pady=6)

        _field_label(3, "doctor.teaching_type")
        edit_dtype_var = tk.StringVar(
            value=doctor.get("doctor_type") or doctor.get("teaching_type") or "theory")
        edit_type_nb = ttk.Notebook(f)
        edit_type_nb.grid(row=3, column=0, sticky="ew", pady=6)
        edit_theory_tab = tk.Frame(edit_type_nb, bg=c["bg_dark"], height=30)
        edit_practical_tab = tk.Frame(edit_type_nb, bg=c["bg_dark"], height=30)
        edit_type_nb.add(edit_theory_tab, text=f"  {t('doctor.theory')}  ")
        edit_type_nb.add(edit_practical_tab, text=f"  {t('doctor.practical')}  ")
        edit_type_nb.select(0 if edit_dtype_var.get() == "theory" else 1)

        def _on_edit_tab_change(event):
            idx = edit_type_nb.index(edit_type_nb.select())
            edit_dtype_var.set("theory" if idx == 0 else "practical")

        edit_type_nb.bind("<<NotebookTabChanged>>", _on_edit_tab_change)

        # ── card status section ──
        card_section = tk.Frame(f, bg=c["bg_card"], padx=14, pady=12)
        card_section.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 8))

        tk.Label(card_section, text=t("doctor.current_card_status"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 6))

        if doctor.get("is_placeholder_card"):
            status_text = f"⚠ {t('doctor.no_card')}"
            status_color = c["warning"]
        elif doctor.get("hashed_uid"):
            status_text = f"✓ {t('doctor.card_linked')}"
            status_color = c["success"]
        else:
            status_text = f"⚠ {t('doctor.card_not_linked')}"
            status_color = c["error"]

        tk.Label(card_section, text=status_text, font=FONTS["body_bold"],
                 bg=c["bg_card"], fg=status_color,
                 anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 8))

        # uid entry
        uid_row = tk.Frame(card_section, bg=c["bg_card"])
        uid_row.pack(fill=tk.X)
        uid_row.columnconfigure(0, weight=1)

        uid_e = tk.Entry(uid_row, font=FONTS["mono"],
                         bg=c["input_bg"], fg=c["accent"],
                         insertbackground=c["accent"],
                         relief="flat", bd=0, justify=text_justify())
        uid_e.grid(row=0, column=0, sticky="ew", ipady=8)

        uid_ok = tk.Label(uid_row, text="", font=("Segoe UI", 14, "bold"),
                          bg=c["bg_card"], fg=c["success"])
        uid_ok.grid(row=0, column=2, padx=(6, 0))

        def _scan_edit():
            from ui.rfid_scanner_dialog import RFIDScanDialog
            def on_uid(u):
                uid_e.delete(0, tk.END)
                uid_e.insert(0, u)
                uid_ok.config(text="✓")
            RFIDScanDialog(win, on_uid).show()

        tk.Button(uid_row, text=t("doctor.change_card"),
                  command=_scan_edit,
                  bg=c["info"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  activeforeground="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=8, bd=0
                  ).grid(row=0, column=1, padx=(8, 0))

        tk.Label(card_section, text=t("doctor.leave_blank_current"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"],
                 anchor=anchor_start()).pack(anchor=anchor_start(), pady=(8, 0))

        # ── account section ──
        acct_section = tk.Frame(f, bg=c["bg_card"], padx=14, pady=12)
        acct_section.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(14, 8))

        tk.Label(acct_section, text=t("doctor.login_account_section"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 6))

        if doctor.get("username"):
            tk.Label(acct_section,
                     text=f"{t('doctor.linked_user_account')}: {doctor['username']}",
                     font=FONTS["body_bold"], bg=c["bg_card"],
                     fg=c["success"], anchor=anchor_start()
                     ).pack(anchor=anchor_start(), pady=(0, 6))
        else:
            tk.Label(acct_section, text=t("doctor.no_user_account"),
                     font=FONTS["body"], bg=c["bg_card"],
                     fg=c["text_muted"], anchor=anchor_start()
                     ).pack(anchor=anchor_start(), pady=(0, 6))

        create_new_acct = tk.BooleanVar()
        acct_fields = tk.Frame(acct_section, bg=c["bg_card"])
        acct_fields.columnconfigure(0, weight=1)

        tk.Label(acct_fields, text=t("doctor.username_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start()).grid(
            row=0, column=1, sticky="e", padx=(0, 10), pady=4)
        new_uname = tk.Entry(acct_fields, font=FONTS["body"],
                              bg=c["input_bg"], fg=c["text_primary"],
                              insertbackground=c["accent"],
                              relief="flat", bd=0, justify=text_justify())
        new_uname.grid(row=0, column=0, sticky="ew", ipady=7, pady=4)

        tk.Label(acct_fields, text=t("doctor.password_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start()).grid(
            row=1, column=1, sticky="e", padx=(0, 10), pady=4)
        new_pass = tk.Entry(acct_fields, font=FONTS["body"],
                             bg=c["input_bg"], fg=c["text_primary"],
                             insertbackground=c["accent"],
                             relief="flat", bd=0, show="●", justify=text_justify())
        new_pass.grid(row=1, column=0, sticky="ew", ipady=7, pady=4)

        def _toggle_acct():
            if create_new_acct.get():
                acct_fields.pack(fill=tk.X, pady=(8, 0))
            else:
                acct_fields.pack_forget()

        if not doctor.get("username"):
            create_themed_checkbutton(acct_section,
                                      text=t("doctor.create_new_account_checkbox"),
                                      variable=create_new_acct,
                                      command=_toggle_acct).pack(anchor=anchor_start(), pady=(8, 4))

        def save():
            payload = {
                "full_name": name_e.get().strip(),
                "first_name": first_e.get().strip(),
                "last_name": last_e.get().strip(),
                "doctor_type": edit_dtype_var.get(),
            }
            new_uid = uid_e.get().strip()
            if new_uid:
                force_uid_change = False
                try:
                    lookup = http_client.api_get(
                        "/api/cards/lookup",
                        uid=new_uid, owner_type="doctor", owner_id=did_int,
                    ).json()
                    if not lookup.get("success"):
                        messagebox.showerror(t("error"), lookup.get("error", ""), parent=win)
                        return
                    linked_to = lookup.get("linked_to")
                    holder_id = lookup.get("id")
                    holder_name = lookup.get("name") or ""
                    if linked_to == "doctor" and holder_id == did_int:
                        messagebox.showinfo(t("warning"), t("doctor.card_used_self"), parent=win)
                        return
                    if linked_to == "doctor":
                        if not messagebox.askyesno(
                            t("warning"),
                            t("doctor.card_used_confirm").format(name=holder_name),
                            parent=win,
                        ):
                            return
                        force_uid_change = True
                    elif linked_to == "student":
                        messagebox.showerror(
                            t("error"),
                            t("doctor.card_used_student").format(name=holder_name),
                            parent=win,
                        )
                        return
                except Exception as e:
                    messagebox.showerror(t("error"), str(e), parent=win)
                    return
                payload["uid"] = new_uid
                if force_uid_change:
                    payload["force_uid_change"] = True
            if create_new_acct.get():
                u = new_uname.get().strip()
                p = new_pass.get().strip()
                if not u or not p:
                    messagebox.showerror(t("error"),
                        t("doctor.username_password_required"),
                        parent=win)
                    return
                payload["create_user"] = True
                payload["username"] = u
                payload["password"] = p
                payload["role"] = "doctor"
            try:
                r = http_client.api_put(f"/api/doctors/{did}",
                                  json_body=payload)
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    self.refresh()
                    messagebox.showinfo(t("ok"), t("doctor.updated_success"))
                else:
                    messagebox.showerror(t("error"),
                        data.get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(f, bg=c["bg_dark"])
        btn_row.grid(row=6, column=0, columnspan=2, sticky="e", pady=(20, 0))
        _btn(btn_row, t("cancel"), win.destroy, color=c["bg_light"]
              ).pack(side=side_end(), padx=(0, 8))
        _btn(btn_row, t("doctor.save_changes_btn"), save, color=c["success"]
              ).pack(side=side_end())

    def _delete(self):
        did = self._selected_id()
        if not did:
            return
        name = self.tree.item(self.tree.selection()[0])["values"][1]
        if not messagebox.askyesno(t("doctor.confirm_delete_title"),
                                   f"{t('doctor.confirm_delete_msg')} '{name}'"):
            return
        try:
            r = http_client.api_delete(f"/api/doctors/{did}")
            data = r.json()
            if data.get("success"):
                messagebox.showinfo(t("ok"), t("doctor.deleted_success"))
                self.refresh()
            else:
                messagebox.showerror(t("error"), data.get("error"))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def _assign_course_dialog(self):
        did = self._selected_id()
        if not did:
            return
        doctor_name = self.tree.item(self.tree.selection()[0])["values"][1]
        c = COLORS

        win = tk.Toplevel()
        win.title(f'{t("doctor.assign_course_title")} {doctor_name}')
        win.geometry("420x200")
        win.configure(bg=c["bg_dark"])
        win.grab_set()

        f = tk.Frame(win, bg=c["bg_dark"], padx=30, pady=24)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text=f'{t("doctor.doctor_label")} {doctor_name}',
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"], anchor=anchor_start()).pack(fill=tk.X, pady=(0, 12))

        courses = []
        try:
            r = http_client.api_get("/api/courses")
            if r.status_code == 200:
                courses = r.json().get("courses", [])
        except Exception:
            pass

        course_var = tk.StringVar()
        course_labels = [f"{c_['course_code']} — {c_['course_name']}"
                         for c_ in courses]
        combo = ttk.Combobox(f, textvariable=course_var, state="normal",
                              font=FONTS["body"])
        combo["values"] = course_labels
        combo.pack(fill=tk.X, pady=(0, 16), ipady=6)

        def _on_type(_e=None):
            q = course_var.get().strip().lower()
            if not q:
                combo["values"] = course_labels
                return
            combo["values"] = [lbl for lbl in course_labels if q in lbl.lower()]
        combo.bind("<KeyRelease>", _on_type)

        def _resolve_course():
            idx = combo.current()
            if idx >= 0 and idx < len(courses):
                return courses[idx]
            typed = course_var.get().strip().lower()
            if not typed:
                return None
            for c_ in courses:
                lbl = f"{c_['course_code']} — {c_['course_name']}".lower()
                if typed == lbl or typed == c_["course_code"].lower() or typed == c_["course_name"].lower():
                    return c_
            for c_ in courses:
                if typed in c_["course_code"].lower() or typed in c_["course_name"].lower():
                    return c_
            return None

        def assign():
            picked = _resolve_course()
            if not picked:
                messagebox.showwarning(t("warning"), t("doctor.select_course_msg"))
                return
            cid = picked["id"]
            try:
                r = http_client.api_put(f"/api/courses/{cid}",
                                 json_body={"doctor_id": did})
                data = r.json()
                if data.get("success"):
                    messagebox.showinfo(t("ok"), t("doctor.course_assigned"))
                    win.destroy()
                    self.refresh()
                else:
                    messagebox.showerror(t("error"), data.get("error"))
            except Exception as e:
                messagebox.showerror(t("error"), str(e))

        _btn(f, t("doctor.assign_btn"), assign, color=c["success"]).pack(anchor=anchor_start())

    def _lectures_dialog(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("doctor.select_doctor"))
            return
        item = self.tree.item(sel[0])
        doctor_id = item["values"][0]
        doctor_name = item["values"][1]

        def do():
            try:
                courses_resp = http_client.api_get(
                    "/api/courses/full")
                courses = [c for c in courses_resp.json().get("courses", [])
                           if c.get("doctor_id") == doctor_id]

                schedules_resp = http_client.api_get(
                    "/api/schedules")
                all_scheds = schedules_resp.json().get("schedules", [])
            except Exception as ex:
                self.parent.after(0, lambda: messagebox.showerror(t("error"), str(ex)))
                return

            def show():
                c = COLORS
                DAYS_AR = {0: t("doctor.day_monday"), 1: t("doctor.day_tuesday"), 2: t("doctor.day_wednesday"),
                            3: t("doctor.day_thursday"), 4: t("doctor.day_friday"), 5: t("doctor.day_saturday"), 6: t("doctor.day_sunday")}
                win = tk.Toplevel(self.parent)
                win.title(f'{t("doctor.lectures_title")} {doctor_name}')
                win.configure(bg=c["bg_card"])
                win.geometry("700x450")
                win.transient(self.parent)
                win.grab_set()

                tk.Label(win, text=f'{t("doctor.lectures_header")} {doctor_name}',
                         font=FONTS["subtitle"], bg=c["bg_card"], fg=c["accent"],
                         anchor=anchor_start(), padx=16, pady=12).pack(fill=tk.X)

                cols = ("course_code", "course_name", "day", "time", "hall")
                tree = create_styled_treeview(win, columns=cols, show="headings", height=15)
                for col, (h, w) in {
                    "course_code": (t("doctor.col_code"), 80),
                    "course_name": (t("doctor.col_course"), 200),
                    "day": (t("doctor.col_day"), 100),
                    "time": (t("doctor.col_time"), 120),
                    "hall": (t("doctor.col_hall"), 120),
                }.items():
                    tree.heading(col, text=h)
                    tree.column(col, width=w)
                tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

                if not courses:
                    tk.Label(win, text=t("doctor.no_courses_registered"),
                             font=FONTS["body"], bg=c["bg_card"],
                             fg=c["text_muted"]).pack(pady=20)
                else:
                    for crs in courses:
                        course_scheds = [s for s in all_scheds
                                         if s["course_id"] == crs["id"]]
                        if course_scheds:
                            for sc in course_scheds:
                                tree.insert("", tk.END, values=(
                                    crs["course_code"], crs["course_name"],
                                    DAYS_AR.get(sc["day_of_week"], "?"),
                                    f"{sc['start_time']}-{sc['end_time']}",
                                    sc["hall_name"],
                                ))
                        else:
                            tree.insert("", tk.END, values=(
                                crs["course_code"], crs["course_name"],
                                "—", "—", "—",
                            ))

            self.parent.after(0, show)
        threading.Thread(target=do, daemon=True).start()
