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
    # Create session if it doesn't exist
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


def get_item(item_id: str) -> dict:
    db = get_db()
    result = db.table("items").select("*").eq("id", item_id).execute()
    return result.data[0] if result.data else None


def find_existing_item(title: str, item_type: str, telegram_id: int) -> dict | None:
    """Fuzzy search for an existing item to avoid duplicates."""
    db = get_db()
    result = db.table("items").select("*") \
        .ilike("title", f"%{title}%") \
        .eq("type", item_type) \
        .eq("telegram_id", telegram_id) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


def append_raw_message(item_id: str, message: str):
    """Append a new message to the item's raw_messages array."""
    db = get_db()
    item = get_item(item_id)
    if item:
        messages = item.get("raw_messages") or []
        messages.append(message)
        update_item(item_id, {"raw_messages": messages})
