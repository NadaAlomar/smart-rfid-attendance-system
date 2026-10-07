"""
إدارة الطلاب
- الإضافة: اسم/أب/أم/كنية + رقم أكاديمي + UID
- البحث: بالاسم والكنية فقط
- التعديل: مع منع تكرار البطاقة + إنشاء بطاقة جديدة (في حال الضياع)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui import http_client
from ui.theme import COLORS, FONTS, create_styled_treeview, create_themed_checkbutton
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify, pad_x
from ui.i18n import t
from ui import client_time
from ui.widgets.date_picker import DatePicker


def _btn(parent, text, cmd, color=None, **kw):
    c = COLORS
    color = color or c["primary"]
    return tk.Button(parent, text=text, command=cmd,
                     bg=color, fg="#ffffff",
                     activebackground=c["primary_light"],
                     activeforeground="#ffffff",
                     relief="flat", font=FONTS["body_bold"],
                     cursor="hand2", padx=16, pady=8, bd=0, **kw)


def _entry(parent, **kw):
    c = COLORS
    return tk.Entry(parent, font=FONTS["body"],
                    bg=c["input_bg"], fg=c["text_primary"],
                    insertbackground=c["accent"],
                    relief="flat", bd=0, justify=text_justify(), **kw)


# ════════════════════════════════════════════════════════
#  StudentForm — صفحة إضافة طالب جديد
# ════════════════════════════════════════════════════════

class StudentForm:
    def __init__(self, parent, on_success=None):
        self.parent = parent
        self.on_success = on_success
        self.branches = []
        self.courses = []
        self._build()
        self._load_data()

    def _build(self):
        c = COLORS

        # ── canvas + scrollbar ──
        canvas = tk.Canvas(self.parent, bg=c["bg_dark"],
                            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self.parent, orient=tk.VERTICAL,
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        outer = tk.Frame(canvas, bg=c["bg_dark"], padx=32, pady=20)
        win_id = canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(win_id, width=e.width))

        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        outer.bind("<Enter>",
                    lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        outer.bind("<Leave>",
                    lambda e: canvas.unbind_all("<MouseWheel>"))

        # ── بطاقة الفورم ──
        card = tk.Frame(outer, bg=c["bg_card"])
        card.pack(fill=tk.X)

        hdr = tk.Frame(card, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=t("student.new_student_data"),
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=16, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        f = tk.Frame(card, bg=c["bg_card"], padx=30, pady=22)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(0, weight=1)

        def lbl(row, text):
            tk.Label(f, text=text, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"],
                     anchor=anchor_start()).grid(row=row, column=1, sticky="e",
                                       padx=pad_x(0, 10), pady=6)

        def ent(row, **kw):
            e = tk.Entry(f, font=FONTS["body"],
                         bg=c["input_bg"], fg=c["text_primary"],
                         insertbackground=c["accent"],
                         relief="flat", bd=0, justify=text_justify(), **kw)
            e.grid(row=row, column=0, sticky="ew", ipady=9, pady=6)
            return e

        def sep(row):
            tk.Frame(f, bg=c["border"], height=1).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        # ── الرقم الأكاديمي ──
        lbl(0, t("student.academic_id_req"))
        self.academic_e = ent(0)
        sep(1)

        # ── حقول الاسم المفصّلة ──
        lbl(2, t("student.first_name_req"))
        self.first_e = ent(2)
        sep(3)

        lbl(4, t("student.father_name_req"))
        self.father_e = ent(4)
        sep(5)

        lbl(6, t("student.mother_name_req"))
        self.mother_e = ent(6)
        sep(7)

        lbl(8, t("student.last_name_req"))
        self.last_e = ent(8)
        sep(9)

        # ── UID + زر مسح ──
        lbl(10, t("student.uid_rfid_req"))
        uid_row = tk.Frame(f, bg=c["bg_card"])
        uid_row.grid(row=10, column=0, sticky="ew", pady=6)
        uid_row.columnconfigure(0, weight=1)

        self.uid_entry = tk.Entry(uid_row, font=FONTS["mono"],
                                   bg=c["input_bg"], fg=c["accent"],
                                   insertbackground=c["accent"],
                                   relief="flat", bd=0, justify=text_justify())
        self.uid_entry.grid(row=0, column=0, sticky="ew", ipady=9)
        self.uid_entry.bind("<KeyRelease>", self._on_uid_paste)

        tk.Button(uid_row, text=t("student.scan"),
                  command=self._scan_rfid,
                  bg=c["info"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  activeforeground="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=8, bd=0
                  ).grid(row=0, column=1, padx=pad_x(8, 0))

        self.uid_ok_lbl = tk.Label(uid_row, text="",
                                    font=("Segoe UI", 16, "bold"),
                                    bg=c["bg_card"], fg=c["success"])
        self.uid_ok_lbl.grid(row=0, column=2, padx=pad_x(6, 0))
        sep(11)

        # ── القسم ──
        lbl(12, t("student.branch_label"))
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(f, textvariable=self.branch_var,
                                          font=FONTS["body"], state="readonly")
        self.branch_combo.grid(row=12, column=0, sticky="ew", ipady=6, pady=6)
        sep(13)

        # ── المادة ──
        lbl(14, t("student.course_optional"))
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(f, textvariable=self.course_var,
                                          font=FONTS["body"], state="readonly")
        self.course_combo.grid(row=14, column=0, sticky="ew", ipady=6, pady=6)
        sep(15)

        # ── بطاقة مؤقتة ──
        self.is_temporary = tk.BooleanVar()
        create_themed_checkbutton(f, text=t("student.temporary_card"),
                                  variable=self.is_temporary,
                                  command=self._toggle_expiry).grid(
            row=16, column=0, sticky="e", pady=(8, 4))

        self.expiry_frame = tk.Frame(f, bg=c["bg_card"])
        self.expiry_frame.grid(row=17, column=0, columnspan=2,
                                 sticky="ew", pady=(0, 6))
        tk.Label(self.expiry_frame, text=t("student.expiry_date_format"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start())
        self.expiry_var = tk.StringVar(value=client_time.now().strftime("%Y-%m-%d"))
        self.expiry_entry = DatePicker(self.expiry_frame, variable=self.expiry_var)
        self.expiry_entry.pack(side=side_start(), padx=pad_x(0, 8))
        self.expiry_frame.grid_remove()

        # ── شريط الأزرار ──
        action_bar = tk.Frame(outer, bg=c["bg_medium"], pady=14)
        action_bar.pack(fill=tk.X, pady=(1, 0))

        tk.Button(action_bar, text=t("student.save_student_btn"), command=self._save,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=24, pady=10, bd=0
                  ).pack(side=side_start(), padx=pad_x(8, 0))

        tk.Button(action_bar, text=t("student.clear_fields_btn"), command=self._clear,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  activeforeground=c["text_primary"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=16, pady=10, bd=0
                  ).pack(side=side_end())

    def _load_data(self):
        def do():
            try:
                r = http_client.api_get("/api/branches")
                if r.status_code == 200:
                    branches = r.json().get("branches", [])
                    def set_branches():
                        self.branches = branches
                        self.branch_combo["values"] = [b["branch_name"] for b in branches]
                    self.parent.after(0, set_branches)
            except Exception:
                pass
            try:
                r = http_client.api_get("/api/courses")
                if r.status_code == 200:
                    courses = r.json().get("courses", [])
                    def set_courses():
                        self.courses = courses
                        self.course_combo["values"] = [
                            f"{c['course_code']} — {c['course_name']}"
                            for c in courses
                        ]
                    self.parent.after(0, set_courses)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _toggle_expiry(self):
        if self.is_temporary.get():
            self.expiry_frame.grid()
        else:
            self.expiry_frame.grid_remove()

    def _scan_rfid(self):
        from ui.rfid_scanner_dialog import RFIDScanDialog
        def on_uid(uid):
            self.uid_entry.delete(0, tk.END)
            self.uid_entry.insert(0, uid)
            self.uid_ok_lbl.config(text="✓")
        RFIDScanDialog(self.parent, on_uid).show()

    def _on_uid_paste(self, event=None):
        import re
        raw = self.uid_entry.get().strip()
        m = re.search(r"CARD:([0-9A-Fa-f]{8,})", raw) or \
            re.search(r"([0-9A-Fa-f]{8,})", raw)
        if m:
            self.uid_entry.delete(0, tk.END)
            self.uid_entry.insert(0, m.group(1).upper())
            self.uid_ok_lbl.config(text="✓")
        else:
            self.uid_ok_lbl.config(text="")

    def _flash_red(self, widget):
        c = COLORS
        widget.config(bg=c["error"], fg="#ffffff")
        widget.after(2000, lambda: widget.config(
            bg=c["input_bg"], fg=c["text_primary"]))

    def _save(self):
        academic_id = self.academic_e.get().strip()
        first = self.first_e.get().strip()
        father = self.father_e.get().strip()
        mother = self.mother_e.get().strip()
        last = self.last_e.get().strip()
        uid = self.uid_entry.get().strip()

        # تحقق من الحقول الإلزامية
        missing = []
        if not academic_id:
            missing.append((t("student.academic_id_field"), self.academic_e))
        if not first:
            missing.append((t("student.first_name_field"), self.first_e))
        if not father:
            missing.append((t("student.father_name_field"), self.father_e))
        if not mother:
            missing.append((t("student.mother_name_field"), self.mother_e))
        if not last:
            missing.append((t("student.last_name_field"), self.last_e))

        if missing:
            for name, w in missing:
                self._flash_red(w)
            messagebox.showerror(t("student.required_fields"),
                t("student.required_fields_prefix") +
                "\n• ".join(n for n, _ in missing))
            return

        if not uid:
            self._flash_red(self.uid_entry)
            messagebox.showerror(t("error"),
                t("student.uid_required_msg"))
            return

        # بناء الاسم الكامل
        full_name = " ".join([first, father, last])

        branch_id = None
        for b in self.branches:
            if b["branch_name"] == self.branch_var.get():
                branch_id = b["id"]
                break

        payload = {
            "academic_id":  academic_id,
            "full_name":    full_name,
            "first_name":   first,
            "father_name":  father,
            "mother_name":  mother,
            "last_name":    last,
            "uid":          uid,
            "is_temporary": self.is_temporary.get(),
            "branch_id":    branch_id,
        }
        if self.is_temporary.get():
            payload["expiry_date"] = self.expiry_var.get().strip()

        def do():
            try:
                r = http_client.api_post("/api/student/add",
                                   json_body=payload)
                data = r.json()
                if data.get("success"):
                    self.parent.after(0, lambda: messagebox.showinfo(
                        t("student.done"), t("student.added_success")))
                    self.parent.after(0, self._clear)
                    if self.on_success:
                        self.parent.after(700, self.on_success)
                else:
                    err = data.get("error", t("student.save_failed"))
                    self.parent.after(0, lambda: messagebox.showerror(t("error"), err))
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("student.connection_error_title"), str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _clear(self):
        for e in (self.academic_e, self.first_e, self.father_e,
                   self.mother_e, self.last_e, self.uid_entry):
            e.delete(0, tk.END)
        self.uid_ok_lbl.config(text="")
        self.is_temporary.set(False)
        self.expiry_frame.grid_remove()
        self.branch_var.set("")
        self.course_var.set("")


# ════════════════════════════════════════════════════════
#  StudentList — قائمة الطلاب مع البحث + تعديل + حذف
# ════════════════════════════════════════════════════════

class StudentList:
    def __init__(self, parent):
        self.parent = parent
        self._build()
        self.refresh()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=20, pady=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── شريط الأدوات ──
        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 12))

        # يمين: البحث
        tk.Label(toolbar, text=t("student.search_name_or_last"), font=FONTS["body"],
                 bg=c["bg_dark"], fg=c["text_muted"]).pack(
            side=side_start(), padx=pad_x(0, 6))
        self.search_var = tk.StringVar()
        se = tk.Entry(toolbar, textvariable=self.search_var,
                      font=FONTS["body"], bg=c["input_bg"],
                      fg=c["text_primary"], insertbackground=c["accent"],
                      relief="flat", bd=0, justify=text_justify(), width=30)
        se.pack(side=side_start(), ipady=7, padx=pad_x(0, 4))
        se.bind("<KeyRelease>", lambda e: self._search_debounced())

        # يسار: أزرار
        _btn(toolbar, t("student.edit_btn"), self._edit, color=c["warning"]
              ).pack(side=side_end(), padx=pad_x(0, 6))
        _btn(toolbar, t("student.courses_btn"), self._courses, color=c["info"]
              ).pack(side=side_end(), padx=pad_x(0, 6))
        _btn(toolbar, t("student.stats_btn"), self._stats, color=c["success"]
              ).pack(side=side_end(), padx=pad_x(0, 6))
        _btn(toolbar, t("student.delete_btn"), self._delete, color=c["error"]
              ).pack(side=side_end())

        self.count_lbl = tk.Label(toolbar, text="",
                                   font=FONTS["small"],
                                   bg=c["bg_dark"], fg=c["text_muted"])
        self.count_lbl.pack(side=side_end(), padx=12)

        footer = tk.Frame(wrap, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        tk.Frame(wrap, bg=c["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        _btn(footer, t("student.refresh_btn"), self.refresh).pack(side=side_end(), padx=pad_x(0, 6))

        # ── جدول ──
        tree_frame = tk.Frame(wrap, bg=c["bg_dark"])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "academic_id", "full_name", "branch", "card", "temporary", "expiry")
        self.tree = create_styled_treeview(tree_frame, columns=cols,
                                            show="headings", selectmode="browse")
        hdrs = {
            "id":          (t("student.col_id"),            60,  "center"),
            "academic_id": (t("student.col_academic_id"), 130, "center"),
            "full_name":   (t("student.col_full_name"),   280,  "e"),
            "branch":      (t("student.col_branch"),       130, "center"),
            "card":        (t("student.col_card"),         110, "center"),
            "temporary":   (t("student.col_temporary"),     70,  "center"),
            "expiry":      (t("student.col_expiry"),       120, "center"),
        }
        for col, (h, w, anch) in hdrs.items():
            self.tree.heading(col, text=h, anchor=anch)
            self.tree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=self.tree.yview)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda e: self._view_details())

        self._search_job = None

    def _search_debounced(self):
        if self._search_job:
            try:
                self.parent.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.parent.after(300, self.refresh)

    def refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        self.count_lbl.config(text=t("student.loading"))
        search = self.search_var.get().strip() if hasattr(self, "search_var") else ""

        def do():
            try:
                r = http_client.api_get("/api/students",
                                 search=search, per_page=500)
                if r.status_code == 200:
                    data = r.json()
                    students = data.get("students", [])
                    def update():
                        for s in students:
                            if s.get("is_placeholder_card") or not s.get("hashed_uid"):
                                card_val = t("student.no_card")
                            else:
                                card_val = s.get("card_hint") or t("student.card_linked")
                            self.tree.insert("", tk.END, values=(
                                s["id"], s["academic_id"], s["full_name"],
                                s.get("branch_name", "—"),
                                card_val,
                                t("yes") if s["is_temporary"] else "—",
                                s["expiry_date"] or "—",
                            ))
                        self.count_lbl.config(
                            text=f'{t("student.total_count")} {data.get("total", 0)} {t("student.students_unit")}')
                    self.parent.after(0, update)
            except Exception as e:
                self.parent.after(0, lambda: self.count_lbl.config(
                    text=f'{t("student.connection_error_label")} {e}'))

        threading.Thread(target=do, daemon=True).start()

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("student.select_student_first"))
            return None
        return self.tree.item(sel[0])["values"]

    def _view_details(self):
        v = self._selected()
        if not v:
            return
        messagebox.showinfo(t("student.details_title"),
                             f"{t('student.detail_id')} {v[0]}\n"
                             f"{t('student.detail_academic_id')} {v[1]}\n"
                             f"{t('student.detail_full_name')} {v[2]}\n"
                             f"{t('student.detail_branch')} {v[3]}\n"
                             f"{t('student.detail_card')} {v[4]}\n"
                             f"{t('student.detail_temporary')} {v[5]}\n"
                             f"{t('student.detail_expiry')} {v[6]}")

    def _edit(self):
        v = self._selected()
        if not v:
            return
        student_id = v[0]
        student_id_int = int(student_id)

        # Fetch full student record (name parts, branch, card status)
        try:
            r = http_client.api_get(f"/api/student/{student_id}")
            data = r.json()
            if not data.get("success"):
                messagebox.showerror(t("error"), data.get("error", ""))
                return
            student = data["student"]
        except Exception as e:
            messagebox.showerror(t("error"), str(e))
            return

        # Fetch branches list
        branches = []
        try:
            br_resp = http_client.api_get("/api/branches").json()
            branches = br_resp.get("branches", [])
        except Exception:
            pass

        c = COLORS
        win = tk.Toplevel()
        win.title(f'{t("student.edit_student_window")} — {student["full_name"]}')
        win.geometry("580x720")
        win.minsize(540, 600)
        win.configure(bg=c["bg_dark"])
        win.grab_set()

        # رأس
        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["warning"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'  {t("student.edit_label")} {student["full_name"]}',
                 font=FONTS["subtitle"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        # جسم قابل للتمرير
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

        # helper for label+entry row
        def _row(row, label_key, value="", widget_factory=None):
            tk.Label(f, text=t(label_key), font=FONTS["small_bold"],
                     bg=c["bg_dark"], fg=c["text_muted"],
                     anchor=anchor_start()).grid(row=row, column=1, sticky="e",
                                                  padx=pad_x(0, 10), pady=6)
            if widget_factory:
                w = widget_factory(f)
            else:
                w = _entry(f)
                if value:
                    w.insert(0, value)
            w.grid(row=row, column=0, sticky="ew", ipady=7, pady=6)
            return w

        # ── الرقم الأكاديمي (للقراءة فقط) ──
        tk.Label(f, text=t("student.academic_id_colon"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_muted"],
                 anchor=anchor_start()).grid(row=0, column=1, sticky="e",
                                              padx=pad_x(0, 10), pady=6)
        tk.Label(f, text=str(student["academic_id"]), font=FONTS["body_bold"],
                 bg=c["bg_dark"], fg=c["accent"],
                 anchor=anchor_start()).grid(row=0, column=0, sticky="ew", pady=6)

        # ── أجزاء الاسم ──
        first_e = _row(1, "student.first_name", student.get("first_name") or "")
        father_e = _row(2, "student.father_name", student.get("father_name") or "")
        mother_e = _row(3, "student.mother_name", student.get("mother_name") or "")
        last_e = _row(4, "student.last_name", student.get("last_name") or "")

        # ── الاسم الكامل ──
        name_e = _row(5, "student.full_name_colon", student["full_name"])

        # ── القسم ──
        tk.Label(f, text=t("student.branch"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_muted"],
                 anchor=anchor_start()).grid(row=6, column=1, sticky="e",
                                              padx=pad_x(0, 10), pady=6)
        branch_var = tk.StringVar()
        branch_options = [(b["id"], f'{b["branch_code"]} — {b["branch_name"]}') for b in branches]
        branch_labels = [t("student.no_branch")] + [lbl for _, lbl in branch_options]
        branch_combo = ttk.Combobox(f, textvariable=branch_var,
                                     values=branch_labels, state="readonly")
        branch_combo.grid(row=6, column=0, sticky="ew", ipady=4, pady=6)
        # Set initial value
        cur_branch_id = student.get("branch_id")
        if cur_branch_id:
            for i, (bid, _) in enumerate(branch_options):
                if bid == cur_branch_id:
                    branch_combo.current(i + 1)
                    break
            else:
                branch_combo.current(0)
        else:
            branch_combo.current(0)

        # ── البطاقة المؤقتة ──
        temp_var = tk.BooleanVar(value=bool(student.get("is_temporary")))
        exp_var = tk.StringVar(value=student.get("expiry_date") or "")
        temp_frame = tk.Frame(f, bg=c["bg_card"], padx=14, pady=12)
        temp_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(14, 8))

        tk.Label(temp_frame, text=t("student.temporary_card"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 4))

        temp_inner = tk.Frame(temp_frame, bg=c["bg_card"])
        temp_inner.pack(fill=tk.X)

        def _sync_expiry_state():
            try:
                exp_entry.set_enabled(bool(temp_var.get()))
            except Exception:
                pass

        create_themed_checkbutton(temp_inner, text=t("student.temporary_card"),
                                  variable=temp_var,
                                  command=_sync_expiry_state).pack(side=side_start())

        tk.Label(temp_inner, text=t("student.card_expiry"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=pad_x(16, 4))
        exp_entry = DatePicker(temp_inner, variable=exp_var)
        exp_entry.pack(side=side_start(), padx=pad_x(0, 4))
        _sync_expiry_state()
        tk.Label(temp_inner, text=t("student.expiry_format_hint"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start())

        # ── قسم البطاقة ──
        sec = tk.Frame(f, bg=c["bg_card"], padx=14, pady=12)
        sec.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(14, 8))

        tk.Label(sec, text=t("student.current_card_status"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["info"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 6))

        if student.get("is_placeholder_card"):
            status_text = f"⚠ {t('student.no_card')}"
            status_color = c["warning"]
        elif student.get("hashed_uid"):
            status_text = f"✓ {t('student.card_linked')}"
            status_color = c["success"]
        else:
            status_text = f"⚠ {t('student.card_not_linked')}"
            status_color = c["error"]

        tk.Label(sec, text=status_text, font=FONTS["body_bold"],
                 bg=c["bg_card"], fg=status_color,
                 anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 8))

        tk.Label(sec, text=t("student.change_card_info"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"], anchor=anchor_start(),
                 justify=text_justify()).pack(anchor=anchor_start(), pady=(0, 8))

        uid_row = tk.Frame(sec, bg=c["bg_card"])
        uid_row.pack(fill=tk.X)
        uid_row.columnconfigure(0, weight=1)

        uid_e = tk.Entry(uid_row, font=FONTS["mono"],
                         bg=c["input_bg"], fg=c["accent"],
                         insertbackground=c["accent"],
                         relief="flat", bd=0, justify=text_justify())
        uid_e.grid(row=0, column=0, sticky="ew", ipady=9)

        uid_ok = tk.Label(uid_row, text="", font=("Segoe UI", 14, "bold"),
                          bg=c["bg_card"], fg=c["success"])
        uid_ok.grid(row=0, column=2, padx=pad_x(6, 0))

        def _scan_for_edit():
            from ui.rfid_scanner_dialog import RFIDScanDialog
            def on_uid(u):
                uid_e.delete(0, tk.END)
                uid_e.insert(0, u)
                uid_ok.config(text="✓")
            RFIDScanDialog(win, on_uid).show()

        tk.Button(uid_row, text=t("student.change_card_btn"),
                  command=_scan_for_edit,
                  bg=c["info"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  activeforeground="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=8, bd=0
                  ).grid(row=0, column=1, padx=pad_x(8, 0))

        # ── أزرار ──
        btn_row = tk.Frame(f, bg=c["bg_dark"])
        btn_row.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(20, 0))

        def save():
            new_name = name_e.get().strip()
            if not new_name:
                messagebox.showerror(t("error"), t("student.name_required"), parent=win)
                return
            payload = {
                "full_name": new_name,
                "first_name": first_e.get().strip(),
                "father_name": father_e.get().strip(),
                "mother_name": mother_e.get().strip(),
                "last_name": last_e.get().strip(),
            }
            new_uid = uid_e.get().strip()
            if new_uid:
                force_uid_change = False
                try:
                    lookup = http_client.api_get(
                        "/api/cards/lookup",
                        uid=new_uid, owner_type="student", owner_id=student_id_int,
                    ).json()
                    if not lookup.get("success"):
                        messagebox.showerror(t("error"), lookup.get("error", ""), parent=win)
                        return
                    linked_to = lookup.get("linked_to")
                    holder_id = lookup.get("id")
                    holder_name = lookup.get("name") or ""
                    if linked_to == "student" and holder_id == student_id_int:
                        messagebox.showinfo(t("warning"), t("student.card_used_self"), parent=win)
                        return
                    if linked_to == "student":
                        if not messagebox.askyesno(
                            t("warning"),
                            t("student.card_used_confirm").format(name=holder_name),
                            parent=win,
                        ):
                            return
                        force_uid_change = True
                    elif linked_to == "doctor":
                        messagebox.showerror(
                            t("error"),
                            t("student.card_used_doctor").format(name=holder_name),
                            parent=win,
                        )
                        return
                except Exception as e:
                    messagebox.showerror(t("error"), str(e), parent=win)
                    return
                payload["uid"] = new_uid
                if force_uid_change:
                    payload["force_uid_change"] = True

            # branch
            sel_idx = branch_combo.current()
            if sel_idx == 0:
                payload["branch_id"] = None
            elif sel_idx > 0 and sel_idx - 1 < len(branch_options):
                payload["branch_id"] = branch_options[sel_idx - 1][0]

            # temporary card
            payload["is_temporary"] = bool(temp_var.get())
            exp_value = exp_var.get().strip()
            if temp_var.get() and exp_value:
                payload["expiry_date"] = exp_value
            elif not temp_var.get():
                # backend treats falsy expiry as no-op; leave alone
                pass

            try:
                r = http_client.api_put(f"/api/student/{student_id}",
                                  json_body=payload)
                data = r.json()
                if data.get("success"):
                    msg = t("student.updated_success")
                    if new_uid:
                        msg += "\n" + t("student.new_card_activated")
                    messagebox.showinfo(t("student.done"), msg, parent=win)
                    win.destroy()
                    self.refresh()
                else:
                    messagebox.showerror(t("error"),
                        data.get("error", t("student.update_failed")), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        tk.Button(btn_row, text=t("student.save_changes"),
                  command=save,
                  bg=c["success"], fg="#ffffff",
                   activebackground=c["success"],
                   font=FONTS["body_bold"], relief="flat",
                   cursor="hand2", padx=20, pady=10, bd=0
                   ).pack(side=side_start(), padx=pad_x(0, 8))

        tk.Button(btn_row, text=t("cancel"),
                  command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=10, bd=0
                  ).pack(side=side_end())

    def _delete(self):
        v = self._selected()
        if not v:
            return
        if not messagebox.askyesno(t("student.confirm_delete_title"),
                                    f"{t('student.confirm_delete_msg')} '{v[2]}'?\n"
                                    f"{t('student.confirm_delete_note')}"):
            return
        try:
            r = http_client.api_delete(f"/api/student/{v[0]}")
            data = r.json()
            if data.get("success"):
                messagebox.showinfo(t("student.done"), t("student.deleted_success"))
                self.refresh()
            else:
                messagebox.showerror(t("error"), data.get("error", t("student.delete_failed")))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def _stats(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("student.select_student"))
            return
        item = self.tree.item(sel[0])
        student_id = item["values"][0]
        student_name = item["values"][2]

        def do():
            try:
                resp = http_client.api_get(f"/api/students/{student_id}/stats")
                data = resp.json()
            except Exception as ex:
                self.parent.after(0, lambda: messagebox.showerror(t("error"), str(ex)))
                return

            def show():
                c = COLORS
                win = tk.Toplevel(self.parent)
                win.title(f'{t("student.stats_window_title")} {student_name}')
                win.configure(bg=c["bg_card"])
                win.geometry("650x400")
                win.transient(self.parent)
                win.grab_set()

                tk.Label(win, text=f'📊  {t("student.stats_attendance")} {student_name}',
                         font=FONTS["subtitle"], bg=c["bg_card"], fg=c["accent"],
                         anchor=anchor_start(), padx=16, pady=12).pack(fill=tk.X)

                cols = ("course_code", "course_name", "total", "attended", "absent", "percentage")
                tree = create_styled_treeview(win, columns=cols, show="headings", height=12)
                for col, (h, w, anch) in {
                    "course_code": (t("student.col_code"), 80, "center"),
                    "course_name": (t("student.col_course"), 200, "e"),
                    "total": (t("student.col_sessions"), 70, "center"),
                    "attended": (t("student.col_attended"), 60, "center"),
                    "absent": (t("student.col_absent"), 60, "center"),
                    "percentage": (t("student.col_percentage"), 80, "center"),
                }.items():
                    tree.heading(col, text=h, anchor=anch)
                    tree.column(col, width=w, anchor=anch)

                vsb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=tree.yview)
                vsb.pack(side=side_end(), fill=tk.Y)
                tree.configure(yscrollcommand=vsb.set)
                tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

                for s in data.get("stats", []):
                    pct = s["percentage"]
                    color = c["success"] if pct >= 75 else (c["warning"] if pct >= 50 else c["error"])
                    iid = tree.insert("", tk.END, values=(
                        s["course_code"], s["course_name"],
                        s["total_sessions"], s["attended"], s["absent"],
                        f"{pct}%",
                    ), tags=(color,))
                    tree.tag_configure(color, foreground=color)

            self.parent.after(0, show)
        threading.Thread(target=do, daemon=True).start()

    def _courses(self):
        v = self._selected()
        if not v:
            return
        StudentCoursesDialog(self.parent, student_id=v[0], student_name=v[2])


class StudentCoursesDialog:
    def __init__(self, parent, student_id, student_name):
        self.parent = parent
        self.student_id = student_id
        self.student_name = student_name
        self._show()

    def _show(self):
        c = COLORS
        win = tk.Toplevel()
        win.title(f'{t("student.courses_window_title")} — {self.student_name}')
        win.geometry("600x440")
        win.minsize(500, 380)
        win.configure(bg=c["bg_dark"])
        win.grab_set()

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["info"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'  📚 {t("student.courses_of")} {self.student_name}',
                 font=FONTS["subtitle"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_dark"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        cols = ("enr_id", "course_code", "course_name", "action")
        tree = create_styled_treeview(body, columns=cols, show="headings",
                                       selectmode="browse")
        for col, h, w in [("enr_id", t("student.col_enrollment_id"), 80),
                          ("course_code", t("student.col_symbol"), 100),
                          ("course_name", t("student.col_course_name"), 220),
                          ("action", "", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, pady=(10, 0))

        all_courses = []

        def load_enrollments():
            if not win.winfo_exists():
                return
            for r in tree.get_children():
                tree.delete(r)
            try:
                r = http_client.api_get("/api/enrollments",
                                  student_id=self.student_id)
                data = r.json()
                if data.get("success"):
                    for e in data["enrollments"]:
                        eid = e["id"]
                        tree.insert("", tk.END, values=(
                            eid, e.get("course_code", ""), e.get("course_name", ""), "🗑"
                        ), tags=("has_del",))
                    tree.tag_configure("has_del", foreground=c["error"])
            except Exception:
                pass

        def load_courses():
            try:
                r = http_client.api_get("/api/courses")
                if r.status_code == 200:
                    return r.json().get("courses", [])
            except Exception:
                pass
            return []

        def add_course():
            nonlocal all_courses
            c_win = tk.Toplevel(win)
            c_win.title(t("student.add_course_title"))
            c_win.geometry("400x200")
            c_win.configure(bg=c["bg_dark"])
            c_win.grab_set()

            tk.Label(c_win, text=t("student.select_course_colon"), font=FONTS["body_bold"],
                     bg=c["bg_dark"], fg=c["text_secondary"]).pack(
                anchor=anchor_start(), padx=16, pady=(16, 6))

            combo = ttk.Combobox(c_win, state="readonly", font=FONTS["body"])
            combo["values"] = [f"{cr['course_code']} — {cr['course_name']}" for cr in all_courses]
            if all_courses:
                combo.current(0)
            combo.pack(fill=tk.X, padx=16, ipady=6)

            def do_add():
                idx = combo.current()
                if idx < 0:
                    messagebox.showwarning(t("warning"), t("student.select_course_msg"), parent=c_win)
                    return
                course_id = all_courses[idx]["id"]
                try:
                    r = http_client.api_post("/api/enrollments",
                                       json_body={"student_id": self.student_id,
                                             "course_id": course_id})
                    data = r.json()
                    if data.get("success"):
                        c_win.destroy()
                        load_enrollments()
                    else:
                        messagebox.showerror(t("error"), data.get("error", ""), parent=c_win)
                except Exception as ex:
                    messagebox.showerror(t("error"), str(ex), parent=c_win)

            tk.Button(c_win, text=t("student.add_btn"), command=do_add,
                      bg=c["success"], fg="#ffffff",
                      font=FONTS["body_bold"], relief="flat",
                      cursor="hand2", padx=18, pady=8, bd=0
                      ).pack(pady=14)

        def remove_course():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(t("warning"), t("student.select_enrollment_first"), parent=win)
                return
            eid = tree.item(sel[0])["values"][0]
            if not messagebox.askyesno(t("student.confirm_title"), t("student.confirm_unenroll_msg"), parent=win):
                return
            try:
                http_client.api_delete(f"/api/enrollments/{eid}")
                load_enrollments()
            except Exception as ex:
                messagebox.showerror(t("error"), str(ex), parent=win)

        _btn(btn_row, t("student.add_course_btn"), add_course, color=c["success"]).pack(side=side_start(), padx=pad_x(0, 6))
        _btn(btn_row, t("student.delete_selected_btn"), remove_course, color=c["error"]).pack(side=side_start())

        def _on_tree_click(event):
            region = tree.identify("region", event.x, event.y)
            if region != "cell":
                return
            col = tree.identify_column(event.x)
            row = tree.identify_row(event.y)
            if not row:
                return
            if col == f"#{len(cols)}":
                tree.selection_set(row)
                remove_course()
        tree.bind("<Button-1>", _on_tree_click)

        def init():
            nonlocal all_courses
            all_courses = load_courses()
            load_enrollments()
        threading.Thread(target=init, daemon=True).start()
