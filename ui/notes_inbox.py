import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start
from ui.i18n import t
from ui import http_client


class NotesInboxPanel:
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
        tk.Button(toolbar, text=t("refresh"), command=self._load,
                  bg=c["primary"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start())

        cols = ("doctor", "student", "course", "severity", "note", "date")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        for col, (h, w) in {
            "doctor":   (t("doctor"), 150),
            "student":  (t("student"), 150),
            "course":   (t("course"), 150),
            "severity": (t("notes.severity"), 80),
            "note":     (t("doctor_portal.my_notes"), 250),
            "date":     (t("time"), 130),
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

        tk.Button(wrap, text=t("notes.mark_read"), command=self._mark_read,
                  bg=c["success"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(anchor=anchor_start(), pady=(8, 0))

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        def do():
            try:
                r = http_client.api_get("/api/doctor-notes/unread")
                data = r.json()
                notes = data.get("notes", [])

                def update():
                    for n in notes:
                        self.tree.insert("", tk.END, values=(
                            n.get("doctor_name", ""),
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

    def _mark_read(self):
        sel = self.tree.selection()
        if not sel:
            return
        nid = sel[0]

        def do():
            try:
                http_client.api_post(f"/api/doctor-notes/{nid}/mark-read")
                self.parent.after(0, self._load)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
