import hmac
import hashlib
from datetime import datetime, timedelta
import time  # Добавил для time.time()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import TelegramAuthRequest, TokenResponse
from app.utils.auth import create_access_token, SECRET_KEY  # Если SECRET_KEY здесь, ок

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/telegram/login", response_model=TokenResponse)
def telegram_login(data: TelegramAuthRequest, db: Session = Depends(get_db)):
    auth_data = data.auth_data.copy()
    # 1. Проверка даты (теперь с time.time() для local consistency)
    auth_date = int(auth_data.get("auth_date", "0"))
    if abs(time.time() - auth_date) > 3600:
        raise HTTPException(status_code=401, detail="Authentication data expired")
    # 2. Подпись
    received_hash = auth_data.pop("hash", "")
    sorted_items = sorted([(k, v) for k, v in auth_data.items() if v is not None])
    sorted_data = "\n".join([f"{k}={v}" for k, v in sorted_items])
    secret_key = hashlib.sha256(SECRET_KEY.encode()).digest()
    calculated_hash = hmac.new(secret_key, sorted_data.encode(), hashlib.sha256).hexdigest()
    if calculated_hash != received_hash:
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")
    # 3. Поиск/создание пользователя
    tg_id = int(auth_data["id"])
    user = db.query(User).filter_by(tg_id=tg_id).first()
    if not user:
        user = User(
            tg_id=tg_id,
            username=auth_data.get("username"),
            full_name=f"{auth_data.get('first_name', '')} {auth_data.get('last_name', '')}".strip(),
            bio="",
            main_role=None,
            ready_to_work=True
        )
        db.add(user)
        db.commit()  # необходимо чтобы получить id
        db.refresh(user)
    # 4. Генерация токена
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)