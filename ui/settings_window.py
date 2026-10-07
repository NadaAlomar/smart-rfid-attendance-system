import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
import threading
from ui import http_client
import config
from ui.theme import COLORS, FONTS, create_styled_treeview, safe_after
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui import client_time
from ui.widgets.date_picker import DatePicker


class SettingsWindow:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self._build()

    def _build(self):
        c = COLORS

        canvas = tk.Canvas(self.parent, bg=c["bg_dark"],
                            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self.parent, orient=tk.VERTICAL,
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        wrap = tk.Frame(canvas, bg=c["bg_dark"], padx=28, pady=20)
        win_id = canvas.create_window((0, 0), window=wrap, anchor="nw")
        wrap.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(win_id, width=e.width))

        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        wrap.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        wrap.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self._section(wrap, t("settings.sys_info"))
        info_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        info_card.pack(fill=tk.X, pady=(0, 14))

        info_items = [
            (t("settings.sys_name"), "AUST Attendance System"),
            (t("settings.version"), "2.0.0"),
            (t("settings.database"), str(config.DATABASE_PATH)),
            (t("settings.server_address"), f"{config.SERVER_HOST}:{config.SERVER_PORT}"),
            (t("settings.rfid_mode"), getattr(config, "RFID_MODE", "http")),
            (t("settings.serial_port"), getattr(config, "SERIAL_PORT", "—") or "—"),
            (t("settings.current_user"), self.user.username if self.user else "—"),
            (t("settings.role"), self.user.role if self.user else "—"),
        ]
        for label, value in info_items:
            row = tk.Frame(info_card, bg=c["bg_card"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"],
                     width=20, anchor=anchor_start()).pack(side=side_start())
            tk.Label(row, text=str(value), font=FONTS["body"],
                     bg=c["bg_card"], fg=c["text_primary"],
                     anchor=anchor_start()).pack(side=side_start(), padx=(0, 12))

        self._section(wrap, t("settings.rfid_connection"))
        rfid_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        rfid_card.pack(fill=tk.X, pady=(0, 14))

        rrow = tk.Frame(rfid_card, bg=c["bg_card"])
        rrow.pack(fill=tk.X, pady=4)
        tk.Label(rrow, text=t("settings.rfid_mode_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"],
                 width=20, anchor=anchor_start()).pack(side=side_start())
        self.rfid_mode_var = tk.StringVar(value=getattr(config, "RFID_MODE", "http"))
        for text, val in [(t("settings.http_server"), "http"), (t("settings.serial_usb"), "serial")]:
            tk.Radiobutton(rrow, text=text, variable=self.rfid_mode_var,
                           value=val, font=FONTS["body"],
                           bg=c["bg_card"], fg=c["text_primary"],
                           selectcolor="#ffffff",
                           activebackground=c["bg_card"]
                           ).pack(side=side_start(), padx=8)

        prow = tk.Frame(rfid_card, bg=c["bg_card"])
        prow.pack(fill=tk.X, pady=4)
        tk.Label(prow, text=t("settings.serial_port_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"],
                 width=20, anchor=anchor_start()).pack(side=side_start())
        self.port_var = tk.StringVar(value=getattr(config, "SERIAL_PORT", "") or "")
        port_entry = tk.Entry(prow, textvariable=self.port_var,
                               font=FONTS["body"], bg=c["input_bg"],
                               fg=c["text_primary"],
                               insertbackground=c["accent"],
                               relief="flat", bd=0, justify="center", width=12)
        port_entry.pack(side=side_start(), padx=(0, 12), ipady=6)
        tk.Label(prow, text=t("settings.port_example"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=8)

        self._section(wrap, t("settings.session_settings"))
        sess_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        sess_card.pack(fill=tk.X, pady=(0, 14))

        srow = tk.Frame(sess_card, bg=c["bg_card"])
        srow.pack(fill=tk.X, pady=4)
        tk.Label(srow, text=t("settings.timeout_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"],
                 width=28, anchor=anchor_start()).pack(side=side_start())
        self.timeout_var = tk.StringVar(value="15")
        self.timeout_entry = tk.Entry(srow, textvariable=self.timeout_var,
                                       font=FONTS["body"], bg=c["input_bg"],
                                       fg=c["text_primary"],
                                       insertbackground=c["accent"],
                                       relief="flat", bd=0, justify="center", width=8)
        self.timeout_entry.pack(side=side_start(), padx=(0, 12), ipady=6)
        tk.Label(srow, text=t("settings.timeout_range"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=8)

        tk.Button(sess_card, text=t("settings.save_session_btn"),
                  command=self._save_session_settings,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_start(), pady=(8, 0))

        self._load_session_settings()

        self._section(wrap, t("settings.network_settings"))
        net_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        net_card.pack(fill=tk.X, pady=(0, 14))

        for label, var_name, default in [
            (t("settings.server_addr_label"), "host_var", config.SERVER_HOST),
            (t("settings.server_port_label"), "sport_var", str(config.SERVER_PORT)),
        ]:
            row = tk.Frame(net_card, bg=c["bg_card"])
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"],
                     width=20, anchor=anchor_start()).pack(side=side_start())
            var = tk.StringVar(value=str(default))
            setattr(self, var_name, var)
            e = tk.Entry(row, textvariable=var, font=FONTS["body"],
                          bg=c["input_bg"], fg=c["text_primary"],
                          insertbackground=c["accent"],
                          relief="flat", bd=0, justify="center", width=18)
            e.pack(side=side_start(), padx=(0, 12), ipady=6)

        self._section(wrap, t("settings.alert_thresholds"))
        alert_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        alert_card.pack(fill=tk.X, pady=(0, 14))

        self.threshold_vars = {}
        for label, key, default in [
            (t("settings.absence_threshold"), "absences", 4),
            (t("settings.low_pct_threshold"), "low_pct", 25),
        ]:
            row = tk.Frame(alert_card, bg=c["bg_card"])
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, font=FONTS["small_bold"],
                     bg=c["bg_card"], fg=c["text_muted"],
                     width=20, anchor=anchor_start()).pack(side=side_start())
            var = tk.StringVar(value=str(default))
            self.threshold_vars[key] = var
            tk.Entry(row, textvariable=var, font=FONTS["body"],
                     bg=c["input_bg"], fg=c["text_primary"],
                     insertbackground=c["accent"],
                     relief="flat", bd=0, justify="center", width=8
                     ).pack(side=side_start(), padx=(0, 12), ipady=6)

        self._section(wrap, t("settings.holiday_calendar"))

        info_box = tk.Frame(wrap, bg=c["bg_card"], padx=14, pady=10)
        info_box.pack(fill=tk.X)
        tk.Label(info_box,
                 text=t("settings.holiday_info"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_secondary"], justify=text_justify(),
                 anchor=anchor_start()).pack(anchor=anchor_start())

        add_card = tk.Frame(wrap, bg=c["bg_card"], padx=20, pady=14)
        add_card.pack(fill=tk.X, pady=(8, 14))

        tk.Label(add_card, text=t("settings.add_new_holiday"),
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(0, 8))

        h_form = tk.Frame(add_card, bg=c["bg_card"])
        h_form.pack(fill=tk.X)
        h_form.columnconfigure(0, weight=1)
        h_form.columnconfigure(2, weight=1)

        tk.Label(h_form, text=t("settings.name_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=12).grid(row=0, column=3, sticky=anchor_start(),
                                 padx=(0, 8), pady=4)
        self.h_name_var = tk.StringVar()
        tk.Entry(h_form, textvariable=self.h_name_var,
                  font=FONTS["body"], bg=c["input_bg"],
                  fg=c["text_primary"], insertbackground=c["accent"],
                  relief="flat", bd=0, justify=text_justify()
                  ).grid(row=0, column=2, sticky="ew", ipady=6, pady=4)

        tk.Label(h_form, text=t("settings.type_label"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=8).grid(row=0, column=1, sticky=anchor_start(),
                                padx=(8, 8), pady=4)
        self.h_type_var = tk.StringVar(value="holiday")
        type_combo = ttk.Combobox(h_form, textvariable=self.h_type_var,
                                    values=["holiday", "exam", "other"],
                                    state="readonly", width=10,
                                    font=FONTS["body"])
        type_combo.grid(row=0, column=0, sticky="ew", ipady=4, pady=4)

        today = date.today().isoformat()
        tk.Label(h_form, text=t("settings.from_date"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=12).grid(row=1, column=3, sticky=anchor_start(),
                                 padx=(0, 8), pady=4)
        self.h_from_var = tk.StringVar(value=today)
        DatePicker(h_form, variable=self.h_from_var
                   ).grid(row=1, column=2, sticky="ew", pady=4)

        tk.Label(h_form, text=t("settings.to_date"), font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"], anchor=anchor_start(),
                 width=10).grid(row=1, column=1, sticky=anchor_start(),
                                padx=(8, 8), pady=4)
        self.h_to_var = tk.StringVar(value=today)
        DatePicker(h_form, variable=self.h_to_var
                   ).grid(row=1, column=0, sticky="ew", pady=4)

        tk.Label(add_card, text=t("settings.date_format_hint"),
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"], anchor=anchor_start()).pack(anchor=anchor_start(), pady=(2, 6))

        tk.Button(add_card, text=t("settings.add_holiday_btn"),
                  command=self._add_holiday,
                  bg=c["success"], fg="#ffffff",
                  activebackground=c["success"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_start(), pady=(8, 0))

        tk.Label(wrap, text=t("settings.registered_holidays"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["text_secondary"], anchor=anchor_start()
                 ).pack(fill=tk.X, pady=(8, 4))

        tree_frame = tk.Frame(wrap, bg=c["bg_dark"], height=240)
        tree_frame.pack(fill=tk.X, pady=(0, 14))
        tree_frame.pack_propagate(False)

        cols = ("id", "date", "name", "type", "notes")
        self.h_tree = create_styled_treeview(tree_frame, columns=cols,
                                              show="headings", height=8)
        for col, (h, w, anch) in {
            "id":    ("ID", 50, "center"),
            "date":  (t("settings.col_date"), 110, "center"),
            "name":  (t("settings.col_name"), 240, "e"),
            "type":  (t("settings.col_type"), 90, "center"),
            "notes": (t("settings.col_notes"), 200, "e"),
        }.items():
            self.h_tree.heading(col, text=h, anchor=anch)
            self.h_tree.column(col, width=w, anchor=anch)

        h_vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                command=self.h_tree.yview)
        h_vsb.pack(side=side_end(), fill=tk.Y)
        self.h_tree.configure(yscrollcommand=h_vsb.set)
        self.h_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        h_btns = tk.Frame(wrap, bg=c["bg_dark"])
        h_btns.pack(fill=tk.X, pady=(0, 14))
        tk.Button(h_btns, text=t("settings.refresh"),
                  command=self._load_holidays,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=7, bd=0
                  ).pack(side=side_end(), padx=(0, 6))
        tk.Button(h_btns, text=t("settings.delete_selected"),
                  command=self._delete_holiday,
                  bg=c["error"], fg="#ffffff",
                   activebackground=c["error"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=7, bd=0
                  ).pack(side=side_end())

        self._section(wrap, t("settings.time_format"))
        self._build_time_format_section(wrap)

        self._build_sim_time_section(wrap)

        self._build_demo_section(wrap)

        self._build_time_travel_section(wrap)

        save_row = tk.Frame(wrap, bg=c["bg_dark"])
        save_row.pack(fill=tk.X, pady=(8, 20))

        tk.Button(save_row, text=t("settings.save_all_btn"),
                  command=self._save_settings,
                  bg=c["success"], fg="#ffffff",
                   activebackground=c["success"],
                  ).pack(side=side_start())

        self._load_holidays()

    def _section(self, parent, title):
        c = COLORS
        tk.Label(parent, text=title, font=FONTS["section"],
                 bg=c["bg_dark"], fg=c["accent"],
                 anchor=anchor_start()).pack(fill=tk.X, pady=(10, 4))

    def _save_settings(self):
        try:
            config.RFID_MODE = self.rfid_mode_var.get()
            config.SERIAL_PORT = self.port_var.get().strip() or None
            config.SERVER_HOST = self.host_var.get().strip()
            config.SERVER_PORT = int(self.sport_var.get())
            config.API_BASE = f"http://127.0.0.1:{config.SERVER_PORT}"
            self._save_session_settings()
            messagebox.showinfo(t("settings.done"), t("settings.saved_msg"))
        except ValueError as e:
            messagebox.showerror(t("settings.error"), f'{t("settings.invalid_value")}\n{e}')

    def _save_session_settings(self):
        try:
            val = int(self.timeout_var.get())
            if val < 1 or val > 180:
                messagebox.showerror(t("settings.error"), t("settings.timeout_range_error"))
                return
        except ValueError:
            messagebox.showerror(t("settings.error"), t("settings.timeout_int_error"))
            return
        try:
            r = http_client.api_put("/api/settings/session_timeout_minutes",
                             json_body={"value": str(val)})
            data = r.json()
            if data.get("success"):
                messagebox.showinfo(t("settings.done"), f'{t("settings.timeout_saved")}: {val} {t("settings.minute")}')
            else:
                messagebox.showerror(t("settings.error"), data.get("error", t("settings.save_failed")))
        except Exception as e:
            messagebox.showerror(t("settings.error"), str(e))

    def _load_session_settings(self):
        def do():
            try:
                r = http_client.api_get("/api/settings")
                if r.status_code == 200:
                    settings = r.json().get("settings", [])
                    for s in settings:
                        if s.get("key") == "session_timeout_minutes":
                            val = s.get("value", "15")
                            def update():
                                self.timeout_var.set(val)
                            self.parent.after(0, update)
                            break
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _load_holidays(self):
        for r in self.h_tree.get_children():
            self.h_tree.delete(r)

        def do():
            try:
                r = http_client.api_get("/api/holidays")
                if r.status_code == 200:
                    holidays = r.json().get("holidays", [])

                    def update():
                        for h in holidays:
                            self.h_tree.insert("", tk.END, values=(
                                h["id"], h["date"], h["name"],
                                h["type"], h.get("notes", "")))

                    self.parent.after(0, update)
            except Exception:
                pass

        threading.Thread(target=do, daemon=True).start()

    def _add_holiday(self):
        name = self.h_name_var.get().strip()
        from_date = self.h_from_var.get().strip()
        to_date = self.h_to_var.get().strip()

        if not name:
            messagebox.showerror(t("settings.error"), t("settings.holiday_name_required"))
            return
        if not from_date:
            messagebox.showerror(t("settings.error"), t("settings.start_date_required"))
            return

        try:
            r = http_client.api_post("/api/holidays", json_body={
                "name": name,
                "type": self.h_type_var.get(),
                "from_date": from_date,
                "to_date": to_date or from_date,
            })
            data = r.json()
            if data.get("success"):
                messagebox.showinfo(t("settings.done"), data.get("message", t("settings.added")))
                self.h_name_var.set("")
                self._load_holidays()
            else:
                messagebox.showerror(t("settings.error"), data.get("error", t("settings.operation_failed")))
        except Exception as e:
            messagebox.showerror(t("settings.error"), str(e))

    def _delete_holiday(self):
        sel = self.h_tree.selection()
        if not sel:
            messagebox.showwarning(t("settings.warning"), t("settings.select_holiday"))
            return
        v = self.h_tree.item(sel[0])["values"]
        hid, hdate, hname = v[0], v[1], v[2]
        if not messagebox.askyesno(t("settings.confirm"),
                                    f'{t("settings.delete_holiday_confirm")}\n{hname} ({hdate})؟'):
            return
        try:
            r = http_client.api_delete(f"/api/holidays/{hid}")
            if r.json().get("success"):
                self._load_holidays()
            else:
                messagebox.showerror(t("settings.error"), r.json().get("error"))
        except Exception as e:
            messagebox.showerror(t("settings.error"), str(e))

    def _build_time_format_section(self, parent):
        c = COLORS
        frame = tk.LabelFrame(parent, text=f'  {t("settings.time_format")}  ',
                               font=FONTS["section"], bg=c["bg_card"], fg=c["accent"],
                               padx=16, pady=12)
        frame.pack(fill=tk.X, padx=16, pady=(8, 0))

        row = tk.Frame(frame, bg=c["bg_card"])
        row.pack(fill=tk.X)

        self.time_format_var = tk.StringVar(value="12h")
        tk.Radiobutton(row, text=t("settings.time_12h"), variable=self.time_format_var,
                       value="12h", bg=c["bg_card"], fg=c["text_secondary"],
                       selectcolor="#ffffff", font=FONTS["body"],
                       command=self._save_time_format).pack(side=side_start(), padx=(0, 16))
        tk.Radiobutton(row, text=t("settings.time_24h"), variable=self.time_format_var,
                       value="24h", bg=c["bg_card"], fg=c["text_secondary"],
                       selectcolor="#ffffff", font=FONTS["body"],
                       command=self._save_time_format).pack(side=side_start())

        def load_fmt():
            try:
                resp = http_client.api_get("/api/settings")
                for s in resp.json().get("settings", []):
                    if s["key"] == "time_format":
                        self.time_format_var.set(s["value"])
            except Exception:
                pass
        threading.Thread(target=load_fmt, daemon=True).start()

    def _save_time_format(self):
        try:
            http_client.api_put("/api/settings/time_format",
                         json_body={"value": self.time_format_var.get()})
        except Exception:
            pass

    def _build_sim_time_section(self, parent):
        """Time-simulation section that persists across server restarts."""
        c = COLORS
        frame = tk.LabelFrame(parent, text=t("settings.time_simulation"),
                               font=FONTS["section"], bg=c["bg_card"],
                               fg=c["info"], padx=16, pady=12)
        frame.pack(fill=tk.X, padx=16, pady=(8, 0))

        # mode selector
        mode_row = tk.Frame(frame, bg=c["bg_card"])
        mode_row.pack(fill=tk.X, pady=4)
        tk.Label(mode_row, text=t("settings.sim_mode"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18,
                 anchor=anchor_start()).pack(side=side_start())

        self.sim_mode_var = tk.StringVar(value="off")
        for label_key, val in [
            ("settings.sim_mode_off", "off"),
            ("settings.sim_mode_freeze", "freeze"),
            ("settings.sim_mode_offset", "offset"),
        ]:
            tk.Radiobutton(mode_row, text=t(label_key),
                            variable=self.sim_mode_var, value=val,
                            font=FONTS["body"], bg=c["bg_card"],
                            fg=c["text_primary"],
                            selectcolor="#ffffff",
                            activebackground=c["bg_card"],
                            command=self._on_sim_mode_change
                            ).pack(side=side_start(), padx=(8, 0))

        # frozen_at row
        self.sim_freeze_row = tk.Frame(frame, bg=c["bg_card"])
        self.sim_freeze_row.pack(fill=tk.X, pady=4)
        tk.Label(self.sim_freeze_row, text=t("settings.sim_frozen_at"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18,
                 anchor=anchor_start()).pack(side=side_start())
        self.sim_date_var = tk.StringVar(value=client_time.now().date().isoformat())
        sim_date_entry = tk.Entry(self.sim_freeze_row, textvariable=self.sim_date_var,
                  font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  width=12, justify=text_justify())
        sim_date_entry.pack(side=side_start(), ipady=4, padx=(0, 4))
        self.sim_time_var = tk.StringVar(value="08:00:00")
        sim_time_entry = tk.Entry(self.sim_freeze_row, textvariable=self.sim_time_var,
                  font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  width=10, justify=text_justify())
        sim_time_entry.pack(side=side_start(), ipady=4)

        def _auto_select_freeze(_e=None):
            try:
                self.sim_mode_var.set("freeze")
            except Exception:
                pass
        sim_date_entry.bind("<FocusIn>", _auto_select_freeze)
        sim_time_entry.bind("<FocusIn>", _auto_select_freeze)
        sim_date_entry.bind("<KeyRelease>", _auto_select_freeze)
        sim_time_entry.bind("<KeyRelease>", _auto_select_freeze)
        tk.Label(self.sim_freeze_row, text="YYYY-MM-DD  HH:MM:SS",
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=(8, 0))

        # offset row
        self.sim_offset_row = tk.Frame(frame, bg=c["bg_card"])
        self.sim_offset_row.pack(fill=tk.X, pady=4)
        tk.Label(self.sim_offset_row, text=t("settings.sim_offset_seconds"),
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["text_muted"], width=18,
                 anchor=anchor_start()).pack(side=side_start())
        self.sim_offset_var = tk.StringVar(value="0")
        sim_offset_entry = tk.Entry(self.sim_offset_row, textvariable=self.sim_offset_var,
                  font=FONTS["body"], bg=c["input_bg"], fg=c["text_primary"],
                  insertbackground=c["accent"], relief="flat", bd=0,
                  width=12, justify=text_justify())
        sim_offset_entry.pack(side=side_start(), ipady=4)

        def _auto_select_offset(_e=None):
            try:
                self.sim_mode_var.set("offset")
            except Exception:
                pass
        sim_offset_entry.bind("<FocusIn>", _auto_select_offset)
        sim_offset_entry.bind("<KeyRelease>", _auto_select_offset)

        # action buttons
        btn_row = tk.Frame(frame, bg=c["bg_card"])
        btn_row.pack(fill=tk.X, pady=(8, 4))
        tk.Button(btn_row, text=f"💾 {t('settings.sim_apply')}",
                  command=self._apply_sim_time,
                  bg=c["primary"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start(), padx=(0, 8))
        tk.Button(btn_row, text=f"↺ {t('settings.sim_reset')}",
                  command=self._reset_sim_time,
                  bg=c["bg_light"], fg=c["text_primary"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start())

        # current status (real + simulated)
        self.sim_status_label = tk.Label(frame, text="",
                                          font=FONTS["mono"], bg=c["bg_card"],
                                          fg=c["text_muted"], justify="left",
                                          anchor=anchor_start())
        self.sim_status_label.pack(fill=tk.X, pady=(8, 0))

        # initial population + auto-refresh status
        self._refresh_sim_time_status()
        self._on_sim_mode_change()  # adjust visibility

    def _on_sim_mode_change(self):
        mode = self.sim_mode_var.get()
        # Don't actually hide rows (visual consistency) — but we could grey them out.
        # Simpler: keep both visible; only the relevant one's value is used on apply.
        # However we may visually emphasize:
        try:
            if mode == "freeze":
                for w in self.sim_freeze_row.winfo_children():
                    try: w.configure(state="normal")
                    except Exception: pass
            if mode == "offset":
                for w in self.sim_offset_row.winfo_children():
                    try: w.configure(state="normal")
                    except Exception: pass
        except Exception:
            pass

    def _apply_sim_time(self):
        mode = self.sim_mode_var.get()
        payload = {"mode": mode}
        if mode == "freeze":
            d = self.sim_date_var.get().strip()
            ti = self.sim_time_var.get().strip()
            if not d or not ti:
                messagebox.showerror(t("settings.error"),
                                      t("settings.sim_invalid_datetime"))
                return
            payload["frozen_at"] = f"{d}T{ti}"
        elif mode == "offset":
            try:
                payload["offset_seconds"] = int(self.sim_offset_var.get())
            except ValueError:
                messagebox.showerror(t("settings.error"),
                                      t("settings.sim_invalid_datetime"))
                return

        def do():
            try:
                r = http_client.api_post("/api/settings/sim-time",
                                   json_body=payload).json()
                if r.get("success"):
                    client_time.sync_now()
                    safe_after(self.parent, 0, lambda: messagebox.showinfo(
                        t("ok"), t("settings.sim_applied")))
                else:
                    err = r.get("error", "")
                    safe_after(self.parent, 0, lambda: messagebox.showerror(
                        t("settings.error"), err))
                safe_after(self.parent, 0, self._refresh_sim_time_status)
            except Exception as ex:
                msg = str(ex)
                safe_after(self.parent, 0, lambda m=msg: messagebox.showerror(
                    t("settings.error"), m))
        threading.Thread(target=do, daemon=True).start()

    def _reset_sim_time(self):
        def do():
            try:
                http_client.api_post("/api/settings/sim-time/reset")
                client_time.sync_now()
                safe_after(self.parent, 0, self._refresh_sim_time_status)
                safe_after(self.parent, 0, lambda: self.sim_mode_var.set("off"))
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _refresh_sim_time_status(self):
        try:
            if not self.parent.winfo_exists():
                return
        except tk.TclError:
            return

        def do():
            try:
                r = http_client.api_get("/api/settings/sim-time").json()
                if not r.get("success"):
                    return
                real = r.get("real_time", "")
                sim = r.get("simulated_time", "")
                mode = r.get("mode", "off")
                text = (f"{t('settings.sim_current_real')}: {real}\n"
                        f"{t('settings.sim_current_simulated')}: {sim}  ({mode})")

                def update():
                    try:
                        if not self.parent.winfo_exists():
                            return
                        if not self.sim_status_label.winfo_exists():
                            return
                    except tk.TclError:
                        return
                    try:
                        self.sim_status_label.config(text=text)
                        self.sim_mode_var.set(mode)
                        if r.get("frozen_at"):
                            fr = r["frozen_at"]
                            if "T" in fr:
                                d, ti = fr.split("T", 1)
                                self.sim_date_var.set(d)
                                self.sim_time_var.set(ti[:8])
                        if r.get("offset_seconds") is not None:
                            self.sim_offset_var.set(str(r["offset_seconds"]))
                    except tk.TclError:
                        return
                safe_after(self.parent, 0, update)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
        try:
            if self.parent.winfo_exists():
                safe_after(self.parent, 3000, self._refresh_sim_time_status)
        except tk.TclError:
            pass

    def _build_demo_section(self, parent):
        c = COLORS
        if not self.user or self.user.role != "dean":
            return
        frame = tk.LabelFrame(parent, text=t("settings.demo_section"),
                               font=FONTS["section"], bg=c["bg_card"], fg=c["warning"],
                               padx=16, pady=12)
        frame.pack(fill=tk.X, padx=16, pady=(8, 0))
        row = tk.Frame(frame, bg=c["bg_card"])
        row.pack(fill=tk.X)
        tk.Button(row, text=t("settings.load_demo_btn"), command=self._seed_demo,
                  bg=c["success"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start(), padx=(0, 12))
        tk.Button(row, text=t("settings.wipe_data_btn"), command=self._wipe_data,
                  bg=c["error"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_start())

    def _seed_demo(self):
        if not messagebox.askyesno(t("settings.confirm"), t("settings.confirm_demo")):
            return
        def do():
            try:
                resp = http_client.api_post("/api/admin/seed-demo",
                                     json_body={"_role": "dean"})
                data = resp.json()
                msg = data.get("success") and messagebox.showinfo or messagebox.showerror
                msg(t("settings.result"), data.get("message", data.get("error", "")))
            except Exception as ex:
                messagebox.showerror(t("settings.error"), str(ex))
        threading.Thread(target=do, daemon=True).start()

    def _wipe_data(self):
        if not messagebox.askyesno(t("settings.confirm"), t("settings.confirm_wipe")):
            return
        def do():
            try:
                resp = http_client.api_post("/api/admin/wipe-data",
                                     json_body={"_role": "dean"})
                data = resp.json()
                msg = data.get("success") and messagebox.showinfo or messagebox.showerror
                msg(t("settings.result"), data.get("message", data.get("error", "")))
            except Exception as ex:
                messagebox.showerror(t("settings.error"), str(ex))
        threading.Thread(target=do, daemon=True).start()

    def _build_time_travel_section(self, parent):
        if not config.DEBUG_MODE:
            return
        c = COLORS
        frame = tk.LabelFrame(parent, text=t("settings.test_section"),
                               font=FONTS["section"], bg=c["bg_card"], fg=c["warning"],
                               padx=16, pady=12)
        frame.pack(fill=tk.X, padx=16, pady=(8, 0))
        self.dev_time_label = tk.Label(frame, text="", font=FONTS["mono"],
                                        bg=c["bg_card"], fg=c["text_primary"])
        self.dev_time_label.pack(fill=tk.X, pady=4)
        row = tk.Frame(frame, bg=c["bg_card"])
        row.pack(fill=tk.X, pady=4)
        for txt, sec in [(t("settings.minus_1_day"), -86400), (t("settings.minus_1_hour"), -3600), (t("settings.minus_1_minute"), -60)]:
            tk.Button(row, text=txt, command=lambda s=sec: self._time_offset(s),
                      bg=c["bg_light"], fg=c["text_primary"], font=FONTS["small"],
                      relief="flat", cursor="hand2", padx=6, pady=3, bd=0
                      ).pack(side=side_start(), padx=2)
        for txt, sec in [(t("settings.plus_1_minute"), 60), (t("settings.plus_1_hour"), 3600), (t("settings.plus_1_day"), 86400)]:
            tk.Button(row, text=txt, command=lambda s=sec: self._time_offset(s),
                      bg=c["bg_light"], fg=c["text_primary"], font=FONTS["small"],
                      relief="flat", cursor="hand2", padx=6, pady=3, bd=0
                      ).pack(side=side_end(), padx=2)
        tk.Button(frame, text=t("settings.reset_time"), command=self._reset_time,
                  bg=c["error"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=8, pady=4, bd=0).pack(pady=(8, 0))
        self._refresh_dev_time()

    def _time_offset(self, seconds):
        try:
            http_client.api_post("/api/dev/time/offset", json_body={"seconds": seconds})
            self._refresh_dev_time()
        except Exception:
            pass

    def _freeze_time(self):
        dt_str = f"{self.freeze_date_var.get()}T{self.freeze_time_var.get()}:00"
        try:
            http_client.api_post("/api/dev/time/freeze", json_body={"datetime": dt_str})
        except Exception:
            pass

    def _reset_time(self):
        try:
            http_client.api_post("/api/dev/time/reset")
            self._refresh_dev_time()
        except Exception:
            pass

    def _refresh_dev_time(self):
        try:
            resp = http_client.api_get("/api/dev/time")
            data = resp.json()
            status = t("settings.overridden") if data.get("overridden") else t("settings.real")
            self.dev_time_label.config(text=f"{data.get('current', '')[:19]}  [{status}]")
        except Exception:
            pass
        try:
            self.parent.after(2000, self._refresh_dev_time)
        except Exception:
            pass
