# نظام الحضور الجامعي الذكي 

نظام ذكي لتسجيل الحضور بتقنية RFID في القاعات الجامعية، مع إدارة الطلاب والدكاترة والمواد والقاعات والجلسات والتقارير والتنبيهات من خلال واجهة رسومية وخادم API.

---

## التشغيل السريع (Windows)

انقر مرتين على **`start.bat`** — سيقوم تلقائياً بـ:

1. تثبيت جميع المتطلبات
2. تهيئة قاعدة البيانات
3. تشغيل الخادم
4. فتح الواجهة الرسومية

### بيانات الدخول التجريبية

**اسم المستخدم:** `admin`  
**كلمة المرور:** `admin123`

>  بيانات الدخول أعلاه مخصصة للاختبار المحلي فقط، ويجب تغييرها عند استخدام النظام في بيئة فعلية.

---

## التشغيل اليدوي

```bash
pip install -r requirements.txt

python main.py

أو تشغيل مكونات منفصلة:

python main.py init      # تهيئة قاعدة البيانات فقط

python main.py server    # الخادم فقط (بدون واجهة)

python main.py gui       # الواجهة فقط
هيكل المشروع
smart-rfid-attendance-system/

├── main.py                         ← نقطة الدخول الرئيسية
├── config.py                       ← إعدادات النظام
├── start.bat                       ← مشغّل Windows بنقرة واحدة
├── requirements.txt

│
├── api/
│   ├── app.py                      ← تطبيق Flask
│   ├── routes/
│   │   ├── scanner_routes.py       ← نقاط نهاية أجهزة RFID
│   │   ├── secretary_routes.py     ← نقاط نهاية الإدارة
│   │   └── management_routes.py    ← دكاترة، مواد، قاعات، جداول
│   └── controllers/
│       ├── attendance_controller.py
│       └── alert_controller.py

│
├── database/
│   ├── __init__.py                 ← محرك قاعدة البيانات
│   ├── models.py                   ← نماذج SQLAlchemy
│   └── init_database.py            ← التهيئة والبيانات التجريبية

│
├── hardware/
│   └── serial_reader.py             ← قارئ RFID عبر المنفذ التسلسلي

│
├── arduino/
│   ├── scanner_hall/
│   │   └── scanner_hall.ino         ← سكانر RFID للقاعة
│   └── scanner_secretary/
│       └── scanner_secretary.ino    ← سكانر RFID للسكرتارية

│
├── security/
│   └── security_manager.py          ← إدارة الأمان والرموز

│
├── ui/                              ← الواجهة الرسومية
│   ├── login_window.py              ← نافذة تسجيل الدخول
│   ├── main_window.py               ← النافذة الرئيسية
│   ├── student_management.py        ← إدارة الطلاب
│   ├── doctor_management.py         ← إدارة الدكاترة
│   ├── course_management.py         ← إدارة المواد والجداول
│   ├── hall_management.py           ← إدارة القاعات والأجهزة
│   ├── attendance_report.py         ← تقارير الحضور
│   ├── alerts_panel.py              ← لوحة التنبيهات
│   └── excel_import.py              ← استيراد Excel

│
└── utils/
    ├── date_utils.py
    └── excel_handler.py
ميزات النظام
الميزة	الوصف
إدارة الطلاب	إضافة / تعديل / حذف / بحث — دعم البطاقات المؤقتة
إدارة الدكاترة	نظري وعملي — إنشاء حسابات دخول — تعيين مواد
إدارة المواد	إضافة / تعديل / حذف — تعيين دكتور — جداول دراسية
إدارة القاعات	نظري وعملي — تسجيل أجهزة RFID
تسجيل الطلاب	ربط الطلاب بالمواد
الجلسات	فتح/إغلاق جلسات الحضور تلقائياً عبر RFID
التقارير	تقارير حضور أسبوعية — تصدير Excel
التنبيهات	تنبيه عند 4 غيابات أو نسبة حضور منخفضة
استيراد Excel	استيراد الطلاب والمواد من ملفات Excel
إعداد أجهزة RFID

يستخدم النظام أجهزة NodeMCU ESP8266 مع قارئات MFRC522 RFID.

يوجد نوعان من أجهزة RFID في النظام:

arduino/scanner_hall/ — سكانر القاعة لتسجيل الحضور.
arduino/scanner_secretary/ — سكانر السكرتارية لتسجيل بطاقات الطلاب والدكاترة.

قبل تشغيل أجهزة NodeMCU، عدّل إعدادات الشبكة في ملفات Arduino:

#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"
#define SERVER_IP      "YOUR_SERVER_IP"
#define SERVER_PORT    5000

يجب أن يكون جهاز NodeMCU والخادم على نفس شبكة Wi-Fi المحلية.

سكانر القاعة

يستخدم سكانر القاعة RFID لتسجيل حضور الطلاب وإرسال بيانات البطاقة إلى خادم النظام.

سكانر السكرتارية

يستخدم سكانر السكرتارية لقراءة بطاقة الطالب أو الدكتور وإرسال UID إلى واجهة النظام لتسجيل البطاقة.

نقاط نهاية API
الطريقة	المسار	الوصف
GET	/	حالة الخادم
GET	/api/status	فحص الاتصال
POST	/api/scan	معالجة مسح RFID
POST	/api/scan/register-card	تسجيل بطاقة عبر سكانر السكرتارية
GET	/api/students	قائمة الطلاب
POST	/api/student/add	إضافة طالب
PUT	/api/student/<id>	تعديل طالب
DELETE	/api/student/<id>	حذف طالب
GET	/api/doctors	قائمة الدكاترة
POST	/api/doctors	إضافة دكتور
GET	/api/courses	قائمة المواد
POST	/api/courses	إضافة مادة
GET	/api/halls	قائمة القاعات
POST	/api/halls	إضافة قاعة
GET	/api/schedules	الجداول الدراسية
POST	/api/schedules	إضافة جدول
GET	/api/enrollments	التسجيلات
POST	/api/enrollments	تسجيل طالب
GET	/api/alerts	التنبيهات النشطة
GET	/api/report/attendance	تقرير الحضور
GET	/api/report/export	تصدير تقرير Excel
POST	/api/import/excel	استيراد من Excel
GET	/api/dashboard/stats	إحصائيات لوحة التحكم
ملاحظات أمنية
لا تضع بيانات Wi-Fi الحقيقية داخل ملفات Arduino عند رفع المشروع إلى GitHub.
استخدم القيم التالية في النسخة العامة:
#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"
#define SERVER_IP      "YOUR_SERVER_IP"
بيانات الدخول المذكورة في هذا الملف مخصصة للتجربة المحلية فقط.
يجب تغيير بيانات الدخول والإعدادات الحساسة قبل استخدام النظام في بيئة فعلية.
لا ترفع ملفات قواعد البيانات المحلية أو ملفات السجلات أو الرموز السرية إلى GitHub.
لا تضع مفاتيح API أو كلمات مرور أو رموز أجهزة حقيقية داخل ملفات المشروع العامة.
ملفات البيانات المحلية

يتم استخدام مجلد data/ لتخزين البيانات المحلية وقاعدة البيانات أثناء التشغيل.

يجب عدم رفع ملفات قاعدة البيانات والسجلات والملفات المحلية إلى GitHub.

كما يتم استخدام مجلد uploads/ للملفات المرفوعة أثناء تشغيل النظام، لذلك يجب عدم رفع ملفات المستخدمين أو بيانات الحضور الحقيقية إلى المستودع العام.

الاختبارات

يحتوي المشروع على ملفات اختبار للتحقق من وظائف النظام وواجهات API والصلاحيات.

بعض بيانات الدخول الموجودة في ملفات الاختبار مخصصة لبيئة الاختبار المحلية فقط وليست بيانات اعتماد حقيقية للاستخدام في الإنتاج.

الترخيص

هذا المشروع مخصص للأغراض التعليمية والأكاديمية والتطويرية.