import tkinter as tk
from tkinter import ttk
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui import http_client
import threading
import hashlib


DAYS_AR = {0: "الاثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس",
            4: "الجمعة", 5: "السبت", 6: "الأحد"}


def _color_for_code(code):
    h = hashlib.md5(code.encode()).hexdigest()
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = min(255, r + 80)
    g = min(255, g + 80)
    b = min(255, b + 80)
    return f"#{r:02x}{g:02x}{b:02x}"


class WeeklyTimetablePanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        c = COLORS

        wrap = tk.Frame(parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        filter_frame = tk.Frame(wrap, bg=c["bg_dark"])
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(filter_frame, text="القاعة:", font=FONTS["body"],
                 bg=c["bg_dark"], fg=c["text_secondary"]).pack(side=side_start(), padx=(0, 4))
        self.hall_var = tk.StringVar(value="الكل")
        self.hall_combo = ttk.Combobox(filter_frame, textvariable=self.hall_var,
                                        state="readonly", width=16)
        self.hall_combo.pack(side=side_start(), padx=(0, 16))

        tk.Label(filter_frame, text="الدكتور:", font=FONTS["body"],
                 bg=c["bg_dark"], fg=c["text_secondary"]).pack(side=side_start(), padx=(0, 4))
        self.doctor_var = tk.StringVar(value="الكل")
        self.doctor_combo = ttk.Combobox(filter_frame, textvariable=self.doctor_var,
                                          state="readonly", width=20)
        self.doctor_combo.pack(side=side_start(), padx=(0, 16))

        tk.Button(filter_frame, text="تحديث", command=self._load,
                  bg=c["primary"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=12, pady=4, bd=0).pack(side=side_start())

        grid_frame = tk.Frame(wrap, bg=c["bg_dark"])
        grid_frame.pack(fill=tk.BOTH, expand=True)

        # رسم الكل (الترويسة + الشبكة) على Canvas واحد لضمان محاذاة الأعمدة
        canvas_frame = tk.Frame(grid_frame, bg=c["bg_dark"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg=c["bg_card"], highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        hsb = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=side_end(), fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # footer مع زر تحديث
        footer = tk.Frame(wrap, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        tk.Button(footer, text=" ⟳  تحديث الجدول",
                  command=self._load,
                  bg=c["primary"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=14, pady=6, bd=0
                  ).pack(side=side_end())

        self._timetable_data = []
        self._load_filters()
        self._load()
        # تحديث تلقائي كل 5 ثوانٍ (يلتقط التعديلات من إدارة المواد)
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self):
        try:
            if self.parent.winfo_exists():
                self.parent.after(5000, self._auto_refresh_tick)
        except Exception:
            pass

    def _auto_refresh_tick(self):
        try:
            if not self.parent.winfo_exists():
                return
            self._load()
            self.parent.after(5000, self._auto_refresh_tick)
        except Exception:
            pass

    def _load_filters(self):
        def do():
            try:
                halls_resp = http_client.api_get("/api/halls")
                halls = ["الكل"] + [h["hall_name"] for h in halls_resp.json().get("halls", [])]
                self.hall_combo["values"] = halls

                docs_resp = http_client.api_get("/api/doctors")
                docs = ["الكل"] + [d["full_name"] for d in docs_resp.json().get("doctors", [])]
                self.doctor_combo["values"] = docs
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _load(self):
        def do():
            try:
                params = {}
                halls_resp = http_client.api_get("/api/halls")
                halls_map = {h["hall_name"]: h["id"] for h in halls_resp.json().get("halls", [])}
                if self.hall_var.get() != "الكل" and self.hall_var.get() in halls_map:
                    params["hall_id"] = halls_map[self.hall_var.get()]

                docs_resp = http_client.api_get("/api/doctors")
                docs_map = {d["full_name"]: d["id"] for d in docs_resp.json().get("doctors", [])}
                if self.doctor_var.get() != "الكل" and self.doctor_var.get() in docs_map:
                    params["doctor_id"] = docs_map[self.doctor_var.get()]

                resp = http_client.api_get("/api/timetable", **params)
                data = resp.json()
                self._timetable_data = data.get("timetable", [])
                self._render()
            except Exception:
                pass
        threading.Thread(target=do, daemon=True).start()

    def _render(self):
        c = COLORS
        self.canvas.delete("all")
        hours = list(range(8, 22))
        cell_h = 60
        cell_w = 150
        time_w = 80
        header_h = 36
        # السبت أولاً (يمين في RTL) ثم باقي الأسبوع
        day_order = [5, 0, 1, 2, 3, 4, 6]
        day_col = {d: i for i, d in enumerate(day_order)}

        total_h = header_h + len(hours) * cell_h + 10
        total_w = time_w + len(day_order) * cell_w + 10
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

        # خلفية الترويسة
        self.canvas.create_rectangle(0, 0, total_w, header_h,
                                      fill=c["bg_medium"], outline="")
        self.canvas.create_text(time_w // 2, header_h // 2,
                                 text="الوقت", fill=c["accent"],
                                 font=FONTS["body_bold"])
        # خط فاصل أسفل الترويسة
        self.canvas.create_line(0, header_h, total_w, header_h,
                                 fill=c["accent"], width=2)

        # عناوين الأيام — مرسومة في منتصف كل عمود
        for col_idx, d in enumerate(day_order):
            x = time_w + col_idx * cell_w + cell_w // 2
            self.canvas.create_text(x, header_h // 2,
                                     text=DAYS_AR.get(d, ""),
                                     fill=c["accent"],
                                     font=FONTS["body_bold"])

        # شبكة الساعات
        for i, hour in enumerate(hours):
            y = header_h + i * cell_h
            self.canvas.create_text(time_w // 2, y + cell_h // 2,
                                     text=f"{hour:02d}:00", fill=c["text_muted"],
                                     font=FONTS["small"])
            self.canvas.create_line(0, y, total_w, y,
                                     fill=c["border"], dash=(2, 4))

        # أعمدة عمودية
        for col_idx in range(len(day_order) + 1):
            x = time_w + col_idx * cell_w
            self.canvas.create_line(x, 0, x, total_h,
                                     fill=c["border"], dash=(2, 4))

        # جمّع الجلسات حسب اليوم وحساب اللين (lane) لكل جلسة عند التداخل
        def _to_minutes(hhmm):
            parts = hhmm.split(":")
            return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)

        parsed = []
        for entry in self._timetable_data:
            d = entry["day_of_week"]
            if d not in day_col:
                continue
            try:
                sm = _to_minutes(entry["start_time"])
                em = _to_minutes(entry["end_time"])
            except Exception:
                continue
            parsed.append({**entry, "_start": sm, "_end": em, "_day": d})

        # رتّب لكل يوم ثم وزّع على lanes لمنع التداخل
        from collections import defaultdict
        by_day = defaultdict(list)
        for e in parsed:
            by_day[e["_day"]].append(e)

        lane_index_map = {}   # id(entry) -> lane_index (int)
        lane_count_map = {}   # id(entry) -> total lanes shown side-by-side
        for d, lst in by_day.items():
            lst.sort(key=lambda x: (x["_start"], x["_end"]))
            # خوارزمية باسيت: عند بدء كل جلسة، خذ أصغر lane غير مستخدم
            active = []
            for e in lst:
                active = [(end, lnx) for end, lnx in active if end > e["_start"]]
                used = {lnx for _, lnx in active}
                ln = 0
                while ln in used:
                    ln += 1
                active.append((e["_end"], ln))
                lane_index_map[id(e)] = ln
            # المجموع = أكبر lane_index + 1 من بين الجلسات المتزامنة لكل جلسة
            for e in lst:
                max_ln = lane_index_map[id(e)]
                for o in lst:
                    if o is e:
                        continue
                    if not (o["_end"] <= e["_start"] or o["_start"] >= e["_end"]):
                        max_ln = max(max_ln, lane_index_map[id(o)])
                lane_count_map[id(e)] = max_ln + 1

        lane_assignments = {k: (lane_index_map[k], lane_count_map.get(k, 1))
                             for k in lane_index_map}

        # ارسم الجلسات
        for entry in parsed:
            d = entry["_day"]
            col = day_col[d]
            start_h = entry["_start"] // 60
            end_h = (entry["_end"] + 59) // 60
            start_row = start_h - 8
            end_row = end_h - 8
            if start_row < 0 or start_row >= len(hours):
                continue

            lane_idx, lane_total = lane_assignments.get(id(entry), (0, 1))
            lane_w = (cell_w - 4) / max(1, lane_total)

            x_base = time_w + col * cell_w + 2
            x1 = int(x_base + lane_idx * lane_w)
            x2 = int(x_base + (lane_idx + 1) * lane_w - 2)
            y1 = header_h + start_row * cell_h + 2
            y2 = header_h + (end_row if end_row <= len(hours) else len(hours)) * cell_h - 2

            color = _color_for_code(entry.get("course_code", ""))
            self.canvas.create_rectangle(x1, y1, x2, y2,
                                          fill=color, outline="", width=0)
            cx = (x1 + x2) // 2
            self.canvas.create_text(cx, y1 + 14,
                                     text=entry.get("course_code", ""),
                                     fill="#000000", font=FONTS["small_bold"])
            self.canvas.create_text(cx, y1 + 30,
                                     text=entry.get("doctor_name", ""),
                                     fill="#333333", font=FONTS["small"])
            self.canvas.create_text(cx, y1 + 46,
                                     text=entry.get("hall_name", ""),
                                     fill="#555555", font=FONTS["small"])
