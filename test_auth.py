import requests
import hmac
import hashlib
import time
import json

BASE_URL = "http://localhost:8000"
SECRET_KEY = "your_secret_key_here"  # Из app/utils/auth.py — измени на реальный!

def generate_telegram_auth_data(tg_id="123456789", username="testuser", first_name="Test", last_name="User"):
    """Генерирует валидные данные для Telegram auth с hash"""
    auth_data = {
        "id": tg_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "auth_date": str(int(time.time()))  # Текущее время
    }
    # Сортируем и формируем строку для hash
    sorted_items = sorted([(k, v) for k, v in auth_data.items() if v is not None])
    sorted_data = "\n".join([f"{k}={v}" for k, v in sorted_items])
    # Secret key для HMAC
    secret_key_hash = hashlib.sha256(SECRET_KEY.encode()).digest()
    # Вычисляем hash
    calculated_hash = hmac.new(secret_key_hash, sorted_data.encode(), hashlib.sha256).hexdigest()
    auth_data["hash"] = calculated_hash
    return auth_data

def test_telegram_login():
    print("\n[1] Тестируем Telegram login...")
    auth_data = generate_telegram_auth_data()
    payload = {"auth_data": auth_data}
    
    response = requests.post(f"{BASE_URL}/auth/telegram/login", json=payload)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   OK: Токен получен - {result.get('access_token')[:20]}...")
        return result.get("access_token")
    else:
        print(f"   ERROR: {response.text}")
        return None

def test_protected_endpoint(token):
    print("\n[2] Тестируем защищённый эндпоинт с токеном (/users/me)...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/users/me", headers=headers)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        user = response.json()
        print(f"   OK: Пользователь - {user.get('full_name')}, ID: {user.get('id')}")
    else:
        print(f"   ERROR: {response.text}")

def test_invalid_hash():
    print("\n[3] Тестируем невалидный hash...")
    auth_data = generate_telegram_auth_data()
    auth_data["hash"] = "invalid_hash"  # Ломаем hash
    payload = {"auth_data": auth_data}
    
    response = requests.post(f"{BASE_URL}/auth/telegram/login", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print(f"   OK: Ошибка как ожидалось - {response.text}")
    else:
        print(f"   UNEXPECTED: {response.text}")

def test_expired_data():
    print("\n[4] Тестируем expired auth_date...")
    auth_data = generate_telegram_auth_data()
    # Делаем auth_date старым (>1 час)
    old_time = int(time.time()) - 7200  # 2 часа назад
    auth_data["auth_date"] = str(old_time)
    # Пересчитываем hash с старым временем (чтобы он был валидным, но expired)
    sorted_items = sorted([(k, v) for k, v in auth_data.items() if k != "hash" and v is not None])
    sorted_data = "\n".join([f"{k}={v}" for k, v in sorted_items])
    secret_key_hash = hashlib.sha256(SECRET_KEY.encode()).digest()
    auth_data["hash"] = hmac.new(secret_key_hash, sorted_data.encode(), hashlib.sha256).hexdigest()
    
    payload = {"auth_data": auth_data}
    response = requests.post(f"{BASE_URL}/auth/telegram/login", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print(f"   OK: Ошибка expired как ожидалось - {response.text}")
    else:
        print(f"   UNEXPECTED: {response.text}")

def test_without_token():
    print("\n[5] Тестируем доступ без токена (/users/me)...")
    response = requests.get(f"{BASE_URL}/users/me")
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print(f"   OK: Ошибка unauthorized как ожидалось - {response.text}")
    else:
        print(f"   UNEXPECTED: {response.text}")

if __name__ == "__main__":
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ АУТЕНТИФИКАЦИИ")
    print("=" * 50)
    
    token = test_telegram_login()
    if token:
        test_protected_endpoint(token)
    test_invalid_hash()
    test_expired_data()
    test_without_token()
    
    print("\nТЕСТ ЗАВЕРШЁН")