"""يستبدل قائمة المواد والدكاترة الحاليين بقائمة الجامعة الفعلية.

ينظّف كل الجداول المرتبطة بترتيب المفاتيح الأجنبية ثم يُدخل:
  - 9 دكاترة (المذكورون بأسمائهم في القائمة)
  - 54 مادة موزّعة على 5 سنوات × فصلين
  - يربط مواد التدريس بأسماء الدكاترة الواردة في القائمة

لا يلمس:
  - الطلاب، الفروع، القاعات، الأجهزة، حسابات المستخدمين غير المرتبطة بدكتور
"""
import sys
import io
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from database import get_session
from database.models import (
    Course, Doctor, User, UserSession,
    Enrollment, Schedule, AttendanceSession, AttendanceRecord,
    DoctorNote, Alert, AbsenceJustification, QRSession,
)


# ── 1. الدكاترة المذكورون ────────────────────────────────────────────────
# (الاسم الكامل كما سيظهر في الواجهة)
DOCTORS = [
    "د. أسماء الشعار",
    "د. يسر الأتاسي",
    "د. رضوان المحمد",
    "د. أسامة الناصر",
    "د. ميساء دياب",
    "د. ديمة شاهين",
    "د. بهاء حمدان",
    "د. فدوى صافية",
    "د. رضوان دنده",
]


# ── 2. كتالوج المواد (الكود، الاسم، الساعات، اسم الدكتور أو None) ─────────
COURSES = [
    # ═══════ السنة الأولى - الفصل الأول ═══════
    ("ITE111", "تنظيم الحاسوب والبرمجة بلغة أسمبلي", 3, None),
    ("UR112",  "مهارات الحاسوب", 2, None),
    ("CR112",  "الرسم الهندسي", 2, None),
    ("CR111",  "الرياضيات الهندسية (1)", 3, None),
    ("CR114",  "الفيزياء الهندسية (1)", 3, None),
    ("CR113",  "البرمجة (1)", 3, None),
    ("UR111",  "مهارات اللغة الإنكليزية (1)", 2, None),

    # ═══════ السنة الأولى - الفصل الثاني ═══════
    ("UR122",  "مهارات اللغة العربية", 3, None),
    ("CR123",  "الميكانيك الهندسي", 2, None),
    ("CR122",  "الكيمياء الهندسية العامة", 2, None),
    ("CR121",  "الرياضيات الهندسية (2)", 3, None),
    ("ITE121", "الفيزياء الهندسية (2)", 3, None),
    ("ITE122", "البرمجة (2)", 3, None),
    ("UR121",  "مهارات اللغة الإنكليزية (2)", 2, None),

    # ═══════ السنة الثانية - الفصل الأول ═══════
    ("ITE215", "البرمجة الموجهة للكائنات (1)", 3, None),
    ("CR211",  "مهارات خاصة في اللغة الإنكليزية (1)", 2, None),
    ("ITE213", "الاحتمالات والإحصاء", 3, None),
    ("ITE211", "الرياضيات المتقطعة", 3, None),
    ("ITE212", "برمجة الويب", 2, None),
    ("ITE214", "الخوارزميات وبنى المعطيات (1)", 3, "د. أسماء الشعار"),
    ("UR211",  "مقرر جامعة اختياري", 2, None),

    # ═══════ السنة الثانية - الفصل الثاني ═══════
    ("ITE225", "البرمجة الموجهة للكائنات (2)", 3, None),
    ("CR221",  "مهارات خاصة في اللغة الإنكليزية (2)", 2, None),
    ("CR222",  "دارات منطقية", 2, None),
    ("ITE221", "التحليل العددي", 2, None),
    ("ITE223", "أسس الهندسة الكهربائية", 3, None),
    ("ITE224", "الخوارزميات وبنى المعطيات (2)", 3, "د. أسماء الشعار"),
    ("ITE222", "أنظمة قواعد البيانات", 2, None),

    # ═══════ السنة الثالثة - الفصل الأول ═══════
    ("CR311",  "مقرر كلية اختياري", 3, None),
    ("ITE314", "تحليل الأنظمة وتصميمها", 3, None),
    ("ITE313", "نظم التشغيل (1)", 3, None),
    ("ITE315", "معمارية الحاسوب", 3, None),
    ("ITE312", "تطوير تطبيقات الشبكة العنكبوتية", 3, None),
    ("ITE311", "هندسة البرمجيات (1)", 3, None),

    # ═══════ السنة الثالثة - الفصل الثاني ═══════
    ("ITE322", "الذكاء الصنعي", 3, None),
    ("ITE324", "المترجمات", 3, "د. يسر الأتاسي"),
    ("ITE323", "نظم التشغيل (2)", 3, None),
    ("ITE325", "أنظمة قواعد البيانات (2)", 3, None),
    ("ITE326", "نظم المعلومات (1)", 3, None),
    ("ITE321", "هندسة البرمجيات (2)", 3, None),

    # ═══════ السنة الرابعة - الفصل الأول ═══════
    ("ITE415", "شبكات الحاسوب (1)", 3, None),
    ("ITE416", "نظم الزمن الحقيقي", 3, None),
    ("ITE414", "الرسم بالحاسوب", 3, None),
    ("ITE412", "تصميم لغات البرمجة", 3, None),
    ("ITE413", "نظم المعلومات (2)", 3, None),
    ("ITE411", "تنقيب البيانات", 3, None),

    # ═══════ السنة الرابعة - الفصل الثاني ═══════
    ("ITE425", "شبكات الحاسوب (2)", 3, None),
    ("ITE426", "النمذجة والمحاكاة", 3, "د. رضوان المحمد"),
    ("ITE422", "تطبيقات التكنولوجيا الإلكترونية", 2, "د. أسامة الناصر"),
    ("ITE424", "تفاعل الإنسان مع الحاسوب", 3, "د. ميساء دياب"),
    ("ITE423", "أنظمة دعم القرارات", 3, None),
    ("ITE421", "إدارة قواعد البيانات", 3, None),

    # ═══════ السنة الخامسة - الفصل الأول ═══════
    ("ITE511", "الشبكات العصبونية", 3, None),
    ("ITE512", "الأنظمة الخبيرة", 3, "د. ديمة شاهين"),
    ("ITE513", "إدارة المشاريع", 3, None),
    ("ITE514", "مشروع تصميم نهائي في هندسة نظم المعلومات (1)", 2, None),

    # ═══════ السنة الخامسة - الفصل الثاني ═══════
    ("ITE522", "أمن المعلومات", 3, "د. بهاء حمدان"),
    ("ITE521", "أنظمة الوسائط المتعددة", 3, "د. فدوى صافية"),
    ("ITE523", "معالجة الصور", 3, "د. رضوان دنده"),
    ("ITE524", "مشروع تصميم نهائي في هندسة نظم المعلومات (2)", 2, None),
]


def _placeholder_uid(name):
    """قيمة فريدة لـ hashed_uid لأن العمود NOT NULL UNIQUE."""
    safe = name.replace(" ", "_").replace(".", "")
    return f"__PLACEHOLDER__doctor_new_{safe}"


def main():
    s = get_session()
    try:
        # ── الخطوة 0: استعلام أولي ────────────────────────────────
        n_courses = s.query(Course).count()
        n_doctors = s.query(Doctor).count()
        n_enrollments = s.query(Enrollment).count()
        n_sessions = s.query(AttendanceSession).count()
        n_schedules = s.query(Schedule).count()
        print(f"حالة قاعدة البيانات الحالية:")
        print(f"  مواد: {n_courses}, دكاترة: {n_doctors}, "
              f"تسجيلات: {n_enrollments}, جلسات: {n_sessions}, "
              f"مفردات جدول: {n_schedules}")

        # ── 1. حذف بترتيب المفاتيح الأجنبية ──────────────────────
        print("\n— تنظيف الجداول المرتبطة...")

        # records تعتمد على sessions
        d = s.query(AttendanceRecord).delete()
        print(f"  attendance_records: {d}")

        # qr_sessions تعتمد على sessions/doctors/courses/halls
        d = s.query(QRSession).delete()
        print(f"  qr_sessions: {d}")

        # sessions تعتمد على schedule/courses/doctors
        d = s.query(AttendanceSession).delete()
        print(f"  attendance_sessions: {d}")

        # schedule يعتمد على courses
        d = s.query(Schedule).delete()
        print(f"  schedule: {d}")

        # enrollments تعتمد على courses (والطلاب يبقون)
        d = s.query(Enrollment).delete()
        print(f"  enrollments: {d}")

        # doctor_notes تعتمد على doctors و courses
        d = s.query(DoctorNote).delete()
        print(f"  doctor_notes: {d}")

        # alerts تعتمد على courses
        d = s.query(Alert).delete()
        print(f"  alerts: {d}")

        # absence_justifications.course_id قابل للنل، نفرّغها فقط
        upd = s.query(AbsenceJustification).update(
            {AbsenceJustification.course_id: None}, synchronize_session=False)
        print(f"  absence_justifications.course_id: cleared {upd} rows")

        s.flush()

        # ── 2. حذف الدكاترة الحاليين + حساباتهم المرتبطة ──────
        old_docs = s.query(Doctor).all()
        del_users = 0
        for doc in old_docs:
            if doc.user_id:
                # جلسات الدخول للمستخدم
                s.query(UserSession).filter_by(user_id=doc.user_id).delete()
                u = s.query(User).filter_by(id=doc.user_id).first()
                if u:
                    s.delete(u)
                    del_users += 1
            s.delete(doc)
        print(f"  doctors deleted: {len(old_docs)}  "
              f"(linked user accounts deleted: {del_users})")

        # ── 3. حذف المواد ─────────────────────────────────────
        d = s.query(Course).delete()
        print(f"  courses: {d}")

        s.flush()

        # ── 4. إدراج الدكاترة الجدد ───────────────────────────
        print("\n— إدراج الدكاترة الجدد...")
        doc_id_by_name = {}
        for name in DOCTORS:
            parts = name.replace("د.", "").strip().split()
            first = parts[0] if parts else name
            last = parts[-1] if len(parts) > 1 else ""
            doc = Doctor(
                full_name=name,
                first_name=first,
                last_name=last,
                hashed_uid=_placeholder_uid(name),
                teaching_type="theory",
            )
            s.add(doc)
            s.flush()
            doc_id_by_name[name] = doc.id
            print(f"  + {name}  (id={doc.id})")

        # ── 5. إدراج المواد ───────────────────────────────────
        print("\n— إدراج المواد...")
        for code, name, hours, doctor_name in COURSES:
            cdoc_id = doc_id_by_name.get(doctor_name) if doctor_name else None
            c = Course(
                course_code=code,
                course_name=name,
                course_type="theory",
                total_weeks=15,
                doctor_id=cdoc_id,
            )
            s.add(c)
            tag = f" -> {doctor_name}" if doctor_name else ""
            print(f"  + {code:7s}  {name}  ({hours}h){tag}")

        s.commit()

        # ── 6. ملخّص نهائي ────────────────────────────────────
        print("\n═══ ملخّص ═══")
        print(f"  دكاترة جدد: {s.query(Doctor).count()}")
        print(f"  مواد جديدة: {s.query(Course).count()}")
        linked = s.query(Course).filter(Course.doctor_id.isnot(None)).count()
        print(f"  مواد مرتبطة بدكاترة: {linked}")
        print(f"  حسابات المستخدمين المتبقية: {s.query(User).count()}")

    except Exception as e:
        s.rollback()
        print(f"\n❌ فشل: {e}")
        raise
    finally:
        s.close()


if __name__ == "__main__":
    main()
