"""
لوحة آخر المسوحات (تحديث تلقائي كل ثانيتين)
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui import http_client
from ui.theme import COLORS, FONTS, create_styled_treeview, safe_after
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t


TYPE_AR = {
    "doctor":   t("scan.doctor"),
    "student":  t("scan.student"),
    "unknown":  t("scan.unknown"),
    "register": t("scan.register"),
}
TYPE_ICON = {
    "doctor":   "👨‍🏫",
    "student":  "🎓",
    "unknown":  "❓",
    "register": "📋",
}


class RecentScansPanel:
    def __init__(self, parent):
        self.parent = parent
        self._auto_refresh_id = None
        self._all_scans = []
        self._filter = "all"
        self._pending_uid = None
        self._dismissed_uid = None
        self._alive = True
        self._build()
        self.refresh()
        self._start_auto_refresh()

    # ──────────────────────────────────────────
    #  أدوات
    # ──────────────────────────────────────────
    def _make_btn(self, parent, text, cmd, bg, fg="#ffffff", hover=None):
        return tk.Button(parent, text=text, command=cmd,
                          bg=bg, fg=fg,
                          activebackground=hover or bg,
                          activeforeground=fg,
                          font=FONTS["body_bold"], relief="flat",
                          cursor="hand2", padx=14, pady=8, bd=0)

    def _selected_uid(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return str(self.tree.item(sel[0])["values"][0])

    # ──────────────────────────────────────────
    #  بناء الواجهة
    # ──────────────────────────────────────────
    def _build(self):
        c = COLORS

        # ── شريط علوي ──
        self._hdr = tk.Frame(self.parent, bg=c["bg_medium"])
        self._hdr.pack(fill=tk.X)
        tk.Frame(self._hdr, bg=c["info"], width=5).pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(self._hdr, text=t("scan.monitor_title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=14, pady=14)

        self._make_btn(self._hdr, t("scan.refresh"), self.refresh,
                        c["primary"], hover=c["primary_light"]
                        ).pack(side=side_end(), padx=16, pady=12)

        tk.Frame(self._hdr, bg=c["border"], height=1).pack(
            side=tk.BOTTOM, fill=tk.X)

        # ── بانر بطاقة غير مسجلة ──
        self._pending_banner = tk.Frame(self.parent, bg=c["warning"], pady=14)
        self._pending_uid_lbl = tk.Label(
            self._pending_banner, text="",
            font=FONTS["subtitle"], bg=c["warning"],
            fg=c["bg_medium"])
        self._pending_uid_lbl.pack(side=side_start(), padx=20)

        self._make_btn(self._pending_banner, "✖", self._dismiss_pending,
                        c["bg_medium"], fg=c["warning"]
                        ).pack(side=side_end(), padx=12)
        self._make_btn(self._pending_banner, t("scan.register_student"),
                        lambda: self._register_pending("student"),
                        c["success"], hover=c["success"]
                        ).pack(side=side_end(), padx=4)
        self._make_btn(self._pending_banner, t("scan.register_doctor"),
                        lambda: self._register_pending("doctor"),
                        c["primary"], hover=c["primary_light"]
                        ).pack(side=side_end())

        # ── مؤشر آخر مسح ──
        self._live_frame = tk.Frame(self.parent, bg=c["bg_card"], padx=18, pady=14)
        self._live_frame.pack(fill=tk.X, padx=14, pady=(12, 8))

        self._live_icon = tk.Label(self._live_frame, text="📡",
                                    font=("Segoe UI Emoji", 28),
                                    bg=c["bg_card"], fg=c["text_muted"])
        self._live_icon.pack(side=side_start(), padx=(0, 14))

        live_col = tk.Frame(self._live_frame, bg=c["bg_card"])
        live_col.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self._live_title = tk.Label(live_col, text=t("scan.waiting"),
                                     font=FONTS["subtitle"],
                                     bg=c["bg_card"], fg=c["text_secondary"],
                                     anchor=anchor_start())
        self._live_title.pack(fill=tk.X)

        self._live_sub = tk.Label(live_col, text="",
                                   font=FONTS["small"],
                                   bg=c["bg_card"], fg=c["text_muted"],
                                   anchor=anchor_start())
        self._live_sub.pack(fill=tk.X)

        # ── أزرار الفلترة ──
        fbar = tk.Frame(self.parent, bg=c["bg_dark"], padx=18, pady=8)
        fbar.pack(fill=tk.X)

        self._f_all_btn = self._make_btn(fbar, t("scan.all"), lambda: self._set_filter("all"),
                                          c["primary"], hover=c["primary_light"])
        self._f_all_btn.pack(side=side_start(), padx=(0, 6))

        self._f_unk_btn = self._make_btn(fbar, t("scan.unknown_only"),
                                          lambda: self._set_filter("unknown"),
                                          c["bg_light"], fg=c["text_secondary"],
                                          hover=c["bg_medium"])
        self._f_unk_btn.pack(side=side_start())

        self._info_lbl = tk.Label(fbar, text="",
                                   font=FONTS["small_bold"],
                                   bg=c["bg_dark"], fg=c["text_muted"])
        self._info_lbl.pack(side=side_end())

        # ── جدول المسوحات ──
        tree_outer = tk.Frame(self.parent, bg=c["bg_dark"], padx=14, pady=4)
        tree_outer.pack(fill=tk.BOTH, expand=True)

        cols = ("uid", "type_ar", "name", "timestamp", "detail")
        self.tree = create_styled_treeview(tree_outer, columns=cols,
                                            show="headings", selectmode="browse")
        col_defs = {
            "uid":       (t("scan.col_uid"),  180, "center"),
            "type_ar":   (t("scan.col_type"), 140, "center"),
            "name":      (t("scan.col_name"), 260, anchor_start()),
            "timestamp": (t("scan.col_time"), 140, "center"),
            "detail":    (t("scan.col_detail"), 180, anchor_start()),
        }
        for col, (h, w, anch) in col_defs.items():
            self.tree.heading(col, text=h, anchor=anch)
            self.tree.column(col, width=w, anchor=anch, minwidth=60)

        vsb = ttk.Scrollbar(tree_outer, orient=tk.VERTICAL,
                              command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>",
                        lambda e: self._copy_uid(self._selected_uid()))

        # tags للألوان حسب النوع
        self.tree.tag_configure("doctor",   foreground=c["info"])
        self.tree.tag_configure("student",  foreground=c["success"])
        self.tree.tag_configure("unknown",  foreground=c["error"])
        self.tree.tag_configure("register", foreground=c["warning"])

        # ── شريط الأزرار السفلي ──
        action_bar = tk.Frame(self.parent, bg=c["bg_medium"], pady=12)
        action_bar.pack(fill=tk.X)
        tk.Frame(action_bar, bg=c["border"], height=1).pack(
            side=tk.TOP, fill=tk.X)

        inner = tk.Frame(action_bar, bg=c["bg_medium"], padx=16, pady=4)
        inner.pack(fill=tk.X)

        self._count_lbl = tk.Label(inner, text="",
                                    font=FONTS["small_bold"],
                                    bg=c["bg_medium"], fg=c["text_muted"])
        self._count_lbl.pack(side=side_start(), padx=10)

        tk.Label(inner, text=t("scan.double_click_copy"),
                 font=FONTS["small"], bg=c["bg_medium"],
                 fg=c["text_muted"]).pack(side=side_start(), padx=16)

        self._make_btn(inner, t("scan.register_doctor"),
                        self._use_for_doctor, c["primary"],
                        hover=c["primary_light"]).pack(side=side_end(), padx=(0, 6))

        self._make_btn(inner, t("scan.register_student"),
                        self._use_for_student, c["success"],
                        hover=c["success"]).pack(side=side_end(), padx=(0, 6))

        self._make_btn(inner, t("scan.copy_uid_btn"),
                        lambda: self._copy_uid(self._selected_uid()),
                        c["info"], hover=c["primary_light"]
                        ).pack(side=side_end())

    # ──────────────────────────────────────────
    #  فلتر
    # ──────────────────────────────────────────
    def _set_filter(self, mode):
        c = COLORS
        self._filter = mode
        if mode == "all":
            self._f_all_btn.config(bg=c["primary"], fg="#ffffff")
            self._f_unk_btn.config(bg=c["bg_light"], fg=c["text_secondary"])
        else:
            self._f_all_btn.config(bg=c["bg_light"], fg=c["text_secondary"])
            self._f_unk_btn.config(bg=c["error"], fg="#ffffff")
        self._render()

    # ──────────────────────────────────────────
    #  بانر بطاقة غير مسجلة
    # ──────────────────────────────────────────
    def _show_pending_banner(self, uid):
        self._pending_uid = uid
        self._pending_uid_lbl.config(
            text=f'{t("scan.unregistered_card_prefix")}   {uid}   {t("scan.register_now")}')
        if not self._pending_banner.winfo_ismapped():
            self._pending_banner.pack(fill=tk.X, after=self._hdr)

    def _dismiss_pending(self):
        self._dismissed_uid = self._pending_uid
        self._pending_uid = None
        self._pending_banner.pack_forget()

    def _register_pending(self, target):
        uid = self._pending_uid
        if not uid:
            return
        self._dismiss_pending()
        self._navigate_with_uid(uid, target)

    # ──────────────────────────────────────────
    #  تسجيل من الجدول
    # ──────────────────────────────────────────
    def _use_for_doctor(self):
        uid = self._selected_uid()
        if uid:
            self._navigate_with_uid(uid, "doctor")

    def _use_for_student(self):
        uid = self._selected_uid()
        if uid:
            self._navigate_with_uid(uid, "student")

    def _navigate_with_uid(self, uid, target):
        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(uid)
            self.parent.update()
        except Exception:
            pass
        target_ar = t("scan.add_doctor") if target == "doctor" else t("scan.add_student")
        messagebox.showinfo(t("scan.uid_copied_title"),
            f'{t("scan.uid_copied_msg")}: {uid}\n\n'
            f'{t("scan.go_to")} «{target_ar}» {t("scan.paste_in_field")}.')

    def _copy_uid(self, uid):
        if not uid:
            return
        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(uid)
            self.parent.update()
            self._info_lbl.config(text=f'{t("scan.copied")} {uid}', fg=COLORS["success"])
            safe_after(self.parent, 2000, lambda: self._info_lbl.config(text=""))
        except Exception:
            pass

    # ──────────────────────────────────────────
    #  تحديث
    # ──────────────────────────────────────────
    def refresh(self):
        def do():
            try:
                r = http_client.api_get("/api/scan/recent", limit=100)
                if r.status_code == 200:
                    scans = r.json().get("scans", [])
                    if self._alive:
                        safe_after(self.parent, 0, lambda: self._apply_scans(scans))

                r = http_client.api_get("/api/scan/pending-card")
                if r.status_code == 200:
                    card = r.json().get("card")
                    if card and card.get("uid"):
                        uid = card["uid"]
                        if uid != self._dismissed_uid and self._alive:
                            safe_after(self.parent, 0,
                                lambda u=uid: self._show_pending_banner(u))
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _apply_scans(self, scans):
        if not self._alive or not self.parent.winfo_exists():
            return
        self._all_scans = scans
        if scans:
            last = scans[0]
            self._update_live(last)
        self._render()

    def _update_live(self, scan):
        if not self._alive:
            return
        try:
            if not self._live_icon.winfo_exists():
                return
        except tk.TclError:
            return
        c = COLORS
        scan_type = scan.get("scan_type", "unknown")
        name = scan.get("name") or scan.get("uid", "")
        time = scan.get("timestamp", "").split("T")[-1][:8] if "T" in scan.get("timestamp", "") else scan.get("timestamp", "")

        color_map = {
            "doctor":   c["info"],
            "student":  c["success"],
            "unknown":  c["error"],
            "register": c["warning"],
        }
        color = color_map.get(scan_type, c["text_muted"])

        self._live_icon.config(text=TYPE_ICON.get(scan_type, "📡"), fg=color)
        self._live_title.config(
            text=f"{TYPE_AR.get(scan_type, '')}: {name}",
            fg=color)
        self._live_sub.config(text=f"UID: {scan.get('uid', '')}  •  {t('scan.time_prefix')} {time}")

    def _render(self):
        if not self._alive or not self.tree.winfo_exists():
            return
        for r in self.tree.get_children():
            self.tree.delete(r)

        filtered = self._all_scans
        if self._filter == "unknown":
            filtered = [s for s in filtered if s.get("scan_type") == "unknown"]

        count_unknown = sum(1 for s in self._all_scans
                              if s.get("scan_type") == "unknown")

        for s in filtered:
            scan_type = s.get("scan_type", "unknown")
            time_str = s.get("timestamp", "")
            if "T" in time_str:
                time_str = time_str.split("T")[-1][:8]
            self.tree.insert("", tk.END,
                values=(s.get("uid", ""),
                        f"{TYPE_ICON.get(scan_type, '')}  {TYPE_AR.get(scan_type, scan_type)}",
                        s.get("name", "—"),
                        time_str,
                        s.get("detail", "")),
                tags=(scan_type,))

        total = len(self._all_scans)
        self._count_lbl.config(
            text=f'{t("scan.total_label")} {total}  •  {t("scan.unregistered_label")} {count_unknown}')

    def _start_auto_refresh(self):
        if not self._alive:
            return
        try:
            if not self.parent.winfo_exists():
                return
        except tk.TclError:
            return
        self.refresh()
        self._auto_refresh_id = safe_after(self.parent, 2000, self._start_auto_refresh)

    def __del__(self):
        self._alive = False
