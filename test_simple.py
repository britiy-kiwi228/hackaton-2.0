"""
Простой тест для проверки рекомендательной системы
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("ПРОСТОЙ ТЕСТ РЕКОМЕНДАЦИЙ")
print("=" * 70)

# Проверка что сервер работает
print("\n[1] Проверка сервера...")
try:
    response = requests.get(f"{BASE_URL}/")
    if response.status_code == 200:
        print(f"   OK: Сервер работает - {response.json()}")
    else:
        print(f"   ERROR: Статус {response.status_code}")
        exit(1)
except Exception as e:
    print(f"   ERROR: Не удалось подключиться - {e}")
    print(f"   Убедитесь что сервер запущен на {BASE_URL}")
    exit(1)

# Тест рекомендаций команд
print("\n[2] Тест: Получить рекомендации команд для пользователя...")
try:
    rec_request = {
        "for_what": "team",
        "hackathon_id": 1
    }
    
    response = requests.post(
        f"{BASE_URL}/recommendations/?user_id=1",
        json=rec_request
    )
    
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        teams_count = len(result.get("recommendations", []))
        print(f"   OK: Найдено {teams_count} рекомендаций")
        
        for i, rec in enumerate(result.get("recommendations", [])[:3], 1):
            score = rec.get("compatibility_score", 0)
            team = rec.get("recommended_team", {})
            print(f"   {i}. Команда '{team.get('name', 'N/A')}' - совместимость: {score:.2f}")
    else:
        print(f"   ERROR: Статус {response.status_code}")
        print(f"   Текст ответа: {response.text[:500]}")
        try:
            print(f"   JSON: {response.json()}")
        except:
            pass
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

# Тест рекомендаций пользователей
print("\n[3] Тест: Получить рекомендации пользователей для команды...")
try:
    rec_request = {
        "for_what": "user",
        "hackathon_id": 1,
        "preferred_roles": ["backend", "frontend"]
    }
    
    response = requests.post(
        f"{BASE_URL}/recommendations/?user_id=1",
        json=rec_request
    )
    
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        users_count = len(result.get("recommendations", []))
        print(f"   OK: Найдено {users_count} рекомендаций")
        
        for i, rec in enumerate(result.get("recommendations", [])[:3], 1):
            score = rec.get("compatibility_score", 0)
            user = rec.get("recommended_user", {})
            print(f"   {i}. Пользователь '{user.get('full_name', 'N/A')}' - совместимость: {score:.2f}")
    elif response.status_code == 400:
        print(f"   INFO: {response.json()['detail']} (нужно быть капитаном команды)")
    else:
        print(f"   ERROR: Статус {response.status_code}")
        print(f"   Текст ответа: {response.text[:500]}")
        try:
            print(f"   JSON: {response.json()}")
        except:
            pass
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 70)

