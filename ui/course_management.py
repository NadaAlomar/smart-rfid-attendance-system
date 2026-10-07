import tkinter as tk
from tkinter import ttk, messagebox
from ui import http_client
import threading
from ui.theme import COLORS, FONTS, apply_theme, create_styled_treeview, create_styled_label_frame
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify, pad_x
from ui.i18n import t
from ui.widgets.scrollable import ScrollFrame


def _days():
    return [t("course.day_mon"), t("course.day_tue"), t("course.day_wed"),
            t("course.day_thu"), t("course.day_fri"), t("course.day_sat"),
            t("course.day_sun")]


class CourseManagement:
    def __init__(self, parent):
        self.parent = parent
        self._build()
        self.refresh()

    def _btn(self, parent, text, cmd, bg, fg=None, width=None):
        if fg is None:
            fg = COLORS["text_primary"]
        kw = dict(text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=bg, activeforeground=fg,
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=12, pady=7, bd=0)
        if width:
            kw["width"] = width
        return tk.Button(parent, **kw)

    def _lbl(self, parent, text, font_key="body", color_key="text_secondary"):
        c = COLORS
        return tk.Label(parent, text=text, font=FONTS[font_key],
                        bg=c["bg_card"], fg=c[color_key], anchor=anchor_start())

    def _entry(self, parent, var=None, width=28, justify="right"):
        c = COLORS
        kw = dict(font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  justify=text_justify(), width=width)
        if var:
            kw["textvariable"] = var
        return tk.Entry(parent, **kw)

    def _row_entry(self, parent, label_text, var=None, width=28):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=pad_x(8, 0))
        kw = dict(font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  justify=text_justify())
        if var:
            kw["textvariable"] = var
        e = tk.Entry(row, **kw)
        e.pack(side=side_end(), fill=tk.X, expand=True, ipady=8, padx=pad_x(0, 8))
        return e

    def _row_widget(self, parent, label_text, widget):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=pad_x(8, 0))
        widget.pack(in_=row, side=side_end(), fill=tk.X, expand=True,
                    ipady=7, padx=pad_x(0, 8))
        return widget

    def _field(self, parent, label_text, widget):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=pad_x(8, 0))
        widget.pack(in_=row, side=side_end(), fill=tk.X, expand=True,
                    ipady=7, padx=pad_x(0, 8))

    def _make_dialog(self, title, width=460, height=360):
        c = COLORS
        win = tk.Toplevel(self.parent)
        win.title(title)
        win.geometry(f"{width}x{height}")
        win.resizable(True, True)
        win.grab_set()
        win.configure(bg=c["bg_dark"])

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["primary"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=f"  {title}", font=FONTS["subtitle"],
                 bg=c["bg_medium"], fg=c["accent"]).pack(side=side_end(), padx=10, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_card"], padx=28, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        return win, body

    def _tree_frame(self, parent):
        c = COLORS
        border = tk.Frame(parent, bg=c["border"], padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(border, bg=c["bg_card"])
        inner.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(inner, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)
        return inner, vsb

    def _build(self):
        c = COLORS

        hdr = tk.Frame(self.parent, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["primary"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=f"  {t('course.manage_title')}",
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=8, pady=14)

        btn_area = tk.Frame(hdr, bg=c["bg_medium"])
        btn_area.pack(side=side_start(), padx=16, pady=10)
        self._btn(btn_area, f"+  {t('course.add_course')}", self._add_dialog, c["success"], fg=c["bg_dark"]).pack(side=side_start())
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        footer = tk.Frame(self.parent, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 8))
        tk.Frame(self.parent, bg=c["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self._btn(footer, f"⟳  {t('refresh')}", self.refresh, c["bg_light"]).pack(side=side_end(), padx=pad_x(0, 6))

        self._scroll = ScrollFrame(self.parent, bg_key="bg_dark")
        self._scroll.pack(fill=tk.BOTH, expand=True)

        nb = ttk.Notebook(self._scroll.inner)
        nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        tab1 = tk.Frame(nb, bg=c["bg_dark"])
        nb.add(tab1, text=f"  {t('course.courses_tab')}  ")

        t1_tree_area = tk.Frame(tab1, bg=c["bg_dark"], padx=8, pady=8)
        t1_tree_area.pack(fill=tk.BOTH, expand=True)

        inner1, vsb1 = self._tree_frame(t1_tree_area)

        cols = ("id", "code", "name", "type", "weeks", "doctor", "enrolled")
        self.tree = create_styled_treeview(inner1, columns=cols, show="headings", selectmode="browse")
        hdrs = {
            "id":       (t("course.col_id"),     50),
            "code":     (t("course.col_code"),     90),
            "name":     (t("course_name"),  220),
            "type":     (t("course.col_type"),     80),
            "weeks":    (t("course.col_weeks"),  70),
            "doctor":   (t("course.col_doctor"),   160),
            "enrolled": (t("course.col_students"),    70),
        }
        for col, (h, w) in hdrs.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center", minwidth=40)

        self.tree.configure(yscrollcommand=vsb1.set)
        vsb1.configure(command=self.tree.yview)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda e: self._edit_dialog())

        ab1 = tk.Frame(tab1, bg=c["bg_medium"], padx=10, pady=8)
        ab1.pack(fill=tk.X)
        self.status = tk.Label(ab1, text="", font=FONTS["small"],
                                bg=c["bg_medium"], fg=c["text_muted"])
        self.status.pack(side=side_start(), padx=10)

        for text, cmd, bg in [
            (f"👥 {t('course_students')}", self._course_students_dialog, c["info"]),
            (t("course.enroll_students_btn"),  self._enroll_dialog,         c["info"]),
            (t("course.add_schedule"),  self._schedule_dialog,        c["warning"]),
            (t("course.assign_doctor"), self._assign_doctor_dialog,   c["primary"]),
            (f"✎  {t('edit')}",    self._edit_dialog,            c["bg_light"]),
            (f"✖  {t('delete')}",      self._delete,                 c["error"]),
        ]:
            self._btn(ab1, text, cmd, bg).pack(side=side_end(), padx=4)

        tab2 = tk.Frame(nb, bg=c["bg_dark"])
        nb.add(tab2, text=f"  {t('course.schedules_tab')}  ")

        t2_tree_area = tk.Frame(tab2, bg=c["bg_dark"], padx=8, pady=8)
        t2_tree_area.pack(fill=tk.BOTH, expand=True)

        inner2, vsb2 = self._tree_frame(t2_tree_area)

        scols = ("id", "course", "hall", "day", "start", "end")
        self.stree = create_styled_treeview(inner2, columns=scols, show="headings", selectmode="browse")
        shdrs = {
            "id":     (t("course.col_id"),   50),
            "course": (t("course.col_course"),  260),
            "hall":   (t("course.col_hall"),  140),
            "day":    (t("day"),   100),
            "start":  (t("course.col_start"),  80),
            "end":    (t("course.col_end"),  80),
        }
        for col, (h, w) in shdrs.items():
            self.stree.heading(col, text=h)
            self.stree.column(col, width=w, anchor="center", minwidth=40)

        self.stree.configure(yscrollcommand=vsb2.set)
        vsb2.configure(command=self.stree.yview)
        self.stree.pack(fill=tk.BOTH, expand=True)

        ab2 = tk.Frame(tab2, bg=c["bg_medium"], padx=10, pady=8)
        ab2.pack(fill=tk.X)
        self._btn(ab2, f"⟳  {t('refresh')}", self._refresh_schedules, c["bg_light"]).pack(side=side_end(), padx=pad_x(0, 6))
        self._btn(ab2, f"✖  {t('course.delete_schedule_btn')}", self._delete_schedule, c["error"]).pack(side=side_end())

        # ── Tab 3: Visual Schedule editor ──
        tab3 = tk.Frame(nb, bg=c["bg_dark"])
        nb.add(tab3, text=f"  {t('course.visual_schedule_tab')}  ")
        from ui.visual_schedule_editor import VisualScheduleEditor
        VisualScheduleEditor(tab3)

    def refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        self.status.config(text=t("course.loading"))

        def do():
            try:
                r = http_client.api_get("/api/courses/full")
                data = r.json()
                if data.get("success"):
                    courses = data["courses"]
                    rows = []
                    for crs in courses:
                        type_ar = t("course.practical") if crs["course_type"] == "practical" else t("course.theory")
                        tag = "practical" if crs["course_type"] == "practical" else ""
                        rows.append((crs["id"], crs["course_code"], crs["course_name"],
                                     type_ar, crs["total_weeks"],
                                     crs["doctor_name"], crs["enrolled_count"], tag))

                    def update():
                        for row in rows:
                            self.tree.insert("", tk.END, values=row[:7], tags=(row[7],))
                        self.tree.tag_configure("practical", background=COLORS["bg_light"])
                        self.status.config(text=f"{t('course.courses_count')} {len(courses)}")

                    self.parent.after(0, update)
                    self._refresh_schedules()
                else:
                    self.parent.after(0, lambda: self.status.config(text=t("course.load_failed")))
            except Exception as e:
                msg = str(e)
                self.parent.after(0, lambda: self.status.config(text=f"{t('error')}: {msg}"))

        threading.Thread(target=do, daemon=True).start()

    def _refresh_schedules(self):
        def do():
            try:
                r = http_client.api_get("/api/schedules")
                data = r.json()
                if data.get("success"):
                    scheds = data["schedules"]
                    days = _days()

                    def update():
                        for r in self.stree.get_children():
                            self.stree.delete(r)
                        for s in scheds:
                            day_ar = days[s["day_of_week"]] if 0 <= s["day_of_week"] <= 6 else s.get("day_name", "")
                            self.stree.insert("", tk.END, values=(
                                s["id"],
                                f"{s['course_code']} — {s['course_name']}",
                                s["hall_name"], day_ar,
                                s["start_time"][:5], s["end_time"][:5],
                            ))

                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()

    def _selected_course(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("course.select_course_first"))
            return None
        return self.tree.item(sel[0])["values"]

    def _add_dialog(self):
        c = COLORS
        win, body = self._make_dialog(t("course.add_new_title"), width=480, height=400)

        code_var = tk.StringVar()
        name_var = tk.StringVar()
        weeks_var = tk.StringVar(value="15")
        type_var = tk.StringVar(value="theory")

        self._row_entry(body, f"{t('course_code')}  *", code_var)
        self._row_entry(body, f"{t('course_name')}  *", name_var)
        self._row_entry(body, t("total_weeks"), weeks_var)

        type_row = tk.Frame(body, bg=c["bg_card"])
        type_row.pack(fill=tk.X, pady=5)
        tk.Label(type_row, text=t("course.col_type"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=16).pack(side=side_start())
        radio_frame = tk.Frame(type_row, bg=c["bg_card"])
        radio_frame.pack(side=side_start(), padx=pad_x(0, 8))
        for val, label in [("practical", t("course.practical")), ("theory", t("course.theory"))]:
            tk.Radiobutton(radio_frame, text=label, variable=type_var, value=val,
                           bg=c["bg_card"], fg=c["text_secondary"],
                           selectcolor="#ffffff",
                           activebackground=c["bg_card"],
                           activeforeground=c["accent"],
                           font=FONTS["body"]).pack(side=side_start(), padx=8)

        doctors = []
        try:
            r = http_client.api_get("/api/doctors")
            if r.status_code == 200:
                doctors = r.json().get("doctors", [])
        except Exception:
            pass
        doc_var = tk.StringVar()
        doc_combo = ttk.Combobox(body, textvariable=doc_var, width=26, state="readonly")
        doc_combo["values"] = [t("course.no_doctor")] + [d["full_name"] for d in doctors]
        doc_combo.current(0)
        self._row_widget(body, t("doctor"), doc_combo)

        def save():
            code = code_var.get().strip().upper()
            name = name_var.get().strip()
            if not code or not name:
                messagebox.showerror(t("error"), t("course.code_name_required"), parent=win)
                return
            try:
                weeks = int(weeks_var.get())
            except ValueError:
                messagebox.showerror(t("error"), t("course.weeks_must_number"), parent=win)
                return
            idx = doc_combo.current()
            doc_id = doctors[idx - 1]["id"] if idx > 0 else None
            try:
                r = http_client.api_post("/api/courses", json_body={
                    "course_code": code, "course_name": name,
                    "course_type": type_var.get(),
                    "total_weeks": weeks, "doctor_id": doc_id,
                })
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    self.refresh()
                    messagebox.showinfo(t("success"), t("course.course_added"))
                else:
                    messagebox.showerror(t("error"), data.get("error", t("course.operation_failed")), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.pack(fill=tk.X, pady=(14, 0))
        self._btn(btn_row, f"✔  {t('course.save_course')}", save, c["success"], fg=c["bg_dark"]).pack(side=side_start())
        self._btn(btn_row, t("cancel"), win.destroy, c["bg_light"]).pack(side=side_start(), padx=pad_x(0, 8))

    def _edit_dialog(self):
        vals = self._selected_course()
        if not vals:
            return
        cid, code, name, ctype, weeks, doctor, enrolled = vals

        c = COLORS
        win, body = self._make_dialog(f"{t('course.edit_title')} — {code}", width=520, height=400)

        name_var = tk.StringVar(value=name)
        weeks_var = tk.StringVar(value=str(weeks))
        type_var = tk.StringVar(value="practical" if ctype == t("course.practical") else "theory")

        self._row_entry(body, t("course_name"), name_var)
        self._row_entry(body, t("total_weeks"), weeks_var, width=10)

        type_row = tk.Frame(body, bg=c["bg_card"])
        type_row.pack(fill=tk.X, pady=5)
        tk.Label(type_row, text=t("course.col_type"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=16).pack(side=side_start())
        radio_frame = tk.Frame(type_row, bg=c["bg_card"])
        radio_frame.pack(side=side_start(), padx=pad_x(0, 8))
        for val, lbl in [("practical", t("course.practical")), ("theory", t("course.theory"))]:
            tk.Radiobutton(radio_frame, text=lbl, variable=type_var, value=val,
                           bg=c["bg_card"], fg=c["text_secondary"],
                           selectcolor="#ffffff",
                           activebackground=c["bg_card"],
                           activeforeground=c["accent"],
                           font=FONTS["body"]).pack(side=side_start(), padx=8)

        def save():
            try:
                r = http_client.api_put(f"/api/courses/{cid}", json_body={
                    "course_name": name_var.get().strip(),
                    "total_weeks": int(weeks_var.get()),
                    "course_type": type_var.get(),
                })
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    self.refresh()
                    messagebox.showinfo(t("course.done"), t("course.course_updated"))
                else:
                    messagebox.showerror(t("error"), data.get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.pack(fill=tk.X, pady=(14, 0))
        self._btn(btn_row, f"✔  {t('course.save_changes')}", save, c["success"], fg=c["bg_dark"]).pack(side=side_start())
        self._btn(btn_row, t("cancel"), win.destroy, c["bg_light"]).pack(side=side_start(), padx=pad_x(0, 8))

    def _delete(self):
        vals = self._selected_course()
        if not vals:
            return
        if not messagebox.askyesno(t("confirm_delete"),
                                    f"{t('course.confirm_delete_course')} '{vals[2]}'?\n{t('course.confirm_delete_details')}"):
            return
        try:
            r = http_client.api_delete(f"/api/courses/{vals[0]}")
            data = r.json()
            if data.get("success"):
                self.refresh()
                messagebox.showinfo(t("course.deleted_title"), t("course.course_deleted"))
            else:
                messagebox.showerror(t("error"), data.get("error", ""))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def _assign_doctor_dialog(self):
        vals = self._selected_course()
        if not vals:
            return
        cid = vals[0]
        c = COLORS
        win, body = self._make_dialog(f"{t('course.assign_doctor')} — {vals[2]}", width=480, height=300)

        tk.Label(body, text=t("course.choose_doctor"),
                 font=FONTS["body_bold"], bg=c["bg_card"],
                 fg=c["text_secondary"]).pack(anchor=anchor_start(), pady=(0, 8))

        doctors = []
        try:
            r = http_client.api_get("/api/doctors")
            if r.status_code == 200:
                doctors = r.json().get("doctors", [])
        except Exception:
            pass

        doc_var = tk.StringVar()
        combo = ttk.Combobox(body, textvariable=doc_var, width=36, state="readonly")
        combo["values"] = [d["full_name"] for d in doctors]
        combo.pack(fill=tk.X, pady=4, ipady=6)

        def assign():
            idx = combo.current()
            if idx < 0:
                messagebox.showwarning(t("warning"), t("course.select_doctor"), parent=win)
                return
            try:
                r = http_client.api_put(f"/api/courses/{cid}",
                                  json_body={"doctor_id": doctors[idx]["id"]})
                if r.json().get("success"):
                    win.destroy()
                    self.refresh()
                    messagebox.showinfo(t("course.done"), t("course.doctor_assigned"))
                else:
                    messagebox.showerror(t("error"), r.json().get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.pack(fill=tk.X, pady=(14, 0))
        self._btn(btn_row, f"✔  {t('course.assign_btn')}", assign, c["success"], fg=c["bg_dark"]).pack(side=side_start())
        self._btn(btn_row, t("cancel"), win.destroy, c["bg_light"]).pack(side=side_start(), padx=pad_x(0, 8))

    def _schedule_dialog(self):
        vals = self._selected_course()
        if not vals:
            return
        cid, code, name = vals[0], vals[1], vals[2]
        c = COLORS

        win = tk.Toplevel(self.parent)
        win.title(f"{t('course.add_schedule')} — {code}")
        win.geometry("560x500")
        win.minsize(520, 460)
        win.configure(bg=c["bg_dark"])
        win.resizable(True, True)
        win.grab_set()
        apply_theme(win)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["info"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f"  {t('course.add_schedule')} — {code}",
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_card"], padx=24, pady=20)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        body.columnconfigure(0, weight=1)

        tk.Label(body, text=f"{t('course.course_label')} {code} — {name}",
                 font=FONTS["body_bold"], bg=c["bg_card"],
                 fg=c["accent"], anchor=anchor_start()).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        halls = []
        try:
            r = http_client.api_get("/api/halls")
            if r.status_code == 200:
                halls = r.json().get("halls", [])
        except Exception:
            pass

        if not halls:
            tk.Label(body,
                     text=t("course.no_halls_warning"),
                     font=FONTS["body_bold"], bg=c["bg_card"],
                     fg=c["error"], justify=text_justify(),
                     anchor=anchor_start()).grid(row=1, column=0, columnspan=2,
                                       sticky="ew", pady=20)
            tk.Button(body, text=t("close"), command=win.destroy,
                      bg=c["bg_light"], fg=c["text_secondary"],
                      font=FONTS["body_bold"], relief="flat",
                      cursor="hand2", padx=20, pady=8, bd=0).grid(
                row=2, column=0, columnspan=2, sticky="e", pady=10)
            return

        tk.Label(body, text=f"{t('course.hall_label')}  *", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=18).grid(row=1, column=1, sticky="e",
                                 padx=pad_x(0, 10), pady=8)
        hall_var = tk.StringVar()
        hall_combo = ttk.Combobox(body, textvariable=hall_var,
                                    state="readonly", font=FONTS["body"])
        hall_combo["values"] = [
            f"{h['hall_name']}  ({t('course.practical') if h['hall_type'] == 'practical' else t('course.theory')})"
            for h in halls
        ]
        hall_combo.grid(row=1, column=0, sticky="ew", ipady=5, pady=8)
        if halls:
            hall_combo.current(0)

        tk.Label(body, text=f"{t('day')}  *", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=18).grid(row=2, column=1, sticky="e",
                                 padx=pad_x(0, 10), pady=8)
        day_var = tk.StringVar()
        day_combo = ttk.Combobox(body, textvariable=day_var,
                                   state="readonly", font=FONTS["body"])
        day_combo["values"] = _days()
        day_combo.current(0)
        day_combo.grid(row=2, column=0, sticky="ew", ipady=5, pady=8)

        tk.Label(body, text=f"{t('start_time')}  *", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=18).grid(row=3, column=1, sticky="e",
                                 padx=pad_x(0, 10), pady=8)
        from ui.widgets.time_picker import TimePicker
        start_picker = TimePicker(body)
        start_picker.set("08:00")
        start_picker.grid(row=3, column=0, sticky="ew", pady=8)

        tk.Label(body, text=f"{t('end_time')}  *", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=18).grid(row=4, column=1, sticky="e",
                                 padx=pad_x(0, 10), pady=8)
        end_picker = TimePicker(body)
        end_picker.set("09:30")
        end_picker.grid(row=4, column=0, sticky="ew", pady=8)

        tk.Label(body,
                 text=t("course.weekly_repeat_note"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["info"], justify=text_justify(), anchor=anchor_start(),
                 wraplength=480).grid(row=5, column=0, columnspan=2,
                                       sticky="ew", pady=(10, 6))

        def save():
            hall_idx = hall_combo.current()
            if hall_idx < 0:
                messagebox.showwarning(t("warning"), t("course.select_hall"), parent=win)
                return
            day_idx = day_combo.current()
            if day_idx < 0:
                messagebox.showwarning(t("warning"), t("course.select_day"), parent=win)
                return
            stime = start_picker.get()
            etime = end_picker.get()
            if not stime or not etime:
                messagebox.showwarning(t("warning"), t("course.times_required"), parent=win)
                return
            try:
                r = http_client.api_post("/api/schedules", json_body={
                    "course_id":   cid,
                    "hall_id":     halls[hall_idx]["id"],
                    "day_of_week": day_idx,
                    "start_time":  stime,
                    "end_time":    etime,
                })
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    if hasattr(self, "_refresh_schedules"):
                        self._refresh_schedules()
                    messagebox.showinfo(t("course.added_title"),
                        t("course.schedule_added_msg"))
                else:
                    messagebox.showerror(t("error"),
                        data.get("error", t("course.operation_failed")), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.grid(row=6, column=0, columnspan=2, sticky="e", pady=(20, 0))
        tk.Button(btn_row, text=t("cancel"), command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=10, bd=0
                  ).pack(side=side_start(), padx=pad_x(8, 0))
        tk.Button(btn_row, text=f"✔  {t('course.add_schedule_save')}", command=save,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=10, bd=0
                  ).pack(side=side_start())

    def _enroll_dialog(self):
        vals = self._selected_course()
        if not vals:
            return
        cid, code, name = vals[0], vals[1], vals[2]
        c = COLORS

        win = tk.Toplevel(self.parent)
        win.title(f"{t('course.enroll_title')} — {code}")
        win.geometry("760x540")
        win.grab_set()
        win.configure(bg=c["bg_dark"])
        apply_theme(win)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["info"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=f"  {t('course.enroll_title')} — {code} : {name}",
                 font=FONTS["subtitle"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=10, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_dark"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        panes = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(panes, bg=c["bg_dark"])
        panes.add(left_frame, weight=1)

        tk.Label(left_frame, text=t("course.all_students"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"]).pack(anchor=anchor_start(), pady=(0, 6))

        search_var = tk.StringVar()
        tk.Entry(left_frame, textvariable=search_var,
                  font=FONTS["body"], bg=c["input_bg"],
                  fg=c["text_primary"], insertbackground=c["accent"],
                  relief="flat", bd=0, justify=text_justify()).pack(
            fill=tk.X, ipady=6, pady=(0, 6))
        tk.Frame(left_frame, bg=c["border_light"], height=1).pack(fill=tk.X, pady=(0, 6))

        left_inner = tk.Frame(left_frame, bg=c["border"], padx=1, pady=1)
        left_inner.pack(fill=tk.BOTH, expand=True)
        left_bg = tk.Frame(left_inner, bg=c["bg_card"])
        left_bg.pack(fill=tk.BOTH, expand=True)

        lvsb = ttk.Scrollbar(left_bg, orient=tk.VERTICAL)
        lvsb.pack(side=side_end(), fill=tk.Y)

        all_tree = create_styled_treeview(left_bg,
                                           columns=("id", "academic_id", "name"),
                                           show="headings", selectmode="extended")
        for col, h, w in [("id", t("course.col_id"), 40), ("academic_id", t("academic_id"), 110), ("name", t("course.col_name_short"), 160)]:
            all_tree.heading(col, text=h)
            all_tree.column(col, width=w, anchor="center")
        all_tree.configure(yscrollcommand=lvsb.set)
        lvsb.configure(command=all_tree.yview)
        all_tree.pack(fill=tk.BOTH, expand=True)

        right_frame = tk.Frame(panes, bg=c["bg_dark"])
        panes.add(right_frame, weight=1)

        tk.Label(right_frame, text=t("enrolled_students"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["success"]).pack(anchor=anchor_start(), pady=(0, 6))

        right_inner = tk.Frame(right_frame, bg=c["border"], padx=1, pady=1)
        right_inner.pack(fill=tk.BOTH, expand=True)
        right_bg = tk.Frame(right_inner, bg=c["bg_card"])
        right_bg.pack(fill=tk.BOTH, expand=True)

        rvsb = ttk.Scrollbar(right_bg, orient=tk.VERTICAL)
        rvsb.pack(side=side_end(), fill=tk.Y)

        enr_tree = create_styled_treeview(right_bg,
                                           columns=("enr_id", "academic_id", "name"),
                                           show="headings", selectmode="extended")
        for col, h, w in [("enr_id", t("course.col_enrollment_id"), 60), ("academic_id", t("academic_id"), 110), ("name", t("course.col_name_short"), 160)]:
            enr_tree.heading(col, text=h)
            enr_tree.column(col, width=w, anchor="center")
        enr_tree.configure(yscrollcommand=rvsb.set)
        rvsb.configure(command=enr_tree.yview)
        enr_tree.pack(fill=tk.BOTH, expand=True)

        all_students = []

        def load_students(*_):
            for r in all_tree.get_children():
                all_tree.delete(r)
            try:
                resp = http_client.api_get("/api/students",
                                     search=search_var.get(), per_page=200)
                if resp.json().get("success"):
                    all_students.clear()
                    for s in resp.json()["students"]:
                        all_students.append(s)
                        all_tree.insert("", tk.END, values=(s["id"], s["academic_id"], s["full_name"]))
            except Exception:
                pass

        def load_enrolled():
            for r in enr_tree.get_children():
                enr_tree.delete(r)
            try:
                resp = http_client.api_get("/api/enrollments",
                                     course_id=cid)
                if resp.json().get("success"):
                    for e in resp.json()["enrollments"]:
                        enr_tree.insert("", tk.END, values=(e["id"], e["academic_id"], e["student_name"]))
            except Exception:
                pass

        def enroll():
            sel = all_tree.selection()
            if not sel:
                messagebox.showwarning(t("warning"), t("course.select_students"), parent=win)
                return
            ok, fail = 0, 0
            for s in sel:
                sid = all_tree.item(s)["values"][0]
                try:
                    r = http_client.api_post("/api/enrollments",
                                       json_body={"student_id": sid, "course_id": cid})
                    if r.json().get("success"):
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
            load_enrolled()
            messagebox.showinfo(t("course.done"), f"{t('course.enrolled_ok')} {ok}  |  {t('course.enrolled_fail')} {fail}", parent=win)

        def unenroll():
            sel = enr_tree.selection()
            if not sel:
                messagebox.showwarning(t("warning"), t("course.select_enrollments"), parent=win)
                return
            if not messagebox.askyesno(t("course.confirm_title"), t("course.confirm_unenroll"), parent=win):
                return
            for s in sel:
                eid = enr_tree.item(s)["values"][0]
                try:
                    http_client.api_delete(f"/api/enrollments/{eid}")
                except Exception:
                    pass
            load_enrolled()

        search_var.trace_add("write", load_students)

        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        self._btn(btn_row, f"← {t('course.unenroll_selected')}", unenroll, c["error"]).pack(side=side_start())
        self._btn(btn_row, f"→ {t('course.enroll_selected')}", enroll, c["success"], fg=c["bg_dark"]).pack(side=side_start(), padx=pad_x(0, 8))

        load_students()
        load_enrolled()

    def _delete_schedule(self):
        sel = self.stree.selection()
        if not sel:
            messagebox.showwarning(t("warning"), t("course.select_schedule_first"))
            return
        sid = self.stree.item(sel[0])["values"][0]
        if not messagebox.askyesno(t("course.confirm_title"), t("course.confirm_delete_schedule")):
            return
        try:
            r = http_client.api_delete(f"/api/schedules/{sid}")
            if r.json().get("success"):
                self._refresh_schedules()
                messagebox.showinfo(t("course.deleted_title"), t("course.schedule_deleted"))
            else:
                messagebox.showerror(t("error"), r.json().get("error", ""))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def _course_students_dialog(self):
        vals = self._selected_course()
        if not vals:
            return
        cid, code, name = vals[0], vals[1], vals[2]
        c = COLORS

        win = tk.Toplevel(self.parent)
        win.title(f"{t('course_students')} — {code}")
        win.geometry("700x500")
        win.grab_set()
        win.configure(bg=c["bg_dark"])

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["info"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=f"  {t('course_students')}: {code} — {name}",
                 font=FONTS["subtitle"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=10, pady=12)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_dark"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        enr_frame = tk.Frame(body, bg=c["bg_dark"])
        enr_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(enr_frame, text=t("course.enrolled_in_course"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"]).pack(anchor=anchor_start(), pady=(0, 6))

        inner = tk.Frame(enr_frame, bg=c["border"], padx=1, pady=1)
        inner.pack(fill=tk.BOTH, expand=True)
        bg = tk.Frame(inner, bg=c["bg_card"])
        bg.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(bg, orient=tk.VERTICAL)
        vsb.pack(side=side_end(), fill=tk.Y)

        cols = ("enr_id", "academic_id", "student_name")
        tree = create_styled_treeview(bg, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("enr_id", t("course.col_enrollment_id"), 80), ("academic_id", t("academic_id"), 130), ("student_name", t("course.col_student_name"), 220)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=tree.yview)
        tree.pack(fill=tk.BOTH, expand=True)

        sched_label = tk.Label(body, text=t("course.work_schedule"),
                               font=FONTS["section"], bg=c["bg_dark"],
                               fg=c["warning"])
        sched_label.pack(anchor=anchor_start(), pady=(12, 4))

        sched_inner = tk.Frame(body, bg=c["border"], padx=1, pady=1)
        sched_inner.pack(fill=tk.X)
        sched_bg = tk.Frame(sched_inner, bg=c["bg_card"])
        sched_bg.pack(fill=tk.X)

        sched_cols = ("day", "hall", "start", "end")
        sched_tree = create_styled_treeview(sched_bg, columns=sched_cols, show="headings", height=4)
        for col, h, w in [("day", t("day"), 120), ("hall", t("course.col_hall"), 160), ("start", t("course.col_start"), 80), ("end", t("course.col_end"), 80)]:
            sched_tree.heading(col, text=h)
            sched_tree.column(col, width=w, anchor="center")
        sched_tree.pack(fill=tk.X)

        count_lbl = tk.Label(body, text="", font=FONTS["small"],
                             bg=c["bg_dark"], fg=c["text_muted"])
        count_lbl.pack(anchor=anchor_start(), pady=(6, 0))

        def load_data():
            for r in tree.get_children():
                tree.delete(r)
            for r in sched_tree.get_children():
                sched_tree.delete(r)

            def do():
                try:
                    resp = http_client.api_get("/api/enrollments",
                                        course_id=cid)
                    enrollments = []
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("success"):
                            enrollments = data["enrollments"]

                    def update():
                        if not win.winfo_exists():
                            return
                        for e in enrollments:
                            tree.insert("", tk.END, values=(e["id"], e["academic_id"], e["student_name"]))
                        count_lbl.config(text=f"{t('course.students_count')} {len(enrollments)}")
                    win.after(0, update)
                except Exception:
                    pass

                try:
                    resp2 = http_client.api_get("/api/schedules",
                                         course_id=cid)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        if data2.get("success"):
                            schedules = data2["schedules"]
                            days = _days()

                            def update2():
                                if not win.winfo_exists():
                                    return
                                for s in schedules:
                                    day_ar = days[s["day_of_week"]] if 0 <= s["day_of_week"] <= 6 else s.get("day_name", "")
                                    sched_tree.insert("", tk.END, values=(day_ar, s["hall_name"], s["start_time"][:5], s["end_time"][:5]))
                            win.after(0, update2)
                except Exception:
                    pass

            threading.Thread(target=do, daemon=True).start()

        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        self._btn(btn_row, f"🔄  {t('refresh')}", load_data, c["bg_light"]).pack(side=side_start())
        self._btn(btn_row, t("close"), win.destroy, c["bg_light"]).pack(side=side_end())

        load_data()
