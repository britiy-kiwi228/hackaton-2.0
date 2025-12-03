"""
Отладочный тест для рекомендаций
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 70)
print("ОТЛАДОЧНЫЙ ТЕСТ")
print("=" * 70)

# Проверка пользователя
print("\n[1] Проверка пользователя с ID 1...")
try:
    response = requests.get(f"{BASE_URL}/users/1")
    if response.status_code == 200:
        user = response.json()
        print(f"   OK: Пользователь найден - {user.get('full_name', 'N/A')}")
        print(f"   Team ID: {user.get('team_id')}")
        print(f"   Role: {user.get('main_role')}")
    else:
        print(f"   ERROR: Пользователь не найден - {response.status_code}")
        print(f"   Текст: {response.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

# Проверка хакатонов
print("\n[2] Проверка хакатонов...")
try:
    response = requests.get(f"{BASE_URL}/hackathons/")
    if response.status_code == 200:
        hackathons = response.json()
        print(f"   OK: Найдено {len(hackathons)} хакатонов")
        if hackathons:
            print(f"   Первый хакатон: ID={hackathons[0].get('id')}, Title={hackathons[0].get('title', 'N/A')}")
    else:
        print(f"   ERROR: {response.status_code}")
        print(f"   Текст: {response.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

# Простой тест рекомендаций
print("\n[3] Тест рекомендаций с минимальными данными...")
try:
    rec_request = {
        "for_what": "team",
        "hackathon_id": 1
    }
    
    response = requests.post(
        f"{BASE_URL}/recommendations/?user_id=1",
        json=rec_request,
        timeout=5
    )
    
    print(f"   Статус: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    print(f"   Текст ответа (первые 1000 символов):")
    print(f"   {response.text[:1000]}")
    
    if response.status_code == 200:
        try:
            result = response.json()
            print(f"   JSON успешно распарсен!")
            print(f"   Рекомендаций: {result.get('total_found', 0)}")
        except:
            print(f"   Не удалось распарсить JSON")
    else:
        try:
            error_json = response.json()
            print(f"   JSON ошибки: {json.dumps(error_json, indent=2, ensure_ascii=False)}")
        except:
            print(f"   Не удалось распарсить JSON ошибки")
            
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("ОТЛАДКА ЗАВЕРШЕНА")
print("=" * 70)


