"""Secretary tool: swipe a student's RFID card, then open a full profile dialog
(info / courses / weekly schedule / attendance stats) with add/remove course
controls.

Entry point: StudentProfileByCard(parent).start()
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading

from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, pad_x, text_justify
from ui.i18n import t
from ui import http_client
from ui.rfid_scanner_dialog import RFIDScanDialog


DAY_NAMES_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس",
                "الجمعة", "السبت", "الأحد"]
DAY_NAMES_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _day_label(idx):
    try:
        from ui.theme import get_lang
        names = DAY_NAMES_AR if get_lang() == "ar" else DAY_NAMES_EN
    except Exception:
        names = DAY_NAMES_AR
    if 0 <= idx < len(names):
        return names[idx]
    return str(idx)


class StudentProfileByCard:
    """Triggers an RFID scan, then opens the profile dialog for the matched student."""

    def __init__(self, parent):
        self.parent = parent

    def start(self):
        RFIDScanDialog(self.parent, self._on_uid).show()

    def _on_uid(self, uid):
        def do():
            try:
                r = http_client.api_get("/api/students/by-uid", uid=uid)
                data = r.json()
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), str(e), parent=self.parent))
                return
            if data.get("success"):
                student_id = data["student"]["id"]
                self.parent.after(0, lambda: StudentProfileDialog(
                    self.parent, student_id).show())
            else:
                msg = data.get("message") or data.get("error") or "غير معروفة"
                self.parent.after(0, lambda: messagebox.showwarning(
                    t("warning"), msg, parent=self.parent))
        threading.Thread(target=do, daemon=True).start()


class StudentProfileDialog:
    """Full profile dialog with tabs for the given student id."""

    def __init__(self, parent, student_id):
        self.parent = parent
        self.student_id = student_id
        self.win = None
        self.bundle = None
        self.all_courses = []

    def show(self):
        self._build_window()
        self._load_bundle()

    def _build_window(self):
        c = COLORS
        self.win = tk.Toplevel()
        self.win.title("ملف الطالب")
        self.win.geometry("900x640")
        self.win.minsize(800, 560)
        self.win.configure(bg=c["bg_dark"])
        self.win.grab_set()

        # ── Header ──
        self.hdr = tk.Frame(self.win, bg=c["bg_medium"])
        self.hdr.pack(fill=tk.X)
        tk.Frame(self.hdr, bg=c["primary"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        self.name_lbl = tk.Label(self.hdr, text="جاري التحميل…",
                                  font=FONTS["section"], bg=c["bg_medium"],
                                  fg=c["accent"])
        self.name_lbl.pack(side=side_start(), padx=16, pady=12)
        self.sub_lbl = tk.Label(self.hdr, text="",
                                 font=FONTS["small"], bg=c["bg_medium"],
                                 fg=c["text_muted"])
        self.sub_lbl.pack(side=side_start(), padx=8, pady=12)
        tk.Frame(self.hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        # ── Tabs ──
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.info_tab = tk.Frame(self.nb, bg=c["bg_dark"])
        self.courses_tab = tk.Frame(self.nb, bg=c["bg_dark"])
        self.schedule_tab = tk.Frame(self.nb, bg=c["bg_dark"])
        self.stats_tab = tk.Frame(self.nb, bg=c["bg_dark"])

        self.nb.add(self.info_tab, text="معلومات")
        self.nb.add(self.courses_tab, text="المواد المسجّل بها")
        self.nb.add(self.schedule_tab, text="الجدول الأسبوعي")
        self.nb.add(self.stats_tab, text="الحضور والغياب")

        # close button
        btn_row = tk.Frame(self.win, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(btn_row, text="إغلاق", command=self.win.destroy,
                  bg=c["bg_light"], fg=c["text_primary"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_end())
        tk.Button(btn_row, text="تحديث", command=self._load_bundle,
                  bg=c["primary"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_end(), padx=pad_x(0, 6))

    # ────────────────────────────────────────────────────────────────────
    def _load_bundle(self):
        def do():
            try:
                r = http_client.api_get(
                    f"/api/students/{self.student_id}/profile-bundle")
                self.bundle = r.json()
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), str(e), parent=self.win))
                return
            try:
                r2 = http_client.api_get("/api/courses")
                self.all_courses = r2.json().get("courses", [])
            except Exception:
                self.all_courses = []

            if not self.bundle or not self.bundle.get("success"):
                err = (self.bundle or {}).get("error", "تعذّر التحميل")
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), err, parent=self.win))
                return
            self.parent.after(0, self._render)
        threading.Thread(target=do, daemon=True).start()

    def _render(self):
        if not self.win or not self.win.winfo_exists():
            return
        st = self.bundle["student"]
        self.name_lbl.config(text=f"👤 {st['full_name']}")
        self.sub_lbl.config(text=f"({st['academic_id']}) — {st.get('branch_name') or '—'}")

        self._render_info(st)
        self._render_courses(self.bundle["courses"])
        self._render_schedule(self.bundle["schedule"])
        self._render_stats(self.bundle["stats"])

    # ── Info tab ───────────────────────────────────────────────────────
    def _render_info(self, st):
        for w in self.info_tab.winfo_children():
            w.destroy()
        c = COLORS
        wrap = tk.Frame(self.info_tab, bg=c["bg_dark"], padx=24, pady=18)
        wrap.pack(fill=tk.BOTH, expand=True)

        rows = [
            ("الرقم الأكاديمي", st.get("academic_id", "")),
            ("الاسم الكامل", st.get("full_name", "")),
            ("الاسم الأول", st.get("first_name") or "—"),
            ("اسم الأب", st.get("father_name") or "—"),
            ("اسم الأم", st.get("mother_name") or "—"),
            ("الكنية", st.get("last_name") or "—"),
            ("القسم/الفرع", st.get("branch_name") or "—"),
            ("بطاقة مؤقتة", "نعم" if st.get("is_temporary") else "لا"),
            ("تاريخ انتهاء البطاقة", st.get("expiry_date") or "—"),
            ("حالة البطاقة",
             ("بدون بطاقة" if st.get("is_placeholder_card")
              else f"مرتبطة (•••{st.get('card_hint') or '----'})")),
        ]
        for i, (k, v) in enumerate(rows):
            tk.Label(wrap, text=k, font=FONTS["small_bold"],
                     bg=c["bg_dark"], fg=c["text_muted"]).grid(
                row=i, column=1, sticky="e", padx=pad_x(0, 12), pady=5)
            tk.Label(wrap, text=str(v), font=FONTS["body"],
                     bg=c["bg_dark"], fg=c["text_primary"]).grid(
                row=i, column=0, sticky="w", pady=5)
        wrap.columnconfigure(0, weight=1)

    # ── Courses tab ────────────────────────────────────────────────────
    def _render_courses(self, courses):
        for w in self.courses_tab.winfo_children():
            w.destroy()
        c = COLORS
        wrap = tk.Frame(self.courses_tab, bg=c["bg_dark"], padx=12, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 8))
        tk.Button(toolbar, text="➕  إضافة مادة", command=self._add_course,
                  bg=c["success"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=7, bd=0
                  ).pack(side=side_start())
        tk.Button(toolbar, text="🗑  إلغاء التسجيل من المادة المحددة",
                  command=self._remove_course,
                  bg=c["error"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=7, bd=0
                  ).pack(side=side_start(), padx=pad_x(8, 0))

        cols = ("enr_id", "code", "name", "type", "doctor")
        self.courses_tree = create_styled_treeview(wrap, columns=cols,
                                                    show="headings", height=14)
        for col, h, w_ in [("enr_id", "#", 60),
                           ("code", "الرمز", 110),
                           ("name", "اسم المادة", 320),
                           ("type", "النوع", 90),
                           ("doctor", "الدكتور", 220)]:
            self.courses_tree.heading(col, text=h)
            self.courses_tree.column(col, width=w_, anchor="center")
        self.courses_tree.pack(fill=tk.BOTH, expand=True)
        for cr in courses:
            self.courses_tree.insert("", tk.END, values=(
                cr.get("enrollment_id", ""),
                cr.get("course_code", ""),
                cr.get("course_name", ""),
                cr.get("course_type", ""),
                cr.get("doctor_name", ""),
            ))

    def _add_course(self):
        if not self.all_courses:
            messagebox.showinfo(t("warning"), "لا توجد مواد متاحة",
                                parent=self.win)
            return
        c = COLORS
        already = {row["course_id"] for row in self.bundle.get("courses", [])}
        available = [cc for cc in self.all_courses if cc["id"] not in already]
        if not available:
            messagebox.showinfo(t("warning"),
                                "الطالب مسجّل بكل المواد المتاحة",
                                parent=self.win)
            return

        win = tk.Toplevel(self.win)
        win.title("إضافة مادة")
        win.geometry("440x220")
        win.configure(bg=c["bg_dark"])
        win.grab_set()
        tk.Label(win, text="اختر المادة:", font=FONTS["body_bold"],
                 bg=c["bg_dark"], fg=c["text_secondary"]
                 ).pack(anchor=anchor_start(), padx=16, pady=(16, 6))
        combo = ttk.Combobox(win, state="readonly", font=FONTS["body"])
        combo["values"] = [f"{cr['course_code']} — {cr['course_name']}"
                           for cr in available]
        combo.current(0)
        combo.pack(fill=tk.X, padx=16, ipady=6)

        def do_add():
            idx = combo.current()
            if idx < 0:
                return
            cid = available[idx]["id"]
            try:
                r = http_client.api_post(
                    "/api/enrollments",
                    json_body={"student_id": self.student_id,
                               "course_id": cid})
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    self._load_bundle()
                else:
                    messagebox.showerror(t("error"),
                                         data.get("error", "فشل"),
                                         parent=win)
            except Exception as ex:
                messagebox.showerror(t("error"), str(ex), parent=win)

        tk.Button(win, text="إضافة", command=do_add,
                  bg=c["success"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(pady=14)

    def _remove_course(self):
        sel = self.courses_tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"),
                                   "اختر تسجيلاً أولاً", parent=self.win)
            return
        enr_id = self.courses_tree.item(sel[0])["values"][0]
        if not enr_id:
            return
        if not messagebox.askyesno(t("confirm_delete"),
                                    "تأكيد إلغاء التسجيل من هذه المادة؟",
                                    parent=self.win):
            return
        try:
            http_client.api_delete(f"/api/enrollments/{enr_id}")
            self._load_bundle()
        except Exception as ex:
            messagebox.showerror(t("error"), str(ex), parent=self.win)

    # ── Schedule tab ───────────────────────────────────────────────────
    def _render_schedule(self, rows):
        for w in self.schedule_tab.winfo_children():
            w.destroy()
        c = COLORS
        wrap = tk.Frame(self.schedule_tab, bg=c["bg_dark"], padx=12, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        cols = ("day", "start", "end", "code", "name", "hall")
        tree = create_styled_treeview(wrap, columns=cols,
                                       show="headings", height=14)
        for col, h, w_ in [("day", "اليوم", 100),
                           ("start", "البداية", 80),
                           ("end", "النهاية", 80),
                           ("code", "الرمز", 100),
                           ("name", "المادة", 280),
                           ("hall", "القاعة", 140)]:
            tree.heading(col, text=h)
            tree.column(col, width=w_, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True)
        if not rows:
            tk.Label(wrap, text="لا يوجد جدول حالياً",
                     font=FONTS["body"], bg=c["bg_dark"],
                     fg=c["text_muted"]).pack(pady=8)
            return

        sorted_rows = sorted(rows, key=lambda r: (r.get("day_of_week", 0),
                                                    r.get("start_time", "")))
        for r in sorted_rows:
            tree.insert("", tk.END, values=(
                _day_label(r.get("day_of_week", 0)),
                r.get("start_time", ""), r.get("end_time", ""),
                r.get("course_code", ""), r.get("course_name", ""),
                r.get("hall_name", "—"),
            ))

    # ── Stats tab ──────────────────────────────────────────────────────
    def _render_stats(self, stats):
        for w in self.stats_tab.winfo_children():
            w.destroy()
        c = COLORS
        wrap = tk.Frame(self.stats_tab, bg=c["bg_dark"], padx=12, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        cols = ("code", "name", "total", "attended", "absent", "pct")
        tree = create_styled_treeview(wrap, columns=cols,
                                       show="headings", height=14)
        for col, h, w_ in [("code", "الرمز", 90),
                           ("name", "المادة", 280),
                           ("total", "إجمالي الجلسات", 110),
                           ("attended", "حضور", 80),
                           ("absent", "غياب", 80),
                           ("pct", "النسبة", 100)]:
            tree.heading(col, text=h)
            tree.column(col, width=w_, anchor="center")

        tree.tag_configure("good", foreground=c["success"])
        tree.tag_configure("warn", foreground=c["warning"])
        tree.tag_configure("bad", foreground=c["error"])

        tree.pack(fill=tk.BOTH, expand=True)
        if not stats:
            tk.Label(wrap, text="لا توجد إحصائيات حضور",
                     font=FONTS["body"], bg=c["bg_dark"],
                     fg=c["text_muted"]).pack(pady=8)
            return

        for s in stats:
            pct = s["percentage"]
            tag = "good" if pct >= 75 else ("warn" if pct >= 50 else "bad")
            tree.insert("", tk.END, values=(
                s["course_code"], s["course_name"],
                s["total_sessions"], s["attended"], s["absent"],
                f"{pct}%",
            ), tags=(tag,))
