import tkinter as tk
from tkinter import ttk
import threading
import time
from ui import http_client
from ui.theme import COLORS, FONTS, safe_after
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui import client_time


class LiveAttendancePanel:
    POLL_INTERVAL_MS = 1000
    HIGHLIGHT_MS = 3000

    def __init__(self, parent):
        self.parent = parent
        self._last_counter = -1
        self._last_attendances = {}
        self._highlight_jobs = {}
        self._alive = True
        self._poll_job = None
        self._build()
        self._poll()

    def _build(self):
        c = COLORS

        hdr = tk.Frame(self.parent, bg=c["bg_medium"])
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["success"], width=5).pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(hdr, text=t("live.page_title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_start(), padx=16, pady=14)

        self.live_dot = tk.Label(hdr, text=t("live.live"),
                                   font=FONTS["small_bold"],
                                   bg=c["bg_medium"], fg=c["success"])
        self.live_dot.pack(side=side_end(), padx=18)

        self.last_update_lbl = tk.Label(hdr, text="",
                                          font=FONTS["small"],
                                          bg=c["bg_medium"], fg=c["text_muted"])
        self.last_update_lbl.pack(side=side_end(), padx=10)

        tk.Frame(hdr, bg=c["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        body_outer = tk.Frame(self.parent, bg=c["bg_dark"])
        body_outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(body_outer, bg=c["bg_dark"],
                            highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(body_outer, orient=tk.VERTICAL,
                              command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scroll_inner = tk.Frame(canvas, bg=c["bg_dark"], padx=16, pady=14)
        self._win_id = canvas.create_window((0, 0),
                                              window=self.scroll_inner,
                                              anchor="nw")
        self.scroll_inner.bind("<Configure>",
                                lambda e: canvas.configure(
                                    scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig(self._win_id, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self.scroll_inner.bind("<Enter>",
                                lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        self.scroll_inner.bind("<Leave>",
                                lambda e: canvas.unbind_all("<MouseWheel>"))

        self._canvas = canvas

        self._empty_label = tk.Label(
            self.scroll_inner,
            text=t("live.no_sessions"),
            font=FONTS["section"], bg=c["bg_dark"],
            fg=c["text_muted"], justify="center")
        self._empty_label.pack(pady=80)

        self.bottom = tk.Frame(self.parent, bg=c["bg_medium"])
        self.bottom.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(self.bottom, bg=c["border"], height=1).pack(side=tk.TOP, fill=tk.X)

        stats_inner = tk.Frame(self.bottom, bg=c["bg_medium"], padx=20, pady=10)
        stats_inner.pack(fill=tk.X)

        self.stats_lbl = tk.Label(stats_inner, text="",
                                    font=FONTS["small_bold"],
                                    bg=c["bg_medium"], fg=c["text_secondary"])
        self.stats_lbl.pack(side=side_start())

        def _manual_refresh():
            self._last_counter = -1
            self._poll()

        tk.Button(stats_inner, text=f'⟳  {t("scan.refresh")}',
                  command=_manual_refresh,
                  bg=c["primary"], fg="#ffffff",
                  activebackground=c["primary_light"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=16, pady=6, bd=0
                  ).pack(side=side_end())

    def _poll(self):
        if not self._alive:
            return

        def fetch():
            try:
                r = http_client.api_get("/api/live/counter")
                if r.status_code != 200:
                    return
                counter = r.json().get("counter", 0)
                if counter != self._last_counter:
                    self._last_counter = counter
                    r2 = http_client.api_get("/api/live/state")
                    if r2.status_code == 200:
                        data = r2.json()
                        if self._alive:
                            safe_after(self.parent, 0, lambda: self._update_ui(data))
                else:
                    if self._alive:
                        safe_after(self.parent, 0, self._tick_timer)
            except Exception:
                if self._alive:
                    safe_after(self.parent, 0, self._set_offline)

        threading.Thread(target=fetch, daemon=True).start()
        if self._alive:
            self._poll_job = safe_after(self.parent, self.POLL_INTERVAL_MS, self._poll)

    def _set_offline(self):
        try:
            if self.live_dot.winfo_exists():
                self.live_dot.config(text=t("live.offline"), fg=COLORS["error"])
        except tk.TclError:
            pass

    def _tick_timer(self):
        if not self._alive:
            return
        try:
            if not self.scroll_inner.winfo_exists():
                return
            for w in self.scroll_inner.winfo_children():
                if hasattr(w, "_elapsed_lbl") and hasattr(w, "_elapsed_base"):
                    if w.winfo_exists():
                        elapsed = w._elapsed_base + int(time.monotonic() - w._elapsed_started_at)
                        w._elapsed_lbl.config(text=self._fmt_elapsed(elapsed))
        except tk.TclError:
            return

    def _fmt_elapsed(self, sec):
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"

    def _update_ui(self, data):
        if not self._alive:
            return
        try:
            if not self.scroll_inner.winfo_exists():
                return
        except tk.TclError:
            return
        c = COLORS
        self.live_dot.config(text=t("live.live"), fg=c["success"])
        self.last_update_lbl.config(text=f'{t("live.last_update")} {client_time.now().strftime("%H:%M:%S")}')

        for w in self.scroll_inner.winfo_children():
            w.destroy()

        sessions = data.get("active_sessions", [])

        if not sessions:
            self._empty_label = tk.Label(
                self.scroll_inner,
                text=t("live.no_sessions"),
                font=FONTS["section"], bg=c["bg_dark"],
                fg=c["text_muted"], justify="center")
            self._empty_label.pack(pady=80)

            self.stats_lbl.config(text=f'{t("live.active_sessions")} 0  •  {t("live.total_attendance")} 0')
            self._last_attendances = {}
            return

        total_attendance = 0
        new_attendances = {}

        for sess in sessions:
            sid = sess["session_id"]
            attendances = sess.get("attendances", [])
            student_ids = {a["student_id"] for a in attendances}
            previous = self._last_attendances.get(sid, set())

            new_ids = student_ids - previous
            new_attendances[sid] = student_ids
            total_attendance += len(attendances)

            self._render_session_card(sess, new_ids)

        self._last_attendances = new_attendances

        self.stats_lbl.config(
            text=f'{t("live.active_sessions")} {len(sessions)}  •  {t("live.total_attendance")} {total_attendance}')

    def _render_session_card(self, sess, new_ids):
        c = COLORS

        card = tk.Frame(self.scroll_inner, bg=c["bg_card"])
        card.pack(fill=tk.X, pady=(0, 14))
        card._start_dt = self._parse_time(sess.get("start_time"))
        tk.Frame(card, bg=c["success"], height=4).pack(fill=tk.X)

        head = tk.Frame(card, bg=c["bg_card"], padx=18, pady=12)
        head.pack(fill=tk.X)

        right_col = tk.Frame(head, bg=c["bg_card"])
        right_col.pack(side=side_start(), fill=tk.X, expand=True)

        tk.Label(right_col,
                 text=f"👨‍🏫  {sess['doctor_name']}",
                 font=FONTS["subtitle"], bg=c["bg_card"],
                 fg=c["accent"], anchor=anchor_start()).pack(fill=tk.X)

        info_text = f"📚  {sess.get('course_code', '')} — {sess['course_name']}"
        if sess.get("hall_name") and sess["hall_name"] != "—":
            info_text += f"   🏛 {sess['hall_name']}"
        tk.Label(right_col, text=info_text,
                 font=FONTS["body"], bg=c["bg_card"],
                 fg=c["text_secondary"], anchor=anchor_start()).pack(fill=tk.X)

        left_col = tk.Frame(head, bg=c["bg_card"])
        left_col.pack(side=side_end())

        elapsed = max(0, int(sess.get("elapsed_seconds", 0) or 0))
        elapsed_lbl = tk.Label(left_col, text=self._fmt_elapsed(elapsed),
                                 font=FONTS["mono_large"], bg=c["bg_card"],
                                 fg=c["info"])
        elapsed_lbl.pack(anchor=anchor_end())
        card._elapsed_lbl = elapsed_lbl
        card._elapsed_base = elapsed
        card._elapsed_started_at = time.monotonic()

        count = sess.get("attendance_count", 0)
        tk.Label(left_col,
                 text=f'{t("live.attendance_label")} {count}',
                 font=FONTS["small_bold"], bg=c["bg_card"],
                 fg=c["success"]).pack(anchor=anchor_end())

        tk.Frame(card, bg=c["border_light"], height=1).pack(
            fill=tk.X, padx=18)

        if not sess.get("attendances"):
            tk.Label(card, text=t("live.waiting"),
                     font=FONTS["body"], bg=c["bg_card"],
                     fg=c["text_muted"], anchor=anchor_start(),
                     padx=18, pady=14).pack(fill=tk.X)
            return

        list_frame = tk.Frame(card, bg=c["bg_card"], padx=18, pady=10)
        list_frame.pack(fill=tk.X)

        for idx, att in enumerate(sess["attendances"]):
            is_new = att["student_id"] in new_ids
            row_bg = c["bg_card2"] if not is_new else c["success"]
            row_fg = c["text_primary"] if not is_new else "#ffffff"

            row = tk.Frame(list_frame, bg=row_bg, padx=12, pady=8)
            row.pack(fill=tk.X, pady=2)

            tk.Label(row, text="✓",
                     font=FONTS["body_bold"], bg=row_bg,
                     fg=row_fg if is_new else c["success"]).pack(side=side_start(), padx=(0, 8))

            tk.Label(row, text=att["name"],
                     font=FONTS["body_bold"], bg=row_bg, fg=row_fg,
                     anchor=anchor_start()).pack(side=side_start(), fill=tk.X, expand=True)

            t_val = att.get("timestamp", "")
            if "T" in t_val:
                t_val = t_val.split("T")[-1][:8]
            tk.Label(row, text=t_val,
                     font=FONTS["mono"], bg=row_bg, fg=row_fg).pack(side=side_end())

            tk.Label(row, text=att.get("academic_id", ""),
                     font=FONTS["small"], bg=row_bg, fg=row_fg
                     ).pack(side=side_end(), padx=10)

            if is_new:
                row_widgets = [row] + list(row.winfo_children())
                def reset_color(widgets=row_widgets, bg=c["bg_card2"], fg=c["text_primary"]):
                    for w in widgets:
                        try:
                            w.config(bg=bg)
                            if isinstance(w, tk.Label):
                                if w.cget("text") == "✓":
                                    w.config(fg=COLORS["success"])
                                else:
                                    w.config(fg=fg)
                        except Exception:
                            pass
                safe_after(self.parent, self.HIGHLIGHT_MS, reset_color)

    def _parse_time(self, time_str):
        if not time_str:
            return client_time.now()
        try:
            h, m, s = time_str.split(":")
            now = client_time.now()
            return now.replace(hour=int(h), minute=int(m), second=int(s),
                                microsecond=0)
        except Exception:
            return client_time.now()

    def stop(self):
        self._alive = False
        if self._poll_job:
            try:
                self.parent.after_cancel(self._poll_job)
            except Exception:
                pass

    def __del__(self):
        self._alive = False
