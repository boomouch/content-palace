"""
Backfill Russian metadata for items belonging to RU users.
Fetches description_ru and genres_ru from Kinopoisk (films/shows) or Google Books (books).
Run from the bot/ directory: python backfill_ru_metadata.py
"""
import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from services.metadata import fetch_kp_metadata, _fetch_google_books

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
db = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_ru_users() -> list[int]:
    result = db.table("users").select("telegram_id").eq("lang", "ru").execute()
    return [r["telegram_id"] for r in result.data]


def get_items_to_backfill(telegram_ids: list[int]) -> list[dict]:
    """Get film/show/book items for RU users that are missing EN or RU metadata."""
    result = (
        db.table("items")
        .select("id, title, title_ru, type, description, description_ru, genres, genres_ru, cover_url, telegram_id")
        .in_("telegram_id", telegram_ids)
        .in_("type", ["film", "show", "book"])
        .execute()
    )
    return result.data


async def backfill_film(item: dict) -> dict | None:
    title = item.get("title_ru") or item["title"]
    data = await fetch_kp_metadata(title, item["type"])
    if not data:
        return None
    update = {}
    # English fields (for EN toggle)
    if data.get("description"):
        update["description"] = data["description"]
    if data.get("genres"):
        update["genres"] = data["genres"]
    if data.get("title") and data["title"] != title:
        update["title"] = data["title"]
    if data.get("title_ru"):
        update["title_ru"] = data["title_ru"]
    # Russian fields (for RU mode)
    if data.get("description_ru"):
        update["description_ru"] = data["description_ru"]
    if data.get("genres_ru"):
        update["genres_ru"] = data["genres_ru"]
    if data.get("cover_url"):
        update["cover_url"] = data["cover_url"]
    return update if update else None


async def backfill_book(item: dict) -> dict | None:
    title = item.get("title_ru") or item["title"]
    gb_en, gb_ru = await asyncio.gather(
        _fetch_google_books(title),
        _fetch_google_books(title, lang_restrict="ru"),
    )
    update = {}
    if gb_en.get("description"):
        update["description"] = gb_en["description"]
    if gb_en.get("genres"):
        update["genres"] = gb_en["genres"]
    if gb_en.get("cover_url") and not item.get("cover_url"):
        update["cover_url"] = gb_en["cover_url"]
    if gb_ru.get("description"):
        update["description_ru"] = gb_ru["description"]
    if gb_ru.get("genres"):
        update["genres_ru"] = gb_ru["genres"]
    return update if update else None


async def main():
    print("Fetching RU users...")
    ru_user_ids = get_ru_users()
    print(f"Found {len(ru_user_ids)} RU users: {ru_user_ids}")

    if not ru_user_ids:
        print("No RU users found.")
        return

    items = get_items_to_backfill(ru_user_ids)
    print(f"Found {len(items)} items missing RU metadata\n")

    updated = 0
    skipped = 0

    for item in items:
        itype = item["type"]
        title = item.get("title_ru") or item["title"]
        print(f"  [{itype}] {title} ...", end=" ")

        try:
            if itype in ("film", "show"):
                update = await backfill_film(item)
            else:
                update = await backfill_book(item)

            if update:
                db.table("items").update(update).eq("id", item["id"]).execute()
                keys = ", ".join(update.keys())
                print(f"✓ updated ({keys})")
                updated += 1
            else:
                print("– nothing found")
                skipped += 1
        except Exception as e:
            print(f"✗ error: {e}")
            skipped += 1

        await asyncio.sleep(0.3)  # be polite to APIs

    print(f"\nDone. Updated: {updated}, Skipped/not found: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
