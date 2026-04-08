import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PARSE_PROMPT = """Parse this Telegram message into a media library entry. Return valid JSON only, no extra text.

Message: "{message}"

Return this JSON structure:
{{
  "type": "book" | "film" | "show" | "other" | "unknown",
  "title": "string or null",
  "creator": "string or null",
  "status": "want" | "in_progress" | "done" | "abandoned" | "unknown",
  "feeling": "essential" | "loved" | "good" | "fine" | "not_for_me" | "regret" | null,
  "source_url": "string or null",
  "is_question": true | false,
  "confidence": "high" | "medium" | "low",
  "ambiguity": "string or null"
}}

Rules:
- "want to", "need to", "should watch/read", "on my list" → status: want
- "started", "reading", "watching", "currently", "in the middle of" → status: in_progress
- "finished", "done", "just read/watched", "completed" → status: done
- "gave up", "stopped", "couldn't finish", "abandoned" → status: abandoned
- If message is a question about a book/film/show (e.g. "what did that ending mean?") → is_question: true
- If a URL is present, put it in source_url and infer type from domain
- Map sentiment to feeling: "loved/amazing/incredible/favourite" → loved, "great/really good" → good, "fine/ok/decent/alright" → fine, "didn't like/bad" → not_for_me, "waste of time/hate" → regret, "must read/essential/life-changing" → essential
- If type is ambiguous (e.g. could be book or show), set confidence: low and describe in ambiguity
- If no clear media item is mentioned, set title: null"""

REFLECT_PROMPT = """You are a warm, thoughtful assistant helping someone reflect on what they just finished.

They finished: {title} ({type})
Their message: "{message}"

Ask them ONE follow-up question to help them reflect — something specific to what they said, not generic.
Keep it short (1 sentence). Don't be formal. Sound like a curious friend."""

SUMMARY_PROMPT = """Based on this conversation, write a 2-3 sentence personal summary of what this person thought about "{title}".

Their messages:
{messages}

Write in first person (as if they wrote it). Capture their actual feelings, specific observations, and any memorable details they mentioned.
No fluff. No "The user said..." — just their thoughts, cleanly written."""

SUGGEST_PROMPT = """Based on what this person thought about "{title}" ({type}), suggest ONE related piece of content they might enjoy.

Their thoughts: {summary}
Their feeling: {feeling}
Their vibe tags: {vibe_tags}

Return JSON only:
{{
  "suggested_title": "string",
  "suggested_type": "book" | "film" | "show" | "other",
  "reason": "one sentence explaining why they'd like it based on their specific reaction"
}}

Priority: if they finished a book, consider its film adaptation first. Otherwise suggest something thematically similar.
Only suggest if you're confident it's a genuinely good match. If not sure, return null."""


def _clean_json(text: str) -> str:
    """Strip markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_message(message: str) -> dict:
    """Parse a free-text message into structured data using Claude Haiku."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": PARSE_PROMPT.format(message=message)}]
    )
    try:
        return json.loads(_clean_json(response.content[0].text))
    except json.JSONDecodeError:
        return {"title": None, "confidence": "low", "is_question": False}


def get_reflection_question(title: str, item_type: str, message: str) -> str:
    """Generate a follow-up reflection question after finishing something."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": REFLECT_PROMPT.format(
            title=title, type=item_type, message=message
        )}]
    )
    return response.content[0].text.strip()


def generate_summary(title: str, messages: list[str]) -> str:
    """Generate a clean summary of the user's thoughts from raw messages."""
    messages_text = "\n".join(f"- {m}" for m in messages)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
            title=title, messages=messages_text
        )}]
    )
    return response.content[0].text.strip()


def generate_suggestion(title: str, item_type: str, summary: str, feeling: str, vibe_tags: list) -> dict | None:
    """Generate a content suggestion based on what the user thought."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": SUGGEST_PROMPT.format(
            title=title,
            type=item_type,
            summary=summary,
            feeling=feeling or "unknown",
            vibe_tags=", ".join(vibe_tags or []) or "none yet"
        )}]
    )
    try:
        text = _clean_json(response.content[0].text)
        if text.lower() == "null":
            return None
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError):
        return None


def answer_content_question(question: str, item: dict | None) -> str:
    """Answer a question about a book/film/show."""
    context = ""
    if item:
        context = f"The user is asking about: {item['title']} ({item['type']}, {item.get('year', 'unknown year')})\n"
        if item.get("description"):
            context += f"Description: {item['description']}\n"
        if item.get("summary"):
            context += f"Their thoughts on it: {item['summary']}\n"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": f"{context}\nQuestion: {question}"}]
    )
    return response.content[0].text.strip()
