import tkinter as tk
from tkinter import ttk
import threading
import time
from datetime import datetime
from ui.theme import COLORS, FONTS, apply_theme
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui import http_client
import config


class RFIDScanDialog:
    def __init__(self, parent, on_uid_callback, mode=None):
        self.parent = parent
        self.on_uid = on_uid_callback
        self._stop = False
        self.win = None
        self.mode = mode or getattr(config, "RFID_MODE", "http")
        self._anim_job = None

    def show(self):
        self._build_window()
        if self.mode == "serial" and config.SERIAL_PORT:
            threading.Thread(target=self._scan_serial_thread, daemon=True).start()
        else:
            self.mode = "http"
            threading.Thread(target=self._scan_http_thread, daemon=True).start()

    def _build_window(self):
        c = COLORS
        self.win = tk.Toplevel(self.parent)
        self.win.title(t("rfid.window_title"))
        self.win.geometry("520x400")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.configure(bg=c["bg_dark"])
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

        apply_theme(self.win)

        # ── header ──
        hdr = tk.Frame(self.win, bg=c["bg_medium"], pady=0)
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=c["primary"], width=6).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text=t("rfid.header_title"),
                 font=FONTS["title"], bg=c["bg_medium"],
                 fg=c["accent"]).pack(side=side_end(), padx=16, pady=14)
        tk.Frame(hdr, bg=c["border"], height=2).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(self.win, bg=c["bg_dark"], padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        # ── أيقونة كبيرة ──
        self.icon_lbl = tk.Label(body, text="📡",
                                  font=("Segoe UI Emoji", 48),
                                  bg=c["bg_dark"], fg=c["primary_light"])
        self.icon_lbl.pack(pady=(0, 10))

        # ── نص الحالة ──
        self.status_var = tk.StringVar(value=t("rfid.connecting"))
        self.status_lbl = tk.Label(body, textvariable=self.status_var,
                                    font=FONTS["subtitle"],
                                    bg=c["bg_dark"], fg=c["text_secondary"],
                                    wraplength=440, justify="center")
        self.status_lbl.pack(pady=4)

        # ── نص التفصيل ──
        self.detail_var = tk.StringVar(value="")
        self.detail_lbl = tk.Label(body, textvariable=self.detail_var,
                                    font=FONTS["small"],
                                    bg=c["bg_dark"], fg=c["text_muted"],
                                    justify="center")
        self.detail_lbl.pack(pady=2)

        # ── شريط التقدم ──
        self.progress = ttk.Progressbar(body, mode="indeterminate",
                                         length=440)
        self.progress.pack(pady=14)
        self.progress.start(12)

        # ── حقل الـ UID ──
        uid_frame = tk.Frame(body, bg=c["bg_card"], padx=16, pady=12,
                              relief="flat", bd=0)
        uid_frame.pack(fill=tk.X, pady=4)

        tk.Label(uid_frame, text=t("rfid.scanned_uid"),
                 font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor="center")

        self.uid_var = tk.StringVar()
        self.uid_entry = tk.Entry(uid_frame, textvariable=self.uid_var,
                                   font=FONTS["mono_large"],
                                   bg=c["bg_card"], fg=c["accent"],
                                   insertbackground=c["accent"],
                                   relief="flat", state="normal",
                                   justify="center", bd=0)
        self.uid_entry.pack(fill=tk.X, pady=4)
        self.uid_entry.bind("<KeyRelease>", self._on_manual_uid)
        self.uid_entry.bind("<Return>", lambda e: self._use_uid() if str(self.use_btn["state"]) == "normal" else None)
        self.uid_entry.focus_set()

        tk.Label(uid_frame,
                 text=t("rfid.manual_hint"),
                 font=FONTS["small"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(anchor="center")

        # ── أزرار ──
        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.pack(pady=10)

        self.use_btn = tk.Button(btn_row, text=t("rfid.use_uid"),
                                  command=self._use_uid,
                                  bg=c["success"], fg=c["bg_dark"],
                                   activebackground=c["success"],
                                  activeforeground=c["bg_dark"],
                                  font=FONTS["body_bold"],
                                  relief="flat", cursor="hand2",
                                  padx=20, pady=8, state="disabled")
        self.use_btn.pack(side=side_end(), padx=8)

        tk.Button(btn_row, text=t("rfid.cancel"),
                  command=self._cancel,
                  bg=c["error"], fg=c["text_primary"],
                  activebackground=c["error"],
                  activeforeground=c["text_primary"],
                  font=FONTS["body_bold"],
                  relief="flat", cursor="hand2",
                  padx=20, pady=8).pack(side=side_end(), padx=8)

    def _animate_waiting(self, dots=0):
        if self._stop or not self.win:
            return
        dots_str = "●" * (dots % 4 + 1) + "○" * (3 - dots % 4)
        self.detail_var.set(dots_str)
        self._anim_job = self.win.after(400, self._animate_waiting, dots + 1)

    def _scan_http_thread(self):
        self._set_status(t("rfid.connecting"), color=COLORS["text_muted"])
        try:
            http_client.api_get("/api/status")
        except Exception:
            self._set_status(f'{t("rfid.connection_failed")}', color=COLORS["error"])
            self._stop_progress()
            return

        # امسح أي UID قديم من جلسة سابقة لضمان انتظار مسح جديد
        try:
            http_client.api_post("/api/scan/clear-pending")
        except Exception:
            pass

        self._set_status(t("rfid.hold_card"), color=COLORS["primary_light"])
        if self.win:
            self.win.after(0, self._animate_waiting)

        consec_errors = 0
        start = time.time()

        while not self._stop:
            if time.time() - start > 120:
                self._set_status(t("rfid.timeout"), color=COLORS["error"])
                self._stop_progress()
                return
            try:
                r = http_client.api_get("/api/scan/pending-card")
                consec_errors = 0
                if r.status_code == 200:
                    data = r.json()
                    card = data.get("card")
                    if card and card.get("uid"):
                        uid = card["uid"].upper()
                        if self.win and not self._stop:
                            self.win.after(0, lambda u=uid: self._on_found(u))
                        return
            except Exception:
                consec_errors += 1
                if consec_errors >= 3:
                    self._set_status(t("rfid.connection_lost"), color=COLORS["error"])
                    self._stop_progress()
                    return
            time.sleep(1.0)

    def _scan_serial_thread(self):
        try:
            import serial
            ser = serial.Serial(config.SERIAL_PORT, config.SERIAL_BAUD_RATE, timeout=1)
            self._set_status(t("rfid.hold_card"), color=COLORS["primary_light"])
            if self.win:
                self.win.after(0, self._animate_waiting)

            start = time.time()
            while not self._stop:
                if time.time() - start > 60:
                    self._set_status(t("rfid.timeout_serial"), color=COLORS["error"])
                    self._stop_progress()
                    ser.close()
                    return
                if ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("CARD:"):
                        uid = line[5:].strip().upper()
                        ser.close()
                        if self.win and not self._stop:
                            self.win.after(0, lambda u=uid: self._on_found(u))
                        return
                time.sleep(0.05)
            ser.close()
        except Exception as e:
            self._set_status(f'{t("rfid.error_prefix")} {e}', color=COLORS["error"])
            self._stop_progress()

    def _on_manual_uid(self, event=None):
        import re
        raw = self.uid_var.get().strip()
        # دعم النسخ من Serial Monitor (CARD:XXXX) أو UID خام
        m = re.search(r"CARD:([0-9A-Fa-f]{6,})", raw) or \
            re.search(r"([0-9A-Fa-f]{6,})", raw)
        if m:
            extracted = m.group(1).upper()
            if extracted != raw.upper():
                self.uid_var.set(extracted)
        uid = self.uid_var.get().strip().upper()
        valid = len(uid) >= 6 and all(c in "0123456789ABCDEF:-" for c in uid)
        self.use_btn.config(state="normal" if valid else "disabled")
        if valid:
            try:
                self.icon_lbl.config(text="✅", fg=COLORS["success"])
                self.detail_var.set(f'{t("rfid.card_number")} {uid}')
                self.detail_lbl.config(fg=COLORS["accent"])
            except Exception:
                pass

    def _on_found(self, uid):
        if self._anim_job and self.win:
            try:
                self.win.after_cancel(self._anim_job)
            except Exception:
                pass

        self.progress.stop()
        self.uid_var.set(uid)

        c = COLORS
        self.status_lbl.config(text=t("rfid.read_success"), fg=c["success"],
                                font=FONTS["subtitle"])
        self.detail_var.set(f'{t("rfid.card_number")} {uid}')
        self.detail_lbl.config(fg=c["accent"])
        self.icon_lbl.config(text="✅", fg=c["success"])

        self.progress["mode"] = "determinate"
        self.progress["value"] = 100

        self.use_btn.config(state="normal")
        self.use_btn.focus_set()

        try:
            self.win.bell()
        except Exception:
            pass

        if self.win:
            self.win.after(1800, self._use_uid)

    def _use_uid(self):
        uid = self.uid_var.get()
        if uid:
            self._cancel_silent()
            self.on_uid(uid)

    def _cancel(self):
        self._stop = True
        if self._anim_job and self.win:
            try:
                self.win.after_cancel(self._anim_job)
            except Exception:
                pass
        self._cancel_silent()

    def _cancel_silent(self):
        self._stop = True
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None

    def _stop_progress(self):
        if self.win:
            self.win.after(0, lambda: self.progress.stop() if self.win else None)

    def _set_status(self, msg, color=None):
        def do():
            if self.win:
                self.status_var.set(msg)
                if color:
                    self.status_lbl.config(fg=color)
        if self.win:
            self.win.after(0, do)
