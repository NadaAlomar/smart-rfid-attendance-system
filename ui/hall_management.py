import tkinter as tk
from tkinter import ttk, messagebox
from ui import http_client
import threading
from ui.theme import COLORS, FONTS, apply_theme, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t


class HallManagement:
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

    def _entry(self, parent, var=None, width=28, justify=text_justify()):
        c = COLORS
        kw = dict(font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  justify=justify, width=width)
        if var:
            kw["textvariable"] = var
        return tk.Entry(parent, **kw)

    def _row_entry(self, parent, label_text, var=None, width=28):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=(8, 0))
        kw = dict(font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  justify=text_justify())
        if var:
            kw["textvariable"] = var
        e = tk.Entry(row, **kw)
        e.pack(side=side_end(), fill=tk.X, expand=True, ipady=8, padx=(0, 8))
        return e

    def _row_widget(self, parent, label_text, widget):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=(8, 0))
        widget.pack(in_=row, side=side_end(), fill=tk.X, expand=True,
                    ipady=7, padx=(0, 8))
        return widget

    def _field(self, parent, label_text, widget):
        c = COLORS
        row = tk.Frame(parent, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=label_text, font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start(), width=18).pack(side=side_start(), padx=(8, 0))
        widget.pack(in_=row, side=side_end(), fill=tk.X, expand=True,
                    ipady=7, padx=(0, 8))

    def _make_dialog(self, title, width=420, height=280):
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
        tk.Frame(hdr, bg=c["accent2"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=t("hall.page_title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=8, pady=14)

        btn_area = tk.Frame(hdr, bg=c["bg_medium"])
        btn_area.pack(side=side_start(), padx=16, pady=10)
        self._btn(btn_area, t("hall.add_hall"), self._add_hall_dialog, c["success"], fg=c["bg_dark"]).pack(side=side_start())
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        footer = tk.Frame(self.parent, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 8))
        tk.Frame(self.parent, bg=c["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        self._btn(footer, t("hall.refresh"), self.refresh, c["bg_light"]).pack(side=side_end(), padx=(0, 6))

        nb = ttk.Notebook(self.parent)
        nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        tab1 = tk.Frame(nb, bg=c["bg_dark"])
        nb.add(tab1, text=t("hall.halls_tab"))

        t1_area = tk.Frame(tab1, bg=c["bg_dark"], padx=8, pady=8)
        t1_area.pack(fill=tk.BOTH, expand=True)

        inner1, vsb1 = self._tree_frame(t1_area)

        cols = ("id", "hall_name", "hall_type")
        self.hall_tree = create_styled_treeview(inner1, columns=cols,
                                                 show="headings", selectmode="browse")
        for col, h, w in [("id", t("hall.col_id"), 55), ("hall_name", t("hall.col_hall_name"), 300), ("hall_type", t("hall.col_type"), 120)]:
            self.hall_tree.heading(col, text=h)
            self.hall_tree.column(col, width=w, anchor="center", minwidth=40)

        self.hall_tree.configure(yscrollcommand=vsb1.set)
        vsb1.configure(command=self.hall_tree.yview)
        self.hall_tree.pack(fill=tk.BOTH, expand=True)

        ab1 = tk.Frame(tab1, bg=c["bg_medium"], padx=10, pady=8)
        ab1.pack(fill=tk.X)

        self.hall_status = tk.Label(ab1, text="", font=FONTS["small"],
                                     bg=c["bg_medium"], fg=c["text_muted"])
        self.hall_status.pack(side=side_start(), padx=10)

        self._btn(ab1, t("hall.register_rfid"), self._add_device_dialog, c["info"]).pack(side=side_end(), padx=(0, 8))
        self._btn(ab1, t("hall.delete_hall_btn"),        self._delete_hall,       c["error"]).pack(side=side_end())

        tab2 = tk.Frame(nb, bg=c["bg_dark"])
        nb.add(tab2, text=t("hall.rfid_devices_tab"))

        t2_area = tk.Frame(tab2, bg=c["bg_dark"], padx=8, pady=8)
        t2_area.pack(fill=tk.BOTH, expand=True)

        inner2, vsb2 = self._tree_frame(t2_area)

        dcols = ("id", "device_id", "hall_name", "is_active", "last_seen", "token")
        self.dev_tree = create_styled_treeview(inner2, columns=dcols,
                                                show="headings", selectmode="browse")
        dhdrs = {
            "id":        (t("hall.col_id"),         50),
            "device_id": (t("hall.col_device_id"),   130),
            "hall_name": (t("hall.col_hall"),        140),
            "is_active": (t("hall.col_active"),       65),
            "last_seen": (t("hall.col_last_seen"),    160),
            "token":     (t("hall.col_token"),        260),
        }
        for col, (h, w) in dhdrs.items():
            self.dev_tree.heading(col, text=h)
            self.dev_tree.column(col, width=w, anchor="center", minwidth=40)

        self.dev_tree.configure(yscrollcommand=vsb2.set)
        vsb2.configure(command=self.dev_tree.yview)
        self.dev_tree.pack(fill=tk.BOTH, expand=True)

        ab2 = tk.Frame(tab2, bg=c["bg_medium"], padx=10, pady=8)
        ab2.pack(fill=tk.X)

        self.dev_status = tk.Label(ab2, text="", font=FONTS["small"],
                                    bg=c["bg_medium"], fg=c["text_muted"])
        self.dev_status.pack(side=side_start(), padx=10)

        self._btn(ab2, t("hall.refresh"),   self._refresh_devices, c["bg_light"]).pack(side=side_end(), padx=(0, 8))
        self._btn(ab2, t("hall.copy_token_btn"), self._copy_token,     c["primary"]).pack(side=side_end())

    def refresh(self):
        for r in self.hall_tree.get_children():
            self.hall_tree.delete(r)
        self.hall_status.config(text=t("hall.loading"))

        def do():
            try:
                r = http_client.api_get("/api/halls")
                data = r.json()
                if data.get("success"):
                    halls = data["halls"]
                    for h in halls:
                        type_ar = t("hall.type_practical") if h["hall_type"] == "practical" else t("hall.type_theory")
                        self.hall_tree.insert("", tk.END,
                                              values=(h["id"], h["hall_name"], type_ar))
                    self.hall_status.config(text=f'{t("hall.halls_count")} {len(halls)}')
            except Exception as e:
                self.hall_status.config(text=f'{t("hall.error_with_msg")} {e}')

        threading.Thread(target=do, daemon=True).start()
        self._refresh_devices()

    def _refresh_devices(self):
        for r in self.dev_tree.get_children():
            self.dev_tree.delete(r)
        self.dev_status.config(text=t("hall.loading"))

        def do():
            try:
                r = http_client.api_get("/api/devices")
                data = r.json()
                if data.get("success"):
                    devs = data["devices"]
                    for d in devs:
                        tag = "active" if d["is_active"] else "inactive"
                        self.dev_tree.insert("", tk.END, values=(
                            d["id"], d["device_id"], d["hall_name"],
                            t("hall.yes_active") if d["is_active"] else t("hall.no_active"),
                            d["last_seen"] or t("hall.never_connected"),
                            d["device_token"],
                        ), tags=(tag,))
                    self.dev_tree.tag_configure("active",   foreground=COLORS["success"])
                    self.dev_tree.tag_configure("inactive", foreground=COLORS["text_muted"])
                    self.dev_status.config(text=f'{t("hall.devices_count")} {len(devs)}')
            except Exception as e:
                self.dev_status.config(text=f'{t("hall.error_with_msg")} {e}')

        threading.Thread(target=do, daemon=True).start()

    def _add_hall_dialog(self):
        c = COLORS
        win = tk.Toplevel(self.parent)
        win.title(t("hall.add_new_hall_title"))
        win.geometry("500x360")
        win.minsize(480, 340)
        win.configure(bg=c["bg_dark"])
        win.resizable(True, True)
        win.grab_set()
        apply_theme(win)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'  {t("hall.add_new_hall_title")}',
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_card"], padx=24, pady=20)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        body.columnconfigure(0, weight=1)

        tk.Label(body, text=t("hall.hall_name_required"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=14).grid(row=0, column=1, sticky=anchor_start(),
                                 padx=(0, 10), pady=8)
        name_var = tk.StringVar()
        name_entry = tk.Entry(body, textvariable=name_var,
                               font=FONTS["body"], bg=c["input_bg"],
                               fg=c["text_primary"],
                               insertbackground=c["accent"],
                               relief="flat", bd=0, justify=text_justify())
        name_entry.grid(row=0, column=0, sticky="ew", ipady=9, pady=8)
        name_entry.focus_set()

        tk.Label(body, text=t("hall.hall_type_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=14).grid(row=1, column=1, sticky=anchor_start(),
                                 padx=(0, 10), pady=8)
        type_var = tk.StringVar(value="theory")
        radio_frame = tk.Frame(body, bg=c["bg_card"])
        radio_frame.grid(row=1, column=0, sticky=anchor_start(), pady=8)
        for val, lbl in [("practical", t("hall.practical_lab")),
                          ("theory", t("hall.theory_hall"))]:
            tk.Radiobutton(radio_frame, text=lbl, variable=type_var,
                           value=val,
                           bg=c["bg_card"], fg=c["text_primary"],
                           selectcolor="#ffffff",
                           activebackground=c["bg_card"],
                           activeforeground=c["accent"],
                           font=FONTS["body"]).pack(side=side_start(), padx=10)

        def save():
            name = name_var.get().strip()
            if not name:
                name_entry.config(bg=c["error"], fg="white")
                name_entry.after(2000, lambda: name_entry.config(
                    bg=c["input_bg"], fg=c["text_primary"]))
                messagebox.showerror(t("hall.error"), t("hall.hall_name_required_msg"), parent=win)
                return
            try:
                r = http_client.api_post("/api/halls",
                                           json_body={"hall_name": name,
                                                  "hall_type": type_var.get()})
                data = r.json()
                if data.get("success"):
                    win.destroy()
                    self.refresh()
                    messagebox.showinfo(t("hall.added_success_title"),
                        t("hall.added_success_msg"))
                else:
                    messagebox.showerror(t("hall.error"),
                        data.get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("hall.error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.grid(row=2, column=0, columnspan=2, sticky=anchor_start(), pady=(20, 0))

        tk.Button(btn_row, text=t("hall.cancel"), command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=10, bd=0
                  ).pack(side=side_start(), padx=(8, 0))
        tk.Button(btn_row, text=t("hall.save_hall"), command=save,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=10, bd=0
                  ).pack(side=side_start())

    def _delete_hall(self):
        sel = self.hall_tree.selection()
        if not sel:
            messagebox.showwarning(t("hall.warning"), t("hall.select_hall_first"))
            return
        vals = self.hall_tree.item(sel[0])["values"]
        if not messagebox.askyesno(t("hall.confirm_delete"), f'{t("hall.confirm_delete_hall")} \'{vals[1]}\'؟'):
            return
        try:
            r = http_client.api_delete(f"/api/halls/{vals[0]}")
            if r.json().get("success"):
                self.refresh()
                messagebox.showinfo(t("hall.deleted_title"), t("hall.deleted_msg"))
            else:
                messagebox.showerror(t("hall.error"), r.json().get("error", ""))
        except Exception as e:
            messagebox.showerror(t("hall.error"), str(e))

    def _add_device_dialog(self):
        c = COLORS
        win = tk.Toplevel(self.parent)
        win.title(t("hall.register_new_rfid_title"))
        win.geometry("520x360")
        win.minsize(480, 340)
        win.configure(bg=c["bg_dark"])
        win.resizable(True, True)
        win.grab_set()
        apply_theme(win)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["info"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'  {t("hall.register_new_rfid_title")}',
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_card"], padx=24, pady=22)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        body.columnconfigure(0, weight=1)

        halls = []
        try:
            r = http_client.api_get("/api/halls")
            if r.status_code == 200:
                halls = r.json().get("halls", [])
        except Exception:
            pass

        if not halls:
            tk.Label(body,
                     text=t("hall.no_halls_msg"),
                     font=FONTS["body_bold"], bg=c["bg_card"],
                     fg=c["error"], justify=text_justify(),
                     anchor=anchor_start()).grid(row=0, column=0, columnspan=2,
                                       sticky="ew", pady=20)
            tk.Button(body, text=t("hall.close"), command=win.destroy,
                      bg=c["bg_light"], fg=c["text_secondary"],
                      font=FONTS["body_bold"], relief="flat",
                      cursor="hand2", padx=20, pady=8, bd=0
                      ).grid(row=1, column=0, columnspan=2,
                              sticky=anchor_start(), pady=10)
            return

        tk.Label(body, text=t("hall.device_id_required"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=14).grid(row=0, column=1, sticky=anchor_start(),
                                 padx=(0, 10), pady=10)
        did_var = tk.StringVar()
        did_entry = tk.Entry(body, textvariable=did_var,
                              font=FONTS["body"], bg=c["input_bg"],
                              fg=c["text_primary"],
                              insertbackground=c["accent"],
                              relief="flat", bd=0, justify=text_justify())
        did_entry.grid(row=0, column=0, sticky="ew", ipady=9, pady=10)
        did_entry.focus_set()

        tk.Label(body, text=t("hall.device_id_example"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"], anchor=anchor_start()).grid(
            row=1, column=0, columnspan=2, sticky=anchor_start(), pady=(0, 6))

        tk.Label(body, text=t("hall.hall_required"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=14).grid(row=2, column=1, sticky=anchor_start(),
                                 padx=(0, 10), pady=10)
        hall_var = tk.StringVar()
        hall_combo = ttk.Combobox(body, textvariable=hall_var,
                                    state="readonly", font=FONTS["body"])
        hall_combo["values"] = [
            f"{h['hall_name']}  ({t('hall.type_practical') if h['hall_type'] == 'practical' else t('hall.type_theory')})"
            for h in halls
        ]
        hall_combo.current(0)
        hall_combo.grid(row=2, column=0, sticky="ew", ipady=6, pady=10)

        def save():
            did = did_var.get().strip().upper()
            if not did:
                did_entry.config(bg=c["error"], fg="white")
                did_entry.after(2000, lambda: did_entry.config(
                    bg=c["input_bg"], fg=c["text_primary"]))
                messagebox.showerror(t("hall.error"), t("hall.device_id_required_msg"), parent=win)
                return
            hall_idx = hall_combo.current()
            if hall_idx < 0:
                messagebox.showerror(t("hall.error"), t("hall.select_hall"), parent=win)
                return
            hall_id = halls[hall_idx]["id"]
            try:
                r = http_client.api_post("/api/devices",
                                           json_body={"device_id": did,
                                                  "hall_id": hall_id})
                data = r.json()
                if data.get("success"):
                    token = data.get("device_token", "")
                    self._refresh_devices()
                    self._show_token_dialog(did, token)
                    win.destroy()
                else:
                    messagebox.showerror(t("hall.error"),
                        data.get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("hall.error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_card"])
        btn_row.grid(row=3, column=0, columnspan=2, sticky=anchor_start(), pady=(20, 0))

        tk.Button(btn_row, text=t("hall.close"), command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=10, bd=0
                  ).pack(side=side_start(), padx=(8, 0))

        tk.Button(btn_row, text=t("hall.register_device_btn"), command=save,
                  bg=c["info"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=20, pady=10, bd=0
                  ).pack(side=side_start())

    def _show_token_dialog(self, device_id, token):
        c = COLORS
        win = tk.Toplevel(self.parent)
        win.title(t("hall.device_registered_title"))
        win.geometry("560x340")
        win.minsize(500, 320)
        win.configure(bg=c["bg_dark"])
        win.grab_set()
        win.transient(self.parent)

        hdr = tk.Frame(win, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=f'  {t("hall.device_registered_title")}',
                 font=FONTS["section"], bg=c["bg_medium"],
                 fg=c["success"]).pack(side=side_start(), padx=14, pady=12)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=c["bg_dark"], padx=24, pady=18)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text=f'{t("hall.device_label")} {device_id}',
                 font=FONTS["body_bold"], bg=c["bg_dark"],
                 fg=c["accent"], anchor=anchor_start()).pack(fill=tk.X, pady=(0, 12))

        tk.Label(body,
                 text=t("hall.copy_token_instruction"),
                 font=FONTS["body"], bg=c["bg_dark"],
                 fg=c["text_secondary"], anchor=anchor_start()).pack(fill=tk.X, pady=(0, 8))

        token_var = tk.StringVar(value=token)
        token_entry = tk.Entry(body, textvariable=token_var,
                                font=FONTS["mono_large"],
                                bg=c["bg_card"], fg=c["accent"],
                                insertbackground=c["accent"],
                                relief="flat", bd=0, justify="center",
                                state="normal", readonlybackground=c["bg_card"])
        token_entry.pack(fill=tk.X, ipady=14, pady=(0, 8))
        token_entry.select_range(0, tk.END)
        token_entry.focus_set()

        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(token)
            self.parent.update()
        except Exception:
            pass

        status = tk.Label(body,
                           text=t("hall.token_copied"),
                           font=FONTS["small_bold"], bg=c["bg_dark"],
                           fg=c["success"], anchor=anchor_start())
        status.pack(fill=tk.X, pady=(0, 12))

        def copy_again():
            try:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(token)
                self.parent.update()
                status.config(text=t("hall.copied_again"),
                              fg=c["success"])
            except Exception as e:
                status.config(text=f'{t("hall.error_with_msg")} {e}', fg=c["error"])

        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(fill=tk.X, pady=(8, 0))

        tk.Button(btn_row, text=t("hall.copy_token_btn"),
                  command=copy_again,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  activeforeground="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=10, bd=0
                  ).pack(side=side_start(), padx=(8, 0))

        tk.Button(btn_row, text=t("hall.close"),
                  command=win.destroy,
                  bg=c["bg_light"], fg=c["text_secondary"],
                  activebackground=c["bg_medium"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=10, bd=0
                  ).pack(side=side_start())

    def _copy_token(self):
        sel = self.dev_tree.selection()
        if not sel:
            messagebox.showwarning(t("hall.warning"), t("hall.select_device_first"))
            return
        vals = self.dev_tree.item(sel[0])["values"]
        token = vals[-1] if vals else ""
        if not token:
            messagebox.showwarning(t("hall.warning"), t("hall.no_token"))
            return
        device_id = vals[1] if len(vals) > 1 else ""
        self._show_token_dialog(device_id, str(token))
