import tkinter as tk
from tkinter import ttk
import config
from ui.theme import COLORS, FONTS, apply_theme
from ui.rtl_helper import side_start, side_end, anchor_start, anchor_end, text_justify
from ui.i18n import t
from ui import http_client


class LoginWindow:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success = on_success_callback
        self.root.title(t("login.window_title"))
        self.root.geometry("520x620")
        self.root.resizable(False, False)
        self.root.eval("tk::PlaceWindow . center")
        apply_theme(self.root)
        self._build()

    def _build(self):
        c = COLORS
        root = self.root

        # ── خلفية كاملة ──
        bg = tk.Frame(root, bg=c["bg_dark"])
        bg.place(relx=0, rely=0, relwidth=1, relheight=1)

        # ── بطاقة مركزية ──
        card = tk.Frame(bg, bg=c["bg_card"], padx=0, pady=0)
        card.place(relx=0.5, rely=0.5, anchor="center", width=420, height=540)

        # شريط علوي ملون
        top_bar = tk.Frame(card, bg=c["primary"], height=6)
        top_bar.pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(card, bg=c["bg_card"], padx=40, pady=30)
        body.pack(fill=tk.BOTH, expand=True)

        # أيقونة وعنوان
        tk.Label(body, text="🎓",
                 font=("Segoe UI Emoji", 38),
                 bg=c["bg_card"], fg=c["accent"]).pack(pady=(0, 6))

        tk.Label(body, text=t("system_title"),
                 font=FONTS["subtitle"],
                 bg=c["bg_card"], fg=c["accent"]).pack()

        tk.Label(body, text=t("login.university_subtitle"),
                 font=FONTS["small"],
                 bg=c["bg_card"], fg=c["text_muted"]).pack(pady=(2, 24))

        # ── فاصل ──
        tk.Frame(body, bg=c["border"], height=1).pack(fill=tk.X, pady=(0, 24))

        # ── حقل اسم المستخدم ──
        tk.Label(body, text=t("username"),
                 font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start()).pack(fill=tk.X)

        self.username_entry = tk.Entry(
            body, font=FONTS["body"],
            bg=c["input_bg"], fg=c["text_primary"],
            insertbackground=c["accent"],
            relief="flat", bd=0,
            justify=text_justify(),
        )
        self.username_entry.pack(fill=tk.X, ipady=10, pady=(4, 16))
        tk.Frame(body, bg=c["border_light"], height=1).pack(fill=tk.X, pady=(0, 16))
        self.username_entry.focus_set()

        # ── حقل كلمة المرور ──
        tk.Label(body, text=t("password"),
                 font=FONTS["small_bold"],
                 bg=c["bg_card"], fg=c["text_secondary"],
                 anchor=anchor_start()).pack(fill=tk.X)

        self.password_entry = tk.Entry(
            body, font=FONTS["body"],
            bg=c["input_bg"], fg=c["text_primary"],
            insertbackground=c["accent"],
            relief="flat", bd=0,
            show="●", justify=text_justify(),
        )
        self.password_entry.pack(fill=tk.X, ipady=10, pady=(4, 4))
        tk.Frame(body, bg=c["border_light"], height=1).pack(fill=tk.X, pady=(0, 6))
        self.password_entry.bind("<Return>", lambda e: self.authenticate())

        # ── رسالة خطأ ──
        self.error_var = tk.StringVar()
        self.error_lbl = tk.Label(body, textvariable=self.error_var,
                                   font=FONTS["small"],
                                   bg=c["bg_card"], fg=c["error"])
        self.error_lbl.pack(pady=(4, 12))

        # ── زر الدخول (بارز بصرياً) ──
        login_btn = tk.Button(
            body, text=f"🔓  {t('login')}",
            command=self.authenticate,
            bg=c["primary"], fg="#ffffff",
            activebackground=c["primary_light"],
            activeforeground="#ffffff",
            font=("Segoe UI", 13, "bold"),
            relief="flat", cursor="hand2",
            pady=14, bd=0,
        )
        login_btn.pack(fill=tk.X, pady=(8, 10), ipady=2)

        # Hover effect for the login button
        def _on_enter(_e):
            login_btn.configure(bg=c["primary_light"])

        def _on_leave(_e):
            login_btn.configure(bg=c["primary"])

        login_btn.bind("<Enter>", _on_enter)
        login_btn.bind("<Leave>", _on_leave)

        exit_btn = tk.Button(
            body, text=t("login.exit"),
            command=root.quit,
            bg=c["bg_medium"], fg=c["text_muted"],
            activebackground=c["bg_light"],
            activeforeground=c["text_primary"],
            font=FONTS["body"],
            relief="flat", cursor="hand2",
            pady=8, bd=0,
        )
        exit_btn.pack(fill=tk.X)

    def authenticate(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.error_var.set(t("login_required"))
            return
        try:
            r = http_client.api_post(
                "/api/auth/login",
                json_body={"username": username, "password": password},
            )
            data = r.json()
            if r.status_code == 401 or not data.get("success"):
                self.error_var.set(t("login_failed"))
                return
            token = data.get("token", "")
            user_info = data.get("user", {})
            http_client.set_token(token)
            user_data = type("UserData", (), {
                "id": user_info.get("id"),
                "username": user_info.get("username"),
                "role": user_info.get("role"),
                "doctor_id": user_info.get("doctor_id"),
            })()
            self.root.destroy()
            self.on_success(user_data)
        except Exception as e:
            err = str(e)
            if "Connection" in err or "connect" in err.lower():
                self.error_var.set(t("connection_error"))
            else:
                self.error_var.set(f'{t("error")}: {e}')
