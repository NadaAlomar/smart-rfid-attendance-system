"""
قارئ RFID عبر المنفذ التسلسلي
يستخدم مع Arduino UNO/Nano بسكانر السكرتارية
"""
import time
import threading


class SerialRFIDReader:
    """
    يقرأ UIDs من Arduino عبر USB Serial.
    يعمل بشكل graceful إذا لم يكن pyserial مثبتاً
    أو إذا لم يكن المنفذ محدداً.
    """

    def __init__(self, port=None, baud_rate=9600, timeout=1, on_scan=None):
        self.port       = port
        self.baud_rate  = baud_rate
        self.timeout    = timeout
        self.on_scan    = on_scan   # callback(uid: str, timestamp: datetime)
        self.serial_conn = None
        self._running   = False
        self._thread    = None

    # ── الاتصال ───────────────────────────────────────────────────────────────
    def connect(self):
        if not self.port:
            print("[RFID] لم يُحدَّد SERIAL_PORT — تخطّي الاتصال.")
            return False
        try:
            import serial
            self.serial_conn = serial.Serial(
                self.port, self.baud_rate, timeout=self.timeout
            )
            time.sleep(2)   # انتظر Arduino حتى يُعيد التشغيل
            print(f"[RFID] متصل على {self.port} @ {self.baud_rate}")
            return True
        except ImportError:
            print("[RFID] مكتبة pyserial غير مثبتة. شغّل: pip install pyserial")
            return False
        except Exception as e:
            print(f"[RFID] خطأ في الاتصال: {e}")
            return False

    def disconnect(self):
        self._running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("[RFID] تم قطع الاتصال.")

    # ── قراءة UID واحد (للسكرتارية) ─────────────────────────────────────────
    def read_one_uid(self, timeout_seconds=15):
        """
        ينتظر حتى timeout_seconds ثانية لقراءة بطاقة واحدة.
        يُعيد الـ UID كـ string أو None عند انتهاء الوقت.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None

        # فحص الاتصال مع Arduino
        self.serial_conn.write(b"PING\n")
        time.sleep(0.2)

        start = time.time()
        while time.time() - start < timeout_seconds:
            if self.serial_conn.in_waiting:
                try:
                    line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("CARD:"):
                        uid = line[5:].strip().upper()
                        print(f"[RFID] بطاقة مقروءة: {uid}")
                        return uid
                except Exception as e:
                    print(f"[RFID] خطأ في القراءة: {e}")
            time.sleep(0.05)

        return None   # انتهى الوقت

    # ── حلقة قراءة مستمرة (للقاعة) ─────────────────────────────────────────
    def read_loop(self):
        """حلقة blocking — استدعِها من thread."""
        from datetime import datetime
        self._running = True
        while self._running and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode("utf-8", errors="ignore").strip()
                    if line.startswith("CARD:"):
                        uid = line[5:].strip().upper()
                        ts  = datetime.now()
                        print(f"[RFID] مسح: {uid} في {ts.strftime('%H:%M:%S')}")
                        if self.on_scan:
                            self.on_scan(uid, ts)
                time.sleep(0.05)
            except Exception as e:
                print(f"[RFID] خطأ في حلقة القراءة: {e}")
                break

    def start_background(self):
        """ابدأ القراءة في خلفية."""
        if not self.serial_conn:
            return False
        self._thread = threading.Thread(target=self.read_loop, daemon=True)
        self._thread.start()
        return True

    def stop_background(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    # ── مساعد: البحث عن المنافذ المتاحة ─────────────────────────────────────
    @staticmethod
    def list_ports():
        """يُعيد قائمة بالمنافذ التسلسلية المتاحة."""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            result = []
            for p in ports:
                result.append({
                    "port":        p.device,
                    "description": p.description,
                    "hwid":        p.hwid,
                })
            return result
        except ImportError:
            return []
        except Exception:
            return []
