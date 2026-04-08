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
  "feeling": "essential" | "loved" | "average" | "not_for_me" | "regret" | null,
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
- If message is a question about a book/film/show → is_question: true
- If a URL is present, put it in source_url and infer type from domain
- YouTube channels, podcasts, newsletters, articles, blogs → type: other (NOT show)
- Map sentiment to feeling:
  - "must/essential/life-changing/changed me" → essential
  - "loved/amazing/incredible/favourite/brilliant/masterpiece" → loved
  - "good/great/liked/enjoyed/decent/fine/ok/alright/not bad" → average
  - "didn't like/bad/boring/disappointing/not for me/not my thing" → not_for_me
  - "waste of time/hate/terrible/awful/worst/regret watching" → regret
- If type is ambiguous, set confidence: low and explain in ambiguity field
- If no clear media item is mentioned, set title: null"""

REFLECT_PROMPT_Q1 = """Someone just finished "{title}" ({type}) and said: "{message}"

Ask them ONE question about what specifically worked or didn't — the story, characters, ideas, pacing, or tone. Force them to be specific, not vague.

Rules:
- Must be impossible to answer in 1-2 words — they need a full sentence at minimum
- If they seem negative or mixed: ask what specifically went wrong or disappointed them
- If they seem positive: ask what made it different or better than similar things they've seen/read
- If neutral: ask what they'll actually remember about it
- Don't ask "what did you think?" or "did you enjoy it?" — too generic
- 1 sentence, casual and direct, no bullet points
- Reply in: {lang}"""

REFLECT_PROMPT_Q2 = """Someone just finished "{title}" ({type}).

Their thoughts so far:
{messages}

Ask them ONE question about meaning or perspective — push them to reflect beyond just describing what happened.

Good angles: what it changed or confirmed about something they believed, what it says about the kind of person who loves this, whether it made them uncomfortable and why, what they'd tell someone who said it's overrated (or overhated).

Rules:
- Must be impossible to answer in 1-2 words
- Don't repeat anything already covered in their messages above
- Push for genuine reflection, not more description
- 1 sentence, casual and direct
- Reply in: {lang}"""

SUMMARY_PROMPT = """Distill what this person said about "{title}" into sharp, memorable observations.

Their messages:
{messages}

Return a JSON array of 3-5 bullet strings. Rules:
- Rework their words — don't just quote or paraphrase them
- Each bullet should be a crisp insight or strong opinion, not a description
- Strip filler — cut "I think", "it was", "really", "kind of"
- If they said something vague, make it specific and concrete
- If they contradicted themselves, pick the stronger opinion
- Punchy, direct, opinionated — like a good review pulled apart into its best lines
- Max 10 words each, no bullet symbols, no numbering

Bad: "I thought the characters were quite interesting and well developed"
Good: "Characters feel like real people, not plot devices"

Bad: "The ending was surprising and I didn't expect it"
Good: "Ending reframes everything — didn't see it coming"

JSON array only, no other text."""

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
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_message(message: str) -> dict:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": PARSE_PROMPT.format(message=message)}]
    )
    try:
        return json.loads(_clean_json(response.content[0].text))
    except json.JSONDecodeError:
        return {"title": None, "confidence": "low", "is_question": False}


def get_reflection_question(title: str, item_type: str, messages: list[str], question_number: int = 1, lang: str = "en") -> str:
    """Generate a reflection question. question_number is 1 or 2."""
    if question_number == 1:
        prompt = REFLECT_PROMPT_Q1.format(
            title=title,
            type=item_type,
            message=messages[0] if messages else "",
            lang=lang
        )
    else:
        messages_text = "\n".join(f"- {m}" for m in messages)
        prompt = REFLECT_PROMPT_Q2.format(
            title=title,
            type=item_type,
            messages=messages_text,
            lang=lang
        )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def quick_reply(key: str, lang: str = "en") -> str:
    messages = {
        "not_understood": {
            "en": "Hmm, I'm not sure what to log. Could you be more specific?",
            "ru": "Хм, не совсем понял что добавить. Можешь уточнить?",
        }
    }
    msg = messages.get(key, {})
    return msg.get(lang) or msg.get(lang[:2]) or msg.get("en", "")


def generate_summary(title: str, messages: list[str]) -> tuple[list[str], str]:
    messages_text = "\n".join(f"- {m}" for m in messages)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
            title=title, messages=messages_text
        )}]
    )
    try:
        highlights = json.loads(_clean_json(response.content[0].text))
        plain = " · ".join(highlights)
        return highlights, plain
    except (json.JSONDecodeError, TypeError):
        plain = response.content[0].text.strip()
        return [], plain


def generate_suggestion(title: str, item_type: str, summary: str, feeling: str, vibe_tags: list) -> dict | None:
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


def answer_content_question(question: str, item: dict | None, lang: str = "en") -> str:
    context = f"Reply in this language: {lang}\n\n"
    if item:
        context += f"The user is asking about: {item['title']} ({item['type']}, {item.get('year', 'unknown year')})\n"
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
