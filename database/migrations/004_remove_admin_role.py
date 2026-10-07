"""Migration 004: Remove admin role — promote admin users to dean."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session
from database.models import User


def upgrade():
    session = get_session()
    try:
        admins = session.query(User).filter_by(role="admin").all()
        for u in admins:
            u.role = "dean"
            print(f"  Promoted user '{u.username}' from admin to dean")
        session.commit()
        print(f"Migration 004: Promoted {len(admins)} admin(s) to dean.")
    except Exception as e:
        session.rollback()
        print(f"Migration 004 failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    upgrade()