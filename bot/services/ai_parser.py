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
  "subtype": "youtube" | "podcast" | "newsletter" | "article" | "blog" | "documentary" | "course" | null,
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
- type: film by default for "watched X" unless explicitly called "show", "series", "TV show", "season", "episode", or it's clearly a well-known TV series
- type: show only when user says "show", "series", "TV", "season", "episode", or it's unambiguously a TV series
- type: book only when explicitly reading
- YouTube channels/shows, podcasts, newsletters, articles, blogs → type: other (NOT show)
- For type: other, always set subtype: youtube | podcast | newsletter | article | blog | documentary | course
- Infer subtype from context: "youtube", "channel", "episode" → youtube; "podcast", "episode" → podcast; "newsletter", "substack" → newsletter; "course", "udemy", "masterclass" → course
- Map sentiment to feeling:
  - "must/essential/life-changing/changed me" → essential
  - "loved/amazing/incredible/favourite/brilliant/masterpiece" → loved
  - "good/great/liked/enjoyed/decent/fine/ok/alright/not bad" → average
  - "didn't like/bad/boring/disappointing/not for me/not my thing" → not_for_me
  - "waste of time/hate/terrible/awful/worst/regret watching" → regret
- If type is ambiguous, set confidence: low and explain in ambiguity field
- If no clear media item is mentioned, set title: null
- title: keep the title exactly as the user wrote it. Do NOT translate. If they wrote "парень из пузыря" keep it as "парень из пузыря". If they wrote "Dune" keep it as "Dune"."""

REFLECT_PROMPT_Q1 = """You are asking a friend one question after they logged something they finished.

Their message: "{message}"

Look only at the words in their message. Ignore what you know about the title.

Does their message contain an opinion word — something like: loved, hated, boring, amazing, terrible, disappointing, incredible, not for me, couldn't stop, mind-blowing, depressing, beautiful, awful, etc.?

If YES: ask one question that drills into that specific word/feeling.
If NO: ask simply "how did you find it?" or "what did you think?" — nothing more specific.

Examples:
"read Misery" → "how did you find it?"
"watched Dune" → "what did you think?"
"watched Midsommar - hated it" → "what put you off?"
"read Sapiens - mind blowing" → "what changed your thinking?"
"finished Joker - so disappointing" → "what fell flat?"

Output only the question. No explanation. One sentence.
Language: {lang}"""

REFLECT_PROMPT_Q2 = """Someone just finished "{title}" ({type}).

Their thoughts so far:
{messages}

Ask them ONE question that helps capture the overall experience — the kind of answer that would become a vibe tag or a bullet point in a short personal review.

Good angles (pick the most relevant given what they said):
- Would they recommend it, and to who specifically?
- What kind of mood or feeling did it leave them with?
- Was it what they expected, or did it surprise them?
- How does it compare to similar things they've seen/read?
- What would they warn someone about before watching/reading it?
- Is it worth the time investment?

Rules:
- Don't ask about specific scenes, characters, or plot details — those don't help with summary or vibes
- The answer should produce something like "slow burn but worth it", "not for everyone", "better than expected", "leaves you unsettled" — that kind of thing
- Directly follow up on the tone of what they said
- 1 sentence, casual and direct
- Reply in: {lang}"""

SUMMARY_PROMPT = """Clean up what this person said about "{title}" into 3-5 bullet points.

Their messages:
{messages}

Reply language: {lang_name}

Return a JSON array of bullet strings. Rules:
- The first message is often just the logging trigger (e.g. "watched X", "finished X", "read X") — skip it if it contains no actual opinion or thought
- Keep their words and phrasing as close as possible — this should sound like them, not like a review
- Only fix spelling, grammar, and awkward phrasing — don't rephrase ideas or add new ones
- Keep slang, casual tone, humour, "lol", strong opinions exactly as they are
- Split long run-on thoughts into separate bullets where it makes sense
- Remove filler like "I think", "it was like", "kind of", "you know"
- No bullet symbols, no numbering
- Each bullet max 15 words

Bad: "Doesn't hurt that the main character is easy on the eyes"
Good: "The main character is genuinely very hot"

Bad: "The narrative tension is maintained despite implausible plot developments"
Good: "Don't think too hard or it falls apart, but it'll keep you hooked"

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


TRANSLATE_PROMPT = """Translate these personal media notes to {target_lang}.

highlights (short bullet strings): {highlights}
summary (plain text): {summary}
vibe_tags (short tag strings): {vibe_tags}

Rules:
- Keep the same casual tone and voice — these are personal opinions
- highlights: each bullet max 15 words, preserve slang and strong opinions
- vibe_tags: short lowercase tags (e.g. "slow burn" → "медленное нарастание", "mind-blowing" → "срывает крышу")
- summary: match the original tone exactly
- Return JSON only, no other text:
{{"highlights": [...], "summary": "...", "vibe_tags": [...]}}"""


def translate_content(highlights: list, summary: str, vibe_tags: list, target_lang: str) -> dict:
    """Translate highlights, summary, vibe_tags to target language. Returns dict with translated values."""
    if not any([highlights, summary, vibe_tags]):
        return {}
    lang_name = "Russian" if target_lang == "ru" else "English"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": TRANSLATE_PROMPT.format(
            target_lang=lang_name,
            highlights=json.dumps(highlights or [], ensure_ascii=False),
            summary=summary or "",
            vibe_tags=json.dumps(vibe_tags or [], ensure_ascii=False),
        )}]
    )
    try:
        return json.loads(_clean_json(response.content[0].text))
    except (json.JSONDecodeError, AttributeError):
        return {}


def get_english_title(title_ru: str, author_ru: str | None = None) -> str | None:
    """Ask Claude Haiku for the English original title of a Russian book.
    Returns None if the book is originally Russian or the title is unknown."""
    prompt = f'What is the original English title of the book "{title_ru}"'
    if author_ru:
        prompt += f' by "{author_ru}"'
    prompt += '? Reply with ONLY the English title, nothing else. If the book was originally written in Russian (not translated from another language), or if you are not certain, reply exactly: UNKNOWN'
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text.strip().strip('"').strip("'")
        return None if result.upper() == "UNKNOWN" or not result else result
    except Exception:
        return None


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


def generate_summary(title: str, messages: list[str], lang: str = "en") -> tuple[list[str], str]:
    messages_text = "\n".join(f"- {m}" for m in messages)
    lang_name = "Russian" if lang == "ru" else "English"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(
            title=title, messages=messages_text, lang_name=lang_name
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
