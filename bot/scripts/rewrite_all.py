"""One-time script to regenerate summaries for all items using the updated prompt."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from services import database, ai_parser

def rewrite_all():
    db = database.get_db()
    result = db.table("items").select("id, title, type, raw_messages, summary").execute()
    items = result.data or []

    skipped = 0
    updated = 0

    for item in items:
        raw = item.get("raw_messages") or []
        if not raw:
            print(f"  SKIP (no messages): {item['title']}")
            skipped += 1
            continue

        try:
            highlights, plain = ai_parser.generate_summary(item["title"], raw)
            summary = json.dumps(highlights) if highlights else plain
            database.update_item(item["id"], {"summary": summary})
            print(f"  OK: {item['title']}")
            updated += 1
        except Exception as e:
            print(f"  ERROR: {item['title']} — {e}")

    print(f"\nDone. {updated} updated, {skipped} skipped.")

if __name__ == "__main__":
    rewrite_all()
