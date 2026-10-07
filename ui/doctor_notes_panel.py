import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start
from ui.i18n import t
from ui import http_client


class DoctorNotesPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._courses = []
        self._students = []
        self._build()
        self._load_courses()
        self._load()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 8))

        tk.Button(toolbar, text=f"+ {t('doctor_portal.add_note')}",
                  command=self._add_note_dialog,
                  bg=c["primary"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start(), padx=(0, 6))

        tk.Button(toolbar, text=t("refresh"), command=self._load,
                  bg=c["bg_light"], fg=c["text_primary"], font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(side=side_start())

        cols = ("student", "course", "severity", "note", "date")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        for col, (h, w) in {
            "student":  (t("full_name"), 180),
            "course":   (t("course"), 180),
            "severity": (t("notes.severity"), 80),
            "note":     (t("doctor_portal.my_notes"), 280),
            "date":     (t("time"), 140),
        }.items():
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self.tree.tag_configure("info", foreground=c["info"])
        self.tree.tag_configure("warning", foreground=c["warning"])
        self.tree.tag_configure("critical", foreground=c["error"])

        tk.Button(wrap, text=t("delete"), command=self._delete_selected,
                  bg=c["error"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=5, bd=0
                  ).pack(anchor=anchor_start(), pady=(8, 0))

    def _load_courses(self):
        def do():
            try:
                r = http_client.api_get("/api/doctor/me/courses")
                data = r.json()
                self._courses = data.get("courses", [])
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        def do():
            try:
                r = http_client.api_get("/api/doctor/me/notes")
                data = r.json()
                notes = data.get("notes", [])

                def update():
                    for n in notes:
                        self.tree.insert("", tk.END, values=(
                            n.get("student_name", ""),
                            n.get("course_name", ""),
                            t(f"notes.severity_{n.get('severity', 'info')}"),
                            n.get("note", ""),
                            (n.get("created_at") or "")[:16],
                        ), tags=(n.get("severity", "info"),), iid=str(n["id"]))
                self.parent.after(0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _add_note_dialog(self):
        dlg = tk.Toplevel(self.parent)
        dlg.title(t("doctor_portal.add_note"))
        dlg.geometry("450x380")
        dlg.configure(bg=COLORS["bg_card"])
        dlg.transient(self.parent)
        dlg.grab_set()

        c = COLORS
        body = tk.Frame(dlg, bg=c["bg_card"], padx=24, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text=t("full_name"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start())
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(body, textvariable=student_var, state="readonly")
        student_combo.pack(fill=tk.X, pady=(2, 12))

        def load_students():
            try:
                r = http_client.api_get("/api/doctor/me/students")
                data = r.json()
                self._students = data.get("students", [])
                names = [f"{s['full_name']} ({s['academic_id']})" for s in self._students]
                student_combo.configure(values=names)
                if names:
                    student_combo.current(0)
            except Exception:
                pass
        threading.Thread(target=load_students, daemon=True).start()

        tk.Label(body, text=t("course"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start())
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(body, textvariable=course_var, state="readonly")
        course_combo.pack(fill=tk.X, pady=(2, 12))
        course_combo.configure(values=[""] + [f"{c['course_name']} ({c['course_code']})" for c in self._courses])

        tk.Label(body, text=t("notes.severity"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start())
        severity_var = tk.StringVar(value="info")
        ttk.Combobox(body, textvariable=severity_var,
                     values=["info", "warning", "critical"], state="readonly",
                     width=12).pack(fill=tk.X, pady=(2, 12))

        tk.Label(body, text=t("doctor_portal.add_note"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor=anchor_start())
        note_text = tk.Text(body, height=4, font=FONTS["body"], bg=c["input_bg"],
                            fg=c["text_primary"], insertbackground=c["accent"],
                            relief="flat", bd=0)
        note_text.pack(fill=tk.X, pady=(2, 12))

        def submit():
            idx = student_combo.current()
            if idx < 0 or idx >= len(self._students):
                messagebox.showwarning(t("warning"), t("alert.select_student_first"))
                return
            student_id = self._students[idx]["id"]
            cidx = course_combo.current()
            course_id = self._courses[cidx]["id"] if cidx > 0 and cidx <= len(self._courses) else None
            note = note_text.get("1.0", tk.END).strip()
            if not note:
                return

            def do():
                try:
                    r = http_client.api_post("/api/doctor/me/notes", {
                        "student_id": student_id,
                        "course_id": course_id,
                        "note": note,
                        "severity": severity_var.get(),
                    })
                    data = r.json()
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
                  ).pack()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        nid = sel[0]
        if not messagebox.askyesno(t("confirm_delete"), t("confirm_delete_msg")):
            return

        def do():
            try:
                http_client.api_delete(f"/api/doctor/me/notes/{nid}")
                self.parent.after(0, self._load)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
