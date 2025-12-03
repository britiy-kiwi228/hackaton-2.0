"""
Тестирование улучшенной рекомендательной системы
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Данные для создания пользователей с разными навыками и ролями
users_data = [
    {
        "tg_id": 1001,
        "username": "backend_dev",
        "main_role": "backend",
        "ready_to_work": True,
        "skills": ["Python", "FastAPI", "SQL"]
    },
    {
        "tg_id": 1002,
        "username": "frontend_dev",
        "main_role": "frontend",
        "ready_to_work": True,
        "skills": ["React", "TypeScript", "CSS"]
    },
    {
        "tg_id": 1003,
        "username": "designer",
        "main_role": "design",
        "ready_to_work": True,
        "skills": ["Figma", "UI/UX", "Adobe"]
    },
    {
        "tg_id": 1004,
        "username": "fullstack",
        "main_role": "backend",
        "ready_to_work": True,
        "skills": ["Python", "React", "SQL", "Docker"]
    },
    {
        "tg_id": 1005,
        "username": "pm",
        "main_role": "pm",
        "ready_to_work": True,
        "skills": ["Management", "Communication", "Planning"]
    }
]

def create_user(user_data):
    """Создать пользователя с навыками"""
    response = requests.post(
        f"{BASE_URL}/users/auth/telegram",
        json={"tg_id": user_data["tg_id"], "username": user_data["username"], "full_name": user_data["username"]}
    )
    result = response.json()
    user_id = result.get("id")
    if not user_id:
        print(f"   ❌ Ошибка при создании пользователя: {result}")
        return None
    
    # Обновить профиль с навыками и ролью
    update_data = {
        "main_role": user_data["main_role"],
        "ready_to_work": user_data["ready_to_work"],
        "skills": user_data["skills"]
    }
    response = requests.patch(
        f"{BASE_URL}/users/me",
        json=update_data,
        params={"user_id": user_id}
    )
    
    if response.status_code != 200:
        print(f"   ❌ Ошибка при обновлении профиля: {response.text}")
    
    return user_id

def create_hackathon():
    """Создать хакатон"""
    now = datetime.utcnow()
    start = now + timedelta(days=1)
    end = start + timedelta(days=2)
    registration_deadline = now + timedelta(hours=12)
    
    response = requests.post(
        f"{BASE_URL}/hackathons",
        json={
            "title": "Test Hackathon",
            "description": "Test hackathon for recommendations",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "registration_deadline": registration_deadline.isoformat(),
            "location": "Online",
            "is_active": True
        }
    )
    result = response.json()
    return result.get("id")

def create_team(captain_id, hackathon_id, name):
    """Создать команду"""
    response = requests.post(
        f"{BASE_URL}/teams",
        json={
            "name": name,
            "description": f"Team {name}",
            "hackathon_id": hackathon_id
        },
        params={"user_id": captain_id}
    )
    result = response.json()
    return result.get("id")

def test_recommendations():
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ УЛУЧШЕННОЙ РЕКОМЕНДАТЕЛЬНОЙ СИСТЕМЫ")
    print("=" * 80)
    
    # 1. Создаем пользователей
    print("\n[1] Creating users...")
    user_ids = {}
    for user_data in users_data:
        user_id = create_user(user_data)
        user_ids[user_data["username"]] = user_id
        print(f"   OK: Created user '{user_data['username']}' (ID: {user_id})")
    
    # 2. Создаем хакатон
    print("\n[2] Creating hackathon...")
    hackathon_id = create_hackathon()
    print(f"   OK: Created hackathon (ID: {hackathon_id})")
    
    # 3. Создаем команду с капитаном backend_dev
    print("\n[3] Creating team...")
    team_id = create_team(
        user_ids["backend_dev"],
        hackathon_id,
        "Backend Team"
    )
    print(f"   OK: Created team 'Backend Team' (ID: {team_id})")
    print(f"      Captain: backend_dev (ID: {user_ids['backend_dev']})")
    
    # 4. Тестируем рекомендации команд для пользователя (for_what="team")
    print("\n[4] Getting TEAM recommendations for user frontend_dev...")
    response = requests.post(
        f"{BASE_URL}/recommendations",
        json={
            "for_what": "team",
            "hackathon_id": hackathon_id,
            "max_results": 10,
            "min_score": 0.3
        },
        params={"user_id": user_ids["frontend_dev"]}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   OK: Got {result['total_found']} recommendations")
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"\n   Recommendation #{i}")
            print(f"      Team: {rec['recommended_team']['name']}")
            print(f"      Score: {rec['compatibility_score']:.2f}")
            print(f"      Reasons:")
            for reason in rec['match_reasons']:
                print(f"        - {reason}")
    else:
        print(f"   ERROR: {response.status_code}")
        print(f"      {response.text}")
    
    # 5. Тестируем рекомендации пользователей для команды (for_what="user")
    print("\n[5] Getting USER recommendations for team Backend Team...")
    response = requests.post(
        f"{BASE_URL}/recommendations",
        json={
            "for_what": "user",
            "hackathon_id": hackathon_id,
            "preferred_roles": ["frontend", "design"],
            "preferred_skills": ["React", "TypeScript"],
            "max_results": 10,
            "min_score": 0.2
        },
        params={"user_id": user_ids["backend_dev"]}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   OK: Got {result['total_found']} recommendations")
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"\n   User #{i}")
            print(f"      Username: {rec['recommended_user']['username']}")
            print(f"      Role: {rec['recommended_user']['main_role']}")
            print(f"      Score: {rec['compatibility_score']:.2f}")
            print(f"      Reasons:")
            for reason in rec['match_reasons']:
                print(f"        - {reason}")
    else:
        print(f"   ERROR: {response.status_code}")
        print(f"      {response.text}")
    
    # 6. Тестируем /teams/{team_id} endpoint
    print("\n[6] Getting recommendations for team via /teams/{team_id}...")
    response = requests.post(
        f"{BASE_URL}/recommendations/teams/{team_id}",
        json={
            "for_what": "user",
            "hackathon_id": hackathon_id,
            "max_results": 5,
            "min_score": 0.3
        },
        params={"user_id": user_ids["backend_dev"]}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"   OK: Got {result['total_found']} recommendations")
        for i, rec in enumerate(result['recommendations'], 1):
            print(f"\n   User #{i}")
            print(f"      Username: {rec['recommended_user']['username']}")
            print(f"      Score: {rec['compatibility_score']:.2f}")
    else:
        print(f"   ERROR: {response.status_code}")
        print(f"      {response.text}")
    
    # 7. Тестируем /stats endpoint
    print("\n[7] Getting recommendation statistics (/stats)...")
    response = requests.get(
        f"{BASE_URL}/recommendations/stats",
        params={"user_id": user_ids["backend_dev"]}
    )
    
    if response.status_code == 200:
        stats = response.json()
        print(f"   OK: Statistics retrieved")
        print(f"      Total users: {stats['total_users']}")
        print(f"      Total teams: {stats['total_teams']}")
        print(f"      Active users: {stats['active_users']}")
        if stats['user_team']:
            print(f"      User team: {stats['user_team']['name']} ({stats['user_team']['member_count']} members)")
    else:
        print(f"   ERROR: {response.status_code}")
        print(f"      {response.text}")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    test_recommendations()
