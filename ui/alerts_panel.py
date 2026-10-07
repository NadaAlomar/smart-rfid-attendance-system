import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import threading
from ui import http_client
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui.widgets.date_picker import DatePicker


ALERT_AR = {
    "4_absences":      t("alert.4_absences"),
    "zero_attendance": t("alert.zero_attendance"),
    "low_percent":     t("alert.low_percent"),
}


class AlertsPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self.can_justify = bool(user) and user.role != "secretary"
        self._build()
        self.refresh_alerts()
        self.refresh_justifications()

    def _build(self):
        c = COLORS

        # Footer must be packed FIRST (with side=BOTTOM) so it always claims
        # the bottom row regardless of how much content the scrollable area has.
        self._footer = tk.Frame(self.parent, bg=c["bg_medium"], pady=10)
        self._footer.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(self.parent, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        canvas = tk.Canvas(self.parent, bg=c["bg_dark"],
                            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self.parent, orient=tk.VERTICAL,
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        wrap = tk.Frame(canvas, bg=c["bg_dark"], padx=20, pady=14)
        win_id = canvas.create_window((0, 0), window=wrap, anchor="nw")
        wrap.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(win_id, width=e.width))

        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        wrap.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        wrap.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        tk.Label(wrap, text=t("alert.section_title"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"], anchor=anchor_start()).pack(fill=tk.X, pady=(0, 8))

        a_frame = tk.Frame(wrap, bg=c["bg_dark"], height=240)
        a_frame.pack(fill=tk.X, pady=(0, 8))
        a_frame.pack_propagate(False)

        cols = ("id", "student", "course", "type", "date")
        self.a_tree = create_styled_treeview(a_frame, columns=cols,
                                              show="headings", height=8)
        for col, (h, w, anch) in {
            "id":      ("ID", 50, "center"),
            "student": (t("alert.col_student"), 240, "e"),
            "course":  (t("alert.col_course"), 220, "e"),
            "type":    (t("alert.col_type"), 130, "center"),
            "date":    (t("alert.col_date"), 110, "center"),
        }.items():
            self.a_tree.heading(col, text=h, anchor=anch)
            self.a_tree.column(col, width=w, anchor=anch)

        a_vsb = ttk.Scrollbar(a_frame, orient=tk.VERTICAL,
                                command=self.a_tree.yview)
        a_vsb.pack(side=side_end(), fill=tk.Y)
        self.a_tree.configure(yscrollcommand=a_vsb.set)
        self.a_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Frame(wrap, bg=c["border"], height=2).pack(fill=tk.X, pady=14)

        # Bottom-anchored refresh button (in the footer that survives scroll)
        tk.Button(self._footer, text=t("alert.refresh_alerts"),
                  command=self.refresh_alerts,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_start(), padx=16)

        tk.Label(wrap, text=t("alert.justifications_title"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"], anchor=anchor_start()).pack(fill=tk.X, pady=(0, 4))

        info_text = (t("alert.can_justify")
                     if self.can_justify
                     else t("alert.view_only"))
        info_color = c["success"] if self.can_justify else c["warning"]
        tk.Label(wrap, text=info_text,
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=info_color, anchor=anchor_start()).pack(fill=tk.X, pady=(0, 8))

        if self.can_justify:
            self._build_justification_form(wrap)

        search_row = tk.Frame(wrap, bg=c["bg_dark"])
        search_row.pack(fill=tk.X, pady=(8, 4))

        tk.Label(search_row, text=t("alert.search_student"),
                 font=FONTS["body"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(0, 6))
        self.j_search_var = tk.StringVar()
        je = tk.Entry(search_row, textvariable=self.j_search_var,
                       font=FONTS["body"], bg=c["input_bg"],
                       fg=c["text_primary"], insertbackground=c["accent"],
                       relief="flat", bd=0, justify=text_justify(), width=28)
        je.pack(side=side_start(), ipady=6, padx=(0, 4))
        je.bind("<KeyRelease>", lambda e: self._search_justifications_debounced())

        tk.Button(search_row, text=t("alert.refresh"),
                  command=self.refresh_justifications,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_end(), padx=(0, 6))

        if self.can_justify:
            tk.Button(search_row, text=t("alert.delete_selected"),
                      command=self._delete_justification,
                      bg=c["error"], fg="#ffffff",
                      activebackground="#dc2626",
                      font=FONTS["body_bold"], relief="flat",
                      cursor="hand2", padx=12, pady=6, bd=0
                      ).pack(side=side_end())

        j_frame = tk.Frame(wrap, bg=c["bg_dark"], height=240)
        j_frame.pack(fill=tk.X, pady=(0, 14))
        j_frame.pack_propagate(False)

        cols_j = ("id", "student", "from", "to", "reason", "by")
        self.j_tree = create_styled_treeview(j_frame, columns=cols_j,
                                              show="headings", height=8)
        for col, (h, w, anch) in {
            "id":      ("ID", 50, "center"),
            "student": (t("alert.col_student"), 200, "e"),
            "from":    (t("alert.col_from"), 100, "center"),
            "to":      (t("alert.col_to"), 100, "center"),
            "reason":  (t("alert.col_reason"), 280, "e"),
            "by":      (t("alert.col_added_by"), 100, "center"),
        }.items():
            self.j_tree.heading(col, text=h, anchor=anch)
            self.j_tree.column(col, width=w, anchor=anch)

        j_vsb = ttk.Scrollbar(j_frame, orient=tk.VERTICAL,
                                command=self.j_tree.yview)
        j_vsb.pack(side=side_end(), fill=tk.Y)
        self.j_tree.configure(yscrollcommand=j_vsb.set)
        self.j_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._j_search_job = None

    def _build_justification_form(self, parent):
        c = COLORS
        form = tk.Frame(parent, bg=c["bg_card"], padx=20, pady=14)
        form.pack(fill=tk.X, pady=(8, 6))

        tk.Label(form, text=t("alert.add_justification"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 8))

        srow = tk.Frame(form, bg=c["bg_card"])
        srow.pack(fill=tk.X, pady=4)
        tk.Label(srow, text=t("alert.search_for_student"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18, anchor=anchor_start()
                 ).pack(side=side_start(), padx=(0, 8))

        self.f_student_var = tk.StringVar()
        student_entry = tk.Entry(srow, textvariable=self.f_student_var,
                                   font=FONTS["body"], bg=c["input_bg"],
                                   fg=c["text_primary"],
                                   insertbackground=c["accent"],
                                   relief="flat", bd=0, justify=text_justify())
        student_entry.pack(side=side_start(), fill=tk.X, expand=True,
                            ipady=7, padx=(0, 8))

        self.f_student_id = None
        self._student_search_job = None

        self.f_listbox = tk.Listbox(form, height=4,
                                      font=FONTS["body"],
                                      bg=c["input_bg"], fg=c["text_primary"],
                                      selectbackground=c["primary"],
                                      selectforeground="#ffffff",
                                      relief="flat", bd=0)
        self.f_listbox.pack(fill=tk.X, pady=4)
        self.f_listbox.bind("<<ListboxSelect>>", self._select_student)

        def search(e=None):
            if self._student_search_job:
                try:
                    parent.after_cancel(self._student_search_job)
                except Exception:
                    pass
            self._student_search_job = parent.after(300, self._do_student_search)

        student_entry.bind("<KeyRelease>", search)
        self._matched = []

        today = date.today().isoformat()

        drow = tk.Frame(form, bg=c["bg_card"])
        drow.pack(fill=tk.X, pady=4)
        tk.Label(drow, text=t("alert.from_date"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18, anchor=anchor_start()
                 ).pack(side=side_start(), padx=(0, 8))
        self.f_from_var = tk.StringVar(value=today)
        DatePicker(drow, variable=self.f_from_var
                   ).pack(side=side_start(), fill=tk.X, expand=True,
                           padx=(0, 8))

        drow2 = tk.Frame(form, bg=c["bg_card"])
        drow2.pack(fill=tk.X, pady=4)
        tk.Label(drow2, text=t("alert.to_date"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18, anchor=anchor_start()
                 ).pack(side=side_start(), padx=(0, 8))
        self.f_to_var = tk.StringVar(value=today)
        DatePicker(drow2, variable=self.f_to_var
                   ).pack(side=side_start(), fill=tk.X, expand=True,
                           padx=(0, 8))

        rrow = tk.Frame(form, bg=c["bg_card"])
        rrow.pack(fill=tk.X, pady=4)
        tk.Label(rrow, text=t("alert.reason_label"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18, anchor=anchor_start()
                 ).pack(side=side_start(), padx=(0, 8), anchor="n")
        self.f_reason_text = tk.Text(rrow, height=4,
                                      font=FONTS["body"],
                                      bg=c["input_bg"], fg=c["text_primary"],
                                      insertbackground=c["accent"],
                                      relief="flat", bd=0, wrap="word")
        self.f_reason_text.pack(side=side_start(), fill=tk.X, expand=True,
                                 padx=(0, 8))

        tk.Button(form, text=t("alert.add_btn"),
                  command=self._add_justification,
                  bg=c["success"], fg="#ffffff",
                  activebackground="#16a34a",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=8, bd=0
                  ).pack(side=side_start(), pady=(8, 0))

    def _do_student_search(self):
        q = self.f_student_var.get().strip()
        if len(q) < 2:
            self.f_listbox.delete(0, tk.END)
            return

        def do():
            try:
                r = http_client.api_get("/api/students/search", q=q)
                if r.status_code == 200:
                    students = r.json().get("students", [])
                    def update():
                        self.f_listbox.delete(0, tk.END)
                        self._matched = students
                        for s in students:
                            self.f_listbox.insert(tk.END,
                                f"{s['full_name']} — {s['academic_id']}")
                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()

    def _select_student(self, event=None):
        sel = self.f_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._matched):
            student = self._matched[idx]
            self.f_student_id = student["id"]
            self.f_student_var.set(student["full_name"])

    def _add_justification(self):
        if not self.f_student_id:
            messagebox.showerror(t("alert.error"), t("alert.select_student_first"))
            return
        from_d = self.f_from_var.get().strip()
        to_d = self.f_to_var.get().strip()
        reason = self.f_reason_text.get("1.0", tk.END).strip()

        if not from_d or not to_d:
            messagebox.showerror(t("alert.error"), t("alert.dates_required"))
            return
        if not reason:
            messagebox.showerror(t("alert.error"), t("alert.reason_required"))
            return

        try:
            r = http_client.api_post("/api/justifications", json_body={
                "student_id":  self.f_student_id,
                "from_date":   from_d,
                "to_date":     to_d,
                "reason":      reason,
                "_role":       self.user.role,
                "_user_id":    self.user.id,
            })
            data = r.json()
            if data.get("success"):
                messagebox.showinfo(t("alert.done"), t("alert.justification_added"))
                self.f_student_id = None
                self.f_student_var.set("")
                self.f_listbox.delete(0, tk.END)
                self.f_reason_text.delete("1.0", tk.END)
                self.refresh_justifications()
            else:
                messagebox.showerror(t("alert.error"), data.get("error", t("alert.failed")))
        except Exception as e:
            messagebox.showerror(t("alert.error"), str(e))

    def _search_justifications_debounced(self):
        if self._j_search_job:
            try:
                self.parent.after_cancel(self._j_search_job)
            except Exception:
                pass
        self._j_search_job = self.parent.after(300, self.refresh_justifications)

    def _delete_justification(self):
        sel = self.j_tree.selection()
        if not sel:
            messagebox.showwarning(t("alert.warning"), t("alert.select_justification"))
            return
        v = self.j_tree.item(sel[0])["values"]
        jid, sname = v[0], v[1]
        if not messagebox.askyesno(t("alert.confirm"),
                                    f'{t("alert.delete_confirm")} {sname}؟'):
            return
        try:
            r = http_client.api_delete(f"/api/justifications/{jid}",
                                        _role=self.user.role)
            if r.json().get("success"):
                self.refresh_justifications()
            else:
                messagebox.showerror(t("alert.error"), r.json().get("error"))
        except Exception as e:
            messagebox.showerror(t("alert.error"), str(e))

    def refresh_alerts(self):
        for r in self.a_tree.get_children():
            self.a_tree.delete(r)

        def do():
            try:
                r = http_client.api_get("/api/alerts")
                if r.status_code == 200:
                    alerts = r.json().get("alerts", [])

                    def update():
                        if not alerts:
                            self.a_tree.insert("", tk.END, values=(
                                "—", t("alert.no_alerts"), "", "", ""))
                            return
                        for a in alerts:
                            atype = ALERT_AR.get(a["alert_type"], a["alert_type"])
                            self.a_tree.insert("", tk.END, values=(
                                a["id"], a["student_name"], a["course_name"],
                                atype, a.get("alert_date", "")))

                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()

    def refresh_justifications(self):
        for r in self.j_tree.get_children():
            self.j_tree.delete(r)

        search = self.j_search_var.get().strip() if hasattr(self, "j_search_var") else ""

        def do():
            try:
                r = http_client.api_get("/api/justifications", search=search)
                if r.status_code == 200:
                    items = r.json().get("justifications", [])

                    def update():
                        if not items:
                            self.j_tree.insert("", tk.END, values=(
                                "—", t("alert.no_justifications"), "", "", "", ""))
                            return
                        for j in items:
                            reason_short = j["reason"][:60] + "..." if len(j["reason"]) > 60 else j["reason"]
                            self.j_tree.insert("", tk.END, values=(
                                j["id"], j["student_name"],
                                j["from_date"], j["to_date"],
                                reason_short, j["created_by"]))

                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()
