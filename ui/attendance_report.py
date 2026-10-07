import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from ui import http_client
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t



class AttendanceReport:
    def __init__(self, parent):
        self.parent = parent
        self.courses = []
        self._build()
        self._load_courses()

    def _btn(self, parent, text, cmd, bg, fg="#f5f3ff", width=None):
        kw = dict(text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=bg, activeforeground=fg,
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=7, bd=0)
        if width:
            kw["width"] = width
        return tk.Button(parent, **kw)

    def _build(self):
        c = COLORS

        hdr = tk.Frame(self.parent, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=t("report.page_title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=8, pady=14)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        filter_card = tk.Frame(self.parent, bg=c["bg_card"], padx=20, pady=14)
        filter_card.pack(fill=tk.X, padx=16, pady=(12, 0))
        tk.Frame(filter_card, bg=c["success"], height=3).pack(fill=tk.X, pady=(0, 10))

        filter_row = tk.Frame(filter_card, bg=c["bg_card"])
        filter_row.pack(fill=tk.X)

        self._btn(filter_row, t("report.export_excel"),
                  self._export, c["warning"], fg=c["bg_dark"]).pack(side=side_end(), padx=(0, 8))
        self._btn(filter_row, t("report.view_report"),
                  self._load_report, c["success"], fg=c["bg_dark"]).pack(side=side_end())

        week_frame = tk.Frame(filter_row, bg=c["bg_card"])
        week_frame.pack(side=side_start())
        tk.Label(week_frame, text=t("report.week_number"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_secondary"]).pack(side=side_start(), padx=(0, 6))
        self.week_var = tk.StringVar(value="1")
        ttk.Spinbox(week_frame, from_=1, to=30, textvariable=self.week_var,
                    width=6).pack(side=side_start())

        course_frame = tk.Frame(filter_row, bg=c["bg_card"])
        course_frame.pack(side=side_start(), padx=(0, 16))
        tk.Label(course_frame, text=t("report.course_label"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_secondary"]).pack(side=side_start(), padx=(0, 6))
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(course_frame, textvariable=self.course_var,
                                          width=38, state="readonly")
        self.course_combo.pack(side=side_start())

        tree_outer = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=10)
        tree_outer.pack(fill=tk.BOTH, expand=True)

        border_frame = tk.Frame(tree_outer, bg=c["border"], padx=1, pady=1)
        border_frame.pack(fill=tk.BOTH, expand=True)

        tree_inner = tk.Frame(border_frame, bg=c["bg_card"])
        tree_inner.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(tree_inner, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)

        cols = ("student_id", "student_name", "sessions", "present", "absent", "percentage")
        self.tree = create_styled_treeview(tree_inner, columns=cols,
                                            show="headings", selectmode="browse")
        hdrs = {
            "student_id":   (t("report.col_student_id"), 130),
            "student_name": (t("report.col_student_name"),       240),
            "sessions":     (t("report.col_sessions"),         100),
            "present":      (t("report.col_present"),               80),
            "absent":       (t("report.col_absent"),               80),
            "percentage":   (t("report.col_percentage"),       120),
        }
        for col, (h, w) in hdrs.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center", minwidth=50)

        self.tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=self.tree.yview)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.tag_configure("low", foreground=COLORS["error"])
        self.tree.tag_configure("ok",  foreground=COLORS["success"])

        summary_bar = tk.Frame(self.parent, bg=c["bg_medium"], padx=16, pady=8)
        summary_bar.pack(fill=tk.X)

        self.summary_label = tk.Label(summary_bar, text=t("report.select_course_week"),
                                       font=FONTS["small"], bg=c["bg_medium"],
                                       fg=c["text_muted"])
        self.summary_label.pack(side=side_start())

        tk.Label(summary_bar,
                 text=t("report.color_legend"),
                 font=FONTS["small"], bg=c["bg_medium"],
                 fg=c["text_muted"]).pack(side=side_end())

    def _load_courses(self):
        def do():
            try:
                r = http_client.api_get("/api/courses")
                if r.status_code == 200:
                    courses = r.json().get("courses", [])

                    def update():
                        self.courses = courses
                        self.course_combo["values"] = [
                            f"{c['course_code']} — {c['course_name']}"
                            for c in courses
                        ]
                        if courses:
                            self.course_combo.current(0)

                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()

    def _get_course_id(self):
        idx = self.course_combo.current()
        if idx < 0 or idx >= len(self.courses):
            return None
        return self.courses[idx]["id"]

    def _load_report(self):
        course_id = self._get_course_id()
        if not course_id:
            messagebox.showwarning(t("report.warning"), t("report.select_course"))
            return
        try:
            week = int(self.week_var.get())
        except ValueError:
            messagebox.showerror(t("report.error"), t("report.week_number_invalid"))
            return

        for r in self.tree.get_children():
            self.tree.delete(r)
        self.summary_label.config(text=t("report.loading"))

        def do():
            try:
                r = http_client.api_get("/api/report/attendance", course_id=course_id, week=week)
                data = r.json()
                if data.get("success"):
                    rows = data.get("data", [])
                    low_count = 0
                    entries = []
                    for rd in rows:
                        att = rd.get("attendance", [])
                        n_s = len(att)
                        n_p = sum(1 for a in att if a["status"] == "present")
                        n_a = n_s - n_p
                        pct = rd.get("percentage", 0)
                        tag = "low" if pct < 75 else "ok"
                        if tag == "low":
                            low_count += 1
                        entries.append((rd["student_id"], rd["student_name"],
                                        n_s, n_p, n_a, f"{pct:.1f}%", tag))
                    summary = (f"{t('report.students')} {len(rows)}  |  {t('report.week')} {week}  |  "
                               f"{t('report.low_attendance')} {low_count}")

                    def update():
                        for vals in entries:
                            self.tree.insert("", tk.END, values=vals[:6], tags=(vals[6],))
                        self.summary_label.config(text=summary)

                    self.parent.after(0, update)
                else:
                    msg = data.get("error", t("report.no_data"))
                    self.parent.after(0, lambda: self.summary_label.config(text=msg))
            except requests.exceptions.ConnectionError:
                self.parent.after(0, lambda: self.summary_label.config(text=t("report.connection_error")))
            except Exception as e:
                msg = str(e)
                self.parent.after(0, lambda: self.summary_label.config(text=msg))

        threading.Thread(target=do, daemon=True).start()

    def _export(self):
        course_id = self._get_course_id()
        if not course_id:
            messagebox.showwarning(t("report.warning"), t("report.select_course"))
            return
        week = self.week_var.get()
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[(t("report.excel_files"), "*.xlsx")],
            title=t("report.save_title"),
        )
        if not save_path:
            return

        def do():
            try:
                r = http_client.api_get("/api/report/export", course_id=course_id, week=week)
                if r.status_code == 200:
                    with open(save_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                    messagebox.showinfo(t("report.exported_title"), f'{t("report.report_saved_at")}\n{save_path}')
                else:
                    messagebox.showerror(t("report.error"), t("report.export_failed"))
            except Exception as e:
                messagebox.showerror(t("report.error"), str(e))

        threading.Thread(target=do, daemon=True).start()


class SessionDetailsDialog:
    def __init__(self, parent, session_id):
        self.parent = parent
        self.session_id = session_id
        c = COLORS

        self.win = tk.Toplevel(parent)
        self.win.title(t("report.session_details"))
        self.win.configure(bg=c["bg_card"])
        self.win.geometry("800x550")
        self.win.transient(parent)
        self.win.grab_set()

        self.info_frame = tk.Frame(self.win, bg=c["bg_card"], padx=16, pady=10)
        self.info_frame.pack(fill=tk.X)

        self.notebook = ttk.Notebook(self.win)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.present_frame = tk.Frame(self.notebook, bg=c["bg_dark"])
        self.absent_frame = tk.Frame(self.notebook, bg=c["bg_dark"])
        self.notebook.add(self.present_frame, text=t("report.present_tab"))
        self.notebook.add(self.absent_frame, text=t("report.absent_tab"))

        self.present_tree = create_styled_treeview(self.present_frame,
            columns=("name", "academic_id", "time"), show="headings", height=15)
        for col, (h, w) in {"name": (t("report.col_name"), 250), "academic_id": (t("report.col_id"), 120),
                             "time": (t("report.col_checkin_time"), 150)}.items():
            self.present_tree.heading(col, text=h)
            self.present_tree.column(col, width=w)
        self.present_tree.pack(fill=tk.BOTH, expand=True)

        self.absent_tree = create_styled_treeview(self.absent_frame,
            columns=("name", "academic_id"), show="headings", height=15)
        for col, (h, w) in {"name": (t("report.col_name"), 250), "academic_id": (t("report.col_id"), 120)}.items():
            self.absent_tree.heading(col, text=h)
            self.absent_tree.column(col, width=w)
        self.absent_tree.pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(self.win, bg=c["bg_card"], padx=16, pady=8)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text=t("report.add_manual_present"), command=self._add_manual,
                  bg=c["success"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0).pack(side=side_start(), padx=(0, 8))
        tk.Button(btn_frame, text=t("report.delete_record"), command=self._delete_record,
                  bg=c["error"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0).pack(side=side_start())

        self._load()

    def _load(self):
        for w in self.info_frame.winfo_children():
            w.destroy()
        for r in self.present_tree.get_children():
            self.present_tree.delete(r)
        for r in self.absent_tree.get_children():
            self.absent_tree.delete(r)

        def do():
            try:
                resp = http_client.api_get(f"/api/attendance/session/{self.session_id}")
                data = resp.json()
            except Exception:
                return

            c = COLORS
            s = data.get("session", {})
            info_text = (f"{t('report.info_course')} {s.get('course_name', '—')}  |  "
                         f"{t('report.info_doctor')} {s.get('doctor_name', '—')}  |  "
                         f"{t('report.info_hall')} {s.get('hall_name', '—')}  |  "
                         f"{t('report.info_date')} {s.get('date', '—')}  |  "
                         f"{t('report.info_start')} {s.get('start_time', '—')[:19]}  |  "
                         f"{t('report.info_status')} {t('report.status_active') if s.get('is_active') else t('report.status_closed')}")

            def update():
                tk.Label(self.info_frame, text=info_text, font=FONTS["body"],
                         bg=c["bg_card"], fg=c["text_secondary"],
                         anchor=anchor_start(), wraplength=750, justify=text_justify()).pack(fill=tk.X)
                for p in data.get("present", []):
                    self.present_tree.insert("", tk.END, values=(
                        p["student_name"], p["academic_id"],
                        p.get("check_in_time", "")[:19].replace("T", " "),
                    ))
                for a in data.get("absent", []):
                    self.absent_tree.insert("", tk.END, values=(
                        a["student_name"], a["academic_id"],
                    ))

            self.win.after(0, update)
        threading.Thread(target=do, daemon=True).start()

    def _add_manual(self):
        from tkinter import simpledialog
        student_id = simpledialog.askinteger(t("report.add_present_title"), t("report.enter_student_id"),
                                              parent=self.win)
        if not student_id:
            return
        def do():
            try:
                resp = http_client.api_post("/api/attendance/manual", json_body={
                    "session_id": self.session_id,
                    "student_id": student_id,
                    "status": "present",
                })
                data = resp.json()
                if data.get("success"):
                    self._load()
                else:
                    self.win.after(0, lambda: messagebox.showerror(t("report.error"), data.get("error", "")))
            except Exception as ex:
                self.win.after(0, lambda: messagebox.showerror(t("report.error"), str(ex)))
        threading.Thread(target=do, daemon=True).start()

    def _delete_record(self):
        sel = self.present_tree.selection()
        if not sel:
            sel = self.absent_tree.selection()
        if not sel:
            messagebox.showwarning(t("report.warning"), t("report.select_record_to_delete"))
            return
        record_id = self.present_tree.item(sel[0])["values"] if sel else None
        if not messagebox.askyesno(t("report.confirm"), t("report.confirm_delete_record")):
            return
        def do():
            try:
                http_client.api_delete(f"/api/attendance/{record_id}")
                self._load()
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
