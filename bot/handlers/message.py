import re
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import ai_parser, database, metadata


FEELING_LABELS = {
    "essential": "🔥 Essential",
    "loved":     "❤️ Loved it",
    "average":   "😐 Average",
    "not_for_me":"🙈 Not for me",
    "regret":    "💀 Regret it",
}

FEELING_TEXT_MAP = {
    "essential": "essential", "🔥": "essential",
    "loved": "loved", "love": "loved", "❤️": "loved",
    "average": "average", "mid": "average", "ok": "average", "okay": "average", "😐": "average",
    "not for me": "not_for_me", "not_for_me": "not_for_me", "🙈": "not_for_me",
    "regret": "regret", "💀": "regret",
}

REVISIT_LABELS = {
    "yes":   "✓ Definitely",
    "maybe": "Maybe",
    "no":    "Nope",
}

_DELETE_RE    = re.compile(r'^(?:delete|remove|удали|удалить)\s+(.+?)(?:\s+entry)?$', re.IGNORECASE)
_RATE_RE      = re.compile(r'^(?:update|rate|change|оцени)\s+(.+?)\s+(?:rating\s+)?(?:to\s+)?(essential|loved|average|not for me|not_for_me|regret|🔥|❤️|😐|🙈|💀|mid|ok)$', re.IGNORECASE)
_RATE_BARE_RE = re.compile(r'^(?:update|rate|change|оцени)\s+(.+?)\s+rating\s*$', re.IGNORECASE)
_NOTE_RE      = re.compile(
    r'^(?:'
    r'add(?:\s+(?:note|to))?\s+to\s+(.+?)(?::|(?:\s+that|\s+saying|\s+-))\s*(.+)'  # "add to X: Y" / "add to X that Y"
    r'|to\s+(.+?),?\s+add(?:\s+(?:note|that|saying))?\s+(.+)'                       # "to X, add that Y" / "to X add Y"
    r')$',
    re.IGNORECASE | re.DOTALL
)
_UPDATE_NOTE_RE = re.compile(r'^(?:update|change)\s+(.+?)\s*[-–]\s*(.{10,})$', re.IGNORECASE | re.DOTALL)
_REWRITE_RE     = re.compile(r'^(?:rewrite|regenerate|recap)\s+(.+)$', re.IGNORECASE)

_STATUS_RE    = re.compile(
    r'^(?:change|update|mark|set|поменяй|отметь)\s+(.+?)\s+(?:status\s+)?(?:to\s+|as\s+)?(watching|reading|in progress|current|done|finished|completed|watched|read|abandoned|dropped|want|want to watch|want to read)$',
    re.IGNORECASE
)

_STATUS_MAP = {
    "watching": "in_progress", "reading": "in_progress", "in progress": "in_progress", "current": "in_progress",
    "done": "done", "finished": "done", "completed": "done", "watched": "done", "read": "done",
    "abandoned": "abandoned", "dropped": "abandoned",
    "want": "want", "want to watch": "want", "want to read": "want",
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    telegram_handle = update.effective_user.username
    lang = update.effective_user.language_code or "en"
    text = update.message.text.strip()

    session = database.get_session(telegram_id, telegram_handle)
    state = session.get("state", "idle")

    # ── Commands always take priority over session state ──
    delete_match = _DELETE_RE.match(text)
    if delete_match:
        await _handle_delete(update, delete_match.group(1).strip(), telegram_id)
        return

    rate_match = _RATE_RE.match(text)
    if rate_match:
        await _handle_rate(update, rate_match.group(1).strip(), rate_match.group(2).strip(), telegram_id)
        return

    rate_bare_match = _RATE_BARE_RE.match(text)
    if rate_bare_match:
        await _handle_rate_pick(update, rate_bare_match.group(1).strip(), telegram_id)
        return

    note_match = _NOTE_RE.match(text)
    if note_match:
        # Groups 1,2 = "add to X: Y" pattern; groups 3,4 = "to X, add Y" pattern
        title_q = (note_match.group(1) or note_match.group(3) or "").strip()
        note_text = (note_match.group(2) or note_match.group(4) or "").strip()
        if title_q and note_text:
            await _handle_add_note(update, context, title_q, note_text, telegram_id)
            return

    status_match = _STATUS_RE.match(text)
    if status_match:
        await _handle_status_update(update, status_match.group(1).strip(), status_match.group(2).strip(), telegram_id)
        return

    update_note_match = _UPDATE_NOTE_RE.match(text)
    if update_note_match and not _RATE_RE.match(text):
        await _handle_add_note(update, context, update_note_match.group(1).strip(), update_note_match.group(2).strip(), telegram_id)
        return

    rewrite_match = _REWRITE_RE.match(text)
    if rewrite_match:
        await _handle_rewrite(update, context, rewrite_match.group(1).strip(), telegram_id)
        return

    # ── State: waiting for feeling rating ──
    if state == "awaiting_feeling":
        await update.message.reply_text("Use the buttons above to rate your feeling ↑")
        return

    # ── State: mid-reflection conversation ──
    if state == "reflecting":
        item_id = session.get("state_item_id")
        if item_id:
            item = database.get_item(item_id)
            if not item:
                # Item was deleted — reset and fall through to normal parsing below
                database.set_session_state(telegram_id, "idle")
                state = "idle"
            else:
                database.append_raw_message(item_id, text)
                payload = session.get("state_payload") or {}
                reflection_count = payload.get("reflection_count", 0)
                reflection_messages = payload.get("reflection_messages", [])
                reflection_messages.append(text)

                if reflection_count < 1:
                    question = ai_parser.get_reflection_question(
                        item["title"], item["type"], reflection_messages,
                        question_number=2, lang=lang
                    )
                    payload["reflection_count"] = reflection_count + 1
                    payload["reflection_messages"] = reflection_messages
                    database.set_session_state(telegram_id, "reflecting", item_id, payload)
                    await update.message.reply_text(question)
                else:
                    context.application.create_task(
                        _generate_summary_and_tags(item_id, item["title"], reflection_messages)
                    )
                    await _ask_feeling(update, telegram_id, item_id)
                return

    # ── State: waiting for quote (optional) ──
    if state == "awaiting_quote":
        item_id = session.get("state_item_id")
        if text.lower() not in ("skip", ".", "-", "no", "нет", "пропустить"):
            database.update_item(item_id, {"highlight_quote": text})
        await _finish_entry(update, context, telegram_id, item_id)
        return

    # ── Default: idle — parse new message ──
    parsed = ai_parser.parse_message(text)

    # Handle questions about content
    if parsed.get("is_question"):
        item = None
        if parsed.get("title"):
            item = database.find_existing_item(parsed["title"], parsed.get("type", "book"), telegram_id)
        answer = ai_parser.answer_content_question(text, item, lang)
        await update.message.reply_text(answer)
        return

    # No media item detected
    if not parsed.get("title"):
        await update.message.reply_text(ai_parser.quick_reply("not_understood", lang))
        return

    # Low confidence — ask for clarification
    if parsed.get("confidence") == "low":
        clarification = parsed.get("ambiguity") or ai_parser.quick_reply("not_understood", lang)
        await update.message.reply_text(clarification)
        return

    title = parsed["title"]
    raw_type = parsed.get("type", "other")
    item_type = raw_type if raw_type in ("book", "film", "show", "other") else "other"
    raw_status = parsed.get("status", "want")
    status = raw_status if raw_status in ("want", "in_progress", "done", "abandoned") else "want"
    subtype = parsed.get("subtype") if item_type == "other" else None

    # Check for duplicate
    existing = database.find_existing_item(title, item_type, telegram_id)

    if existing:
        update_data = {"status": status, "raw_messages": (existing.get("raw_messages") or []) + [text]}
        if status == "in_progress" and not existing.get("started_at"):
            from datetime import date
            update_data["started_at"] = date.today().isoformat()
        if status == "done" and not existing.get("finished_at"):
            from datetime import date
            update_data["finished_at"] = date.today().isoformat()
        if subtype and not existing.get("subtype"):
            update_data["subtype"] = subtype

        item = database.update_item(existing["id"], update_data)
        item_id = existing["id"]
        action = "updated"
    else:
        from datetime import date
        today = date.today().isoformat()
        item_data = {
            "type": item_type,
            "title": title,
            "creator": parsed.get("creator"),
            "status": status,
            "raw_messages": [text],
            "source_url": parsed.get("source_url"),
            "telegram_id": telegram_id,
        }
        if subtype:
            item_data["subtype"] = subtype
        if status == "in_progress":
            item_data["started_at"] = today
        if status == "done":
            item_data["finished_at"] = today

        item = database.save_item(item_data)
        item_id = item["id"]
        action = "added"

    context.application.create_task(
        _fetch_and_update_metadata(item_id, title, item_type, parsed.get("source_url"))
    )

    await _send_confirmation(update, item, action, status)

    already_reflected = existing and existing.get("feeling")
    if status in ("done", "abandoned") and not already_reflected:
        initial_messages = [text]
        database.set_session_state(telegram_id, "reflecting", item_id, {
            "reflection_count": 0,
            "reflection_messages": initial_messages,
        })
        context.application.create_task(
            _send_reflection_question(update, telegram_id, item_id, title, item_type, initial_messages, lang)
        )


async def _handle_delete(update: Update, title_query: str, telegram_id: int):
    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return

    if len(matches) == 1:
        item = matches[0]
        keyboard = [[
            InlineKeyboardButton("Yes, delete", callback_data=f"confirm_delete:{item['id']}"),
            InlineKeyboardButton("Cancel", callback_data="cancel_delete"),
        ]]
        await update.message.reply_text(
            f"Delete *{item['title']}* ({item['type']}, {item.get('year', 'unknown year')})?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        keyboard = [
            [InlineKeyboardButton(
                f"{item['title']} ({item['type']}{', ' + str(item['year']) if item.get('year') else ''})",
                callback_data=f"confirm_delete:{item['id']}"
            )]
            for item in matches
        ]
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_delete")])
        await update.message.reply_text(
            f"Found {len(matches)} matches. Which one to delete?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def _handle_rate_pick(update: Update, title_query: str, telegram_id: int):
    """Show rating buttons when no rating value was given."""
    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return

    item = matches[0] if len(matches) == 1 else None
    if len(matches) > 1:
        # Let user pick item first, then we'd need another step — for now just use closest match
        item = matches[0]

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"rate_item:{item['id']}:{key}")]
        for key, label in FEELING_LABELS.items()
    ]
    await update.message.reply_text(
        f"Rate *{item['title']}*:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def _handle_rate(update: Update, title_query: str, feeling_text: str, telegram_id: int):
    feeling = FEELING_TEXT_MAP.get(feeling_text.lower())
    if not feeling:
        await update.message.reply_text(f"Unknown rating \"{feeling_text}\". Use: essential, loved, average, not for me, regret.")
        return

    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return

    if len(matches) == 1:
        item = matches[0]
        database.update_item(item["id"], {"feeling": feeling})
        await update.message.reply_text(
            f"{FEELING_LABELS[feeling]} — updated for *{item['title']}*.",
            parse_mode="Markdown"
        )
    else:
        keyboard = [
            [InlineKeyboardButton(
                f"{item['title']} ({item['type']})",
                callback_data=f"rate_item:{item['id']}:{feeling}"
            )]
            for item in matches
        ]
        await update.message.reply_text(
            "Found multiple matches. Which one?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def _handle_status_update(update: Update, title_query: str, status_text: str, telegram_id: int):
    status = _STATUS_MAP.get(status_text.lower())
    if not status:
        await update.message.reply_text(f"Unknown status \"{status_text}\".")
        return

    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return

    item = matches[0]
    update_data: dict = {"status": status}
    from datetime import date
    today = date.today().isoformat()
    if status == "in_progress" and not item.get("started_at"):
        update_data["started_at"] = today
    if status == "done" and not item.get("finished_at"):
        update_data["finished_at"] = today

    database.update_item(item["id"], update_data)

    status_labels = {"want": "Want list", "in_progress": "Currently watching/reading", "done": "Finished", "abandoned": "Abandoned"}
    await update.message.reply_text(
        f"✓ *{item['title']}* → {status_labels[status]}",
        parse_mode="Markdown"
    )


async def _handle_add_note(update: Update, context: ContextTypes.DEFAULT_TYPE, title_query: str, note: str, telegram_id: int):
    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return

    if len(matches) == 1:
        item = matches[0]
        database.append_raw_message(item["id"], note)
        await update.message.reply_text(f"Note added to *{item['title']}*. Updating summary...", parse_mode="Markdown")
        context.application.create_task(_regenerate_summary(update, item["id"]))
    else:
        keyboard = [
            [InlineKeyboardButton(
                f"{item['title']} ({item['type']})",
                callback_data=f"add_note:{item['id']}:{note[:50]}"
            )]
            for item in matches
        ]
        await update.message.reply_text(
            "Found multiple matches. Which one?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def _generate_summary_and_tags(item_id: str, title: str, messages: list[str]):
    """Generate summary + vibe tags from reflection messages. Called after Q2 is answered."""
    try:
        item = database.get_item(item_id)
        if not item:
            return
        all_messages = list(item.get("raw_messages") or [])
        highlights, plain = ai_parser.generate_summary(title, all_messages)
        summary = json.dumps(highlights) if highlights else plain
        database.update_item(item_id, {"summary": summary})
        item["summary"] = summary

        # Generate vibe tags
        import anthropic as anth, os as _os
        _client = anth.Anthropic(api_key=_os.getenv("ANTHROPIC_API_KEY"))
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": f"""Based on this reflection about "{title}": {summary}

Generate 2-4 vibe tags as a JSON array.

Mix two types:
1. Tone/feel of the content (e.g. dark, funny, slow burn, intense, cozy, disturbing) — infer from what you know about it if not mentioned
2. Emotional experience from their words (e.g. "first seasons only", "consistently good", "lost the plot", "couldn't stop", "left me cold", "mind-blowing") — only from what they actually said

Rules:
- 2-4 tags total, no overlap or repetition between them
- Each tag should say something different
- Short, lowercase, no quotes inside
- If experience and tone would overlap, drop the redundant one

JSON only, no markdown fences."""}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        tags = json.loads(raw)
        database.update_item(item_id, {"vibe_tags": tags})
    except Exception:
        pass


async def _handle_rewrite(update: Update, context: ContextTypes.DEFAULT_TYPE, title_query: str, telegram_id: int):
    matches = database.find_items_fuzzy(title_query, telegram_id)
    if not matches:
        await update.message.reply_text(f"Couldn't find anything matching \"{title_query}\".")
        return
    item = matches[0]
    if not item.get("raw_messages"):
        await update.message.reply_text(f"No messages saved for *{item['title']}* to rewrite from.", parse_mode="Markdown")
        return
    await update.message.reply_text(f"Rewriting thoughts for *{item['title']}*...", parse_mode="Markdown")
    context.application.create_task(_regenerate_summary(update, item["id"]))


async def _regenerate_summary(update: Update, item_id: str):
    """Regenerate summary + vibe tags from all raw messages."""
    try:
        item = database.get_item(item_id)
        if not item:
            return
        raw = item.get("raw_messages") or []
        if not raw:
            return
        highlights, plain = ai_parser.generate_summary(item["title"], raw)
        database.update_item(item_id, {"summary": json.dumps(highlights) if highlights else plain})
        await update.message.reply_text(
            f"✓ Summary updated for *{item['title']}*.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def _send_reflection_question(update: Update, telegram_id: int, item_id: str, title: str, item_type: str, messages: list[str], lang: str = "en"):
    try:
        question = ai_parser.get_reflection_question(title, item_type, messages, question_number=1, lang=lang)
        await update.message.reply_text(question)
    except Exception:
        pass


async def _fetch_and_update_metadata(item_id: str, title: str, item_type: str, source_url: str | None = None):
    try:
        data = await metadata.fetch_metadata(title, item_type, source_url)
        if data:
            data.pop("title", None)
            database.update_item(item_id, data)
    except Exception:
        pass


async def _send_confirmation(update: Update, item: dict, action: str, status: str):
    status_labels = {
        "want": "Added to Want List",
        "in_progress": "Currently reading/watching",
        "done": "Marked as done",
        "abandoned": "Marked as abandoned",
    }
    type_emoji = {"book": "📚", "film": "🎬", "show": "📺", "other": "✦"}

    emoji = type_emoji.get(item.get("type"), "✦")
    label = status_labels.get(status, "Saved")

    msg = f"{emoji} *{item['title']}*"
    if item.get("creator"):
        msg += f" — {item['creator']}"
    if item.get("year"):
        msg += f" ({item['year']})"
    msg += f"\n_{label}_"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def _ask_feeling(update: Update, telegram_id: int, item_id: str):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"feeling:{item_id}:{key}")]
        for key, label in FEELING_LABELS.items()
    ]
    database.set_session_state(telegram_id, "awaiting_feeling", item_id)
    await update.message.reply_text(
        "Last step — how would you sum it up?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    data = query.data

    # ── Feeling rating ──
    if data.startswith("feeling:"):
        _, item_id, feeling = data.split(":")
        # Map legacy values from old cached Telegram buttons
        feeling = {"good": "average", "fine": "average"}.get(feeling, feeling)
        database.update_item(item_id, {"feeling": feeling})
        keyboard = [[
            InlineKeyboardButton(label, callback_data=f"revisit:{item_id}:{key}")
            for key, label in REVISIT_LABELS.items()
        ]]
        database.set_session_state(telegram_id, "awaiting_feeling", item_id)
        await query.edit_message_text(
            f"{FEELING_LABELS[feeling]} — noted!\n\nWould you revisit it?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ── Would revisit ──
    elif data.startswith("revisit:"):
        _, item_id, revisit = data.split(":")
        database.update_item(item_id, {"would_revisit": revisit})
        database.set_session_state(telegram_id, "awaiting_quote", item_id)
        await query.edit_message_text(
            f"{REVISIT_LABELS[revisit]}!\n\nAny quote or line that stuck with you? (or send . to skip)"
        )

    # ── Confirm delete ──
    elif data.startswith("confirm_delete:"):
        _, item_id = data.split(":", 1)
        item = database.get_item(item_id)
        if item:
            database.delete_item(item_id)
            # Reset session if it was pointing at this item
            session = database.get_session(telegram_id)
            if session.get("state_item_id") == item_id:
                database.set_session_state(telegram_id, "idle")
            await query.edit_message_text(f"✓ Deleted *{item['title']}*.", parse_mode="Markdown")
        else:
            await query.edit_message_text("Item not found.")

    elif data == "cancel_delete":
        await query.edit_message_text("Cancelled.")

    # ── Rate item (from multiple match selection) ──
    elif data.startswith("rate_item:"):
        _, item_id, feeling = data.split(":", 2)
        item = database.get_item(item_id)
        if item:
            database.update_item(item_id, {"feeling": feeling})
            await query.edit_message_text(
                f"{FEELING_LABELS[feeling]} — updated for *{item['title']}*.",
                parse_mode="Markdown"
            )

    # ── AI suggestion response ──
    elif data.startswith("suggest_add:"):
        _, item_id, suggested_title, suggested_type = data.split(":", 3)
        from datetime import date
        database.save_item({
            "type": suggested_type,
            "title": suggested_title,
            "status": "want",
            "added_at": date.today().isoformat(),
        })
        await query.edit_message_text(f"✓ Added *{suggested_title}* to your Want List!", parse_mode="Markdown")

    elif data.startswith("suggest_dismiss:"):
        await query.edit_message_text("Got it, skipped.")


async def _finish_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int, item_id: str):
    database.set_session_state(telegram_id, "idle")
    item = database.get_item(item_id)
    if not item:
        return

    raw = item.get("raw_messages") or []
    if raw:
        highlights, plain = ai_parser.generate_summary(item["title"], raw)
        summary_to_save = json.dumps(highlights) if highlights else plain
        database.update_item(item_id, {"summary": summary_to_save})
        item["summary"] = summary_to_save
        item["highlights"] = highlights
    else:
        highlights = []

    type_emoji = {"book": "📚", "film": "🎬", "show": "📺", "other": "✦"}
    emoji = type_emoji.get(item.get("type"), "✦")

    revisit_labels = {"yes": "Would revisit ✓", "maybe": "Maybe revisit", "no": "Wouldn't revisit"}

    title_line = f"{emoji} *{item['title']}*"
    if item.get("creator"):
        title_line += f" — {item['creator']}"
    if item.get("year"):
        title_line += f" · {item['year']}"

    meta_parts = []
    if item.get("feeling"):
        meta_parts.append(FEELING_LABELS.get(item["feeling"], ""))
    if item.get("would_revisit"):
        meta_parts.append(revisit_labels.get(item["would_revisit"], ""))
    meta_line = " · ".join(p for p in meta_parts if p)

    if highlights:
        bullets = "\n".join(f"• {h}" for h in highlights)
        msg = f"{title_line}\n{meta_line}\n\n{bullets}"
    elif item.get("summary"):
        msg = f"{title_line}\n{meta_line}\n\n_{item['summary']}_"
    else:
        msg = f"{title_line}\n{meta_line}\n\n_Saved to your library._"

    await update.message.reply_text(msg, parse_mode="Markdown")

    if item.get("summary"):
        context.application.create_task(_generate_and_save_tags(item_id, item))


async def _generate_and_save_tags(item_id: str, item: dict):
    import anthropic as anth
    import json as _json
    import os

    _client = anth.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": f"""Based on this reflection about "{item['title']}": {item['summary']}

Generate 2-4 vibe tags as a JSON array.

Mix two types:
1. Tone/feel of the content (e.g. dark, funny, slow burn, intense, cozy, disturbing) — infer from what you know about it if not mentioned
2. Emotional experience from their words (e.g. "first seasons only", "consistently good", "lost the plot", "couldn't stop", "left me cold", "mind-blowing") — only from what they actually said

Rules:
- 2-4 tags total, no overlap or repetition between them
- Each tag should say something different
- Short, lowercase, no quotes inside
- If experience and tone would overlap, drop the redundant one

JSON only, no other text."""}]
    )
    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        tags = _json.loads(raw)
        database.update_item(item_id, {"vibe_tags": tags})
        item["vibe_tags"] = tags
    except Exception:
        pass

    suggestion = ai_parser.generate_suggestion(
        item["title"],
        item["type"],
        item.get("summary", ""),
        item.get("feeling"),
        item.get("vibe_tags", [])
    )

    if suggestion:
        from services.database import get_db
        db = get_db()
        item_full = database.get_item(item_id)
        db.table("suggestions").insert({
            "source_item_id": item_id,
            "telegram_id": item_full.get("telegram_id") if item_full else None,
            "suggested_title": suggestion["suggested_title"],
            "suggested_type": suggestion["suggested_type"],
            "reason": suggestion["reason"],
        }).execute()
