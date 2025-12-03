from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, BigInteger, Enum, ForeignKey, Table
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional
from app.database import Base

# ==================== ENUM КЛАССЫ ====================

class Role(PyEnum):
    """Роли участников"""
    backend = "backend"
    frontend = "frontend"
    design = "design"
    pm = "pm"
    analyst = "analyst"


class RequestStatus(PyEnum):
    """Статусы заявок/приглашений"""
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    canceled = "canceled"


# ==================== ТАБЛИЦЫ-ПОСРЕДНИКИ ====================

# Таблица M2M для User ↔ Skill
user_skills = Table(
    "user_skills",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


# ==================== МОДЕЛИ ====================

class Skill(Base):
    """Навыки участников"""
    __tablename__ = "skills"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    
    # Связь M2M с User
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_skills,
        back_populates="skills",
        cascade="all, delete",
    )


class Hackathon(Base):
    """Хакатоны"""
    __tablename__ = "hackathons"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    start_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime, index=True, comment="До какого времени можно подать заявку")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Ссылка на логотип")
    location: Mapped[str] = mapped_column(String(255), comment="Онлайн или город")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с Team (one-to-many)
    teams: Mapped[List["Team"]] = relationship(
        "Team",
        back_populates="hackathon",
        cascade="all, delete",
    )
    
    # Связь с Request (one-to-many)
    requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="hackathon",
        cascade="all, delete",
    )


class User(Base):
    """Участники хакатона"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)  # Важно для телеграма
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    bio: Mapped[str] = mapped_column(Text, default="")
    main_role: Mapped[Optional[Role]] = mapped_column(Enum(Role), index=True, nullable=True, default=None)  # Опциональная роль
    ready_to_work: Mapped[bool] = mapped_column(Boolean, default=True)  # Готов ли работать (в проектах)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Foreign Key на Team
    team_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Связи
    # M2M со Skill
    skills: Mapped[List[Skill]] = relationship(
        "Skill",
        secondary=user_skills,
        back_populates="users",
    )
    
    # One-to-many с Team (обратная ссылка из Team)
    team: Mapped[Optional["Team"]] = relationship(
        "Team",
        back_populates="members",
        foreign_keys=[team_id],
    )
    
    # One-to-many с TeamRequest
    requests_sent: Mapped[List["TeamRequest"]] = relationship(
        "TeamRequest",
        back_populates="user",
        foreign_keys="TeamRequest.user_id",
        cascade="all, delete",
    )
    
    # One-to-many (капитан команды)
    teams_led: Mapped[List["Team"]] = relationship(
        "Team",
        back_populates="captain",
        foreign_keys="Team.captain_id",
    )
    
    # One-to-many с Achievement (достижения/портфолио)
    achievements: Mapped[List["Achievement"]] = relationship(
        "Achievement",
        back_populates="user",
        cascade="all, delete",
    )
    
    # One-to-many с Request (отправленные запросы)
    sent_requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="sender",
        foreign_keys="Request.sender_id",
        cascade="all, delete",
    )
    
    # One-to-many с Request (полученные запросы)
    received_requests: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="receiver",
        foreign_keys="Request.receiver_id",
        cascade="all, delete",
    )


class Team(Base):
    """Команды в хакатоне"""
    __tablename__ = "teams"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    chat_link: Mapped[str] = mapped_column(String(500), default="")  # Ссылка на ТГ чат
    is_looking: Mapped[bool] = mapped_column(Boolean, default=True)  # Ищем участников?
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    hackathon_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hackathons.id", ondelete="CASCADE"),
        index=True,
    )
    
    captain_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Связи
    hackathon: Mapped["Hackathon"] = relationship(
        "Hackathon",
        back_populates="teams",
    )
    
    captain: Mapped["User"] = relationship(
        "User",
        back_populates="teams_led",
        foreign_keys=[captain_id],
    )
    
    # Список участников команды
    members: Mapped[List["User"]] = relationship(
        "User",
        back_populates="team",
        foreign_keys="User.team_id",
    )
    
    # Заявки/приглашения в команду
    requests: Mapped[List["TeamRequest"]] = relationship(
        "TeamRequest",
        back_populates="team",
        cascade="all, delete",
    )
    
    # Общие запросы к команде
    requests_general: Mapped[List["Request"]] = relationship(
        "Request",
        back_populates="team",
        cascade="all, delete",
    )


class TeamRequest(Base):
    """Заявки и приглашения в команду"""
    __tablename__ = "team_requests"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Foreign Keys
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Флаги и статус
    is_invite: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True = капитан пригласил юзера, False = юзер постучался"
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.pending,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship(
        "User",
        back_populates="requests_sent",
        foreign_keys=[user_id],
    )
    
    team: Mapped["Team"] = relationship(
        "Team",
        back_populates="requests",
        foreign_keys=[team_id],
    )


class Achievement(Base):
    """Достижения и портфолио пользователя (победы в прошлых хакатонах)"""
    __tablename__ = "achievements"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Foreign Key на User
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Основная информация
    hackathon_name: Mapped[str] = mapped_column(String(255), index=True)
    place: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Занятое место (если был результат)")
    team_name: Mapped[str] = mapped_column(String(255))
    project_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Ссылка на GitHub или презентацию")
    year: Mapped[int] = mapped_column(Integer, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Связь с User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="achievements",
        foreign_keys=[user_id],
    )


class RequestType(PyEnum):
    """Типы запросов"""
    join_team = "join_team"
    collaborate = "collaborate"
    invite = "invite"


class Request(Base):
    """Общие запросы (на сотрудничество, вступление и т.д.)"""
    __tablename__ = "requests"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Foreign Keys
    sender_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    receiver_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Получатель (если это личный запрос)"
    )
    
    team_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Команда (если это запрос на вступление)"
    )
    
    hackathon_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hackathons.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Основная информация
    request_type: Mapped[RequestType] = mapped_column(
        Enum(RequestType),
        index=True,
        comment="Тип запроса (join_team, collaborate, invite)"
    )
    
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus),
        default=RequestStatus.pending,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_requests",
        foreign_keys=[sender_id],
    )
    
    receiver: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="received_requests",
        foreign_keys=[receiver_id],
    )
    
    team: Mapped[Optional["Team"]] = relationship(
        "Team",
        back_populates="requests_general",
    )
    
    hackathon: Mapped["Hackathon"] = relationship(
        "Hackathon",
        back_populates="requests",
    )
