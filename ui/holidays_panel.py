import tkinter as tk
from tkinter import ttk, messagebox
from ui.theme import COLORS, FONTS, create_styled_treeview
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui import http_client
from ui.widgets.date_picker import DatePicker
import threading



class HolidaysPanel:
    def __init__(self, parent, user=None):
        self.parent = parent
        self.user = user
        c = COLORS
        wrap = tk.Frame(parent, bg=c["bg_dark"], padx=24, pady=16)
        wrap.pack(fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(wrap, bg=c["bg_dark"])
        toolbar.pack(fill=tk.X, pady=(0, 12))

        tk.Button(toolbar, text="  إضافة عطلة", command=self._add_holiday_dialog,
                  bg=c["primary"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0).pack(side=side_start(), padx=(0, 8))

        footer = tk.Frame(wrap, bg=c["bg_dark"])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        tk.Frame(wrap, bg=c["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(footer, text="  تحديث", command=self._load,
                  bg=c["bg_light"], fg=c["text_primary"], font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=14, pady=6, bd=0).pack(side=side_end(), padx=(0, 6))

        cols = ("id", "date", "name", "type", "notes")
        self.tree = create_styled_treeview(wrap, columns=cols, show="headings", height=20)
        headers = {"id": ("#", 50, "center"), "date": ("التاريخ", 120, "center"),
                   "name": ("الاسم", 200, anchor_start()), "type": ("النوع", 100, "center"),
                   "notes": ("ملاحظات", 250, anchor_start())}
        for col, (h, w, anch) in headers.items():
            self.tree.heading(col, text=h, anchor=anch)
            self.tree.column(col, width=w, anchor=anch)

        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.pack(side=side_end(), fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self._on_double_click)

        self._load()

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        def do():
            try:
                resp = http_client.api_get("/api/holidays")
                data = resp.json()
            except Exception:
                return
            type_ar = {"holiday": "عطلة", "exam": "امتحان", "other": "أخرى"}
            for h in data.get("holidays", []):
                self.tree.insert("", tk.END, values=(
                    h["id"], h["date"], h["name"],
                    type_ar.get(h["type"], h["type"]), h.get("notes", ""),
                ))
        threading.Thread(target=do, daemon=True).start()

    def _add_holiday_dialog(self):
        top = tk.Toplevel(self.parent)
        top.title("إضافة عطلة")
        top.configure(bg=COLORS["bg_card"])
        top.geometry("420x420")
        top.transient(self.parent)
        top.grab_set()

        c = COLORS
        canvas = tk.Canvas(top, bg=c["bg_card"], highlightthickness=0, bd=0)
        vsb_dlg = ttk.Scrollbar(top, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb_dlg.set)
        vsb_dlg.pack(side=side_end(), fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form = tk.Frame(canvas, bg=c["bg_card"], padx=20, pady=20)
        form_win = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(form_win, width=e.width))
        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        form.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        form.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        fields = {}
        date_keys = {"from_date", "to_date"}
        for label, key in [("اسم العطلة:", "name"), ("من تاريخ:", "from_date"),
                           ("إلى تاريخ (اختياري):", "to_date"), ("ملاحظات:", "notes")]:
            tk.Label(form, text=label, font=FONTS["body"], bg=c["bg_card"],
                     fg=c["text_secondary"], anchor=anchor_start()).pack(fill=tk.X, pady=(8, 2))
            if key in date_keys:
                e = DatePicker(form, variable=tk.StringVar(), bg=c["bg_card"])
                e.pack(fill=tk.X)
            else:
                e = tk.Entry(form, font=FONTS["body"], bg=c["input_bg"],
                             fg=c["text_primary"], insertbackground=c["accent"],
                             relief="flat", bd=0)
                e.pack(fill=tk.X, ipady=6)
            fields[key] = e

        tk.Label(form, text="النوع:", font=FONTS["body"], bg=c["bg_card"],
                 fg=c["text_secondary"], anchor=anchor_start()).pack(fill=tk.X, pady=(8, 2))
        type_var = tk.StringVar(value="holiday")
        type_combo = ttk.Combobox(form, textvariable=type_var,
                                   values=["holiday", "exam", "other"],
                                   state="readonly")
        type_combo.pack(fill=tk.X)

        def save():
            name = fields["name"].get().strip()
            from_d = fields["from_date"].get().strip()
            if not name or not from_d:
                messagebox.showwarning("تنبيه", "الاسم والتاريخ مطلوبان", parent=top)
                return
            try:
                resp = http_client.api_post("/api/holidays", json_body={
                    "name": name,
                    "type": type_var.get(),
                    "from_date": from_d,
                    "to_date": fields["to_date"].get().strip() or from_d,
                    "notes": fields["notes"].get().strip(),
                })
                data = resp.json()
                if data.get("success"):
                    top.destroy()
                    self._load()
                else:
                    messagebox.showerror("خطأ", data.get("error", "فشل الإضافة"), parent=top)
            except Exception as ex:
                messagebox.showerror("خطأ", str(ex), parent=top)

        tk.Button(form, text="حفظ", command=save,
                  bg=c["primary"], fg="#ffffff", font=FONTS["body_bold"],
                  relief="flat", cursor="hand2", padx=20, pady=8, bd=0).pack(pady=(16, 0))

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        hid = item["values"][0]
        if messagebox.askyesno("تأكيد", "هل تريد حذف هذه العطلة؟"):
            try:
                resp = http_client.api_delete(f"/api/holidays/{hid}")
                if resp.json().get("success"):
                    self._load()
            except Exception:
                pass
