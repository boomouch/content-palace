from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import ai_parser, database, metadata


FEELING_LABELS = {
    "essential": "🔥 Essential",
    "loved":     "❤️ Loved it",
    "good":      "👍 Good",
    "fine":      "😐 Fine",
    "not_for_me":"👎 Not for me",
    "regret":    "💀 Regret it",
}

REVISIT_LABELS = {
    "yes":   "✓ Definitely",
    "maybe": "Maybe",
    "no":    "Nope",
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    telegram_handle = update.effective_user.username
    lang = update.effective_user.language_code or "en"
    text = update.message.text.strip()

    session = database.get_session(telegram_id, telegram_handle)
    state = session.get("state", "idle")

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

            # Ask one more reflection question or move to rating
            payload = session.get("state_payload") or {}
            reflection_count = payload.get("reflection_count", 0)

            if reflection_count < 1:
                # Ask one follow-up question
                question = ai_parser.get_reflection_question(
                    item["title"], item["type"], text
                )
                payload["reflection_count"] = reflection_count + 1
                database.set_session_state(telegram_id, "reflecting", item_id, payload)
                await update.message.reply_text(question)
            else:
                # Done reflecting — move to feeling rating
                await _ask_feeling(update, telegram_id, item_id)
        return

    # ── State: waiting for quote (optional) ──
    if state == "awaiting_quote":
        item_id = session.get("state_item_id")
        if text.lower() not in ("skip", ".", "-", "no"):
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
    if not parsed.get("title") or parsed.get("confidence") == "low" and parsed.get("ambiguity"):
        if parsed.get("ambiguity"):
            await update.message.reply_text(parsed["ambiguity"])
        else:
            await update.message.reply_text(ai_parser.quick_reply("not_understood", lang))
        return

    title = parsed["title"]
    item_type = parsed.get("type", "other")
    status = parsed.get("status", "want")

    # Check for duplicate
    existing = database.find_existing_item(title, item_type, telegram_id)

    if existing:
        # Update existing item
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
        # Create new item
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

    # Fetch metadata in background (don't block the response)
    context.application.create_task(
        _fetch_and_update_metadata(item_id, title, item_type)
    )

    # Send confirmation immediately — user gets a response fast
    await _send_confirmation(update, item, action, status)

    # If done/abandoned — kick off reflection in background so confirmation lands first
    already_reflected = existing and existing.get("feeling")  # skip if already rated
    if status in ("done", "abandoned") and not already_reflected:
        database.set_session_state(telegram_id, "reflecting", item_id, {"reflection_count": 0})
        context.application.create_task(
            _send_reflection_question(update, telegram_id, item_id, title, item_type, text, lang)
        )


async def _send_reflection_question(update: Update, telegram_id: int, item_id: str, title: str, item_type: str, text: str, lang: str = "en"):
    """Generate and send reflection question in background."""
    try:
        question = ai_parser.get_reflection_question(title, item_type, text, lang)
        await update.message.reply_text(question)
    except Exception:
        pass


async def _fetch_and_update_metadata(item_id: str, title: str, item_type: str):
    """Fetch metadata from APIs and update the item. Runs in background."""
    try:
        data = await metadata.fetch_metadata(title, item_type)
        if data:
            # Don't override user-set fields
            data.pop("title", None)
            database.update_item(item_id, data)
    except Exception:
        pass  # Metadata fetch failing should never crash the bot


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
    """Send the feeling rating keyboard."""
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"feeling:{item_id}:{key}")]
        for key, label in FEELING_LABELS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    database.set_session_state(telegram_id, "awaiting_feeling", item_id)
    await update.message.reply_text(
        "Last step — how would you sum it up?",
        reply_markup=reply_markup
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id
    data = query.data

    # ── Feeling rating ──
    if data.startswith("feeling:"):
        _, item_id, feeling = data.split(":")
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
        database.update_item(item_id, {})  # trigger updated_at
        await query.edit_message_text(f"✓ Added *{suggested_title}* to your Want List!", parse_mode="Markdown")

    elif data.startswith("suggest_dismiss:"):
        await query.edit_message_text("Got it, skipped.")


async def _finish_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int, item_id: str):
    """Wrap up an entry: generate summary, suggest related content."""
    database.set_session_state(telegram_id, "idle")
    item = database.get_item(item_id)
    if not item:
        return

    # Generate highlights from all raw messages
    raw = item.get("raw_messages") or []
    if raw:
        highlights, plain = ai_parser.generate_summary(item["title"], raw)
        database.update_item(item_id, {"summary": plain})
        item["summary"] = plain
        item["highlights"] = highlights
    else:
        highlights = []

    # Build the saved message
    type_emoji = {"book": "📚", "film": "🎬", "show": "📺", "other": "✦"}
    emoji = type_emoji.get(item.get("type"), "✦")
    feeling_labels = {
        "essential": "🔥 Essential", "loved": "❤️ Loved it", "good": "👍 Good",
        "fine": "😐 Fine", "not_for_me": "👎 Not for me", "regret": "💀 Regret it"
    }
    revisit_labels = {"yes": "Would revisit ✓", "maybe": "Maybe revisit", "no": "Wouldn't revisit"}

    title_line = f"{emoji} *{item['title']}*"
    if item.get("creator"):
        title_line += f" — {item['creator']}"
    if item.get("year"):
        title_line += f" · {item['year']}"

    meta_parts = []
    if item.get("feeling"):
        meta_parts.append(feeling_labels.get(item["feeling"], ""))
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

    # Generate vibe tags from summary
    if item.get("summary"):
        context.application.create_task(
            _generate_and_save_tags(item_id, item)
        )


async def _generate_and_save_tags(item_id: str, item: dict):
    """Generate vibe tags and a content suggestion in the background."""
    import anthropic as anth
    import json
    import os

    client = anth.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": f"""Based on this reflection about "{item['title']}": {item['summary']}

Return 3-4 vibe tags as a JSON array. Examples: ["slow burn", "dark", "atmospheric", "thought-provoking", "funny", "emotional", "page-turner", "light", "rewatchable", "demanding"]
JSON only, no other text."""}]
    )
    try:
        tags = json.loads(response.content[0].text.strip())
        database.update_item(item_id, {"vibe_tags": tags})
        item["vibe_tags"] = tags
    except Exception:
        pass

    # Now generate suggestion
    suggestion = ai_parser.generate_suggestion(
        item["title"],
        item["type"],
        item.get("summary", ""),
        item.get("feeling"),
        item.get("vibe_tags", [])
    )

    if suggestion:
        database.save_item  # just reference to avoid unused import warning
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
