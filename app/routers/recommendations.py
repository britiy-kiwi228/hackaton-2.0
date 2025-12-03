"""
Улучшенная рекомендательная система на основе навыков, ролей и метрик совместимости
"""
from typing import List, Set, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.models import User, Team, Skill, Request as RequestModel, RequestStatus, RequestType
from app.schemas import (
    RecommendationRequest, 
    RecommendationResponse, 
    UserResponse, 
    TeamListResponse,
    EnhancedRecommendation
)
from app.utils.security import get_current_user  # Импортируем новую зависимость

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)


def get_user_skills(user: User) -> Set[str]:
    """Получить набор навыков пользователя"""
    try:
        skills = user.skills or []
        return {skill.name.lower() for skill in skills if skill and skill.name}
    except Exception:
        return set()


def get_user_roles_in_team(team: Team) -> Set[str]:
    """Получить набор ролей в команде"""
    roles = set()
    try:
        members = team.members or []
        for member in members:
            try:
                if member.main_role:
                    role_value = member.main_role.value if hasattr(member.main_role, 'value') else str(member.main_role)
                    roles.add(role_value.lower())
            except Exception:
                continue
    except Exception:
        pass
    return roles


def get_team_skills(team: Team) -> Set[str]:
    """Получить набор всех навыков в команде"""
    skills = set()
    try:
        members = team.members or []
        for member in members:
            try:
                member_skills = member.skills or []
                for skill in member_skills:
                    if skill and skill.name:
                        skills.add(skill.name.lower())
            except Exception:
                continue
    except Exception:
        pass
    return skills


def calculate_skill_coverage(user_skills: Set[str], needed_skills: Set[str]) -> float:
    """
    Рассчитать, какой процент нужных навыков покрывает пользователь
    
    Args:
        user_skills: набор навыков пользователя
        needed_skills: набор нужных навыков
    
    Returns:
        float: Процент покрытия (0.0 - 1.0)
    """
    if not needed_skills:
        return 0.0
    covered = len(user_skills.intersection(needed_skills))
    return covered / len(needed_skills)


def calculate_role_need(team_roles: Set[str], preferred_roles: List[str]) -> Tuple[float, List[str]]:
    """
    Рассчитать необходимость роли
    
    Args:
        team_roles: текущие роли в команде
        preferred_roles: предпочитаемые роли
    
    Returns:
        Tuple[float, List[str]]: (score, reasons)
    """
    if not preferred_roles:
        return 0.0, []
    
    preferred_set = {r.lower() for r in preferred_roles}
    missing_roles = preferred_set - team_roles
    if not missing_roles:
        return 0.0, []
    
    coverage = len(missing_roles) / len(preferred_set)
    reasons = [f"Нужна роль: {role}" for role in missing_roles]
    return coverage * 0.4, reasons  # Вес роли - 40%


def calculate_skill_need(team_skills: Set[str], preferred_skills: List[str]) -> Tuple[float, List[str]]:
    """
    Рассчитать необходимость навыков
    
    Args:
        team_skills: текущие навыки команды
        preferred_skills: предпочитаемые навыки
    
    Returns:
        Tuple[float, List[str]]: (score, reasons)
    """
    if not preferred_skills:
        return 0.0, []
    
    preferred_set = {s.lower() for s in preferred_skills}
    missing_skills = preferred_set - team_skills
    if not missing_skills:
        return 0.0, []
    
    coverage = len(missing_skills) / len(preferred_set)
    reasons = [f"Нужен навык: {skill}" for skill in missing_skills]
    return coverage * 0.3, reasons  # Вес навыков - 30%


def calculate_collaboration_potential(user: User, team: Team, db: Session) -> Tuple[float, List[str]]:
    """
    Рассчитать потенциал сотрудничества на основе предыдущих взаимодействий
    
    Args:
        user: кандидат
        team: команда
        db: сессия БД
    
    Returns:
        Tuple[float, List[str]]: (score, reasons)
    """
    score = 0.0
    reasons = []
    
    # Проверяем предыдущие запросы
    previous_requests = db.query(RequestModel).filter(
        and_(
            RequestModel.hackathon_id == team.hackathon_id,
            or_(
                and_(
                    RequestModel.sender_id == user.id,
                    RequestModel.team_id == team.id
                ),
                and_(
                    RequestModel.receiver_id == user.id,
                    RequestModel.team_id == team.id
                )
            )
        )
    ).all()
    
    if previous_requests:
        accepted = sum(1 for r in previous_requests if r.status == RequestStatus.accepted)
        if accepted > 0:
            score += 0.2
            reasons.append(f"Уже сотрудничали ранее ({accepted} раз)")
    
    # Общие навыки с командой
    user_skills = get_user_skills(user)
    team_skills = get_team_skills(team)
    common_skills = user_skills.intersection(team_skills)
    if common_skills:
        score += min(len(common_skills) * 0.05, 0.2)
        reasons.append(f"Общие навыки: {', '.join(list(common_skills)[:3])}")
    
    return min(score, 0.3), reasons  # Макс вес - 30%


def calculate_team_compatibility(
    team: Team, 
    preferred_roles: List[str] = None,
    preferred_skills: List[str] = None
) -> Tuple[float, List[str]]:
    """
    Рассчитать совместимость команды с предпочтениями
    
    Args:
        team: Команда-кандидат
        preferred_roles: Предпочитаемые роли
        preferred_skills: Предпочитаемые навыки
    
    Returns:
        Tuple[float, List[str]]: (score, reasons)
    """
    reasons = []
    score = 0.0
    
    # Текущие роли и навыки команды
    team_roles = get_user_roles_in_team(team)
    team_skills = get_team_skills(team)
    
    # Необходимость ролей
    role_score, role_reasons = calculate_role_need(team_roles, preferred_roles or [])
    score += role_score
    reasons.extend(role_reasons)
    
    # Необходимость навыков
    skill_score, skill_reasons = calculate_skill_need(team_skills, preferred_skills or [])
    score += skill_score
    reasons.extend(skill_reasons)
    
    # Размер команды (оптимально 3-5 человек)
    member_count = len(team.members)
    if 3 <= member_count <= 5:
        score += 0.1
        reasons.append(f"Оптимальный размер команды: {member_count} участников")
    elif member_count < 3:
        score += 0.05
        reasons.append(f"Маленькая команда: {member_count} участников (нуждается в людях)")
    
    # Активность капитана
    if team.captain.ready_to_work:
        score += 0.1
        reasons.append("Капитан готов к работе")
    
    return min(score, 1.0), reasons


def calculate_user_compatibility(
    candidate: User,
    preferred_roles: List[str] = None,
    preferred_skills: List[str] = None
) -> Tuple[float, List[str]]:
    """
    Рассчитать совместимость пользователя с предпочтениями
    
    Args:
        candidate: Кандидат
        preferred_roles: Предпочитаемые роли
        preferred_skills: Предпочитаемые навыки
    
    Returns:
        Tuple[float, List[str]]: (score, reasons)
    """
    reasons = []
    score = 0.0
    
    # Проверка роли
    if preferred_roles and candidate.main_role:
        candidate_role = candidate.main_role.value.lower() if hasattr(candidate.main_role, 'value') else str(candidate.main_role).lower()
        if candidate_role in {r.lower() for r in preferred_roles}:
            score += 0.4
            reasons.append(f"Подходит роль: {candidate_role}")
    
    # Проверка навыков
    candidate_skills = get_user_skills(candidate)
    if preferred_skills:
        coverage = calculate_skill_coverage(candidate_skills, {s.lower() for s in preferred_skills})
        score += coverage * 0.3
        matched_skills = candidate_skills.intersection({s.lower() for s in preferred_skills})
        if matched_skills:
            reasons.append(f"Навыки: {', '.join(list(matched_skills)[:3])}")
    
    # Дополнительные факторы
    if candidate.ready_to_work:
        score += 0.1
        reasons.append("Готов к работе")
    
    if candidate.achievements:
        score += min(len(candidate.achievements) * 0.05, 0.2)
        reasons.append(f"Имеет достижения: {len(candidate.achievements)}")
    
    return min(score, 1.0), reasons


@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(
    rec_request: RecommendationRequest,
    current_user: User = Depends(get_current_user),  # Заменяем http_request
    db: Session = Depends(get_db)
):
    """
    POST /recommendations/
    Получить рекомендации команд/пользователей.
    
    Тело запроса: RecommendationRequest
    """
    recommendations_list = []
    
    if rec_request.for_what == "team":
        # Рекомендации команд для пользователя
        exclude_team_ids = rec_request.exclude_team_ids or []
        
        teams_query = db.query(Team).filter(
            and_(
                Team.hackathon_id == rec_request.hackathon_id,
                Team.id.notin_(exclude_team_ids),
                Team.captain_id != current_user.id
            )
        )
        
        teams = teams_query.all()
        
        for team in teams:
            score, reasons = calculate_team_compatibility(
                team=team,
                preferred_roles=rec_request.preferred_roles,
                preferred_skills=rec_request.preferred_skills
            )
            
            # Добавить потенциал сотрудничества
            collab_score, collab_reasons = calculate_collaboration_potential(current_user, team, db)
            score += collab_score
            reasons.extend(collab_reasons)
            
            if score >= rec_request.min_score:
                recommendations_list.append(EnhancedRecommendation(
                    recommended_user=None,
                    recommended_team=TeamListResponse.from_orm(team),
                    compatibility_score=min(score, 1.0),
                    match_reasons=reasons
                ))
    
    elif rec_request.for_what == "user":
        # Рекомендации пользователей для команды
        # Находим команду пользователя
        user_team = db.query(Team).filter(
            and_(
                Team.captain_id == current_user.id,
                Team.hackathon_id == rec_request.hackathon_id
            )
        ).first()
        
        if not user_team:
            raise HTTPException(
                status_code=400,
                detail="You must be a team captain to request user recommendations"
            )
        
        # Собрать членов команды для исключения
        team_member_ids = {member.id for member in user_team.members}
        
        exclude_user_ids = list(team_member_ids)
        if rec_request.exclude_user_ids:
            exclude_user_ids.extend(rec_request.exclude_user_ids)
        
        users_query = db.query(User).filter(
            and_(
                User.id.notin_(exclude_user_ids),
                User.ready_to_work == True,
                User.id != current_user.id
            )
        )
        
        users = users_query.all()
        
        for user in users:
            score, reasons = calculate_user_compatibility(
                candidate=user,
                preferred_roles=rec_request.preferred_roles,
                preferred_skills=rec_request.preferred_skills
            )
            
            # Добавить потенциал сотрудничества
            collab_score, collab_reasons = calculate_collaboration_potential(user, user_team, db)
            score += collab_score
            reasons.extend(collab_reasons)
            
            if score >= rec_request.min_score:
                recommendations_list.append(EnhancedRecommendation(
                    recommended_user=UserResponse.from_orm(user),
                    recommended_team=None,
                    compatibility_score=min(score, 1.0),
                    match_reasons=reasons
                ))
    
    else:
        raise HTTPException(
            status_code=400,
            detail='for_what must be "team" or "user"'
        )
    
    # Сортировать и ограничить результаты
    recommendations_list.sort(key=lambda x: x.compatibility_score, reverse=True)
    recommendations_list = recommendations_list[:rec_request.max_results]
    
    return RecommendationResponse(
        recommendations=recommendations_list,
        total_found=len(recommendations_list)
    )


@router.post("/teams/{team_id}", response_model=RecommendationResponse)
async def get_recommendations_for_team(
    team_id: int,
    rec_request: RecommendationRequest,
    current_user: User = Depends(get_current_user),  # Заменяем http_request
    db: Session = Depends(get_db)
):
    """
    POST /recommendations/teams/{team_id}
    Получить рекомендации пользователей для конкретной команды.
    Только капитан может.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )
    
    if team.captain_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only team captain can request recommendations for this team"
        )
    
    # Собрать членов команды для исключения
    team_member_ids = {member.id for member in team.members}
    
    exclude_user_ids = list(team_member_ids)
    if rec_request.exclude_user_ids:
        exclude_user_ids.extend(rec_request.exclude_user_ids)
    
    # Получить пользователей для рекомендации
    users_query = db.query(User).filter(
        and_(
            User.id.notin_(exclude_user_ids),
            User.ready_to_work == True,
            User.id != current_user.id
        )
    )
    
    users = users_query.all()
    recommendations_list = []
    
    for user in users:
        score, reasons = calculate_user_compatibility(
            candidate=user,
            preferred_roles=rec_request.preferred_roles,
            preferred_skills=rec_request.preferred_skills
        )
        
        # Добавить если оценка выше минимума
        if score >= rec_request.min_score:
            recommendations_list.append(EnhancedRecommendation(
                recommended_user=UserResponse.from_orm(user),
                recommended_team=None,
                compatibility_score=score,
                match_reasons=reasons
            ))
    
    # Сортировать и ограничить результаты
    recommendations_list.sort(key=lambda x: x.compatibility_score, reverse=True)
    recommendations_list = recommendations_list[:rec_request.max_results]
    
    return RecommendationResponse(
        recommendations=recommendations_list,
        total_found=len(recommendations_list)
    )


@router.get("/stats", response_model=dict)
async def get_recommendation_stats(
    current_user: User = Depends(get_current_user),  # Заменяем http_request
    db: Session = Depends(get_db)
):
    """
    Получить статистику по рекомендациям
    """
    
    # Получить команду пользователя (если он капитан)
    user_team = db.query(Team).filter(Team.captain_id == current_user.id).first()
    
    total_users = db.query(func.count(User.id)).scalar()
    total_teams = db.query(func.count(Team.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.ready_to_work == True).scalar()
    
    stats = {
        "total_users": total_users,
        "total_teams": total_teams,
        "active_users": active_users,
        "user_team": {
            "id": user_team.id,
            "name": user_team.name,
            "member_count": len(user_team.members)
        } if user_team else None
    }
    
    return stats