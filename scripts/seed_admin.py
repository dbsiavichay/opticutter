"""Seeds the first administrator from ADMIN_EMAIL / ADMIN_PASSWORD in .env."""

import sys

sys.path.insert(0, ".")

from src.modules.users.enums import UserRole
from src.modules.users.model import UserModel
from src.shared.config import config
from src.shared.database import SessionLocal
from src.shared.security import hash_password

if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
    print("ERROR: set ADMIN_EMAIL and ADMIN_PASSWORD in .env")
    sys.exit(1)

db = SessionLocal()
try:
    exists = db.query(UserModel).filter(UserModel.email == config.ADMIN_EMAIL).first()
    if exists:
        print(f"User already exists: {config.ADMIN_EMAIL}")
        sys.exit(0)
    db.add(
        UserModel(
            email=config.ADMIN_EMAIL,
            hashed_password=hash_password(config.ADMIN_PASSWORD),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db.commit()
    print(f"Admin created: {config.ADMIN_EMAIL}")
finally:
    db.close()
