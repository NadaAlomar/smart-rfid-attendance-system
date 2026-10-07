"""Doctor's QR-based attendance panel.

Flow:
  1. Doctor picks course (+ optional hall) → presses Start.
  2. Backend creates a QR session valid for 5 minutes; token rotates every
     ~8 seconds. UI polls /api/doctor/qr/current/<id> every second to refresh
     the displayed QR image and the live counters.
  3. Students scan the QR with their phone → it opens the public web page
     served by the API → they enter academic_id → attendance recorded.
  4. Doctor can Stop early; otherwise the session auto-closes after 5 min.
"""
import io
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, pad_x
from ui.i18n import t
from ui import http_client


class DoctorQRAttendancePanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        self.qr_session_id = None
        self.attendance_session_id = None
        self.token = None
        self.checkin_url = None
        self._poll_job = None
        self._image_cache_token = None
        self._tk_qr_image = None
        self._build()
        self._load_lookups()

    # ─────────────────────────────────────────────────────────────────
    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=20, pady=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── Top: course/hall pickers + Start/Stop ──
        top = tk.Frame(wrap, bg=c["bg_card"], padx=14, pady=12)
        top.pack(fill=tk.X)

        tk.Label(top, text="بدء حضور بـ QR",
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"]).grid(row=0, column=0, columnspan=4,
                                       sticky="w", pady=(0, 8))

        tk.Label(top, text="المادة:", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]
                 ).grid(row=1, column=0, sticky="e", padx=pad_x(0, 8), pady=6)
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(top, textvariable=self.course_var,
                                          state="readonly", width=42)
        self.course_combo.grid(row=1, column=1, sticky="ew", pady=6, padx=pad_x(0, 16))

        tk.Label(top, text="القاعة (اختياري):", font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]
                 ).grid(row=1, column=2, sticky="e", padx=pad_x(0, 8), pady=6)
        self.hall_var = tk.StringVar()
        self.hall_combo = ttk.Combobox(top, textvariable=self.hall_var,
                                        state="readonly", width=22)
        self.hall_combo.grid(row=1, column=3, sticky="ew", pady=6)

        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        btn_row = tk.Frame(top, bg=c["bg_card"])
        btn_row.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.start_btn = tk.Button(btn_row, text="▶  بدء الجلسة",
                                    command=self._start,
                                    bg=c["success"], fg="#ffffff",
                                    font=FONTS["body_bold"], relief="flat",
                                    cursor="hand2", padx=18, pady=8, bd=0)
        self.start_btn.pack(side=side_start())
        self.stop_btn = tk.Button(btn_row, text="■  إيقاف",
                                   command=self._stop,
                                   bg=c["error"], fg="#ffffff",
                                   font=FONTS["body_bold"], relief="flat",
                                   cursor="hand2", padx=18, pady=8, bd=0,
                                   state="disabled")
        self.stop_btn.pack(side=side_start(), padx=pad_x(8, 0))

        # ── Body: split QR panel (left) + attendance list (right) ──
        body = tk.Frame(wrap, bg=c["bg_dark"])
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        # left: QR card
        self.qr_card = tk.Frame(body, bg=c["bg_card"], padx=14, pady=14)
        self.qr_card.pack(side=side_start(), fill=tk.BOTH, expand=True)

        self.qr_status = tk.Label(self.qr_card,
                                   text="اضغط 'بدء الجلسة' لإنشاء QR",
                                   font=FONTS["body_bold"], bg=c["bg_card"],
                                   fg=c["text_muted"])
        self.qr_status.pack(pady=(0, 8))

        # حاوية مع خلفية بيضاء عريضة لزيادة التباين عند قراءة الكاميرا
        qr_holder = tk.Frame(self.qr_card, bg="#ffffff", padx=10, pady=10)
        qr_holder.pack(pady=8)
        self.qr_image_lbl = tk.Label(qr_holder, bg="#ffffff",
                                      width=30, height=15, cursor="hand2")
        self.qr_image_lbl.pack()
        # نقرة على الـ QR تفتح عرض ملء الشاشة لقراءة أوضح من بعيد
        self.qr_image_lbl.bind("<Button-1>", lambda e: self._show_fullscreen())

        tk.Button(self.qr_card, text="🔍  عرض كبير (ملء الشاشة)",
                  command=self._show_fullscreen,
                  bg=c["info"], fg="#ffffff", font=FONTS["small_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=6, bd=0
                  ).pack(pady=(2, 4))

        self.qr_meta = tk.Label(self.qr_card, text="",
                                 font=FONTS["small"], bg=c["bg_card"],
                                 fg=c["text_muted"], justify="center")
        self.qr_meta.pack(pady=4)

        self.qr_url_lbl = tk.Label(self.qr_card, text="",
                                    font=FONTS["mono"], bg=c["bg_card"],
                                    fg=c["accent"], wraplength=360,
                                    justify="center")
        self.qr_url_lbl.pack(pady=4)

        self.timer_lbl = tk.Label(self.qr_card, text="",
                                   font=FONTS["title"], bg=c["bg_card"],
                                   fg=c["primary_light"])
        self.timer_lbl.pack(pady=(8, 0))

        tk.Label(self.qr_card,
                 text="ينتجد الرمز كل بضع ثوانٍ — تصوير الرمز لا يفيد لأنه ينتهي بسرعة.",
                 font=FONTS["small"], bg=c["bg_card"],
                 fg=c["text_muted"], wraplength=380,
                 justify="center").pack(pady=(8, 0))

        # right: live attendance list
        right = tk.Frame(body, bg=c["bg_card"], padx=14, pady=14)
        right.pack(side=side_start(), fill=tk.BOTH, expand=True,
                   padx=pad_x(14, 0))

        tk.Label(right, text="الحاضرون الآن",
                 font=FONTS["section"], bg=c["bg_card"],
                 fg=c["accent"]).pack(anchor=anchor_start(), pady=(0, 6))

        self.count_lbl = tk.Label(right, text="0", font=FONTS["title"],
                                   bg=c["bg_card"], fg=c["success"])
        self.count_lbl.pack(anchor=anchor_start())

        cols = ("aid", "name", "t")
        self.list_tree = create_styled_treeview(right, columns=cols,
                                                 show="headings", height=14)
        for col, h, w_ in [("aid", "الرقم", 100),
                            ("name", "الاسم", 260),
                            ("t", "الوقت", 100)]:
            self.list_tree.heading(col, text=h)
            self.list_tree.column(col, width=w_, anchor="center")
        self.list_tree.pack(fill=tk.BOTH, expand=True, pady=8)

    # ─────────────────────────────────────────────────────────────────
    def _load_lookups(self):
        def do():
            try:
                r = http_client.api_get("/api/doctor/me/courses")
                data = r.json()
                self._courses = data.get("courses", []) if data.get("success") else []
            except Exception:
                self._courses = []
            try:
                r = http_client.api_get("/api/doctor/qr/halls")
                data = r.json()
                self._halls = data.get("halls", []) if data.get("success") else []
            except Exception:
                self._halls = []

            def update():
                self.course_combo["values"] = [
                    f"{c['course_code']} — {c['course_name']}" for c in self._courses]
                self.hall_combo["values"] = ["—"] + [h["hall_name"] for h in self._halls]
                if self._courses:
                    self.course_combo.current(0)
                self.hall_combo.current(0)
            self.parent.after(0, update)
        threading.Thread(target=do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────
    def _start(self):
        idx = self.course_combo.current()
        if idx < 0 or idx >= len(getattr(self, "_courses", [])):
            messagebox.showwarning(t("warning"), "اختر مادة أولاً", parent=self.parent)
            return
        course_id = self._courses[idx]["id"]
        hall_idx = self.hall_combo.current()
        hall_id = None
        if hall_idx > 0 and hall_idx - 1 < len(getattr(self, "_halls", [])):
            hall_id = self._halls[hall_idx - 1]["id"]

        def do():
            try:
                r = http_client.api_post("/api/doctor/qr/start",
                                         json_body={"course_id": course_id,
                                                    "hall_id": hall_id})
                data = r.json()
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), str(e), parent=self.parent))
                return
            if not data.get("success"):
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), data.get("error", "فشل"),
                    parent=self.parent))
                return
            self.qr_session_id = data["qr_session_id"]
            self.attendance_session_id = data["attendance_session_id"]
            self.token = data["token"]
            self.checkin_url = data["checkin_url"]

            def update():
                self.start_btn.config(state="disabled")
                self.stop_btn.config(state="normal")
                self.qr_status.config(text="الجلسة فعّالة — اطلب من الطلاب مسح الرمز",
                                       fg=COLORS["success"])
                self._begin_polling()
            self.parent.after(0, update)
        threading.Thread(target=do, daemon=True).start()

    def _stop(self):
        if not self.qr_session_id:
            return
        if not messagebox.askyesno("تأكيد", "إيقاف جلسة QR الآن؟",
                                    parent=self.parent):
            return
        qid = self.qr_session_id

        def do():
            try:
                http_client.api_post(f"/api/doctor/qr/stop/{qid}")
            except Exception:
                pass
            self.parent.after(0, self._reset_idle)
        threading.Thread(target=do, daemon=True).start()

    def _reset_idle(self):
        if self._poll_job:
            try:
                self.parent.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        self.qr_session_id = None
        self.token = None
        self.checkin_url = None
        try:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.qr_status.config(text="تم إيقاف الجلسة", fg=COLORS["text_muted"])
            self.qr_image_lbl.config(image="", text="")
            self.qr_meta.config(text="")
            self.qr_url_lbl.config(text="")
            self.timer_lbl.config(text="")
        except Exception:
            pass
        self._qr_image_raw = None
        if getattr(self, "_fs_win", None):
            try:
                if self._fs_win.winfo_exists():
                    self._fs_win.destroy()
            except Exception:
                pass
            self._fs_win = None

    # ─────────────────────────────────────────────────────────────────
    def _begin_polling(self):
        self._poll_once()

    def _poll_once(self):
        if not self.qr_session_id:
            return
        qid = self.qr_session_id

        def do():
            try:
                r = http_client.api_get(f"/api/doctor/qr/current/{qid}")
                if r.status_code == 410:
                    # expired
                    self.parent.after(0, self._on_expired)
                    return
                data = r.json()
            except Exception:
                data = None
            if not data or not data.get("success"):
                # transient error — try again
                self.parent.after(0, self._schedule_next)
                return
            self.parent.after(0, lambda: self._apply_state(data))
        threading.Thread(target=do, daemon=True).start()

    def _on_expired(self):
        try:
            self.qr_status.config(text="انتهت مدة الجلسة (5 دقائق)",
                                   fg=COLORS["warning"])
        except Exception:
            pass
        self._reset_idle()

    def _schedule_next(self):
        try:
            self._poll_job = self.parent.after(1000, self._poll_once)
        except Exception:
            self._poll_job = None

    def _apply_state(self, data):
        if not self.qr_session_id:
            return
        token = data.get("token")
        checkin_url = data.get("checkin_url", "")
        sec_left = int(data.get("session_seconds_left", 0))
        tok_left = int(data.get("token_seconds_left", 0))
        rot = int(data.get("rotation_seconds", 8))
        count = int(data.get("attendance_count", 0))

        self.checkin_url = checkin_url
        if token and token != self.token:
            self.token = token
        # تحديث الصورة عند تبديل الرمز فقط
        if token and token != self._image_cache_token:
            self._image_cache_token = token
            self._refresh_qr_image()

        mm, ss = divmod(max(0, sec_left), 60)
        self.timer_lbl.config(text=f"{mm:02d}:{ss:02d}")
        self.qr_meta.config(
            text=f"تجديد الرمز خلال {tok_left}ث • كل {rot}ث")
        self.qr_url_lbl.config(text=checkin_url)
        self.count_lbl.config(text=str(count))
        self._refresh_attendance_list()
        self._schedule_next()

    def _refresh_qr_image(self):
        qid = self.qr_session_id

        def do():
            try:
                r = http_client.api_get_raw(f"/api/doctor/qr/image/{qid}")
                if r.status_code != 200:
                    return
                raw = r.content
                try:
                    from PIL import Image, ImageTk
                except ImportError:
                    return
                img = Image.open(io.BytesIO(raw))
                self._qr_image_raw = img.copy()  # احتفظ بالأصل للعرض الكبير
                img_small = img.resize((420, 420), Image.NEAREST)
                tk_img = ImageTk.PhotoImage(img_small)

                def show():
                    if not self.qr_session_id:
                        return
                    self._tk_qr_image = tk_img
                    self.qr_image_lbl.config(image=tk_img, text="")
                    # حدّث نافذة الـ fullscreen إذا مفتوحة
                    self._update_fullscreen()
                self.parent.after(0, show)
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _refresh_attendance_list(self):
        sid = self.attendance_session_id
        if not sid:
            return

        def do():
            try:
                r = http_client.api_get(f"/api/attendance/session/{sid}")
                data = r.json()
            except Exception:
                return
            if not data or not data.get("success"):
                return
            present = data.get("present", [])

            def update():
                if not self.list_tree.winfo_exists():
                    return
                self.list_tree.delete(*self.list_tree.get_children())
                for r in present:
                    tm = r.get("check_in_time", "")
                    if "T" in tm:
                        tm = tm.split("T")[1][:8]
                    self.list_tree.insert("", tk.END, values=(
                        r.get("academic_id", ""), r.get("student_name", ""), tm,
                    ))
            self.parent.after(0, update)
        threading.Thread(target=do, daemon=True).start()

    # ── Fullscreen QR viewer ────────────────────────────────────────────
    def _show_fullscreen(self):
        """يفتح نافذة كبيرة بحجم الشاشة تعرض الـ QR لقراءته من بعيد."""
        if getattr(self, "_qr_image_raw", None) is None:
            return
        if getattr(self, "_fs_win", None) and self._fs_win.winfo_exists():
            try:
                self._fs_win.lift()
            except Exception:
                pass
            return

        self._fs_win = tk.Toplevel(self.parent)
        self._fs_win.title("QR — عرض كبير")
        self._fs_win.configure(bg="#ffffff")
        # ملء الشاشة
        try:
            self._fs_win.state("zoomed")
        except Exception:
            sw = self._fs_win.winfo_screenwidth()
            sh = self._fs_win.winfo_screenheight()
            self._fs_win.geometry(f"{sw}x{sh}+0+0")

        self._fs_win.bind("<Escape>", lambda e: self._fs_win.destroy())
        self._fs_win.protocol("WM_DELETE_WINDOW",
                               lambda: self._fs_win.destroy())

        top = tk.Frame(self._fs_win, bg="#ffffff")
        top.pack(fill=tk.X, pady=(10, 0))
        tk.Label(top, text="امسح الرمز بكاميرا الهاتف لتسجيل الحضور",
                 font=("Segoe UI", 20, "bold"),
                 bg="#ffffff", fg="#111").pack()
        tk.Label(top, text="(اضغط Esc للخروج)  —  الرمز يتجدّد كل بضع ثوان",
                 font=("Segoe UI", 12),
                 bg="#ffffff", fg="#666").pack(pady=(2, 6))

        self._fs_qr_lbl = tk.Label(self._fs_win, bg="#ffffff")
        self._fs_qr_lbl.pack(expand=True)

        self._fs_timer_lbl = tk.Label(self._fs_win, text="",
                                       font=("Segoe UI", 22, "bold"),
                                       bg="#ffffff", fg="#8b5cf6")
        self._fs_timer_lbl.pack(pady=(0, 10))

        self._update_fullscreen()

    def _update_fullscreen(self):
        if not getattr(self, "_fs_win", None):
            return
        try:
            if not self._fs_win.winfo_exists():
                self._fs_win = None
                return
        except Exception:
            self._fs_win = None
            return
        if getattr(self, "_qr_image_raw", None) is None:
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return
        # حجم QR = أصغر بُعد للشاشة - هامش
        self._fs_win.update_idletasks()
        sh = self._fs_win.winfo_height()
        sw = self._fs_win.winfo_width()
        side = max(300, min(sw, sh) - 180)
        img = self._qr_image_raw.resize((side, side), Image.NEAREST)
        self._tk_fs_image = ImageTk.PhotoImage(img)
        self._fs_qr_lbl.config(image=self._tk_fs_image)
        # حدّث المؤقّت
        try:
            self._fs_timer_lbl.config(text=self.timer_lbl.cget("text") or "")
        except Exception:
            pass
