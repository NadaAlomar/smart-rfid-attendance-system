import tkinter as tk
from tkinter import ttk, messagebox
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui import http_client
import threading



class BackupPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        c = COLORS
        wrap = tk.Frame(parent, bg=c["bg_dark"], padx=24, pady=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        info = tk.Label(wrap, text=t("backup.restore_note"),
                        font=FONTS["small"], bg=c["bg_dark"], fg=c["warning"], anchor=anchor_start(),
                        justify=text_justify(), wraplength=900)
        info.pack(fill=tk.X, pady=(0, 10))

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Button(toolbar, text=t("backup.create_btn"), command=self._create_backup,
                  bg=c["primary"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=16, pady=8, bd=0).pack(side=side_start(), padx=(0, 8))
        tk.Button(toolbar, text=t("backup.refresh_btn"), command=self._load,
                  bg=c["bg_light"], fg=c["text_primary"], font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0).pack(side=side_start())

        tree_frame = tk.Frame(wrap, bg=c["bg_dark"])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("filename", "size", "date", "action")
        self.tree = create_styled_treeview(tree_frame, columns=cols, show="headings", height=18)
        headers = {"filename": (t("backup.col_filename"), 280, anchor_start()), "size": (t("backup.col_size"), 120, "center"),
                   "date": (t("backup.col_date"), 200, "center"), "action": ("", 100, "center")}
        for col, (h, w, anch) in headers.items():
            self.tree.heading(col, text=h, anchor=anch)
            self.tree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._load()

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        def do():
            try:
                resp = http_client.api_get("/api/backup/list")
                data = resp.json()
            except Exception:
                return
            for b in data.get("backups", []):
                size_kb = b["size"] / 1024
                self.tree.insert("", tk.END, values=(
                    b["filename"],
                    f"{size_kb:.1f} KB",
                    b["date"][:19].replace("T", " "),
                    t("restore"),
                ))
        threading.Thread(target=do, daemon=True).start()

    def _create_backup(self):
        def do():
            try:
                resp = http_client.api_post("/api/backup/create")
                data = resp.json()
                if data.get("success"):
                    messagebox.showinfo(t("backup.success"), f'{t("backup.created_msg")} {data.get("filename", "")}')
                    self._load()
                else:
                    messagebox.showerror(t("error"), data.get("error", t("backup.failed")))
            except Exception as ex:
                messagebox.showerror(t("error"), str(ex))
        threading.Thread(target=do, daemon=True).start()

    def _restore(self, filename):
        if not messagebox.askyesno(t("backup.confirm_title"),
                t("restore_warning")):
            return
        def do():
            try:
                resp = http_client.api_post("/api/backup/restore", json_body={"filename": filename})
                data = resp.json()
                if data.get("success"):
                    messagebox.showinfo(t("backup.success"),
                        t("backup.restored_msg"))
                    self._load()
                else:
                    messagebox.showerror(t("error"), data.get("error", t("backup.failed")))
            except Exception as ex:
                messagebox.showerror(t("error"), str(ex))
        threading.Thread(target=do, daemon=True).start()
