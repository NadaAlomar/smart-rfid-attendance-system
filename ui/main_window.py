import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import config
from ui.theme import (COLORS, FONTS, apply_theme, set_theme, get_theme,
                       save_prefs, get_lang, create_styled_treeview)
from ui.i18n import set_lang, t
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify, pad_x
from ui import client_time
from ui import http_client
from ui.widgets.role_badge import RoleBadge

API_BASE = config.API_BASE


class ScrollFrame(tk.Frame):
    """Frame قابل للتمرير — عجلة الماوس + scrollbar"""

    def __init__(self, parent, bg=None, **kw):
        bg = bg or COLORS["bg_dark"]
        super().__init__(parent, bg=bg, **kw)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient=tk.VERTICAL,
                                  command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        from ui.rtl_helper import side_end, side_start
        self.vsb.pack(side=side_end(), fill=tk.Y)
        self.canvas.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win_id = self.canvas.create_window((0, 0), window=self.inner,
                                                   anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self._win_id, width=e.width)

    def _bind_wheel(self, e):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, e):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, e):
        if e.num == 4:
            self.canvas.yview_scroll(-3, "units")
        elif e.num == 5:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


class MainWindow:
    def __init__(self, root, user, on_logout=None):
        self.root = root
        self.user = user
        self.on_logout = on_logout
        self.root.title(t("main.window_title"))
        self.root.geometry("1366x768")
        self.root.minsize(1100, 660)
        client_time.start_sync_thread()
        apply_theme(self.root)
        self._active_btn = None
        self._sidebar_buttons = []
        http_client.on_session_expired(self._handle_session_expired)
        self._build()
        self.load_dashboard()

    def _handle_session_expired(self):
        try:
            self.root.after(0, lambda: (
                messagebox.showwarning(t("warning"), t("auth.session_expired")),
                self._logout() if self.on_logout else None,
            ))
        except Exception:
            pass

    def _build(self):
        c = COLORS

        # ── شريط علوي ──
        hdr = tk.Frame(self.root, bg=c["bg_medium"], height=64)
        hdr.pack(side=tk.TOP, fill=tk.X)
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=c["primary"], width=5).pack(side=tk.RIGHT, fill=tk.Y)

        # يمين: العنوان
        right_hdr = tk.Frame(hdr, bg=c["bg_medium"])
        right_hdr.pack(side=side_start(), fill=tk.Y, padx=20)
        tk.Label(right_hdr, text=t("main.system_title_header"),
                 font=FONTS["subtitle"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(anchor=anchor_start(), pady=(12, 0))
        tk.Label(right_hdr, text=t("main.university_header"),
                 font=FONTS["small"], bg=c["bg_medium"],
                 fg=c["text_muted"]).pack(anchor=anchor_start())

        # يسار: حالة + وقت + أزرار
        left_hdr = tk.Frame(hdr, bg=c["bg_medium"])
        left_hdr.pack(side=side_end(), fill=tk.Y, padx=10)

        # أزرار الـ theme واللغة (أقصى يسار)
        toggles = tk.Frame(left_hdr, bg=c["bg_medium"])
        toggles.pack(side=side_end(), padx=pad_x(0, 12))

        self.theme_btn = tk.Button(
            toggles,
            text=t("main.theme_light") if get_theme() == "dark" else t("main.theme_dark"),
            command=self._toggle_theme,
            bg=c["bg_light"], fg=c["text_primary"],
            activebackground=c["primary"], activeforeground="#ffffff",
            font=FONTS["small_bold"], relief="flat",
            cursor="hand2", padx=10, pady=6, bd=0)
        self.theme_btn.pack(side=side_end(), padx=pad_x(0, 6))

        self.lang_btn = tk.Button(
            toggles,
            text="EN" if get_lang() == "ar" else "AR",
            command=self._toggle_lang,
            bg=c["bg_light"], fg=c["text_primary"],
            activebackground=c["primary"], activeforeground="#ffffff",
            font=FONTS["small_bold"], relief="flat",
            cursor="hand2", padx=10, pady=6, bd=0, width=4)
        self.lang_btn.pack(side=side_end())

        # حالة + وقت
        status_col = tk.Frame(left_hdr, bg=c["bg_medium"])
        status_col.pack(side=side_end())
        self.conn_label = tk.Label(status_col, text=t("main.connecting"),
                                    font=FONTS["small_bold"],
                                    bg=c["bg_medium"], fg=c["warning"])
        self.conn_label.pack(anchor=anchor_end(), pady=(12, 0))
        self.time_label = tk.Label(status_col, text="",
                                    font=FONTS["small"],
                                    bg=c["bg_medium"], fg=c["text_muted"])
        self.time_label.pack(anchor=anchor_end())

        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        # ── شريط سفلي ──
        role_ar = {"dean": t("role.dean"), "dean_assistant": t("role.dean_assistant"), "doctor": t("main.role_doctor"), "secretary": t("main.role_secretary")}.get(self.user.role, self.user.role)
        bar = tk.Frame(self.root, bg=c["bg_medium"], height=28)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        tk.Frame(bar, bg=c["border"], height=1).pack(side=tk.TOP, fill=tk.X)
        from ui.widgets.role_badge import RoleBadge
        RoleBadge(bar, self.user.role).pack(side=side_start(), padx=pad_x(16, 4))
        tk.Label(bar, text=f'{self.user.username}  |  {role_ar}',
                 font=FONTS["small"], bg=c["bg_medium"],
                 fg=c["text_muted"]).pack(side=side_start())
        tk.Label(bar, text="AUST Attendance System  v2.0",
                 font=FONTS["small"], bg=c["bg_medium"],
                 fg=c["text_muted"]).pack(side=side_end(), padx=16)

        # ── body ──
        body = tk.Frame(self.root, bg=c["bg_dark"])
        body.pack(fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(body, bg=c["sidebar_bg"], width=240)
        self.sidebar.pack(side=side_start(), fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        tk.Frame(body, bg=c["border"], width=1).pack(side=side_start(), fill=tk.Y)

        self.content = tk.Frame(body, bg=c["bg_dark"])
        self.content.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self._tick()
        self._check_server()
        self._check_test_mode()

    def _build_sidebar(self):
        c = COLORS
        p = self.sidebar

        logo = tk.Frame(p, bg=c["sidebar_bg"])
        logo.pack(fill=tk.X, pady=(20, 8))

        tk.Label(logo, text="AUST",
                 font=("Segoe UI", 22, "bold"),
                 bg=c["sidebar_bg"],
                 fg=c["primary_light"]).pack()

        tk.Label(logo, text=t("main.sidebar_subtitle"),
                 font=FONTS["small"],
                 bg=c["sidebar_bg"],
                 fg="#9384c2").pack()

        tk.Frame(p, bg=c["border_light"], height=1).pack(
            fill=tk.X, padx=16, pady=(8, 0))

        nav_outer = tk.Frame(p, bg=c["sidebar_bg"])
        nav_outer.pack(fill=tk.BOTH, expand=True)

        nav_canvas = tk.Canvas(nav_outer, bg=c["sidebar_bg"],
                                highlightthickness=0, bd=0)
        nav_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        nav_inner = tk.Frame(nav_canvas, bg=c["sidebar_bg"])
        nav_win = nav_canvas.create_window((0, 0), window=nav_inner, anchor="nw")

        nav_inner.bind("<Configure>",
                       lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all")))
        nav_canvas.bind("<Configure>",
                        lambda e: nav_canvas.itemconfig(nav_win, width=e.width))

        def _on_wheel(e):
            nav_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        nav_inner.bind("<Enter>",
                        lambda e: nav_canvas.bind_all("<MouseWheel>", _on_wheel))
        nav_inner.bind("<Leave>",
                        lambda e: nav_canvas.unbind_all("<MouseWheel>"))

        nav = self._nav_for_role(self.user.role)

        for section, items in nav:
            tk.Label(nav_inner, text=section.upper(),
                     font=FONTS["sidebar_sec"],
                     bg=c["sidebar_bg"], fg=c["sidebar_muted"],
                     anchor=anchor_start(), padx=16).pack(fill=tk.X, pady=(14, 2))

            for label, cmd in items:
                btn = tk.Button(
                    nav_inner, text=label,
                    command=lambda c=cmd, l=label: self._nav_click(c, l),
                    bg=c["sidebar_bg"], fg="#c4b5fd",
                    activebackground=c["primary_dark"],
                    activeforeground="#ffffff",
                    relief="flat", font=FONTS["sidebar_btn"],
                    cursor="hand2", anchor=anchor_start(),
                    padx=16, pady=9, bd=0)
                btn.pack(fill=tk.X, padx=4, pady=1)
                btn.bind("<Enter>", lambda e, b=btn: self._hover_btn(b, True))
                btn.bind("<Leave>", lambda e, b=btn: self._hover_btn(b, False))
                self._sidebar_buttons.append((label, btn))

        bottom = tk.Frame(p, bg=c["sidebar_bg"])
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(bottom, bg=c["border"], height=1).pack(fill=tk.X, padx=16, pady=4)
        tk.Button(bottom, text=t("main.nav_logout"),
                  command=self._logout,
                  bg=c["sidebar_bg"], fg=c["error"],
                  activebackground=c["error"],
                  activeforeground="#ffffff",
                  relief="flat", font=FONTS["sidebar_btn"],
                   cursor="hand2", anchor=anchor_start(),
                  padx=16, pady=10, bd=0).pack(fill=tk.X, padx=4, pady=(0, 12))

    def _nav_for_role(self, role):
        if role == "doctor":
            return self._doctor_nav()
        elif role in ("dean", "dean_assistant"):
            return self._dean_nav()
        elif role == "secretary":
            return self._secretary_nav()
        return self._dean_nav()

    def _dean_nav(self):
        return [
            (t("main.nav_home_section"), [
                (t("main.nav_dashboard"),   self.load_dashboard),
                (t("main.nav_live_attendance"),     self.load_live_attendance),
                (t("main.nav_recent_scans"),      self.load_recent_scans),
            ]),
            (t("main.nav_students_section"), [
                (t("main.nav_add_student"),        self.load_add_student),
                (t("main.nav_student_list"),       self.load_view_students),
                (t("main.nav_student_profile_card"), self.load_student_profile_by_card),
                (t("main.nav_course_enrollment"),      self.load_course_enrollment),
                (t("main.nav_import_excel"),      self.load_import),
            ]),
            (t("main.nav_staff_section"), [
                (t("main.nav_doctors"), self.load_doctors),
            ]),
            (t("main.nav_courses_halls_section"), [
                (t("main.nav_manage_courses"),       self.load_courses),
                (t("main.nav_halls"),  self.load_halls),
                (t("main.nav_weekly_timetable"),   self.load_weekly_timetable),
            ]),
            (t("main.nav_attendance_section"), [
                (t("main.nav_attendance_reports"),     self.load_attendance_report),
                (t("main.nav_active_sessions"),    self.load_active_sessions),
                (t("attendance_logs.title"),       self.load_attendance_logs),
            ]),
            (t("main.nav_alerts_section"), [
                (t("main.nav_alerts"),          self.load_alerts),
                (t("main.nav_notes_inbox"), self.load_notes_inbox),
            ]),
            (t("main.nav_system_section"), [
                (t("main.nav_holidays"),   self.load_holidays),
                (t("main.nav_backup"),   self.load_backup),
                (t("main.nav_accounts"), self.load_accounts),
                (t("main.nav_audit_log"), self.load_audit_log),
                (t("main.nav_diagnostics"), self.load_diagnostics),
                (t("main.nav_settings"),          self.load_settings),
            ]),
        ]

    def _secretary_nav(self):
        return [
            (t("main.nav_home_section"), [
                (t("main.nav_dashboard"),   self.load_dashboard),
                (t("main.nav_live_attendance"),     self.load_live_attendance),
                (t("main.nav_recent_scans"),      self.load_recent_scans),
            ]),
            (t("main.nav_students_section"), [
                (t("main.nav_add_student"),        self.load_add_student),
                (t("main.nav_student_list"),       self.load_view_students),
                (t("main.nav_student_profile_card"), self.load_student_profile_by_card),
                (t("main.nav_course_enrollment"),      self.load_course_enrollment),
                (t("main.nav_import_excel"),      self.load_import),
            ]),
            (t("main.nav_staff_section"), [
                (t("main.nav_doctors"), self.load_doctors),
            ]),
            (t("main.nav_courses_halls_section"), [
                (t("main.nav_manage_courses"),       self.load_courses),
                (t("main.nav_halls"),  self.load_halls),
                (t("main.nav_weekly_timetable"),   self.load_weekly_timetable),
            ]),
            (t("main.nav_attendance_section"), [
                (t("main.nav_attendance_reports"),     self.load_attendance_report),
                (t("main.nav_active_sessions"),    self.load_active_sessions),
                (t("attendance_logs.title"),       self.load_attendance_logs),
            ]),
            (t("main.nav_alerts_section"), [
                (t("main.nav_alerts"),          self.load_alerts),
                (t("main.nav_notes_inbox"), self.load_notes_inbox),
            ]),
            (t("main.nav_system_section"), [
                (t("main.nav_diagnostics"), self.load_diagnostics),
            ]),
        ]

    def _doctor_nav(self):
        return [
            (t("main.nav_home_section"), [
                (t("main.nav_dashboard"),   self.load_dashboard),
            ]),
            (t("main.nav_doctor_section"), [
                (t("main.nav_my_courses"), self.load_doctor_courses),
                (t("main.nav_my_students"), self.load_doctor_students),
                (t("main.nav_my_notes"), self.load_doctor_notes),
            ]),
            (t("main.nav_attendance_section"), [
                (t("main.nav_qr_attendance"),     self.load_doctor_qr_attendance),
                (t("main.nav_live_attendance"),     self.load_live_attendance),
                (t("main.nav_attendance_reports"),     self.load_attendance_report),
                (t("attendance_logs.title"),       self.load_attendance_logs),
            ]),
            (t("main.nav_alerts_section"), [
                (t("main.nav_alerts"),          self.load_alerts),
            ]),
        ]

    def _hover_btn(self, btn, hovering):
        if btn == self._active_btn:
            return
        c = COLORS
        if hovering:
            btn.config(bg=c["primary_dark"], fg="#ffffff")
        else:
            btn.config(bg=c["sidebar_bg"], fg=c["sidebar_text"])

    def _nav_click(self, cmd, label):
        c = COLORS
        if self._active_btn:
            self._active_btn.config(bg=c["sidebar_bg"], fg=c["sidebar_text"])
        for lbl, btn in self._sidebar_buttons:
            if lbl == label:
                self._active_btn = btn
                btn.config(bg=c["primary"], fg="#ffffff")
                break
        cmd()

    # ── تبديل الـ theme واللغة ──
    def _toggle_theme(self):
        new_theme = "light" if get_theme() == "dark" else "dark"
        set_theme(new_theme)
        # إعادة تطبيق الـ theme فوراً + إعادة بناء الواجهة
        apply_theme(self.root)
        self._rebuild_ui()

    def _toggle_lang(self):
        new_lang = "en" if get_lang() == "ar" else "ar"
        set_lang(new_lang)
        save_prefs(lang=new_lang)
        from ui.theme import reload_fonts
        reload_fonts()
        self._rebuild_ui()

    def _rebuild_ui(self):
        """يعيد بناء كامل الواجهة بعد تغيير الوضع"""
        # امسح كل children
        for w in self.root.winfo_children():
            w.destroy()
        self._active_btn = None
        self._sidebar_buttons = []
        self._build()
        self.load_dashboard()

    def _logout(self):
        """تسجيل خروج → إغلاق النافذة الرئيسية والعودة لشاشة الدخول"""
        if not messagebox.askyesno(t("main.confirm"), t("main.confirm_logout")):
            return
        if self.on_logout:
            self.on_logout()
        else:
            self.root.quit()

    # ── شريط الحالة ──
    def _tick(self):
        from utils.date_utils import format_time
        now = client_time.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = format_time(now)
        self.time_label.config(text=f"{date_str}   {time_str}")
        self.root.after(1000, self._tick)

    def _check_test_mode(self):
        try:
            r = requests.get(f"{API_BASE}/api/time/current", timeout=2)
            data = r.json()
            overridden = data.get("is_overridden", False)
        except Exception:
            overridden = False

        if overridden:
            if not hasattr(self, '_test_badge') or not self._test_badge.winfo_exists():
                status_col = self.time_label.master
                self._test_badge = tk.Label(
                    status_col, text=t("main.test_mode"),
                    font=FONTS["small_bold"], bg=COLORS["bg_medium"],
                    fg=COLORS["error"])
                self._test_badge.pack(anchor=anchor_end())
        else:
            if hasattr(self, '_test_badge') and self._test_badge.winfo_exists():
                self._test_badge.destroy()
                del self._test_badge

        self.root.after(3000, self._check_test_mode)

    def _check_server(self):
        def do():
            try:
                r = requests.get(f"{API_BASE}/api/status", timeout=2)
                ok = r.status_code == 200
            except Exception:
                ok = False
            try:
                self.conn_label.config(
                    text=(t("main.server_online") if ok else t("main.server_offline")),
                    fg=(COLORS["success"] if ok else COLORS["error"]))
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()
        self.root.after(10000, self._check_server)

    # ── أدوات ──
    def clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _page_title(self, text):
        c = COLORS
        hdr = tk.Frame(self.content, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["primary"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=text,
                 font=FONTS["section"],
                 bg=c["bg_medium"], fg=c["accent"],
                 anchor=anchor_start(), padx=20).pack(side=side_start(), pady=14)
        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

    def _api(self, method, path, **kwargs):
        try:
            r = getattr(requests, method)(f"{API_BASE}{path}", timeout=5, **kwargs)
            return r.json()
        except requests.exceptions.ConnectionError:
            messagebox.showerror(t("main.connection_error_title"),
                                  t("main.connection_error_msg"))
            return None
        except Exception as e:
            messagebox.showerror(t("error"), str(e))
            return None

    # ══════════════════════════════════════════════════════
    #  لوحة التحكم
    # ══════════════════════════════════════════════════════
    def load_dashboard(self):
        self.clear()
        c = COLORS
        self._page_title(t("main.dashboard"))

        sf = ScrollFrame(self.content)
        sf.pack(fill=tk.BOTH, expand=True)
        wrap = tk.Frame(sf.inner, bg=c["bg_dark"], padx=24, pady=20)
        wrap.pack(fill=tk.BOTH, expand=True)

        # بطاقات
        cards_row = tk.Frame(wrap, bg=c["bg_dark"])
        cards_row.pack(fill=tk.X, pady=(0, 20))

        stat_defs = [
            ("total_students",   t("total_students"),    c["primary"],  "👨‍🎓"),
            ("active_sessions",  t("main.stat_sessions"),       c["success"],  "📋"),
            ("today_attendance", t("today_attendance"),       c["warning"],  "✅"),
            ("active_alerts",    t("main.stat_alerts"),          c["error"],    "🔔"),
        ]
        self.stat_labels = {}
        for i, (key, label, color, icon) in enumerate(stat_defs):
            card = tk.Frame(cards_row, bg=c["bg_card"])
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            tk.Frame(card, bg=color, height=4).pack(fill=tk.X)
            inner = tk.Frame(card, bg=c["bg_card"], padx=20, pady=14)
            inner.pack(fill=tk.BOTH, expand=True)
            tk.Label(inner, text=icon, font=("Segoe UI Emoji", 20),
                     bg=c["bg_card"], fg=color).pack(anchor=anchor_start())
            val_lbl = tk.Label(inner, text="—", font=FONTS["stat_value"],
                                bg=c["bg_card"], fg=color)
            val_lbl.pack(anchor=anchor_start())
            tk.Label(inner, text=label, font=FONTS["stat_label"],
                     bg=c["bg_card"], fg=c["text_muted"],
                     anchor=anchor_start()).pack(fill=tk.X)
            self.stat_labels[key] = val_lbl
        cards_row.columnconfigure([0, 1, 2, 3], weight=1)

        # وصول سريع
        tk.Label(wrap, text=t("quick_access"), font=FONTS["section"],
                 bg=c["bg_dark"], fg=c["text_secondary"],
                 anchor=anchor_start()).pack(fill=tk.X, pady=(0, 8))
        quick_row = tk.Frame(wrap, bg=c["bg_dark"])
        quick_row.pack(fill=tk.X, pady=(0, 20))
        quick_items = [
            (t("main.quick_add_student"),      self.load_add_student,        c["primary"]),
            (t("main.quick_manage_doctors"),  self.load_doctors,            c["info"]),
            (t("main.quick_manage_courses"),    self.load_courses,            c["warning"]),
            (t("main.quick_manage_halls"),   self.load_halls,              c["accent"]),
            (t("main.quick_attendance_reports"),   self.load_attendance_report,  c["success"]),
            (t("main.quick_alerts"),        self.load_alerts,             c["error"]),
        ]
        for i, (lbl, cmd, color) in enumerate(quick_items):
            btn = tk.Button(quick_row, text=lbl, command=cmd,
                            bg=color, fg="#ffffff",
                            activebackground=c["bg_light"],
                            activeforeground="#ffffff",
                            font=FONTS["body_bold"],
                            relief="flat", cursor="hand2",
                            padx=10, pady=10, bd=0)
            btn.grid(row=0, column=i, padx=6, sticky="ew")
        quick_row.columnconfigure(list(range(6)), weight=1)

        # آخر التنبيهات
        tk.Label(wrap, text=t("latest_alerts"), font=FONTS["section"],
                 bg=c["bg_dark"], fg=c["text_secondary"],
                 anchor=anchor_start()).pack(fill=tk.X, pady=(0, 8))
        self.alert_frame = tk.Frame(wrap, bg=c["bg_card"], padx=16, pady=12)
        self.alert_frame.pack(fill=tk.X)

        tk.Button(wrap, text=t("main.refresh_data"),
                  command=self._refresh_dashboard,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"],
                  relief="flat", cursor="hand2",
                   padx=20, pady=8, bd=0).pack(anchor=anchor_start(), pady=14)

        self._refresh_dashboard()

    def _refresh_dashboard(self):
        ALERT_AR = {
            "4_absences":      "4 غيابات",
            "zero_attendance": "غياب كامل",
            "low_percent":     "نسبة منخفضة",
        }

        def do():
            data = self._api("get", "/api/dashboard/stats")
            if data and data.get("success"):
                for key, lbl in self.stat_labels.items():
                    try:
                        lbl.config(text=str(data["stats"].get(key, 0)))
                    except Exception:
                        pass

            alerts_data = self._api("get", "/api/alerts")
            c = COLORS
            try:
                for w in self.alert_frame.winfo_children():
                    w.destroy()
            except Exception:
                return
            if alerts_data and alerts_data.get("success"):
                alerts = alerts_data.get("alerts", [])[:5]
                if not alerts:
                    tk.Label(self.alert_frame,
                             text=t("main.no_active_alerts"),
                             font=FONTS["body"], bg=c["bg_card"],
                              fg=c["success"], anchor=anchor_start()).pack(fill=tk.X)
                    return
                for a in alerts:
                    atype_ar = ALERT_AR.get(a["alert_type"], a["alert_type"])
                    row = tk.Frame(self.alert_frame, bg=c["bg_card2"], pady=6, padx=12)
                    row.pack(fill=tk.X, pady=2)
                    tk.Label(row,
                             text=f"🔴  {a['student_name']}  —  {a['course_name']}  —  {atype_ar}",
                             font=FONTS["body"],
                              bg=c["bg_card2"], fg=c["error"],
                              anchor=anchor_start()).pack(fill=tk.X)

        threading.Thread(target=do, daemon=True).start()

    # ══════════════════════════════════════════════════════
    #  التنقل بين الصفحات
    # ══════════════════════════════════════════════════════
    def load_add_student(self):
        self.clear()
        self._page_title(t("add_student"))
        from ui.student_management import StudentForm
        StudentForm(self.content, on_success=self.load_view_students)

    def load_view_students(self):
        self.clear()
        self._page_title(t("view_students"))
        from ui.student_management import StudentList
        StudentList(self.content)

    def load_doctors(self):
        self.clear()
        self._page_title(t("main.page_doctors"))
        from ui.doctor_management import DoctorManagement
        DoctorManagement(self.content)

    def load_courses(self):
        self.clear()
        self._page_title(t("manage_courses"))
        from ui.course_management import CourseManagement
        CourseManagement(self.content)

    def load_halls(self):
        self.clear()
        self._page_title(t("main.page_halls"))
        from ui.hall_management import HallManagement
        HallManagement(self.content)

    def load_attendance_report(self):
        self.clear()
        self._page_title(t("main.page_attendance_reports"))
        from ui.attendance_report import AttendanceReport
        AttendanceReport(self.content)

    def load_attendance_logs(self):
        self.clear()
        self._page_title(t("attendance_logs.title"))
        from ui.attendance_logs import AttendanceLogsPanel
        AttendanceLogsPanel(self.content)

    def load_active_sessions(self):
        self.clear()
        self._page_title(t("active_sessions"))
        c = COLORS

        inner = tk.Frame(self.content, bg=c["bg_dark"], padx=24, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "doctor", "course", "hall", "start", "status")
        tree = create_styled_treeview(inner, columns=cols, show="headings", height=20)
        for col, (h, w, anch) in {
            "id":     (t("main.col_id"), 60, "center"),
            "doctor": (t("doctor"), 220, anchor_start()),
            "course": (t("course"), 260, anchor_start()),
            "hall":   (t("main.col_hall"), 150, "center"),
            "start":  (t("start_time"), 140, "center"),
            "status": (t("main.col_status"), 110, "center"),
        }.items():
            tree.heading(col, text=h, anchor=anch)
            tree.column(col, width=w, anchor=anch)

        tree.tag_configure("active", foreground=c["success"])
        tree.tag_configure("scheduled", foreground=c["info"])

        from ui.rtl_helper import side_end as _se, side_start as _ss
        vsb = ttk.Scrollbar(inner, orient=tk.VERTICAL)
        vsb.pack(side=_se(), fill=tk.Y)
        tree.configure(yscrollcommand=vsb.set)
        vsb.configure(command=tree.yview)
        tree.pack(side=_ss(), fill=tk.BOTH, expand=True)

        def refresh():
            for r in tree.get_children():
                tree.delete(r)
            from database import get_session as db_sess
            from database.models import AttendanceSession, Doctor, Course, Schedule, Hall
            from utils.time_provider import now as tp_now
            s = db_sess()
            try:
                current = tp_now()
                cur_day = current.weekday()
                cur_time = current.time()

                # 1) الجلسات النشطة فعلياً (الدكتور مسح بطاقته)
                actives = s.query(AttendanceSession).filter_by(is_active=True).all()
                active_by_sched = {a.schedule_id: a for a in actives if a.schedule_id}

                # 2) الجلسات المقررة الآن (حسب الجدول)
                scheduled = s.query(Schedule).join(Course).filter(
                    Schedule.day_of_week == cur_day,
                    Schedule.start_time <= cur_time,
                    Schedule.end_time >= cur_time,
                ).all()

                rows = []
                seen_active_ids = set()

                for sched in scheduled:
                    co = s.query(Course).filter_by(id=sched.course_id).first()
                    ha = s.query(Hall).filter_by(id=sched.hall_id).first()
                    doctor = None
                    if co and co.doctor_id:
                        doctor = s.query(Doctor).filter_by(id=co.doctor_id).first()
                    active = active_by_sched.get(sched.id)
                    if active:
                        seen_active_ids.add(active.id)
                        rows.append((
                            active.id,
                            doctor.full_name if doctor else "—",
                            co.course_name if co else "—",
                            ha.hall_name if ha else "—",
                            active.start_timestamp.strftime("%H:%M:%S"),
                            t("main.status_active"),
                            "active",
                        ))
                    else:
                        time_str = f"{sched.start_time.strftime('%H:%M')}–{sched.end_time.strftime('%H:%M')}"
                        rows.append((
                            "—",
                            doctor.full_name if doctor else "—",
                            co.course_name if co else "—",
                            ha.hall_name if ha else "—",
                            time_str,
                            t("main.status_scheduled"),
                            "scheduled",
                        ))

                # 3) جلسات نشطة خارج وقتها المقرر (تجاوزت أو بلا جدول)
                for active in actives:
                    if active.id in seen_active_ids:
                        continue
                    doctor = s.query(Doctor).filter_by(id=active.doctor_id).first()
                    course_name, hall_name = "—", "—"
                    if active.schedule_id:
                        sched = s.query(Schedule).filter_by(id=active.schedule_id).first()
                        if sched:
                            co = s.query(Course).filter_by(id=sched.course_id).first()
                            ha = s.query(Hall).filter_by(id=sched.hall_id).first()
                            course_name = co.course_name if co else "—"
                            hall_name = ha.hall_name if ha else "—"
                    rows.append((
                        active.id,
                        doctor.full_name if doctor else "؟",
                        course_name, hall_name,
                        active.start_timestamp.strftime("%H:%M:%S"),
                        t("main.status_active"),
                        "active",
                    ))

                if not rows:
                    tree.insert("", tk.END,
                                values=("—", t("main.no_active_sessions"), "", "", "", ""))
                    return

                for r in rows:
                    tree.insert("", tk.END, values=r[:6], tags=(r[6],))
            finally:
                s.close()

        tk.Button(inner, text=t("refresh"),
                  command=refresh,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"],
                  relief="flat", cursor="hand2",
                   padx=16, pady=7, bd=0).pack(anchor=anchor_start(), pady=10)
        refresh()

    def load_recent_scans(self):
        self.clear()
        self._page_title(t("recent_scans"))
        from ui.recent_scans import RecentScansPanel
        RecentScansPanel(self.content)

    def load_live_attendance(self):
        self.clear()
        self._page_title(t("main.page_live_attendance"))
        from ui.live_attendance import LiveAttendancePanel
        LiveAttendancePanel(self.content)

    def load_alerts(self):
        self.clear()
        self._page_title(t("main.page_alerts"))
        from ui.alerts_panel import AlertsPanel
        AlertsPanel(self.content, user=self.user)

    def load_import(self):
        self.clear()
        self._page_title(t("main.page_import"))
        from ui.excel_import import ExcelImport
        ExcelImport(self.content)

    def load_settings(self):
        self.clear()
        self._page_title(t("settings"))
        from ui.settings_window import SettingsWindow
        SettingsWindow(self.content, user=self.user)

    def load_holidays(self):
        self.clear()
        self._page_title(t("holidays_panel"))
        from ui.holidays_panel import HolidaysPanel
        HolidaysPanel(self.content, user=self.user)

    def load_backup(self):
        self.clear()
        self._page_title(t("backup_panel"))
        from ui.backup_panel import BackupPanel
        BackupPanel(self.content, user=self.user)

    def load_diagnostics(self):
        self.clear()
        self._page_title(t("diagnostics.title"))
        from ui.diagnostics_panel import DiagnosticsPanel
        DiagnosticsPanel(self.content, user=self.user)

    def load_course_enrollment(self):
        self.clear()
        self._page_title(t("course_enrollment"))
        from ui.course_enrollment import CourseEnrollmentPanel
        CourseEnrollmentPanel(self.content, user=self.user)

    def load_weekly_timetable(self):
        self.clear()
        self._page_title(t("weekly_timetable"))
        from ui.weekly_timetable import WeeklyTimetablePanel
        WeeklyTimetablePanel(self.content, user=self.user)

    def load_accounts(self):
        self.clear()
        self._page_title(t("accounts.title"))
        from ui.accounts_management import AccountsPanel
        AccountsPanel(self.content, user=self.user)

    def load_notes_inbox(self):
        self.clear()
        self._page_title(t("notes.inbox_title"))
        from ui.notes_inbox import NotesInboxPanel
        NotesInboxPanel(self.content, user=self.user)

    def load_doctor_courses(self):
        self.clear()
        self._page_title(t("doctor_portal.my_courses"))
        from ui.doctor_dashboard import DoctorCoursesPanel
        DoctorCoursesPanel(self.content, user=self.user)

    def load_doctor_students(self):
        self.clear()
        self._page_title(t("doctor_portal.my_students"))
        from ui.doctor_dashboard import DoctorStudentsPanel
        DoctorStudentsPanel(self.content, user=self.user)

    def load_audit_log(self):
        self.clear()
        self._page_title(t("audit_log.title"))
        from ui.audit_log_panel import AuditLogPanel
        AuditLogPanel(self.content, user=self.user)

    def load_doctor_notes(self):
        self.clear()
        self._page_title(t("doctor_portal.my_notes"))
        from ui.doctor_notes_panel import DoctorNotesPanel
        DoctorNotesPanel(self.content, user=self.user)

    def load_doctor_qr_attendance(self):
        self.clear()
        self._page_title(t("main.nav_qr_attendance"))
        from ui.doctor_qr_attendance import DoctorQRAttendancePanel
        DoctorQRAttendancePanel(self.content, user=self.user)

    def load_student_profile_by_card(self):
        """يطلب من السكرتارية تمرير بطاقة الطالب، ثم يفتح ملف الطالب الكامل."""
        from ui.student_profile_card import StudentProfileByCard
        StudentProfileByCard(self.root).start()
