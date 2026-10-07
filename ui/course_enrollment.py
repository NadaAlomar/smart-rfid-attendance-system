"""Course Enrollment panel with student search, conflict warnings and badges."""
import tkinter as tk
from tkinter import ttk, messagebox
from ui import http_client
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, text_justify
from ui.i18n import t


class CourseEnrollmentPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._selected_student_id = None
        self._all_courses = []
        self._enrolled_ids = set()
        self._build()

    # ─────────────────────────── UI BUILD ───────────────────────────
    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=24, pady=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        search_frame = tk.Frame(wrap, bg=c["bg_dark"])
        search_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(search_frame, text=t("enroll.search_student"), font=FONTS["small_bold"],
                 bg=c["bg_dark"], fg=c["text_secondary"],
                 anchor=anchor_start()).pack(side=side_start(), padx=(0, 8))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                font=FONTS["body"], bg=c["input_bg"],
                                fg=c["text_primary"], insertbackground=c["accent"],
                                relief="flat", bd=0, justify=text_justify())
        search_entry.pack(side=side_start(), fill=tk.X, expand=True, ipady=7, padx=(0, 12))
        search_entry.bind("<KeyRelease>", lambda e: self._on_search_debounced())

        self.student_listbox = tk.Listbox(wrap, height=5, font=FONTS["body"],
                                            bg=c["input_bg"], fg=c["text_primary"],
                                            selectbackground=c["primary"],
                                            selectforeground="#ffffff",
                                            relief="flat", bd=0)
        self.student_listbox.pack(fill=tk.X, pady=(0, 6))
        self._search_job = None
        self._matched_students = []
        self.student_listbox.bind("<<ListboxSelect>>", self._on_student_select)

        # ── شريط معلومات (badges) ──
        info = tk.Frame(wrap, bg=c["bg_dark"])
        info.pack(fill=tk.X, pady=(0, 12))

        self.badge_courses = tk.Label(info, text=t("enroll.total_courses").format(n=0),
                                      font=FONTS["small_bold"], bg=c["bg_medium"],
                                      fg=c["accent"], padx=14, pady=6)
        self.badge_courses.pack(side=side_start(), padx=(0, 8))

        self.badge_hours = tk.Label(info, text=t("enroll.total_weekly_hours").format(h=0),
                                    font=FONTS["small_bold"], bg=c["bg_medium"],
                                    fg=c["info"], padx=14, pady=6)
        self.badge_hours.pack(side=side_start(), padx=(0, 8))

        self.badge_status = tk.Label(info, text=t("enroll.no_student_selected"),
                                     font=FONTS["small"], bg=c["bg_dark"],
                                     fg=c["text_muted"])
        self.badge_status.pack(side=side_start(), padx=(8, 0))

        refresh_btn = tk.Button(info, text=f"⟳ {t('enroll.refresh')}",
                                command=self._load_courses,
                                bg=c["bg_light"], fg=c["text_primary"],
                                font=FONTS["small_bold"], relief="flat",
                                cursor="hand2", padx=10, pady=4, bd=0)
        refresh_btn.pack(side=side_end())

        # ── جزء الجداول (متاحة | مسجلة) ──
        panels = tk.Frame(wrap, bg=c["bg_dark"])
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)
        panels.rowconfigure(0, weight=1)

        # متاحة
        left = tk.LabelFrame(panels, text=t("enroll.available_courses"),
                             font=FONTS["section"], bg=c["bg_card"],
                             fg=c["accent"], padx=12, pady=8)
        left.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        self.available_tree = create_styled_treeview(left,
            columns=("code", "name", "doctor", "schedule"),
            show="headings", height=12)
        for col, (h, w) in {
            "code":     (t("enroll.col_code"),     90),
            "name":     (t("enroll.col_name"),     220),
            "doctor":   (t("enroll.col_doctor"),   140),
            "schedule": (t("enroll.col_schedule"), 200),
        }.items():
            self.available_tree.heading(col, text=h)
            self.available_tree.column(col, width=w, anchor="center", minwidth=40)
        self.available_tree.pack(fill=tk.BOTH, expand=True)

        # مسجلة
        right = tk.LabelFrame(panels, text=t("enroll.enrolled_courses"),
                              font=FONTS["section"], bg=c["bg_card"],
                              fg=c["success"], padx=12, pady=8)
        right.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        self.enrolled_tree = create_styled_treeview(right,
            columns=("code", "name", "doctor", "schedule"),
            show="headings", height=12)
        for col, (h, w) in {
            "code":     (t("enroll.col_code"),     90),
            "name":     (t("enroll.col_name"),     220),
            "doctor":   (t("enroll.col_doctor"),   140),
            "schedule": (t("enroll.col_schedule"), 200),
        }.items():
            self.enrolled_tree.heading(col, text=h)
            self.enrolled_tree.column(col, width=w, anchor="center", minwidth=40)
        self.enrolled_tree.pack(fill=tk.BOTH, expand=True)

        # ── أزرار العمليات ──
        btn_frame = tk.Frame(wrap, bg=c["bg_medium"], padx=12, pady=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))

        tk.Button(btn_frame, text=f"➕  {t('enroll.enroll_btn')}",
                  command=self._enroll_selected,
                  bg=c["primary"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=9, bd=0
                  ).pack(side=side_start(), padx=(0, 8))

        tk.Button(btn_frame, text=f"✖  {t('enroll.unenroll_btn')}",
                  command=self._unenroll_selected,
                  bg=c["error"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=9, bd=0
                  ).pack(side=side_start())

        panels.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def _on_search_debounced(self):
        if self._search_job:
            try:
                self.parent.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.parent.after(300, self._do_student_search)

    def _do_student_search(self):
        q = self.search_var.get().strip()
        if len(q) < 2:
            self.student_listbox.delete(0, tk.END)
            self._matched_students = []
            return

        def do():
            try:
                r = http_client.api_get("/api/students/search", q=q)
                if r.status_code == 200:
                    students = r.json().get("students", [])
                    def update():
                        self.student_listbox.delete(0, tk.END)
                        self._matched_students = students
                        for s in students:
                            self.student_listbox.insert(tk.END,
                                f"{s['full_name']} — {s['academic_id']}")
                    self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _on_student_select(self, _event=None):
        sel = self.student_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._matched_students):
            student = self._matched_students[idx]
            self._selected_student_id = student["id"]
            self.search_var.set(f"{student['full_name']} ({student['academic_id']})")
            self.badge_status.config(
                text=f"{student['full_name']} ({student['academic_id']})",
                fg=COLORS["accent"])
            self._load_courses()

    def _format_schedules(self, schedules):
        """Turn schedule dicts into human-readable text."""
        if not schedules:
            return "—"
        # try translate the day; falls back to digit
        day_keys = [
            "course.day_mon", "course.day_tue", "course.day_wed",
            "course.day_thu", "course.day_fri", "course.day_sat",
            "course.day_sun",
        ]
        parts = []
        for s in schedules:
            d = s.get("day_of_week", 0)
            day_name = t(day_keys[d]) if 0 <= d < 7 else str(d)
            st = (s.get("start_time") or "")[:5]
            et = (s.get("end_time") or "")[:5]
            parts.append(f"{day_name} {st}-{et}")
        return ", ".join(parts)

    def _load_courses(self):
        if not self._selected_student_id:
            return
        # clear
        for r in self.available_tree.get_children():
            self.available_tree.delete(r)
        for r in self.enrolled_tree.get_children():
            self.enrolled_tree.delete(r)

        sid = self._selected_student_id

        def do():
            try:
                # detailed enrollments (with schedules + total hours)
                det = http_client.api_get(f"/api/students/{sid}/courses-detailed").json()
                enrolled_courses = det.get("courses", [])
                enrolled_ids = {c["course_id"] for c in enrolled_courses}
                total_hours = det.get("total_weekly_hours", 0)

                # all courses (full)
                all_resp = http_client.api_get("/api/courses/full").json()
                all_courses = all_resp.get("courses", [])

                # we need schedule info for "available" courses too — fetch /api/schedules
                sched_resp = http_client.api_get("/api/schedules").json()
                all_sched = sched_resp.get("schedules", [])
                # group schedules by course_id
                sched_by_course = {}
                for s in all_sched:
                    sched_by_course.setdefault(s["course_id"], []).append(s)

                self._all_courses = all_courses
                self._enrolled_ids = enrolled_ids

                # update badges
                self.parent.after(0, lambda: self.badge_courses.config(
                    text=t("enroll.total_courses").format(n=len(enrolled_courses))))
                self.parent.after(0, lambda: self.badge_hours.config(
                    text=t("enroll.total_weekly_hours").format(h=total_hours)))

                # populate enrolled (with detailed schedule info)
                for c in enrolled_courses:
                    sched_text = self._format_schedules(c.get("schedules", []))
                    row = (c["course_code"], c["course_name"],
                           c.get("doctor_name") or t("course.no_doctor"),
                           sched_text)
                    self.parent.after(0, lambda r=row, cid=c["course_id"]:
                        self.enrolled_tree.insert("", tk.END, values=r, tags=(str(cid),)))

                # populate available (everything else, with schedules from sched_by_course)
                for c in all_courses:
                    if c["id"] in enrolled_ids:
                        continue
                    scheds = sched_by_course.get(c["id"], [])
                    sched_text = self._format_schedules(scheds)
                    row = (c["course_code"], c["course_name"],
                           c.get("doctor_name") or t("course.no_doctor"),
                           sched_text)
                    self.parent.after(0, lambda r=row, cid=c["id"]:
                        self.available_tree.insert("", tk.END, values=r, tags=(str(cid),)))
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), f"{t('course.load_failed')}: {e}"))
        threading.Thread(target=do, daemon=True).start()

    # ─────────────────────────── ACTIONS ────────────────────────────
    def _enroll_selected(self):
        if not self._selected_student_id:
            messagebox.showwarning(t("warning"), t("enroll.select_student_first"))
            return
        selected = self.available_tree.selection()
        if not selected:
            messagebox.showwarning(t("warning"), t("enroll.select_courses"))
            return
        course_ids = []
        for s in selected:
            tags = self.available_tree.item(s, "tags")
            if tags:
                course_ids.append(int(tags[0]))

        sid = self._selected_student_id

        def do():
            try:
                resp = http_client.api_post("/api/enrollments/bulk", json_body={
                    "student_id": sid,
                    "course_ids": course_ids,
                })
                data = resp.json()
                if data.get("success"):
                    created = data.get("created", 0)
                    conflicts = data.get("conflicts", []) or []
                    msg = t("enroll.enrolled_n").format(n=created)
                    if conflicts:
                        msg += "\n" + t("enroll.conflicts_n").format(n=len(conflicts))
                    self.parent.after(0, lambda: messagebox.showinfo(t("ok"), msg))
                    self.parent.after(0, self._load_courses)
                else:
                    err = data.get("error", t("course.enrolled_fail"))
                    self.parent.after(0, lambda: messagebox.showerror(t("error"), err))
            except Exception as ex:
                self.parent.after(0, lambda: messagebox.showerror(t("error"), str(ex)))
        threading.Thread(target=do, daemon=True).start()

    def _unenroll_selected(self):
        if not self._selected_student_id:
            messagebox.showwarning(t("warning"), t("enroll.select_student_first"))
            return
        selected = self.enrolled_tree.selection()
        if not selected:
            messagebox.showwarning(t("warning"), t("enroll.select_to_remove"))
            return
        if not messagebox.askyesno(t("course.confirm_title"),
                                    t("course.confirm_unenroll")):
            return
        sid = self._selected_student_id

        def do():
            removed = 0
            for s in selected:
                tags = self.enrolled_tree.item(s, "tags")
                if not tags:
                    continue
                cid = int(tags[0])
                try:
                    enroll_resp = http_client.api_get("/api/enrollments", student_id=sid, course_id=cid)
                    enrollments = enroll_resp.json().get("enrollments", [])
                    for e in enrollments:
                        if e["course_id"] == cid:
                            http_client.api_delete(f"/api/enrollments/{e['id']}")
                            removed += 1
                except Exception:
                    pass
            self.parent.after(0, self._load_courses)
        threading.Thread(target=do, daemon=True).start()
