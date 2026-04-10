import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client = None

def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SECRET_KEY")
        )
    return _client


def get_session(telegram_id: int, telegram_handle: str = None) -> dict:
    db = get_db()
    result = db.table("telegram_sessions").select("*").eq("telegram_id", telegram_id).execute()
    if result.data:
        return result.data[0]
    new_session = {"telegram_id": telegram_id, "state": "idle", "telegram_handle": telegram_handle}
    db.table("telegram_sessions").insert(new_session).execute()
    return new_session


def set_session_state(telegram_id: int, state: str, item_id: str = None, payload: dict = None):
    db = get_db()
    update = {"state": state, "state_item_id": item_id, "state_payload": payload or {}}
    db.table("telegram_sessions").upsert({"telegram_id": telegram_id, **update}).execute()


def save_item(data: dict) -> dict:
    db = get_db()
    result = db.table("items").insert(data).execute()
    return result.data[0] if result.data else None


def update_item(item_id: str, data: dict) -> dict:
    db = get_db()
    result = db.table("items").update(data).eq("id", item_id).execute()
    return result.data[0] if result.data else None


def delete_item(item_id: str):
    db = get_db()
    db.table("items").delete().eq("id", item_id).execute()


def get_item(item_id: str) -> dict:
    db = get_db()
    result = db.table("items").select("*").eq("id", item_id).execute()
    return result.data[0] if result.data else None


def find_existing_item(title: str, item_type: str, telegram_id: int) -> dict | None:
    """Fuzzy search for a single existing item. Searches both title and title_ru."""
    db = get_db()
    fil = f"title.ilike.%{title}%,title_ru.ilike.%{title}%"
    # Try exact type match first
    result = db.table("items").select("*") \
        .or_(fil) \
        .eq("type", item_type) \
        .eq("telegram_id", telegram_id) \
        .limit(1) \
        .execute()
    if result.data:
        return result.data[0]
    # Fall back to any type — catches film/show misclassifications
    result = db.table("items").select("*") \
        .or_(fil) \
        .eq("telegram_id", telegram_id) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


def find_items_fuzzy(title: str, telegram_id: int, limit: int = 5) -> list[dict]:
    """Fuzzy search across all types. Searches both title and title_ru columns."""
    db = get_db()
    fil = f"title.ilike.%{title}%,title_ru.ilike.%{title}%"
    result = db.table("items").select("*") \
        .or_(fil) \
        .eq("telegram_id", telegram_id) \
        .limit(limit) \
        .execute()
    return result.data or []


def append_raw_message(item_id: str, message: str):
    db = get_db()
    item = get_item(item_id)
    if item:
        messages = item.get("raw_messages") or []
        messages.append(message)
        update_item(item_id, {"raw_messages": messages})


def get_or_create_user(telegram_id: int, name: str, lang: str = 'en') -> dict:
    db = get_db()
    result = db.table("users").select("*").eq("telegram_id", telegram_id).execute()
    if result.data:
        return result.data[0]
    new_user = {"telegram_id": telegram_id, "name": name, "lang": lang, "avatar_emoji": "🎬", "color": "#6366f1"}
    result = db.table("users").insert(new_user).execute()
    return result.data[0] if result.data else new_user


def get_user(telegram_id: int) -> dict | None:
    db = get_db()
    result = db.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return result.data[0] if result.data else None


def update_user(telegram_id: int, data: dict) -> dict:
    db = get_db()
    result = db.table("users").update(data).eq("telegram_id", telegram_id).execute()
    return result.data[0] if result.data else None


def get_all_users() -> list[dict]:
    db = get_db()
    result = db.table("users").select("id, name, telegram_id, lang, avatar_emoji, color").order("created_at").execute()
    return result.data or []
