# Hackathon Backend API

## Status Report
I have cleaned up the code from the chat history. Here are the key fixes:

1.  **Circular Imports Fixed**: Split `auth.py` into `auth.py` (Telegram logic) and `security.py` (JWT/Token logic) to prevent the recursion error.
2.  **Router Ordering**: In `users.py`, the `/me` endpoint is strictly defined before `/{user_id}` to prevent the "int parsing" error.
3.  **Timezone/Timestamp Validation**: Updated Telegram auth to use `time.time()` (Unix timestamp) consistently to avoid `Authentication data expired` errors due to timezone mismatches.
4.  **New Fields Added**: 
    *   `User`: `avatar_url`, `tg_username`, `hide_tg_username`.
    *   `Achievement`: `icon_url`.
    *   New Model: `HackathonParticipation` (Portfolio).

## Setup

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

2. Install dependencies:
   ```bash
   pip install fastapi uvicorn sqlalchemy pydantic python-jose passlib[bcrypt] python-multipart
   ```

3. Run server:
   ```bash
   uvicorn app.main:app --reload
   ```
