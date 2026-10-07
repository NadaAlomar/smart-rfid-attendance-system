"""
نظام الحضور الجامعي الذكي — نقطة الدخول الرئيسية
====================================================
طريقة الاستخدام:
    python main.py           ← تهيئة DB + تشغيل الخادم + فتح الواجهة
    python main.py server    ← الخادم فقط (بدون واجهة)
    python main.py init      ← تهيئة قاعدة البيانات فقط
    python main.py gui       ← الواجهة فقط (الخادم يجب أن يكون مشغّلاً)
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def init_database():
    from database.init_database import main as db_main
    db_main()


def start_server(daemon=True):
    import config
    from api.app import app
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    def run():
        print(f"\n[الخادم] يعمل على http://{config.SERVER_HOST}:{config.SERVER_PORT}")
        app.run(
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            debug=False,
            use_reloader=False,
        )

    if daemon:
        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(1.5)
        return t
    else:
        run()


def start_gui():
    import tkinter as tk
    from ui.login_window import LoginWindow

    def show_login():
        """يفتح نافذة تسجيل الدخول"""
        root = tk.Tk()
        LoginWindow(root, on_login)
        root.mainloop()

    def on_login(user):
        """بعد نجاح تسجيل الدخول → يفتح النافذة الرئيسية"""
        from ui.main_window import MainWindow
        root2 = tk.Tk()

        def on_logout():
            """عند تسجيل الخروج → يُغلق النافذة الرئيسية ويعود لشاشة الدخول"""
            try:
                root2.destroy()
            except Exception:
                pass
            show_login()

        MainWindow(root2, user, on_logout=on_logout)
        root2.mainloop()

    show_login()


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if mode == "init":
        init_database()

    elif mode == "server":
        init_database()
        start_server(daemon=False)

    elif mode == "gui":
        start_gui()

    else:
        print("=" * 50)
        print("  نظام الحضور الجامعي الذكي — AUST")
        print("=" * 50)
        init_database()
        start_server(daemon=True)
        start_gui()


if __name__ == "__main__":
    main()
