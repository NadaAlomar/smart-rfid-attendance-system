import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
from ui import http_client
import threading
from ui.theme import COLORS, FONTS
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify, pad_x
from ui.i18n import t


class ExcelImport:
    def __init__(self, parent):
        self.parent = parent
        self._build()

    def _btn(self, parent, text, cmd, bg, fg="#f5f3ff", width=None):
        kw = dict(text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=bg, activeforeground=fg,
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=8, bd=0)
        if width:
            kw["width"] = width
        return tk.Button(parent, **kw)

    def _build(self):
        c = COLORS

        # ── Header ──
        hdr = tk.Frame(self.parent, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["warning"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=t("import.title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=8, pady=14)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        # ── Body (scrollable) ──
        body_outer = tk.Frame(self.parent, bg=c["bg_dark"])
        body_outer.pack(fill=tk.BOTH, expand=True)
        body_canvas = tk.Canvas(body_outer, bg=c["bg_dark"],
                                highlightthickness=0, bd=0)
        body_vsb = ttk.Scrollbar(body_outer, orient=tk.VERTICAL,
                                 command=body_canvas.yview)
        body_canvas.configure(yscrollcommand=body_vsb.set)
        body_vsb.pack(side=side_end(), fill=tk.Y)
        body_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body = tk.Frame(body_canvas, bg=c["bg_dark"], padx=24, pady=16)
        body_win = body_canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: body_canvas.configure(scrollregion=body_canvas.bbox("all")))
        body_canvas.bind("<Configure>",
                         lambda e: body_canvas.itemconfig(body_win, width=e.width))

        def _wheel(e): body_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        body.bind("<Enter>", lambda e: body_canvas.bind_all("<MouseWheel>", _wheel))
        body.bind("<Leave>", lambda e: body_canvas.unbind_all("<MouseWheel>"))

        # ── Import type card ──
        type_card = tk.Frame(body, bg=c["bg_card"], padx=20, pady=14)
        type_card.pack(fill=tk.X, pady=(0, 12))
        tk.Frame(type_card, bg=c["warning"], height=3).pack(fill=tk.X, pady=(0, 10))
        tk.Label(type_card, text=t("import.type_label"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"]).pack(anchor=anchor_start())

        self.import_type = tk.StringVar(value="students")
        radio_row = tk.Frame(type_card, bg=c["bg_card"])
        radio_row.pack(fill=tk.X, pady=(8, 0))

        for val, label in [
            ("full",     t("import.full")),
            ("students", t("import.students_only")),
            ("courses",  t("import.courses_only")),
        ]:
            tk.Radiobutton(
                radio_row, text=label,
                variable=self.import_type, value=val,
                bg=c["bg_card"], fg=c["text_secondary"],
                selectcolor="#ffffff",
                activebackground=c["bg_card"],
                activeforeground=c["accent"],
                font=FONTS["body"],
            ).pack(side=side_start(), padx=16)

        # ── File selection card ──
        file_card = tk.Frame(body, bg=c["bg_card"], padx=20, pady=14)
        file_card.pack(fill=tk.X, pady=(0, 12))
        tk.Frame(file_card, bg=c["info"], height=3).pack(fill=tk.X, pady=(0, 10))
        tk.Label(file_card, text=t("import.select_file"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"]).pack(anchor=anchor_start())

        file_row = tk.Frame(file_card, bg=c["bg_card"])
        file_row.pack(fill=tk.X, pady=(8, 0))
        self._btn(file_row, t("import.browse"), self._browse, c["primary"]).pack(side=side_start(), padx=pad_x(8, 0))

        self.file_path = tk.StringVar()
        tk.Entry(file_row, textvariable=self.file_path,
                  font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  state="readonly", justify=text_justify()).pack(
            side=side_start(), fill=tk.X, expand=True, ipady=8)

        # ── Progress card ──
        prog_card = tk.Frame(body, bg=c["bg_card"], padx=20, pady=12)
        prog_card.pack(fill=tk.X, pady=(0, 12))

        prog_header = tk.Frame(prog_card, bg=c["bg_card"])
        prog_header.pack(fill=tk.X)
        self.progress_lbl = tk.Label(prog_header, text=t("import.ready"),
                                      font=FONTS["small"], bg=c["bg_card"],
                                      fg=c["text_muted"])
        self.progress_lbl.pack(side=side_start())

        self.progress = ttk.Progressbar(prog_card, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(8, 0))

        # ── Action buttons ──
        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, pady=(0, 12))
        self._btn(btn_row, t("import.start_import"),
                  self._import, c["success"], fg=c["bg_dark"]).pack(side=side_start())

        # ── Log area ──
        log_card = tk.Frame(body, bg=c["bg_card"], padx=16, pady=14)
        log_card.pack(fill=tk.BOTH, expand=True)
        tk.Frame(log_card, bg=c["primary_light"], height=3).pack(fill=tk.X, pady=(0, 8))
        tk.Label(log_card, text=t("import.log_title"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"]).pack(anchor=anchor_start())

        log_inner = tk.Frame(log_card, bg=c["bg_dark"])
        log_inner.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        log_vsb = ttk.Scrollbar(log_inner, orient=tk.VERTICAL)
        log_vsb.pack(side=side_end(), fill=tk.Y)

        self.log_text = tk.Text(
            log_inner, wrap="word",
            font=FONTS["mono"],
            bg=c["bg_dark"], fg=c["text_primary"],
            insertbackground=c["accent"],
            relief="flat", bd=0,
            state="disabled",
            yscrollcommand=log_vsb.set,
        )
        log_vsb.configure(command=self.log_text.yview)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("ok",   foreground=COLORS["success"])
        self.log_text.tag_configure("err",  foreground=COLORS["error"])
        self.log_text.tag_configure("info", foreground=COLORS["info"])
        self.log_text.tag_configure("muted",foreground=COLORS["text_muted"])

    def _log(self, msg, tag=""):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n", tag if tag else None)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def _update_progress(self, value, label=""):
        self.progress["value"] = value
        if label:
            self.progress_lbl.config(text=label)

    def _browse(self):
        path = filedialog.askopenfilename(
            title=t("import.select_file_dialog"),
            filetypes=[(t("import.excel_files"), "*.xlsx *.xls")],
        )
        if path:
            self.file_path.set(path)
            self._log(f'{t("import.file_selected")} {path}', "ok")

    def _import(self):
        path = self.file_path.get()
        if not path:
            messagebox.showwarning(t("import.warning"), t("import.select_file_first"))
            return

        import_type = self.import_type.get()
        type_labels = {"students": t("import.type_students"), "courses": t("import.type_courses"), "full": t("import.type_full")}
        self._log("—" * 44, "muted")
        self._log(f'{t("import.starting")} {type_labels.get(import_type, import_type)}...', "info")
        self._update_progress(10, t("import.sending"))

        def do():
            try:
                endpoint = "/api/import/full" if import_type == "full" else "/api/import/excel"
                with open(path, "rb") as f:
                    self._update_progress(30, t("import.uploading"))
                    r = http_client.api_post_file(
                        endpoint,
                        files={"file": (path.split("/")[-1].split("\\")[-1], f,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                        data={"type": import_type} if import_type != "full" else {},
                    )
                self._update_progress(80, t("import.processing"))
                data = r.json()
                if data.get("success"):
                    self._update_progress(100, t("import.complete"))
                    if import_type == "full":
                        for section, items in data.get("data", {}).items():
                            if items:
                                created = sum(1 for d in items if d.get("action") == "created")
                                updated = sum(1 for d in items if d.get("action") == "updated")
                                self._log(f'  {section}: {t("import.added")} {created}، {t("import.updated")} {updated}')
                    else:
                        records = data.get("data", [])
                        created = sum(1 for d in records if d.get("action") == "created")
                        updated = sum(1 for d in records if d.get("action") == "updated")
                        self._log(f'  {t("import.added_count")} {created}  |  {t("import.updated_count")} {updated}')
                    self._log(f'✔ {data.get("message", t("import.import_success"))}', "ok")
                    messagebox.showinfo(t("import.import_complete_title"), data.get("message", t("import.operation_done")))
                else:
                    self._update_progress(0, t("import.import_failed"))
                    err = data.get("error", t("import.unknown_error"))
                    self._log(f'✖ {t("import.error")}: {err}', "err")
                    messagebox.showerror(t("import.import_failed"), err)
            except requests.exceptions.ConnectionError:
                self._update_progress(0, t("import.connection_error"))
                self._log(f'✖ {t("import.server_unreachable")}', "err")
                messagebox.showerror(t("import.connection_error"), t("import.server_unreachable_msg"))
            except Exception as e:
                self._update_progress(0, t("import.error"))
                self._log(f'✖ {str(e)}', "err")
                messagebox.showerror(t("import.error"), str(e))

        threading.Thread(target=do, daemon=True).start()


