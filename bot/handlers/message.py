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

_DELETE_RE = re.compile(r'^(?:delete|remove|удали|удалить)\s+(.+?)(?:\s+entry)?$', re.IGNORECASE)
_RATE_RE   = re.compile(r'^(?:update|rate|change|оцени)\s+(.+?)\s+(?:rating\s+)?(?:to\s+)?(essential|loved|average|not for me|not_for_me|regret|🔥|❤️|😐|🙈|💀|mid|ok)$', re.IGNORECASE)
_NOTE_RE   = re.compile(r'^add(?:\s+note)?\s+to\s+(.+?):\s*(.+)$', re.IGNORECASE | re.DOTALL)


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

    note_match = _NOTE_RE.match(text)
    if note_match:
        await _handle_add_note(update, context, note_match.group(1).strip(), note_match.group(2).strip(), telegram_id)
        return

    # ── State: waiting for feeling rating ──
    if state == "awaiting_feeling":
        await update.message.reply_text("Use the buttons above to rate your feeling ↑")
        return

    # ── State: mid-reflection conversation ──
    if state == "reflecting":
        item_id = session.get("state_item_id")
        if item_id:
            database.append_raw_message(item_id, text)
            item = database.get_item(item_id)
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
    item_type = parsed.get("type", "other")
    status = parsed.get("status", "want")

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
        if status == "in_progress":
            item_data["started_at"] = today
        if status == "done":
            item_data["finished_at"] = today

        item = database.save_item(item_data)
        item_id = item["id"]
        action = "added"

    context.application.create_task(
        _fetch_and_update_metadata(item_id, title, item_type)
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


async def _fetch_and_update_metadata(item_id: str, title: str, item_type: str):
    try:
        data = await metadata.fetch_metadata(title, item_type)
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

Return 3-4 vibe tags as a JSON array. Examples: ["slow burn", "dark", "atmospheric", "thought-provoking", "funny", "emotional", "page-turner", "light", "rewatchable", "demanding"]
JSON only, no other text."""}]
    )
    try:
        tags = _json.loads(response.content[0].text.strip())
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
