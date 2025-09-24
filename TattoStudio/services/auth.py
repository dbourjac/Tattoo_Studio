from datetime import datetime
from typing import Optional, Dict

import bcrypt
from sqlalchemy.orm import Session

from data.models.user import User

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def authenticate(db: Session, username: str, password: str) -> Optional[Dict]:
    """Devuelve un dict con info mínima del usuario si credenciales válidas; de lo contrario None."""
    u = get_user_by_username(db, username)
    if not u or not u.is_active:
        return None
    if not verify_password(password, u.password_hash):
        return None

    # actualizar last_login
    u.last_login = datetime.utcnow()
    db.commit()

    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "artist_id": u.artist_id,
    }
