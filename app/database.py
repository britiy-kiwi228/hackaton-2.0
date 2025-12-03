from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from typing import Generator

# ==================== КОНФИГУРАЦИЯ БД ====================
DATABASE_URL = "sqlite:///./hackathon.db"

# Engine (движок для подключения к БД)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Только для SQLite
    poolclass=StaticPool,  # Оптимально для SQLite
)

# SessionLocal (фабрика для создания сессий)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Не обнулять объекты после commit
)

# Base (базовый класс для всех моделей)
class Base(DeclarativeBase):
    """Базовый класс для SQLAlchemy 2.0+ моделей"""
    pass

# ==================== ФУНКЦИЯ ЗАВИСИМОСТИ ====================
def get_db() -> Generator:
    """
    Dependency для FastAPI.
    Создает сессию БД, передает в обработчик эндпоинта,
    и закрывает после выполнения.
    
    Использование в FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()  # Откатываем изменения при ошибке
        raise e
    finally:
        db.close()  # Закрываем сессию в любом случае
