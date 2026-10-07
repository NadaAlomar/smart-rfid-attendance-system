from database import Base
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Date, Time, ForeignKey, Text,
)
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("Doctor", back_populates="user", uselist=False)


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_name = Column(String(100), nullable=False)
    branch_code = Column(String(20), unique=True, nullable=False)

    students = relationship("Student", back_populates="branch")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    academic_id = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    # تفاصيل الاسم (اختيارية لتوافق الإصدار القديم)
    first_name = Column(String(80), nullable=True)
    father_name = Column(String(80), nullable=True)
    mother_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    hashed_uid = Column(String(255), unique=True, nullable=False)
    is_temporary_card = Column(Boolean, default=False)
    card_expiry_date = Column(Date, nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    branch = relationship("Branch", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="student", cascade="all, delete-orphan")
    justifications = relationship("AbsenceJustification", back_populates="student",
                                   cascade="all, delete-orphan")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(200), nullable=False)
    first_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    hashed_uid = Column(String(255), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    teaching_type = Column(String(20), default="theory")

    user = relationship("User", back_populates="doctor")
    courses = relationship("Course", back_populates="doctor")
    attendance_sessions = relationship("AttendanceSession", back_populates="doctor")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_name = Column(String(200), nullable=False)
    course_code = Column(String(20), unique=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    course_type = Column(String(20), default="theory")
    total_weeks = Column(Integer, default=15)

    doctor = relationship("Doctor", back_populates="courses")
    branch = relationship("Branch")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="course", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="course", cascade="all, delete-orphan")
    # Direct sessions for courses without schedule
    attendance_sessions = relationship("AttendanceSession", back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    enrollment_date = Column(Date, default=datetime.utcnow().date)

    student = relationship("Student", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class Hall(Base):
    __tablename__ = "halls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hall_name = Column(String(100), unique=True, nullable=False)
    hall_type = Column(String(20), default="theory")

    devices = relationship("Device", back_populates="hall")
    schedules = relationship("Schedule", back_populates="hall")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(100), unique=True, nullable=False)
    hall_id = Column(Integer, ForeignKey("halls.id"), nullable=True)
    device_token = Column(String(255), nullable=False)
    last_seen = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    hall = relationship("Hall", back_populates="devices")


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    hall_id = Column(Integer, ForeignKey("halls.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    course = relationship("Course", back_populates="schedules")
    hall = relationship("Hall", back_populates="schedules")
    attendance_sessions = relationship("AttendanceSession", back_populates="schedule")


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)  # FIX: added
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    session_date = Column(Date, nullable=False)
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    schedule = relationship("Schedule", back_populates="attendance_sessions")
    course = relationship("Course", back_populates="attendance_sessions")  # FIX: added
    doctor = relationship("Doctor", back_populates="attendance_sessions")
    attendance_records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    check_in_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="present")

    session = relationship("AttendanceSession", back_populates="attendance_records")
    student = relationship("Student", back_populates="attendance_records")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    alert_type = Column(String(20), nullable=False)
    alert_date = Column(Date, default=datetime.utcnow().date)
    is_read = Column(Boolean, default=False)

    student = relationship("Student", back_populates="alerts")
    course = relationship("Course", back_populates="alerts")


class Holiday(Base):
    """عطل وأيام عدم دوام (يوميتان أو فترة)"""
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    holiday_date = Column(Date, nullable=False, unique=True)
    holiday_name = Column(String(200), nullable=False)
    holiday_type = Column(String(20), default="holiday")  # holiday | exam | other
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AbsenceJustification(Base):
    """تبرير غياب طالب لفترة معينة (تُضاف من العميدة فقط)"""
    __tablename__ = "absence_justifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # العميدة
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="justifications")
    course = relationship("Course")
    creator = relationship("User", foreign_keys=[created_by])


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(String(256), nullable=False)
    description = Column(String(256))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ScanLog(Base):
    """سجل كل محاولات مسح البطاقات (ناجحة وفاشلة).

    scan_type values:
        doctor_open, doctor_close, student_in,
        unknown_card, wrong_hall, no_session, expired_card
    """
    __tablename__ = "scan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    hashed_uid = Column(String(255), nullable=True, index=True)
    raw_uid_hint = Column(String(50), nullable=True)
    device_id = Column(String(100), nullable=True, index=True)
    hall_id = Column(Integer, ForeignKey("halls.id"), nullable=True, index=True)
    scan_type = Column(String(20), nullable=False, index=True)
    success = Column(Boolean, default=False, nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=True)
    error_reason = Column(String(200), nullable=True)

    hall = relationship("Hall")
    student = relationship("Student")
    doctor = relationship("Doctor")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    note = Column(Text, nullable=False)
    severity = Column(String(20), default="info")
    is_read_by_secretary = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("Doctor")
    student = relationship("Student")
    course = relationship("Course")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String(100), nullable=True)
    role = Column(String(30), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    entity_label = Column(String(200), nullable=True)
    changes_json = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)

    user = relationship("User")


class RoleLabel(Base):
    __tablename__ = "role_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_key = Column(String(30), unique=True, nullable=False)
    label_ar = Column(String(100), nullable=False)
    label_en = Column(String(100), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QRSession(Base):
    """جلسة حضور تعتمد على QR متجدد. ترتبط بـ AttendanceSession موجودة."""
    __tablename__ = "qr_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    attendance_session_id = Column(Integer, ForeignKey("attendance_sessions.id"),
                                    nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    hall_id = Column(Integer, ForeignKey("halls.id"), nullable=True)
    current_token = Column(String(64), nullable=False, index=True)
    token_rotates_at = Column(DateTime, nullable=False)
    session_expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    attendance_session = relationship("AttendanceSession")
    doctor = relationship("Doctor")
    course = relationship("Course")
    hall = relationship("Hall")
