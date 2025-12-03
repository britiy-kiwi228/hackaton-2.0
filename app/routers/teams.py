# app/routers/teams.py

from fastapi import APIRouter, Depends, HTTPException, status, Request # Оставляем Request только если нужно для других целей, но не для user
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from app.database import get_db
from app.models import User, Team, Hackathon, TeamRequest, RequestStatus
from app.schemas import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamListResponse,
    TeamRequestResponse,
    UserResponse,
)
from app.utils.security import get_current_user # Импортируем новую зависимость

# ==================== РОУТЕР ====================

router = APIRouter(prefix="/teams", tags=["teams"])


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

# УБИРАЕМ СТАРУЮ ФУНКЦИЮ get_current_user_from_request
# def get_current_user_from_request(request: Request) -> User:
#     """Получить текущего пользователя из request.state.user"""
#     user = getattr(request.state, "user", None)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Требуется аутентификация"
#         )
#     return user


def check_user_is_captain(team: Team, user: User):
    """Проверить, что пользователь — капитан команды"""
    if team.captain_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только капитан может выполнить это действие"
        )


# ==================== СОЗДАНИЕ И ПОЛУЧЕНИЕ ====================

@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    team_in: TeamCreate,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/
    Создание новой команды.
    Только автор может создать команду.
    Пользователь не должен быть в другой команде этого хакатона.
    """
    # current_user уже получен из JWT

    # Проверяем, что хакатон существует
    hackathon = db.query(Hackathon).filter(Hackathon.id == team_in.hackathon_id).first()
    if not hackathon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Хакатон с ID {team_in.hackathon_id} не найден"
        )

    # Проверяем, что юзер не состоит в другой команде этого хакатона
    existing_team = db.query(Team).join(
        User, User.team_id == Team.id
    ).filter(
        and_(
            Team.hackathon_id == team_in.hackathon_id,
            User.id == current_user.id
        )
    ).first()

    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже состоите в команде этого хакатона"
        )

    # Создаем команду
    new_team = Team(
        name=team_in.name,
        description=team_in.description or "",
        hackathon_id=team_in.hackathon_id,
        captain_id=current_user.id,
        is_looking=True,
    )

    db.add(new_team)
    db.flush()  # Чтобы получить ID команды

    # Добавляем капитана в команду
    current_user.team_id = new_team.id

    db.commit()
    db.refresh(new_team)

    return new_team


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, db: Session = Depends(get_db)):
    """
    GET /teams/{team_id}
    Получить информацию о команде (капитан + участники).
    """
    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    return team


@router.get("/", response_model=List[TeamListResponse])
def get_teams(
    hackathon_id: int = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    GET /teams/
    Получить список команд.
    Фильтр по hackathon_id (опционально).
    """
    query = db.query(Team)

    if hackathon_id:
        query = query.filter(Team.hackathon_id == hackathon_id)

    teams = query.offset(skip).limit(limit).all()
    return teams


# ==================== РЕДАКТИРОВАНИЕ ====================

@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_update: TeamUpdate,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    PUT /teams/{team_id}
    Обновление информации о команде.
    Только капитан может обновить.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    # Обновляем поля
    update_data = team_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    db.add(team)
    db.commit()
    db.refresh(team)

    return team


# ==================== УДАЛЕНИЕ ====================

@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    DELETE /teams/{team_id}
    Распускание команды.
    Только капитан может распустить команду.
    При этом сбрасывается team_id у всех участников.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    # Сбрасываем team_id у всех участников
    db.query(User).filter(User.team_id == team_id).update({User.team_id: None})

    # Удаляем команду
    db.delete(team)
    db.commit()


# ==================== ВСТУПЛЕНИЕ И ВЫХОД ====================

@router.post("/{team_id}/join", status_code=status.HTTP_201_CREATED)
def send_join_request(
    team_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/{team_id}/join
    Отправка запроса на вступление в команду.
    Юзер не должен быть капитаном другой команды на этом хакатоне.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    # Проверяем, что юзер не уже в команде
    if current_user.team_id == team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже в этой команде"
        )

    # Проверяем, что юзер не в другой команде этого хакатона
    other_team = db.query(Team).filter(
        and_(
            Team.hackathon_id == team.hackathon_id,
            Team.id != team_id,
            Team.captain_id == current_user.id
        )
    ).first()

    if other_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы — капитан другой команды на этом хакатоне"
        )

    # Проверяем, что нет уже запроса от этого юзера
    existing_request = db.query(TeamRequest).filter(
        and_(
            TeamRequest.user_id == current_user.id,
            TeamRequest.team_id == team_id,
            TeamRequest.status == RequestStatus.pending
        )
    ).first()

    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже отправили запрос в эту команду"
        )

    # Создаем запрос
    new_request = TeamRequest(
        user_id=current_user.id,
        team_id=team_id,
        is_invite=False,
        status=RequestStatus.pending
    )

    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return {"id": new_request.id, "status": "Запрос отправлен"}


@router.post("/{team_id}/leave", status_code=status.HTTP_200_OK)
def leave_team(
    team_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/{team_id}/leave
    Покинуть команду.
    Капитан не может просто покинуть команду (только распустить).
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    # Проверяем, что юзер в этой команде
    if current_user.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не в этой команде"
        )

    # Проверяем, что юзер не капитан
    if team.captain_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Капитан не может просто покинуть команду. Распустите команду вместо этого"
        )

    # Сбрасываем team_id
    current_user.team_id = None
    db.commit()

    return {"status": "Вы покинули команду"}


# ==================== УПРАВЛЕНИЕ УЧАСТНИКАМИ ====================

@router.post("/{team_id}/kick/{user_id}", status_code=status.HTTP_200_OK)
def kick_user_from_team(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/{team_id}/kick/{user_id}
    Исключить пользователя из команды.
    Только капитан может. Нельзя выгнать капитана.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    # Проверяем, что это не капитан
    if team.captain_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя выгнать капитана"
        )

    # Получаем пользователя
    user_to_kick = db.query(User).filter(User.id == user_id).first()

    if not user_to_kick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )

    # Проверяем, что он в этой команде
    if user_to_kick.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот пользователь не в вашей команде"
        )

    # Выгоняем пользователя
    user_to_kick.team_id = None
    db.commit()

    return {"status": f"Пользователь {user_id} исключен из команды"}


# ==================== УПРАВЛЕНИЕ ЗАПРОСАМИ ====================

@router.post("/{team_id}/accept_request/{request_id}", status_code=status.HTTP_200_OK)
def accept_join_request(
    team_id: int,
    request_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/{team_id}/accept_request/{request_id}
    Принятие запроса на вступление.
    Только капитан может.
    При успешном принятии добавляй user в команду.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    # Получаем запрос
    team_request = db.query(TeamRequest).filter(
        TeamRequest.id == request_id
    ).first()

    if not team_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Запрос с ID {request_id} не найден"
        )

    if team_request.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Запрос не относится к этой команде"
        )

    if team_request.status != RequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Запрос уже имеет статус {team_request.status.value}"
        )

    # Получаем пользователя
    user = db.query(User).filter(User.id == team_request.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )

    # Проверяем, что юзер не в другой команде этого хакатона
    if user.team_id and user.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже в другой команде этого хакатона"
        )

    # Добавляем юзера в команду
    user.team_id = team_id
    team_request.status = RequestStatus.accepted

    # Отклоняем другие запросы от этого юзера на этот хакатон
    db.query(TeamRequest).filter(
        and_(
            TeamRequest.user_id == team_request.user_id,
            TeamRequest.id != request_id,
            TeamRequest.team_id != team_id,
            TeamRequest.status == RequestStatus.pending
        )
    ).update({TeamRequest.status: RequestStatus.declined})

    db.commit()

    return {"status": "Запрос принят, пользователь добавлен в команду"}


@router.post("/{team_id}/decline_request/{request_id}", status_code=status.HTTP_200_OK)
def decline_join_request(
    team_id: int,
    request_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    POST /teams/{team_id}/decline_request/{request_id}
    Отклонение запроса на вступление.
    Только капитан может.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    # Получаем запрос
    team_request = db.query(TeamRequest).filter(
        TeamRequest.id == request_id
    ).first()

    if not team_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Запрос с ID {request_id} не найден"
        )

    if team_request.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Запрос не относится к этой команде"
        )

    if team_request.status != RequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Запрос уже имеет статус {team_request.status.value}"
        )

    # Отклоняем запрос
    team_request.status = RequestStatus.declined
    db.commit()

    return {"status": "Запрос отклонен"}


# ==================== ПОЛУЧЕНИЕ ЗАПРОСОВ ====================

@router.get("/{team_id}/requests", response_model=List[TeamRequestResponse])
def get_team_requests(
    team_id: int,
    current_user: User = Depends(get_current_user), # Заменяем request на current_user
    db: Session = Depends(get_db)
):
    """
    GET /teams/{team_id}/requests
    Получить список запросов на вступление в команду.
    Только капитан может.
    """
    # current_user уже получен из JWT

    team = db.query(Team).filter(Team.id == team_id).first()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Команда с ID {team_id} не найдена"
        )

    check_user_is_captain(team, current_user)

    requests = db.query(TeamRequest).filter(
        TeamRequest.team_id == team_id
    ).all()

    return requests