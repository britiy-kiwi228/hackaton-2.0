from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

# Импортируем Enum Role из моделей (для использования в схемах)
class RoleEnum(str, Enum):
    """Роли участников"""
    backend = "backend"
    frontend = "frontend"
    design = "design"
    pm = "pm"
    analyst = "analyst"


# ==================== USER СХЕМЫ ====================

class UserBase(BaseModel):
    """Базовая схема пользователя"""
    username: Optional[str] = None
    full_name: str
    bio: str = ""
    main_role: RoleEnum
    ready_to_work: bool = True


class UserLogin(BaseModel):
    """Схема для логина через Telegram"""
    tg_id: int
    username: Optional[str] = None
    full_name: str


class UserUpdate(BaseModel):
    """Схема для обновления профиля"""
    bio: Optional[str] = None
    main_role: Optional[RoleEnum] = None
    ready_to_work: Optional[bool] = None  # Готов ли работать
    skills: Optional[List[str]] = None  # Список названий навыков


class SkillResponse(BaseModel):
    """Схема для ответа со скиллом"""
    id: int
    name: str
    
    class Config:
        from_attributes = True


class AchievementResponse(BaseModel):
    """Схема для ответа с достижением"""
    id: int
    hackathon_name: str
    place: Optional[int]
    team_name: str
    project_link: Optional[str]
    year: int
    description: str
    
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Модель ответа пользователя (полная информация)"""
    id: int
    tg_id: int
    username: Optional[str]
    full_name: str
    bio: str
    main_role: Optional[str]  # Может быть None если роль еще не выбрана
    ready_to_work: bool
    team_id: Optional[int]
    created_at: datetime
    skills: List[SkillResponse] = []
    achievements: List[AchievementResponse] = []
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Модель для списка пользователей (краткая информация)"""
    id: int
    tg_id: int
    username: Optional[str]
    full_name: str
    main_role: Optional[str]
    team_id: Optional[int]
    
    class Config:
        from_attributes = True


class UserCreateOld(BaseModel):
    """Модель для создания пользователя (старая версия)"""
    name: str
    email: EmailStr


class UserResponseOld(BaseModel):
    """Модель ответа пользователя (старая версия)"""
    id: int
    name: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== HACKATHON СХЕМЫ ====================

class HackathonCreate(BaseModel):
    """Схема для создания нового хакатона"""
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    registration_deadline: datetime
    logo_url: Optional[str] = None
    location: str
    is_active: bool = True


class HackathonUpdate(BaseModel):
    """Схема для обновления хакатона"""
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    registration_deadline: Optional[datetime] = None
    logo_url: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class HackathonResponse(BaseModel):
    """Модель для ответа с информацией о хакатоне"""
    id: int
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    registration_deadline: datetime
    logo_url: Optional[str]
    location: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CalendarResponse(BaseModel):
    """Ответ для календаря хакатонов"""
    upcoming: List[HackathonResponse]
    history: List[HackathonResponse]


class NotificationResponse(BaseModel):
    """Ответ с уведомлением о ближайшем хакатоне"""
    has_notification: bool
    message: Optional[str] = None
    hackathon_id: Optional[int] = None


# ==================== TEAM СХЕМЫ ====================

class TeamCreate(BaseModel):
    """Схема для создания команды"""
    name: str
    description: Optional[str] = None
    hackathon_id: int


class TeamUpdate(BaseModel):
    """Схема для обновления команды"""
    name: Optional[str] = None
    description: Optional[str] = None
    is_looking: Optional[bool] = None


class TeamResponse(BaseModel):
    """Полная информация о команде"""
    id: int
    name: str
    description: str
    hackathon_id: int
    captain_id: int
    is_looking: bool
    created_at: datetime
    captain: Optional['UserResponse'] = None
    members: List['UserResponse'] = []
    
    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Краткая информация о команде"""
    id: int
    name: str
    hackathon_id: int
    captain_id: int
    is_looking: bool
    
    class Config:
        from_attributes = True


class TeamRequestCreate(BaseModel):
    """Схема для создания заявки в команду"""
    team_id: int
    is_invite: bool = False  # False = юзер постучался, True = капитан пригласил


class TeamRequestResponse(BaseModel):
    """Информация о заявке в команду"""
    id: int
    user_id: int
    team_id: int
    is_invite: bool
    status: str
    created_at: datetime
    user: Optional['UserListResponse'] = None
    
    class Config:
        from_attributes = True


# ==================== GENERAL REQUEST СХЕМЫ ====================

class RequestTypeEnum(str, Enum):
    """Типы запросов"""
    join_team = "join_team"
    collaborate = "collaborate"
    invite = "invite"


class RequestStatusEnum(str, Enum):
    """Статусы запросов"""
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    canceled = "canceled"


class RequestCreate(BaseModel):
    """Схема для создания запроса"""
    receiver_id: Optional[int] = None
    team_id: Optional[int] = None
    hackathon_id: int
    request_type: RequestTypeEnum


class RequestUpdate(BaseModel):
    """Схема для обновления запроса"""
    status: Optional[RequestStatusEnum] = None


class RequestResponse(BaseModel):
    """Информация о общем запросе (запрос на сотрудничество, вступление и т.д.)"""
    id: int
    sender_id: int
    receiver_id: Optional[int]
    team_id: Optional[int]
    request_type: str
    status: str
    hackathon_id: int
    created_at: datetime
    sender: Optional['UserResponse'] = None
    receiver: Optional['UserResponse'] = None
    team: Optional['TeamResponse'] = None
    
    class Config:
        from_attributes = True


# ==================== RECOMMENDATIONS СХЕМЫ ====================

class RecommendationRequest(BaseModel):
    """Запрос рекомендаций для пользователя или команды"""
    for_what: str  # "team" или "user"
    preferred_roles: Optional[List[str]] = None  # Предпочитаемые роли
    preferred_skills: Optional[List[str]] = None  # Предпочитаемые навыки
    exclude_team_ids: Optional[List[int]] = None  # Исключить команды
    exclude_user_ids: Optional[List[int]] = None  # Исключить пользователей
    hackathon_id: int  # ID хакатона для контекста
    max_results: int = 10  # Максимум результатов
    min_score: float = 0.3  # Минимальный порог совместимости


class EnhancedRecommendation(BaseModel):
    """Рекомендация с оценкой совместимости"""
    recommended_user: Optional[UserResponse] = None
    recommended_team: Optional[TeamListResponse] = None
    compatibility_score: float  # 0.0 - 1.0
    match_reasons: List[str] = []  # Причины рекомендации
    
    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    """Ответ с рекомендациями"""
    recommendations: List[EnhancedRecommendation] = []
    total_found: int = 0
    
    class Config:
        from_attributes = True


class TelegramAuthRequest(BaseModel):
    auth_data: Dict[str, str]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

