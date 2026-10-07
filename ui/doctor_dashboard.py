import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start
from ui.i18n import t
from ui import http_client


class DoctorCoursesPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._build()
        self._load()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        cols = ("code", "name", "type", "students")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        for col, (h, w) in {
            "code":     (t("course_code"), 120),
            "name":     (t("course_name"), 300),
            "type":     (t("course_type"), 100),
            "students": (t("enrolled_students"), 100),
        }.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self.status = tk.Label(wrap, text="", font=FONTS["small"],
                               bg=c["bg_dark"], fg=c["text_muted"])
        self.status.pack(anchor=anchor_start(), pady=6)

    def _load(self):
        def do():
            try:
                r = http_client.api_get("/api/doctor/me/courses")
                data = r.json()
                if not data.get("success"):
                    self.parent.after(0, lambda: self.status.config(text=data.get("error", "")))
                    return
                courses = data.get("courses", [])

                def update():
                    for c in courses:
                        self.tree.insert("", tk.END, values=(
                            c.get("course_code", ""),
                            c.get("course_name", ""),
                            c.get("course_type", ""),
                            c.get("enrollment_count", 0),
                        ))
                    self.status.config(text=f"{len(courses)} courses")

                self.parent.after(0, update)
            except Exception as e:
                self.parent.after(0, lambda: self.status.config(text=str(e)))
        threading.Thread(target=do, daemon=True).start()


class DoctorStudentsPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._build()
        self._load()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        search_bar = tk.Frame(wrap, bg=c["bg_dark"])
        search_bar.pack(fill=tk.X, pady=(0, 8))
        tk.Label(search_bar, text=t("doctor_portal.search_student"),
                 font=FONTS["small_bold"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(0, 6))
        self.search_var = tk.StringVar()
        tk.Entry(search_bar, textvariable=self.search_var,
                 font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                 insertbackground=c["accent"], relief="flat", bd=0,
                 width=25).pack(side=side_start(), ipady=5)
        tk.Button(search_bar, text=t("search"), command=self._load,
                  bg=c["primary"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=5, bd=0
                  ).pack(side=side_start(), padx=6)

        cols = ("academic_id", "name", "branch")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        for col, (h, w) in {
            "academic_id": (t("student_id"), 140),
            "name":        (t("full_name"), 300),
            "branch":      (t("branch"), 120),
        }.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=side_start(), fill=tk.BOTH, expand=True)

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        q = self.search_var.get().strip()

        def do():
            try:
                r = http_client.api_get("/api/doctor/me/students", q=q)
                data = r.json()
                students = data.get("students", [])

                def update():
                    for s in students:
                        self.tree.insert("", tk.END, values=(
                            s.get("academic_id", ""),
                            s.get("full_name", ""),
                            s.get("branch_id", ""),
                        ))
                self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
