from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import config

Base = declarative_base()
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
        _engine = create_engine(
            config.DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()


def init_db():
    from database.models import Base as ModelBase
    engine = get_engine()
    ModelBase.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Run idempotent migrations in order."""
    import importlib.util
    import os as _os

    mig_dir = _os.path.join(_os.path.dirname(__file__), "migrations")
    mig_files = [
        ("002_add_scan_logs.py", "DATABASE_PATH"),
        ("003_add_roles_and_notes.py", None),
        ("004_remove_admin_role.py", None),
        ("005_audit_and_teaching_type.py", None),
        ("006_qr_sessions.py", None),
    ]
    for filename, pass_arg in mig_files:
        try:
            mig_path = _os.path.join(mig_dir, filename)
            if not _os.path.exists(mig_path):
                continue
            spec = importlib.util.spec_from_file_location(
                f"_mig_{filename.replace('.py', '')}", mig_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if pass_arg == "DATABASE_PATH":
                mod.run(config.DATABASE_PATH)
            elif hasattr(mod, "run"):
                mod.run()
            elif hasattr(mod, "upgrade"):
                mod.upgrade()
        except Exception as e:
            print(f"[migrations] {filename} failed: {e}")
