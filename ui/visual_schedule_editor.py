"""Visual weekly schedule grid editor.

Layout: 7 day columns × N time-slot rows. Each cell shows the course assigned
at that day/time (if any). Left-click on an empty cell opens an "Add" dialog;
right-click on an existing cell opens a context menu (Edit / Delete).
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui import http_client
import threading
import hashlib
from datetime import datetime
from ui.theme import COLORS, FONTS
from ui.rtl_helper import side_start, side_end, text_justify, pad_x, rtl_columns
from ui.i18n import t

# Days arranged Sat → Fri (Arabic/local week convention).
# Underlying day_of_week ints (0=Mon … 6=Sun).
DAYS_ORDER = [5, 6, 0, 1, 2, 3, 4]  # Sat, Sun, Mon, Tue, Wed, Thu, Fri
DAY_LABEL_KEYS = [
    "course.day_mon", "course.day_tue", "course.day_wed",
    "course.day_thu", "course.day_fri", "course.day_sat",
    "course.day_sun",
]

# Default time slots
TIME_SLOTS = [
    ("08:00", "09:30"),
    ("09:30", "11:00"),
    ("11:00", "12:30"),
    ("12:30", "14:00"),
    ("14:00", "15:30"),
    ("15:30", "17:00"),
]


def _color_for_course(course_id):
    """Deterministic, soft-pastel color from course id."""
    h = hashlib.md5(str(course_id).encode()).hexdigest()
    r = int(h[0:2], 16) // 2 + 80   # 80-207
    g = int(h[2:4], 16) // 2 + 80
    b = int(h[4:6], 16) // 2 + 80
    return f"#{r:02x}{g:02x}{b:02x}"


def _time_in_slot(start_str, end_str, slot_start, slot_end):
    """Return True if the schedule's time range overlaps with the slot range."""
    try:
        s_start = datetime.strptime(start_str[:5], "%H:%M").time()
        s_end = datetime.strptime(end_str[:5], "%H:%M").time()
        slot_s = datetime.strptime(slot_start, "%H:%M").time()
        slot_e = datetime.strptime(slot_end, "%H:%M").time()
        return s_start < slot_e and s_end > slot_s
    except Exception:
        return False


class VisualScheduleEditor:
    def __init__(self, parent):
        self.parent = parent
        self._schedules = []
        self._courses = []
        self._halls = []
        self._cells = {}    # {(day_idx, slot_idx): frame_widget}
        self._build()
        self.refresh()

    def _build(self):
        c = COLORS
        wrap = tk.Frame(self.parent, bg=c["bg_dark"], padx=16, pady=12)
        wrap.pack(fill=tk.BOTH, expand=True)

        # ── Toolbar ──
        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(toolbar, text=t("course.visual_schedule_tab"),
                 font=FONTS["section"], bg=c["bg_dark"],
                 fg=c["accent"]).pack(side=side_start())

        tk.Button(toolbar, text=f"⟳ {t('refresh')}",
                  command=self.refresh,
                  bg=c["bg_light"], fg=c["text_primary"],
                  font=FONTS["small_bold"], relief="flat",
                  cursor="hand2", padx=10, pady=4, bd=0
                  ).pack(side=side_end())

        tk.Label(toolbar, text=t("course.weekly_repeat_note"),
                 font=FONTS["small"], bg=c["bg_dark"],
                 fg=c["text_muted"]).pack(side=side_end(), padx=8)

        # ── Scrollable grid ──
        grid_container = tk.Frame(wrap, bg=c["bg_dark"])
        grid_container.pack(fill=tk.BOTH, expand=True)

        self.grid_canvas = tk.Canvas(grid_container, bg=c["bg_dark"],
                                    highlightthickness=0)
        self.grid_vscroll = ttk.Scrollbar(grid_container, orient="vertical",
                                          command=self.grid_canvas.yview)
        self.grid_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.grid_canvas.configure(yscrollcommand=self.grid_vscroll.set)

        self.grid_frame = tk.Frame(self.grid_canvas, bg=c["bg_dark"])
        self._canvas_window = self.grid_canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.grid_canvas.configure(
                scrollregion=self.grid_canvas.bbox("all")))

        def _on_canvas_configure(event):
            self.grid_canvas.itemconfigure(self._canvas_window,
                                           width=event.width)
        self.grid_canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            self.grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.grid_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.grid_frame.bind("<MouseWheel>", _on_mousewheel)

    def _draw_grid(self):
        c = COLORS

        # clear previous
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self._cells = {}

        # Headers row 0: time column + 7 days
        tk.Label(self.grid_frame, text="", bg=c["bg_dark"]).grid(
            row=0, column=0, padx=1, pady=1, sticky="nsew")
        days_order = list(rtl_columns(*DAYS_ORDER))
        for col, day_idx in enumerate(days_order, start=1):
            tk.Label(self.grid_frame, text=t(DAY_LABEL_KEYS[day_idx]),
                     font=FONTS["small_bold"], bg=c["bg_medium"],
                     fg=c["accent"], pady=8
                     ).grid(row=0, column=col, padx=1, pady=1, sticky="nsew")
            self.grid_frame.columnconfigure(col, weight=1, minsize=120)

        # Rows for each time slot
        for r, (slot_start, slot_end) in enumerate(TIME_SLOTS, start=1):
            tk.Label(self.grid_frame, text=f"{slot_start}\n{slot_end}",
                     font=FONTS["small_bold"], bg=c["bg_medium"],
                     fg=c["info"], padx=10, pady=6
                     ).grid(row=r, column=0, padx=1, pady=1, sticky="nsew")
            self.grid_frame.rowconfigure(r, weight=1, minsize=70)

            for col, day_idx in enumerate(days_order, start=1):
                # find schedule(s) covering this cell
                hits = [s for s in self._schedules
                        if s["day_of_week"] == day_idx
                        and _time_in_slot(s["start_time"], s["end_time"], slot_start, slot_end)]

                cell_frame = tk.Frame(self.grid_frame, bg=c["bg_card"], padx=4, pady=4)
                cell_frame.grid(row=r, column=col, padx=1, pady=1, sticky="nsew")

                if hits:
                    if len(hits) == 1:
                        s = hits[0]
                        color = _color_for_course(s["course_id"])
                        cell_frame.configure(bg=color)
                        tk.Label(cell_frame, text=s["course_code"],
                                 font=FONTS["body_bold"], bg=color, fg=c["text_primary"]
                                 ).pack(anchor="w")
                        tk.Label(cell_frame, text=s.get("course_name", ""),
                                 font=FONTS["small"], bg=color, fg=c["text_primary"],
                                 wraplength=110, justify="right"
                                 ).pack(anchor="w")
                        tk.Label(cell_frame, text=f'{s.get("hall_name","")}',
                                 font=("Segoe UI", 8), bg=color, fg=c["text_primary"]
                                 ).pack(anchor="w")
                        tk.Label(cell_frame,
                                 text=f'{s["start_time"][:5]}-{s["end_time"][:5]}',
                                 font=("Segoe UI", 8), bg=color, fg=c["text_primary"]
                                 ).pack(anchor="w")
                        edit_btn = tk.Label(cell_frame, text="✎",
                                            font=("Segoe UI", 10, "bold"),
                                            bg=color, fg=c["warning"], cursor="hand2",
                                            padx=4)
                        edit_btn.place(relx=0.0, rely=0.0, anchor="nw")
                        edit_btn.bind("<Button-1>",
                                      lambda e, sched=s: self._edit_dialog(sched))
                        delete_btn = tk.Label(cell_frame, text="✖",
                                              font=("Segoe UI", 10, "bold"),
                                              bg=color, fg=c["error"], cursor="hand2",
                                              padx=4)
                        delete_btn.place(relx=1.0, rely=0.0, anchor="ne")
                        delete_btn.bind("<Button-1>",
                                        lambda e, sched=s: self._delete_schedule(sched))
                        cell_frame.bind("<Button-3>",
                                        lambda e, sched=s: self._show_context_menu(e, sched))
                        for w in cell_frame.winfo_children():
                            w.bind("<Button-3>",
                                    lambda e, sched=s: self._show_context_menu(e, sched))
                    else:
                        conflict_lbl = tk.Label(cell_frame, text="⚠",
                                                font=("Segoe UI", 10, "bold"),
                                                bg=c["bg_card"], fg=c["error"])
                        conflict_lbl.pack(anchor="w")
                        for s in hits:
                            color = _color_for_course(s["course_id"])
                            row_f = tk.Frame(cell_frame, bg=color, padx=2, pady=1)
                            row_f.pack(fill=tk.X, pady=1)
                            tk.Label(row_f, text=f'{s["course_code"]} | {s.get("hall_name","")}',
                                     font=("Segoe UI", 8), bg=color, fg=c["text_primary"]
                                     ).pack(anchor="w", side=side_start())
                            edit_btn = tk.Label(row_f, text="✎",
                                                font=("Segoe UI", 8, "bold"),
                                                bg=color, fg=c["warning"], cursor="hand2",
                                                padx=2)
                            edit_btn.pack(anchor="e", side=side_end())
                            edit_btn.bind("<Button-1>",
                                          lambda e, sched=s: self._edit_dialog(sched))
                            delete_btn = tk.Label(row_f, text="✖",
                                                  font=("Segoe UI", 8, "bold"),
                                                  bg=color, fg=c["error"], cursor="hand2",
                                                  padx=2)
                            delete_btn.pack(anchor="e", side=side_end())
                            delete_btn.bind("<Button-1>",
                                            lambda e, sched=s: self._delete_schedule(sched))
                            row_f.bind("<Button-3>",
                                        lambda e, sched=s: self._show_context_menu(e, sched))
                            for w in row_f.winfo_children():
                                w.bind("<Button-3>",
                                        lambda e, sched=s: self._show_context_menu(e, sched))
                else:
                    tk.Label(cell_frame, text="+",
                             font=("Segoe UI", 18), bg=c["bg_card"],
                             fg=c["text_muted"]
                             ).pack(expand=True)
                    cell_frame.bind("<Button-1>",
                                     lambda e, d=day_idx, ss=slot_start, se=slot_end:
                                     self._add_dialog(default_day=d,
                                                       default_start=ss,
                                                       default_end=se))
                    for w in cell_frame.winfo_children():
                        w.bind("<Button-1>",
                                lambda e, d=day_idx, ss=slot_start, se=slot_end:
                                self._add_dialog(default_day=d,
                                                  default_start=ss,
                                                  default_end=se))

                self._cells[(day_idx, r - 1)] = cell_frame

    def refresh(self):
        def do():
            try:
                sched_resp = http_client.api_get("/api/schedules").json()
                self._schedules = sched_resp.get("schedules", [])

                courses_resp = http_client.api_get("/api/courses/full").json()
                self._courses = courses_resp.get("courses", [])

                halls_resp = http_client.api_get("/api/halls").json()
                self._halls = halls_resp.get("halls", [])

                self.parent.after(0, self._draw_grid)
            except Exception as e:
                self.parent.after(0, lambda: messagebox.showerror(
                    t("error"), f"{t('course.load_failed')}: {e}"))
        threading.Thread(target=do, daemon=True).start()

    # ────────── context menu (right-click on a filled cell) ──────────
    def _show_context_menu(self, event, schedule):
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(label=f"✎ {t('edit')}",
                         command=lambda: self._edit_dialog(schedule))
        menu.add_command(label=f"✖ {t('delete')}",
                         command=lambda: self._delete_schedule(schedule))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_schedule(self, schedule):
        if not messagebox.askyesno(t("course.confirm_title"),
                                    t("course.confirm_delete_schedule")):
            return
        try:
            r = http_client.api_delete(f"/api/schedules/{schedule['id']}").json()
            if r.get("success"):
                messagebox.showinfo(t("ok"), t("course.schedule_deleted"))
                self.refresh()
            else:
                messagebox.showerror(t("error"), r.get("error", ""))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    # ────────── add / edit dialog ──────────
    def _add_dialog(self, default_day=5, default_start="08:00", default_end="09:30"):
        self._schedule_dialog(None, default_day=default_day,
                              default_start=default_start, default_end=default_end)

    def _edit_dialog(self, schedule):
        self._schedule_dialog(schedule)

    def _schedule_dialog(self, schedule, *, default_day=5,
                          default_start="08:00", default_end="09:30"):
        c = COLORS
        is_edit = schedule is not None
        win = tk.Toplevel(self.parent)
        win.title(t("course.edit_title") if is_edit else t("course.add_schedule"))
        win.geometry("440x420")
        win.configure(bg=c["bg_dark"])
        win.grab_set()

        body = tk.Frame(win, bg=c["bg_dark"], padx=24, pady=18)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)

        def _row(row, label_text, widget):
            tk.Label(body, text=label_text, font=FONTS["small_bold"],
                     bg=c["bg_dark"], fg=c["text_muted"]).grid(row=row, column=1,
                                                                sticky="e",
                                                                padx=pad_x(0, 10),
                                                                pady=6)
            widget.grid(row=row, column=0, sticky="ew", ipady=5, pady=6)
            return widget

        # course
        course_var = tk.StringVar()
        course_labels = [f"{c2['course_code']} — {c2['course_name']}" for c2 in self._courses]
        course_combo = ttk.Combobox(body, textvariable=course_var,
                                     values=course_labels, state="readonly")
        _row(0, t("course.col_course"), course_combo)
        if is_edit:
            for i, c2 in enumerate(self._courses):
                if c2["id"] == schedule["course_id"]:
                    course_combo.current(i)
                    break

        # hall
        hall_var = tk.StringVar()
        hall_labels = [h["hall_name"] for h in self._halls]
        hall_combo = ttk.Combobox(body, textvariable=hall_var,
                                   values=hall_labels, state="readonly")
        _row(1, t("course.col_hall"), hall_combo)
        if is_edit:
            for i, h in enumerate(self._halls):
                if h["id"] == schedule["hall_id"]:
                    hall_combo.current(i)
                    break

        # day
        day_var = tk.StringVar()
        day_labels = [t(DAY_LABEL_KEYS[d]) for d in DAYS_ORDER]
        day_combo = ttk.Combobox(body, textvariable=day_var,
                                  values=day_labels, state="readonly")
        _row(2, t("day"), day_combo)
        default_day_local = schedule["day_of_week"] if is_edit else default_day
        try:
            day_combo.current(DAYS_ORDER.index(default_day_local))
        except ValueError:
            day_combo.current(0)

        # start time
        start_var = tk.StringVar(value=schedule["start_time"][:5] if is_edit else default_start)
        start_e = tk.Entry(body, textvariable=start_var,
                            font=FONTS["body"], bg=c["input_bg"],
                            fg=c["text_primary"], insertbackground=c["accent"],
                            relief="flat", bd=0, justify=text_justify())
        _row(3, t("course.col_start"), start_e)

        # end time
        end_var = tk.StringVar(value=schedule["end_time"][:5] if is_edit else default_end)
        end_e = tk.Entry(body, textvariable=end_var,
                          font=FONTS["body"], bg=c["input_bg"],
                          fg=c["text_primary"], insertbackground=c["accent"],
                          relief="flat", bd=0, justify=text_justify())
        _row(4, t("course.col_end"), end_e)

        tk.Label(body,
                 text=t("course.weekly_repeat_note"),
                 font=FONTS["small"], bg=c["bg_dark"],
                 fg=c["text_muted"]).grid(row=5, column=0, columnspan=2,
                                           sticky="ew", pady=(8, 0))

        # save
        def save():
            cidx = course_combo.current()
            hidx = hall_combo.current()
            didx = day_combo.current()
            if cidx < 0 or cidx >= len(self._courses):
                messagebox.showerror(t("error"), t("course.select_course_first"), parent=win)
                return
            if hidx < 0 or hidx >= len(self._halls):
                messagebox.showerror(t("error"), t("course.select_hall"), parent=win)
                return
            if didx < 0:
                messagebox.showerror(t("error"), t("course.select_day"), parent=win)
                return
            start_s = start_var.get().strip()
            end_s = end_var.get().strip()
            if not start_s or not end_s:
                messagebox.showerror(t("error"), t("course.times_required"), parent=win)
                return
            try:
                st = datetime.strptime(start_s, "%H:%M").time()
                et = datetime.strptime(end_s, "%H:%M").time()
            except ValueError:
                messagebox.showerror(t("error"), t("course.invalid_time"), parent=win)
                return
            if st >= et:
                messagebox.showerror(t("error"), t("course.start_before_end"), parent=win)
                return

            payload = {
                "course_id": self._courses[cidx]["id"],
                "hall_id": self._halls[hidx]["id"],
                "day_of_week": DAYS_ORDER[didx],
                "start_time": start_s,
                "end_time": end_s,
            }

            # Pre-check conflicts (server also validates on PUT)
            try:
                cp = dict(payload)
                if is_edit:
                    cp["exclude_id"] = schedule["id"]
                conflict_resp = http_client.api_post(
                    "/api/schedules/conflicts",
                    json_body=cp).json()
                if conflict_resp.get("has_conflict"):
                    info = conflict_resp.get("conflict", {})
                    if not messagebox.askyesno(
                        t("warning"),
                        f"{t('course.conflict_detected')}: "
                        f"{info.get('course_code', '')} "
                        f"({info.get('start_time', '')}-{info.get('end_time', '')})",
                        parent=win,
                    ):
                        return
            except Exception:
                pass

            try:
                if is_edit:
                    r = http_client.api_put(
                        f"/api/schedules/{schedule['id']}",
                        json_body=payload).json()
                    if r.get("success"):
                        messagebox.showinfo(t("ok"), t("course.schedule_updated_msg"), parent=win)
                        win.destroy()
                        self.refresh()
                    else:
                        messagebox.showerror(t("error"), r.get("error", ""), parent=win)
                else:
                    r = http_client.api_post(
                        "/api/schedules",
                        json_body=payload).json()
                    if r.get("success"):
                        messagebox.showinfo(t("ok"), t("course.schedule_added_msg"), parent=win)
                        win.destroy()
                        self.refresh()
                    else:
                        messagebox.showerror(t("error"), r.get("error", ""), parent=win)
            except Exception as e:
                messagebox.showerror(t("error"), str(e), parent=win)

        btn_row = tk.Frame(body, bg=c["bg_dark"])
        btn_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(20, 0))

        tk.Button(btn_row, text=t("save") if is_edit else t("course.add"),
                  command=save,
                  bg=c["success"], fg="#ffffff",
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_start(), padx=pad_x(0, 8))
        tk.Button(btn_row, text=t("cancel"),
                  command=win.destroy,
                  bg=c["bg_light"], fg=c["text_primary"],
                  font=FONTS["body_bold"], relief="flat",
                  cursor="hand2", padx=18, pady=8, bd=0
                  ).pack(side=side_start())
