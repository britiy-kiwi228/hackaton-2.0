"""
Роутер для управления запросами и приглашениями
"""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request as StarletteRequest # Оставляем, если нужен для других целей
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.database import get_db
from app.models import Request, RequestStatus, RequestType, User, Team, Hackathon
from app.schemas import RequestResponse, RequestCreate, RequestUpdate
from app.utils.security import get_current_user # Импортируем новую зависимость

router = APIRouter(
    prefix="/requests",
    tags=["requests"]
)


# УБИРАЕМ СТАРУЮ ФУНКЦИЮ get_current_user_from_request
# def get_current_user_from_request(http_request: StarletteRequest) -> User:
#     """Получить текущего пользователя из request.state"""
#     if not hasattr(http_request, 'state') or not hasattr(http_request.state, 'user'):
#         raise HTTPException(status_code=401, detail="User not authenticated")
#     return http_request.state.user


@router.get("/sent", response_model=List[RequestResponse])
async def get_sent_requests(
    # http_request: StarletteRequest, # Убираем
    current_user: User = Depends(get_current_user), # Добавляем
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: RequestStatus = None,
    request_type: RequestType = None,
    db: Session = Depends(get_db)
):
    """
    Получить исходящие запросы текущего пользователя

    - **skip**: Пропустить N записей
    - **limit**: Максимум записей на странице
    - **status**: Фильтр по статусу (pending, accepted, declined, canceled)
    - **request_type**: Фильтр по типу (join_team, collaborate, invite)
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    query = db.query(Request).filter(Request.sender_id == current_user.id)

    if status:
        query = query.filter(Request.status == status)

    if request_type:
        query = query.filter(Request.request_type == request_type)

    requests = query.order_by(Request.created_at.desc()).offset(skip).limit(limit).all()

    return requests


@router.get("/received", response_model=List[RequestResponse])
async def get_received_requests(
    # http_request: StarletteRequest, # Убираем
    current_user: User = Depends(get_current_user), # Добавляем
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: RequestStatus = None,
    request_type: RequestType = None,
    db: Session = Depends(get_db)
):
    """
    Получить входящие запросы текущего пользователя

    Включает:
    - Запросы, где текущий пользователь получатель (receiver_id)
    - Запросы к командам, где текущий пользователь капитан

    - **skip**: Пропустить N записей
    - **limit**: Максимум записей на странице
    - **status**: Фильтр по статусу
    - **request_type**: Фильтр по типу
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    # Получить команды, где пользователь капитан
    captain_teams = db.query(Team.id).filter(Team.captain_id == current_user.id).all()
    captain_team_ids = [t[0] for t in captain_teams]

    # Запросы где текущий пользователь получатель ИЛИ запросы к его командам
    query = db.query(Request).filter(
        or_(
            Request.receiver_id == current_user.id,
            Request.team_id.in_(captain_team_ids) if captain_team_ids else False
        )
    )

    if status:
        query = query.filter(Request.status == status)

    if request_type:
        query = query.filter(Request.request_type == request_type)

    requests = query.order_by(Request.created_at.desc()).offset(skip).limit(limit).all()

    return requests


@router.post("/", response_model=RequestResponse, status_code=201)
async def create_request(
    # http_request: StarletteRequest, # Убираем
    req_data: RequestCreate,
    current_user: User = Depends(get_current_user), # Добавляем
    db: Session = Depends(get_db)
):
    """
    Создать новый запрос/приглашение

    Типы запросов:
    - **join_team**: Присоединиться к команде (требует team_id, sender становится member)
    - **collaborate**: Приглашение сотрудничать (требует receiver_id)
    - **invite**: Приглашение в команду (требует receiver_id и team_id, только капитан)

    Валидация:
    - Нельзя отправить запрос самому себе
    - Не может быть дубликата активного запроса с тем же типом
    - join_team: требует team_id
    - collaborate: требует receiver_id
    - invite: требует receiver_id и team_id, отправитель должен быть капитаном
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    # Валидация: нельзя отправить запрос самому себе
    if req_data.receiver_id and req_data.receiver_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot send request to yourself"
        )

    # Получить хакатон
    hackathon = db.query(Hackathon).filter(
        Hackathon.id == req_data.hackathon_id
    ).first()
    if not hackathon:
        raise HTTPException(status_code=404, detail="Hackathon not found")

    # Валидация по типу запроса
    if req_data.request_type == RequestType.join_team:
        if not req_data.team_id:
            raise HTTPException(
                status_code=400,
                detail="team_id required for join_team request"
            )

        team = db.query(Team).filter(Team.id == req_data.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Проверить, что пользователь не в другой команде того же хакатона
        if current_user.team_id:
            user_team = db.query(Team).filter(
                and_(
                    Team.id == current_user.team_id,
                    Team.hackathon_id == hackathon.id
                )
            ).first()
            if user_team:
                raise HTTPException(
                    status_code=400,
                    detail="You are already in a team for this hackathon"
                )

    elif req_data.request_type == RequestType.collaborate:
        if not req_data.receiver_id:
            raise HTTPException(
                status_code=400,
                detail="receiver_id required for collaborate request"
            )

        # Проверить, что получатель существует
        receiver = db.query(User).filter(User.id == req_data.receiver_id).first()
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")

    elif req_data.request_type == RequestType.invite:
        if not req_data.receiver_id or not req_data.team_id:
            raise HTTPException(
                status_code=400,
                detail="receiver_id and team_id required for invite request"
            )

        # Проверить, что отправитель капитан команды
        team = db.query(Team).filter(Team.id == req_data.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        if team.captain_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Only team captain can send invites"
            )

        # Проверить, что приглашаемый существует
        receiver = db.query(User).filter(User.id == req_data.receiver_id).first()
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver not found")

    # Проверить дубликат активного запроса
    existing_request = db.query(Request).filter(
        and_(
            Request.sender_id == current_user.id,
            Request.receiver_id == req_data.receiver_id if req_data.receiver_id else True,
            Request.team_id == req_data.team_id if req_data.team_id else True,
            Request.request_type == req_data.request_type,
            Request.status == RequestStatus.pending,
            Request.hackathon_id == req_data.hackathon_id,
        )
    ).first()

    if existing_request:
        raise HTTPException(
            status_code=400,
            detail="Pending request of this type already exists"
        )

    # Создать новый запрос
    new_request = Request(
        sender_id=current_user.id,
        receiver_id=req_data.receiver_id,
        team_id=req_data.team_id,
        hackathon_id=req_data.hackathon_id,
        request_type=req_data.request_type,
        status=RequestStatus.pending,
    )

    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return new_request


@router.post("/{request_id}/accept", response_model=RequestResponse)
async def accept_request(
    # http_request: StarletteRequest, # Убираем
    request_id: int,
    current_user: User = Depends(get_current_user), # Добавляем
    db: Session = Depends(get_db)
):
    """
    Принять входящий запрос

    Допускается:
    - Получателю запроса (для collaborate)
    - Капитану команды (для invite, join_team на команду)

    При принятии:
    - join_team: пользователь добавляется в команду
    - invite: пользователь добавляется в команду
    - collaborate: запрос переходит в accepted
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверить прав доступа
    is_receiver = req.receiver_id == current_user.id
    is_team_captain = (
        req.team_id and
        db.query(Team).filter(
            and_(
                Team.id == req.team_id,
                Team.captain_id == current_user.id
            )
        ).first()
    )

    if req.request_type == RequestType.collaborate:
        if not is_receiver:
            raise HTTPException(
                status_code=403,
                detail="Only receiver can accept collaboration request"
            )
    elif req.request_type in [RequestType.join_team, RequestType.invite]:
        if not is_team_captain:
            raise HTTPException(
                status_code=403,
                detail="Only team captain can accept this request"
            )

    # Проверить статус
    if req.status != RequestStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Request is already {req.status}"
        )

    # Обновить статус
    req.status = RequestStatus.accepted

    # Дополнительные действия в зависимости от типа
    if req.request_type in [RequestType.join_team, RequestType.invite]:
        # Добавить пользователя в команду
        user = db.query(User).filter(User.id == req.sender_id).first()
        if user:
            user.team_id = req.team_id

            # Отклонить все остальные pending запросы join_team от этого пользователя на этот хакатон
            db.query(Request).filter(
                and_(
                    Request.sender_id == req.sender_id,
                    Request.hackathon_id == req.hackathon_id,
                    Request.request_type == RequestType.join_team,
                    Request.status == RequestStatus.pending,
                    Request.id != request_id
                )
            ).update({Request.status: RequestStatus.declined})

    db.commit()
    db.refresh(req)

    return req


@router.post("/{request_id}/decline", response_model=RequestResponse)
async def decline_request(
    # http_request: StarletteRequest, # Убираем
    request_id: int,
    current_user: User = Depends(get_current_user), # Добавляем
    db: Session = Depends(get_db)
):
    """
    Отклонить входящий запрос

    Допускается:
    - Получателю запроса (для collaborate)
    - Капитану команды (для invite, join_team на команду)
    - Отправителю запроса (для отмены собственного запроса)
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    # Проверить права доступа
    is_sender = req.sender_id == current_user.id
    is_receiver = req.receiver_id == current_user.id
    is_team_captain = (
        req.team_id and
        db.query(Team).filter(
            and_(
                Team.id == req.team_id,
                Team.captain_id == current_user.id
            )
        ).first()
    )

    if req.request_type == RequestType.collaborate:
        if not (is_receiver or is_sender):
            raise HTTPException(
                status_code=403,
                detail="Only receiver or sender can decline collaboration request"
            )
    elif req.request_type in [RequestType.join_team, RequestType.invite]:
        if not (is_team_captain or is_sender):
            raise HTTPException(
                status_code=403,
                detail="Only team captain or sender can decline this request"
            )

    # Проверить статус
    if req.status != RequestStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Request is already {req.status}"
        )

    # Обновить статус
    req.status = RequestStatus.declined

    db.commit()
    db.refresh(req)

    return req


@router.delete("/{request_id}", status_code=204)
async def cancel_request(
    # http_request: StarletteRequest, # Убираем
    request_id: int,
    current_user: User = Depends(get_current_user), # Добавляем
    db: Session = Depends(get_db)
):
    """
    Отменить запрос (только отправитель, только если pending)
    """
    # current_user = get_current_user_from_request(http_request) # Убираем
    # current_user уже получен из JWT

    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if req.sender_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only request sender can cancel"
        )

    if req.status != RequestStatus.pending:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel request with status {req.status}"
        )

    req.status = RequestStatus.canceled
    db.commit()

    return None