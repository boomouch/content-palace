"""
One-time backfill: translate existing library items to Russian (or English for Russian users).
Run from the bot/ directory: python backfill_translations.py

What it does:
- Fetches all items missing title_ru (i.e. logged before dual-language was added)
- For films/shows: fetches official Russian title + description from TMDB
- For all types: translates highlights, summary, vibe_tags via Claude Haiku
- Determines translation direction from the user's language preference
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from services import database, metadata
from services.ai_parser import translate_content


async def backfill():
    db = database.get_db()

    # Build user → lang map
    users_result = db.table("users").select("telegram_id, lang").execute()
    user_langs: dict[int, str] = {u["telegram_id"]: u["lang"] for u in (users_result.data or [])}

    # Items missing Russian content (catches all pre-migration items)
    result = db.table("items").select("*").is_("title_ru", "null").execute()
    items = result.data or []
    print(f"Found {len(items)} items to backfill.\n")

    ok = 0
    skipped = 0

    for item in items:
        title = item.get("title") or ""
        item_type = item.get("type") or ""
        telegram_id = item.get("telegram_id")

        source_lang = user_langs.get(telegram_id, "en") if telegram_id else "en"
        target_lang = "ru" if source_lang == "en" else "en"

        updates: dict = {}

        # ── TMDB: official translated title + description ──
        if item_type in ("film", "show"):
            try:
                tmdb_data = await metadata.fetch_metadata(title, item_type)
                if tmdb_data.get("title_ru"):
                    updates["title_ru"] = tmdb_data["title_ru"]
                if tmdb_data.get("description_ru"):
                    updates["description_ru"] = tmdb_data["description_ru"]
            except Exception as e:
                print(f"  TMDB error for '{title}': {e}")

        # ── Claude: translate thoughts, summary, vibe tags ──
        raw_summary = item.get("summary") or ""
        try:
            highlights = json.loads(raw_summary) if raw_summary.startswith("[") else []
        except Exception:
            highlights = []
        plain_summary = raw_summary if raw_summary and not raw_summary.startswith("[") else ""
        vibe_tags = item.get("vibe_tags") or []

        if any([highlights, plain_summary, vibe_tags]):
            try:
                translated = translate_content(
                    highlights=highlights,
                    summary=plain_summary,
                    vibe_tags=vibe_tags,
                    target_lang=target_lang,
                )
                hl_key = "highlights_ru" if target_lang == "ru" else "highlights"
                sm_key = "summary_ru" if target_lang == "ru" else "summary"
                vt_key = "vibe_tags_ru" if target_lang == "ru" else "vibe_tags"

                if translated.get("highlights"):
                    updates[hl_key] = translated["highlights"]
                if translated.get("summary"):
                    updates[sm_key] = translated["summary"]
                if translated.get("vibe_tags"):
                    updates[vt_key] = translated["vibe_tags"]
            except Exception as e:
                print(f"  Translation error for '{title}': {e}")

        if updates:
            database.update_item(item["id"], updates)
            fields = ", ".join(updates.keys())
            print(f"OK {title} ({item_type}) -> {fields}")
            ok += 1
        else:
            print(f"-- {title} ({item_type}): nothing to translate")
            skipped += 1

    print(f"\nDone. Updated: {ok}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(backfill())
