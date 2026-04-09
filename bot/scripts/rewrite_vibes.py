"""One-time script to regenerate vibe tags for all items using the updated prompt."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

from services import database

VIBE_PROMPT = """Generate 2-4 vibe tags as a JSON array.

Mix two types:
1. Tone/feel of the content (e.g. dark, funny, slow burn, intense, cozy, disturbing) — infer from what you know about it if not mentioned
2. Emotional experience from their words (e.g. "first seasons only", "consistently good", "lost the plot", "couldn't stop", "left me cold", "mind-blowing") — only from what they actually said

Rules:
- 2-4 tags total, no overlap or repetition between them
- Each tag should say something different
- Short, lowercase, no quotes inside
- If experience and tone would overlap, drop the redundant one

JSON only, no other text."""

def rewrite_vibes():
    db = database.get_db()
    result = db.table("items").select("id, title, type, summary, raw_messages").execute()
    items = result.data or []

    updated = 0
    skipped = 0

    for item in items:
        summary = item.get("summary") or ""
        raw = item.get("raw_messages") or []
        if not summary and not raw:
            print(f"  SKIP (no data): {item['title']}")
            skipped += 1
            continue

        context = f'Title: {item["title"]} ({item["type"]})\n'
        if summary:
            context += f"Their thoughts: {summary}\n"
        if raw:
            context += f"Their messages: {chr(10).join(raw[:5])}\n"

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": f"{context}\n{VIBE_PROMPT}"}]
            )
            raw_text = response.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            tags = json.loads(raw_text)
            database.update_item(item["id"], {"vibe_tags": tags})
            print(f"  OK: {item['title']} -> {tags}")
            updated += 1
        except Exception as e:
            print(f"  ERROR: {item['title']} — {e}")

    print(f"\nDone. {updated} updated, {skipped} skipped.")

if __name__ == "__main__":
    rewrite_vibes()
