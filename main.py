from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Начинаем инициализацию приложения...")

try:
    from app.database import engine, Base
    logger.info("✓ Database импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта database: {e}", exc_info=True)
    raise

try:
    from app.routers import hackathons
    logger.info("✓ Routers импортированы")
except Exception as e:
    logger.error(f"✗ Ошибка импорта routers: {e}", exc_info=True)
    raise

try:
    from app.routers import users
    logger.info("✓ Users router импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта users router: {e}", exc_info=True)
    raise

try:
    from app.routers import teams
    logger.info("✓ Teams router импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта teams router: {e}", exc_info=True)
    raise

try:
    from app.routers import requests as requests_router
    logger.info("✓ Requests router импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта requests router: {e}", exc_info=True)
    raise

try:
    from app.routers import recommendations as recommendations_router
    logger.info("✓ Recommendations router импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта recommendations router: {e}", exc_info=True)
    raise

try:
    from app.routers import auth as auth_router
    logger.info("✓ Auth router импортирован")
except Exception as e:
    logger.error(f"✗ Ошибка импорта auth router: {e}", exc_info=True)
    raise

# Импортируем модели для админ-панели
from app.models import User, Hackathon, Team, Skill, Achievement

# Создаем таблицы БД
try:
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Таблицы БД созданы")
except Exception as e:
    logger.error(f"✗ Ошибка создания таблиц: {e}", exc_info=True)

# Создаем приложение
app = FastAPI(title="Hackathon API")
logger.info("✓ FastAPI приложение создано")

# ==================== MIDDLEWARE ====================

class AddUserToRequestMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления текущего пользователя в request.state"""
    
    async def dispatch(self, request: Request, call_next):
        # Получаем user_id из query параметров (для тестирования)
        # В реальности это будет из JWT токена
        user_id = request.query_params.get("user_id")
        
        if user_id:
            try:
                user_id = int(user_id)
                # Получаем пользователя из БД
                from app.database import SessionLocal
                db = SessionLocal()
                user = db.query(User).filter(User.id == user_id).first()
                db.close()
                
                if user:
                    request.state.user = user
                    logger.debug(f"✓ Пользователь {user.full_name} добавлен в request.state")
            except Exception as e:
                logger.warning(f"⚠️  Ошибка при получении пользователя: {e}")
        
        response = await call_next(request)
        return response


# Добавляем middleware
app.add_middleware(AddUserToRequestMiddleware)
logger.info("✓ Middleware добавлен")

# НАСТРОЙКА CORS (ОЧЕНЬ ВАЖНО!)
# Это разрешает фронтенду стучаться к тебе
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем всем (для хакатона ок)
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем любые методы (GET, POST и т.д.)
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(hackathons.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(requests_router.router)
app.include_router(recommendations_router.router)
app.include_router(auth_router.router)
logger.info("✓ Роутеры подключены")


# ==================== АДМИН-ПАНЕЛЬ ====================

try:
    from sqladmin import Admin, ModelView  # type: ignore
    
    # Классы представления для админ-панели
    class UserAdmin(ModelView, model=User):
        """Админ-панель для пользователей"""
        name = "User"
        name_plural = "Users"
        icon = "fa-solid fa-user"
        column_list = [User.id, User.tg_id, User.username, User.full_name, User.created_at]
        column_searchable_list = [User.full_name, User.username]
        column_sortable_list = [User.created_at, User.full_name]
        column_details_exclude_list = [User.skills, User.team, User.requests_sent, User.teams_led, User.achievements]
        page_size = 20


    class HackathonAdmin(ModelView, model=Hackathon):
        """Админ-панель для хакатонов"""
        name = "Hackathon"
        name_plural = "Hackathons"
        icon = "fa-solid fa-calendar"
        column_list = [Hackathon.id, Hackathon.title, Hackathon.location, Hackathon.start_date, Hackathon.is_active]
        column_searchable_list = [Hackathon.title, Hackathon.location]
        column_sortable_list = [Hackathon.start_date, Hackathon.title]
        column_details_exclude_list = [Hackathon.teams]
        page_size = 20


    class TeamAdmin(ModelView, model=Team):
        """Админ-панель для команд"""
        name = "Team"
        name_plural = "Teams"
        icon = "fa-solid fa-people-group"
        column_list = [Team.id, Team.name, Team.is_looking, Team.created_at]
        column_searchable_list = [Team.name, Team.chat_link]
        column_sortable_list = [Team.created_at, Team.name]
        column_details_exclude_list = [Team.members, Team.requests, Team.hackathon, Team.captain]
        page_size = 20


    class SkillAdmin(ModelView, model=Skill):
        """Админ-панель для навыков"""
        name = "Skill"
        name_plural = "Skills"
        icon = "fa-solid fa-star"
        column_list = [Skill.id, Skill.name]
        column_searchable_list = [Skill.name]
        column_details_exclude_list = [Skill.users]
        page_size = 50


    class AchievementAdmin(ModelView, model=Achievement):
        """Админ-панель для достижений"""
        name = "Achievement"
        name_plural = "Achievements"
        icon = "fa-solid fa-trophy"
        column_list = [Achievement.id, Achievement.hackathon_name, Achievement.place, Achievement.year, Achievement.created_at]
        column_searchable_list = [Achievement.hackathon_name, Achievement.team_name]
        column_sortable_list = [Achievement.year, Achievement.place, Achievement.created_at]
        column_details_exclude_list = [Achievement.user]
        page_size = 20


    # Регистрируем админ-панель
    admin = Admin(app=app, engine=engine, title="Hackathon Admin Panel", base_url="/admin")
    
    # Добавляем модели в админ-панель
    admin.add_model_view(UserAdmin)
    admin.add_model_view(HackathonAdmin)
    admin.add_model_view(TeamAdmin)
    admin.add_model_view(SkillAdmin)
    admin.add_model_view(AchievementAdmin)
    
    logger.info("✓ Админ-панель настроена")
    admin_enabled = True

except ImportError as e:
    logger.warning(f"⚠️  Админ-панель недоступна: {e}")
    admin_enabled = False
except Exception as e:
    logger.error(f"✗ Ошибка при настройке админ-панели: {e}", exc_info=True)
    admin_enabled = False


@app.get("/")
def read_root():
    return {"status": "ok", "message": "Бэкенд работает! Поехали!"}

@app.get("/admin-status")
def admin_status():
    return {"admin_enabled": admin_enabled, "admin_url": "http://localhost:8000/admin" if admin_enabled else "Админ-панель не установлена"}

# Запуск сервера, если файл запущен напрямую
if __name__ == "__main__":
    logger.info("🚀 Запуск сервера на http://0.0.0.0:8000")
    if admin_enabled:
        logger.info("📊 Админ-панель доступна на http://0.0.0.0:8000/admin")
    else:
        logger.warning("⚠️  Админ-панель отключена (не установлена sqladmin)")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)