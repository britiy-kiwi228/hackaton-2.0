# app/routers/users.py

from fastapi import APIRouter, Depends, HTTPException, status, Query # Убираем Request из импортов
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.database import get_db
from app.models import User, Skill, Role, Achievement
from app.schemas import (
    UserLogin,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from app.utils.security import get_current_user # Импортируем новую зависимость

# ==================== РОУТЕР ====================

router = APIRouter(prefix="/users", tags=["users"])


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_or_create_skill(db: Session, skill_name: str) -> Skill:
    """
    Получить навык по названию, или создать новый если его нет.
    """
    skill = db.query(Skill).filter(Skill.name.ilike(skill_name)).first()

    if not skill:
        skill = Skill(name=skill_name)
        db.add(skill)
        db.commit()
        db.refresh(skill)

    return skill


def update_user_skills(db: Session, user: User, skill_names: List[str]):
    """
    Обновить навыки пользователя.
    Принимает список названий навыков.
    """
    if not skill_names:
        return

    # Очищаем старые навыки
    user.skills.clear()

    # Добавляем новые
    for skill_name in skill_names:
        skill = get_or_create_skill(db, skill_name)
        if skill not in user.skills:
            user.skills.append(skill)

    db.commit()


# ==================== АУТЕНТИФИКАЦИЯ ====================

@router.post("/auth/telegram", response_model=UserResponse, status_code=status.HTTP_200_OK)
def telegram_auth(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    POST /users/auth/telegram
    Аутентификация через Telegram.

    Логика:
    - Ищем пользователя по tg_id
    - Если есть: возвращаем его
    - Если нет: создаем нового и возвращаем
    """
    # Ищем пользователя по tg_id
    user = db.query(User).filter(User.tg_id == user_data.tg_id).first()

    if user:
        # Обновляем username и full_name если нужно
        if user_data.username:
            user.username = user_data.username
        user.full_name = user_data.full_name
        db.commit()
        db.refresh(user)
        return user

    # Создаем нового пользователя
    new_user = User(
        tg_id=user_data.tg_id,
        username=user_data.username,
        full_name=user_data.full_name,
        main_role=None,  # Роль не обязательна при регистрации
        ready_to_work=True,  # По умолчанию готов работать
        bio="",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ==================== ПРОФИЛЬ ====================

# УБИРАЕМ Query параметр user_id, так как он теперь берётся из JWT
@router.patch("/me", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate = None,
    current_user: User = Depends(get_current_user), # Добавляем зависимость
    db: Session = Depends(get_db)
):
    """
    PATCH /users/me
    Обновление своего профиля.

    Параметры:
    - Тело запроса: bio, main_role, skills
    """
    # current_user уже получен из JWT
    user = current_user

    # Обновляем поля
    if user_update.bio is not None:
        user.bio = user_update.bio

    if user_update.main_role is not None:
        try:
            user.main_role = Role[user_update.main_role.value]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестная роль: {user_update.main_role}"
            )

    if user_update.ready_to_work is not None:
        user.ready_to_work = user_update.ready_to_work

    # Обновляем навыки
    if user_update.skills is not None:
        update_user_skills(db, user, user_update.skills)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# ==================== СПИСОК ПОЛЬЗОВАТЕЛЕЙ ====================

@router.get("/", response_model=List[UserListResponse])
def get_users(
    role: Optional[str] = Query(None, description="Фильтр по роли (backend, frontend, design, pm, analyst)"),
    hackathon_id: Optional[int] = Query(None, description="ID хакатона для фильтра"),
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(10, ge=1, le=100, description="Максимум записей в ответе"),
    db: Session = Depends(get_db)
):
    """
    GET /users/
    Получить список пользователей с фильтрами.

    Query параметры:
    - role: фильтр по роли
    - hackathon_id: получить участников хакатона
    - skip: смещение
    - limit: лимит результатов
    """
    query = db.query(User)

    # Фильтр по роли
    if role:
        try:
            role_enum = Role[role]
            query = query.filter(User.main_role == role_enum)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестная роль: {role}. Допустимые: backend, frontend, design, pm, analyst"
            )

    # Фильтр по хакатону (пользователи, которые уже в команде этого хакатона)
    if hackathon_id:
        # JOIN с Team где hackathon_id совпадает и user_id совпадает
        from app.models import Team
        query = query.join(Team, User.team_id == Team.id).filter(
            Team.hackathon_id == hackathon_id
        )

    # Пагинация
    users = query.offset(skip).limit(limit).all()

    return users


# ==================== ДЕТАЛЬНАЯ ИНФОРМАЦИЯ ====================

@router.get("/{user_id}", response_model=UserResponse)
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    """
    GET /users/{user_id}
    Получить детальную информацию о пользователе.

    Включает:
    - Основную информацию
    - Список навыков
    - Список достижений
    - Информацию о команде
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    return user


# ==================== ПОИСК ====================

@router.get("/search/by-tg-id/{tg_id}", response_model=Optional[UserResponse])
def get_user_by_tg_id(tg_id: int, db: Session = Depends(get_db)):
    """
    GET /users/search/by-tg-id/{tg_id}
    Получить пользователя по Telegram ID.
    """
    user = db.query(User).filter(User.tg_id == tg_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с tg_id {tg_id} не найден"
        )

    return user


@router.get("/search/by-username/{username}", response_model=Optional[UserResponse])
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """
    GET /users/search/by-username/{username}
    Получить пользователя по username.
    """
    user = db.query(User).filter(User.username.ilike(username)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с username '{username}' не найден"
        )

    return user


# ==================== НАВЫКИ ====================

@router.get("/{user_id}/skills", response_model=List[str])
def get_user_skills(user_id: int, db: Session = Depends(get_db)):
    """
    GET /users/{user_id}/skills
    Получить список навыков пользователя.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    return [skill.name for skill in user.skills]


# ==================== ДОСТИЖЕНИЯ ====================

@router.get("/{user_id}/achievements", response_model=List)
def get_user_achievements(user_id: int, db: Session = Depends(get_db)):
    """
    GET /users/{user_id}/achievements
    Получить список всех достижений пользователя.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    return user.achievements


@router.post("/{user_id}/achievements", status_code=status.HTTP_201_CREATED)
def add_achievement(
    user_id: int,
    achievement_data: dict,
    db: Session = Depends(get_db)
):
    """
    POST /users/{user_id}/achievements
    Добавить достижение пользователю.

    Параметры в теле запроса:
    - hackathon_name: str
    - place: Optional[int]
    - team_name: str
    - project_link: Optional[str]
    - year: int
    - description: str
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    achievement = Achievement(
        user_id=user_id,
        **achievement_data
    )

    db.add(achievement)
    db.commit()
    db.refresh(achievement)

    return achievement


# ==================== УДАЛЕНИЕ ====================

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)): # Добавляем current_user
    """
    DELETE /users/{user_id}
    Удалить пользователя. (Требуется аутентификация, упрощённая проверка)
    """
    # Простая проверка: можно удалить только себя
    if current_user.id != user_id:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    db.delete(user)
    db.commit()