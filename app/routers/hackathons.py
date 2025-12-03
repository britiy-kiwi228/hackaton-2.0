from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import List

from app.database import get_db
from app.models import Hackathon
from app.schemas import (
    HackathonCreate,
    HackathonUpdate,
    HackathonResponse,
    CalendarResponse,
    NotificationResponse,
)

# ==================== РОУТЕР ====================

router = APIRouter(prefix="/hackathons", tags=["hackathons"])


# ==================== ОСНОВНЫЕ CRUD ОПЕРАЦИИ ====================

@router.post("/", response_model=HackathonResponse, status_code=status.HTTP_201_CREATED)
def create_hackathon(hackathon_in: HackathonCreate, db: Session = Depends(get_db)):
    """
    POST /hackathons/
    Создает новый хакатон.
    """
    # Проверяем корректность дат
    if hackathon_in.start_date >= hackathon_in.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date должна быть раньше end_date"
        )
    
    if hackathon_in.registration_deadline > hackathon_in.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_deadline не может быть после start_date"
        )
    
    # Создаем новый хакатон
    db_hackathon = Hackathon(**hackathon_in.dict())
    db.add(db_hackathon)
    db.commit()
    db.refresh(db_hackathon)
    
    return db_hackathon


@router.get("/", response_model=List[HackathonResponse])
def get_all_hackathons(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(10, ge=1, le=100, description="Максимум записей в ответе"),
    db: Session = Depends(get_db)
):
    """
    GET /hackathons/
    Возвращает список всех хакатонов с пагинацией.
    
    Query параметры:
    - skip: смещение (по умолчанию 0)
    - limit: лимит результатов (по умолчанию 10, макс 100)
    """
    hackathons = db.query(Hackathon).offset(skip).limit(limit).all()
    return hackathons


@router.get("/{hackathon_id}", response_model=HackathonResponse)
def get_hackathon_by_id(hackathon_id: int, db: Session = Depends(get_db)):
    """
    GET /hackathons/{hackathon_id}
    Возвращает информацию о конкретном хакатоне.
    """
    hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
    
    if not hackathon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Хакатон с ID {hackathon_id} не найден"
        )
    
    return hackathon


@router.put("/{hackathon_id}", response_model=HackathonResponse)
def update_hackathon(
    hackathon_id: int,
    hackathon_update: HackathonUpdate,
    db: Session = Depends(get_db)
):
    """
    PUT /hackathons/{hackathon_id}
    Обновляет информацию о хакатоне.
    """
    db_hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
    
    if not db_hackathon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Хакатон с ID {hackathon_id} не найден"
        )
    
    # Обновляем только переданные поля
    update_data = hackathon_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_hackathon, field, value)
    
    db.add(db_hackathon)
    db.commit()
    db.refresh(db_hackathon)
    
    return db_hackathon


@router.delete("/{hackathon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hackathon(hackathon_id: int, db: Session = Depends(get_db)):
    """
    DELETE /hackathons/{hackathon_id}
    Удаляет хакатон.
    """
    db_hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
    
    if not db_hackathon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Хакатон с ID {hackathon_id} не найден"
        )
    
    db.delete(db_hackathon)
    db.commit()


# ==================== СПЕЦИАЛИЗИРОВАННЫЕ ЭНДПОИНТЫ ====================

@router.get("/calendar/view", response_model=CalendarResponse)
def get_hackathons_calendar(db: Session = Depends(get_db)):
    """
    GET /hackathons/calendar/view
    Возвращает список будущих и прошедших хакатонов.
    Будущие отсортированы по start_date (от ближайшего к дальнему).
    """
    now = datetime.utcnow()
    
    # Получаем все хакатоны
    all_hackathons = db.query(Hackathon).all()
    
    # Разделяем на будущие и прошедшие
    upcoming = [h for h in all_hackathons if h.start_date > now]
    history = [h for h in all_hackathons if h.start_date <= now]
    
    # Сортируем будущие по start_date (от ближайшего)
    upcoming.sort(key=lambda x: x.start_date)
    
    # Сортируем историю в обратном порядке (от новых к старым)
    history.sort(key=lambda x: x.start_date, reverse=True)
    
    return CalendarResponse(
        upcoming=[HackathonResponse.from_orm(h) for h in upcoming],
        history=[HackathonResponse.from_orm(h) for h in history],
    )


@router.get("/notifications/check_upcoming", response_model=NotificationResponse)
def check_upcoming_hackathon(db: Session = Depends(get_db)):
    """
    GET /hackathons/notifications/check_upcoming
    Проверяет, есть ли хакатон, который начнется в течение 3 дней.
    Используется фронтендом при входе в приложение.
    
    Возвращает:
    - has_notification: bool
    - message: str (если есть уведомление)
    - hackathon_id: int (если есть уведомление)
    """
    now = datetime.utcnow()
    three_days_later = now + timedelta(days=3)
    
    # Ищем хакатон, который начнется в течение 3 дней
    upcoming_hackathon = db.query(Hackathon).filter(
        and_(
            Hackathon.start_date > now,
            Hackathon.start_date <= three_days_later,
            Hackathon.is_active == True,
        )
    ).order_by(Hackathon.start_date).first()
    
    if not upcoming_hackathon:
        return NotificationResponse(has_notification=False)
    
    # Вычисляем, через сколько часов начнется хакатон
    time_diff = upcoming_hackathon.start_date - now
    hours_left = round(time_diff.total_seconds() / 3600)
    
    # Формируем сообщение с правильным склонением
    if hours_left < 1:
        hours_text = "менее часа"
    elif hours_left == 1:
        hours_text = "1 час"
    elif hours_left % 10 == 1 and hours_left % 100 != 11:
        hours_text = f"{hours_left} час"
    elif hours_left % 10 in [2, 3, 4] and hours_left % 100 not in [12, 13, 14]:
        hours_text = f"{hours_left} часа"
    else:
        hours_text = f"{hours_left} часов"
    
    message = f"Хакатон '{upcoming_hackathon.title}' начинается через {hours_text}! Успей собрать команду."
    
    return NotificationResponse(
        has_notification=True,
        message=message,
        hackathon_id=upcoming_hackathon.id,
    )
