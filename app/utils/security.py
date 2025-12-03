from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.utils.auth import verify_access_token

oauth2_scheme = HTTPBearer()

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"}
)

def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not token or not token.credentials:
        raise CREDENTIALS_EXCEPTION
    payload = verify_access_token(token=token.credentials)
    user_id: str = payload.get("sub")
    if not user_id:
        raise CREDENTIALS_EXCEPTION
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise CREDENTIALS_EXCEPTION
    return user
