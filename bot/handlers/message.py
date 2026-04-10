import re
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services import ai_parser, database, metadata
# database.get_user is used for language preference lookup


FEELING_LABELS = {
    "essential": "🔥 Essential",
    "loved":     "❤️ Loved it",
    "average":   "😐 Average",
    "not_for_me":"🙈 Not for me",
    "regret":    "💀 Regret it",
}

FEELING_LABELS_RU = {
    "essential": "🔥 Маст-си",
    "loved":     "❤️ Понравилось",
    "average":   "😐 Нормально",
    "not_for_me":"🙈 Не моё",
    "regret":    "💀 Зря потратил(а) время",
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

REVISIT_LABELS_RU = {
    "yes":   "✓ Пересмотрю/перечитаю",
    "maybe": "Может быть",
    "no":    "Вряд ли",
}


def _titles_match(input_title: str, found_title: str) -> bool:
    """Return True if the found title is close enough to what the user typed — no confirmation needed."""
    a = input_title.lower().strip()
    b = found_title.lower().strip()
    # Exact or substring match
    if a in b or b in a:
        return True
    # Check if any word from input appears in found title (handles transliterations like "мизери" → "misery")
    words_a = set(a.split())
    words_b = set(b.split())
    if words_a & words_b:
        return True
    return False


def _feeling_labels(lang: str) -> dict:
    return FEELING_LABELS_RU if lang == "ru" else FEELING_LABELS


def _revisit_labels(lang: str) -> dict:
    return REVISIT_LABELS_RU if lang == "ru" else REVISIT_LABELS


def _get_lang(telegram_id: int) -> str:
    user = database.get_user(telegram_id)
    return user.get("lang", "en") if user else "en"

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
# Note prefixes — no separator required; handler does progressive search
_RU_NOTE_RE   = re.compile(r'^добав(?:ить|ь|и)(?:\s+заметку)?\s+к\s+(.+)$', re.IGNORECASE | re.DOTALL)
_EN_NOTE_RE   = re.compile(r'^add(?:\s+(?:note|to))?\s+to\s+(.+)$', re.IGNORECASE | re.DOTALL)
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


_RU_INTENT_RE = re.compile(
    r'^(?:хочу\s+(?:посмотреть|прочитать|послушать|посмотрим|почитать)\s+|'
    r'(?:посмотрел[аи]?|прочитал[аи]?|послушал[аи]?)\s+|'
    r'(?:смотрю|читаю|слушаю)\s+|'
    r'(?:начал[аи]?\s+(?:смотреть|читать|слушать)\s+)|'
    r'(?:закончил[аи]?\s+(?:смотреть|читать|слушать)?\s*)|'
    r'(?:бросил[аи]?\s+(?:смотреть|читать)?\s*))',
    re.IGNORECASE
)

def _extract_ru_title(text: str) -> str:
    """Strip Russian intent phrases to get just the title."""
    return _RU_INTENT_RE.sub("", text).strip()


async def _show_kp_picker(update, context, candidates: list, parsed: dict, telegram_id: int, lang: str, text: str):
    """Show Kinopoisk disambiguation picker. Used as fallback when AI parser can't identify the title."""
    raw_status = parsed.get("status", "want")
    status = raw_status if raw_status in ("want", "in_progress", "done", "abandoned") else "want"
    item_type = parsed.get("type", "film") if parsed.get("type") in ("film", "show") else "film"
    candidates.sort(key=lambda c: c.get("year") or 0, reverse=True)
    context.bot_data[f"pending_{telegram_id}"] = {
        "parsed": {**parsed, "status": status, "type": item_type},
        "item_type": item_type,
        "status": status,
        "subtype": None,
        "text": text,
        "candidates": candidates,
        "lang": lang,
    }
    keyboard = [
        [InlineKeyboardButton(
            f"{c['title']} ({c['year'] or '?'})",
            callback_data=f"pick_media:{telegram_id}:{i}"
        )]
        for i, c in enumerate(candidates)
    ]
    keyboard.append([InlineKeyboardButton("Это не то — сохранить как введено", callback_data=f"pick_media:{telegram_id}:none")])
    keyboard.append([InlineKeyboardButton("❌ Отмена — не добавлять", callback_data=f"pick_media:{telegram_id}:cancel")])
    query_title = parsed.get("title") or text
    await update.message.reply_text(
        f"Нашла несколько вариантов для *{query_title}* — какой?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    telegram_handle = update.effective_user.username
    text = update.message.text.strip()

    # Use stored user language preference; fall back to Telegram locale
    user_record = database.get_user(telegram_id)
    if user_record:
        lang = user_record.get("lang", "en")
    else:
        raw_lang = update.effective_user.language_code or "en"
        lang = raw_lang[:2] if raw_lang else "en"

    session = database.get_session(telegram_id, telegram_handle)
    state = session.get("state", "idle")

    # ── Awaiting note text (after "добавить к X" with no note) ──
    awaiting_note_item_id = context.bot_data.pop(f"awaiting_note_{telegram_id}", None)
    if awaiting_note_item_id:
        item = database.get_item(awaiting_note_item_id)
        if item:
            database.append_raw_message(awaiting_note_item_id, text)
            display_title = item.get("title_ru") or item["title"] if lang == "ru" else item["title"]
            msg = f"Заметка добавлена к *{display_title}*. Обновляю summary..." if lang == "ru" else f"Note added to *{display_title}*. Updating summary..."
            await update.message.reply_text(msg, parse_mode="Markdown")
            context.application.create_task(_regenerate_summary(update, awaiting_note_item_id))
            return

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
        # Groups 1,2 = "add to X: Y"; 3,4 = "to X, add Y"
        title_q = (note_match.group(1) or note_match.group(3) or "").strip()
        note_text = (note_match.group(2) or note_match.group(4) or "").strip()
        if title_q and note_text:
            await _handle_add_note(update, context, title_q, note_text, telegram_id)
            return

    ru_note_match = _RU_NOTE_RE.match(text)
    if ru_note_match:
        await _handle_ru_note(update, context, ru_note_match.group(1).strip(), telegram_id, lang)
        return

    en_note_match = _EN_NOTE_RE.match(text)
    if en_note_match:
        await _handle_ru_note(update, context, en_note_match.group(1).strip(), telegram_id, lang)
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
        msg = "Используй кнопки выше ↑" if lang == "ru" else "Use the buttons above to rate your feeling ↑"
        await update.message.reply_text(msg)
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

    # No media item detected — for RU users try KP search before giving up
    if not parsed.get("title"):
        if lang == "ru":
            kp_query = _extract_ru_title(text)
            if kp_query:
                kp_fallback = await metadata.fetch_kp_candidates(kp_query, limit=3)
                if kp_fallback:
                    await _show_kp_picker(update, context, kp_fallback, parsed, telegram_id, lang, text)
                    return
        await update.message.reply_text(ai_parser.quick_reply("not_understood", lang))
        return

    # Low confidence — for RU users try KP search first using parsed title
    if parsed.get("confidence") == "low":
        if lang == "ru":
            kp_query = parsed.get("title") or _extract_ru_title(text)
            if kp_query:
                kp_fallback = await metadata.fetch_kp_candidates(kp_query, limit=3)
                if kp_fallback:
                    await _show_kp_picker(update, context, kp_fallback, parsed, telegram_id, lang, text)
                    return
        _low_title = parsed.get("title", "")
        if lang == "ru":
            clarification = f"Не поняла — уточни: _фильм {_low_title}_, _сериал {_low_title}_ или _книга {_low_title}_" if _low_title else "Не поняла — напиши, например: «посмотрела Дюну» или «читаю Сапиенс»"
        else:
            clarification = f"Not sure what to log — try: _film {_low_title}_, _show {_low_title}_ or _book {_low_title}_" if _low_title else "Not sure what you mean — try: \"watched Dune\" or \"reading Sapiens\""
        await update.message.reply_text(clarification, parse_mode="Markdown")
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
        # Don't demote a finished/abandoned item back to want
        if existing.get("status") in ("done", "abandoned") and status == "want":
            existing_title = existing.get("title", title)
            if lang == "ru":
                await update.message.reply_text(f"*{existing_title}* уже у тебя в библиотеке как завершённое. Хочешь добавить заметку?", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"*{existing_title}* is already in your library as finished. Want to add a note?", parse_mode="Markdown")
            return

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
        # For films/shows: fetch candidates and let user pick
        if item_type in ("film", "show"):
            if lang == "ru":
                all_candidates = await metadata.fetch_kp_candidates(title, limit=6)
                # Filter by type: show → only series, film → only non-series
                want_series = item_type == "show"
                candidates = [c for c in all_candidates if c.get("is_series") == want_series]
                # Fall back to unfiltered if nothing survived the filter
                if not candidates:
                    candidates = all_candidates
                candidates = candidates[:3]
            else:
                candidates = await metadata.fetch_tmdb_candidates(title, item_type, lang=lang)
            # Sort candidates: most recent year first
            candidates.sort(key=lambda c: c.get("year") or 0, reverse=True)
            if len(candidates) >= 2 or (len(candidates) == 1 and not _titles_match(title, candidates[0]["title"])):
                context.bot_data[f"pending_{telegram_id}"] = {
                    "parsed": parsed,
                    "item_type": item_type,
                    "status": status,
                    "subtype": subtype,
                    "text": text,
                    "candidates": candidates,
                    "lang": lang,
                }
                def _candidate_label(c: dict) -> str:
                    label = c["title"]
                    if c.get("year"):
                        label += f" ({c['year']})"
                    # Show type indicator for KP results (is_series field present)
                    if "is_series" in c:
                        label += " 📺" if c["is_series"] else " 🎬"
                    return label

                keyboard = [
                    [InlineKeyboardButton(_candidate_label(c), callback_data=f"pick_media:{telegram_id}:{i}")]
                    for i, c in enumerate(candidates)
                ]
                if lang == "ru":
                    none_label   = "Это не то — сохранить как введено"
                    cancel_label = "❌ Отмена — не добавлять"
                    prompt = f"Нашла несколько вариантов для *{title}* — какой?"
                else:
                    none_label   = "None of these — save as typed"
                    cancel_label = "❌ Cancel — don't add"
                    prompt = f"Found a few matches for *{title}* — which one?"
                keyboard.append([InlineKeyboardButton(none_label,   callback_data=f"pick_media:{telegram_id}:none")])
                keyboard.append([InlineKeyboardButton(cancel_label, callback_data=f"pick_media:{telegram_id}:cancel")])
                await update.message.reply_text(
                    prompt,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
                return

        # For RU books: search GB for candidates and show a picker (same as KP for films)
        if item_type == "book" and lang == "ru":
            book_candidates = await metadata.fetch_book_candidates(title, lang_restrict="ru", limit=3)
            if book_candidates:
                context.bot_data[f"pending_{telegram_id}"] = {
                    "parsed": parsed,
                    "item_type": item_type,
                    "status": status,
                    "text": text,
                    "candidates": book_candidates,
                    "lang": lang,
                }
                keyboard = [
                    [InlineKeyboardButton(
                        f"{c['title']}{' — ' + c['creator'] if c.get('creator') else ''}{' (' + str(c['year']) + ')' if c.get('year') else ''}",
                        callback_data=f"pick_media:{telegram_id}:{i}"
                    )]
                    for i, c in enumerate(book_candidates)
                ]
                keyboard.append([InlineKeyboardButton("Это не то — сохранить как введено", callback_data=f"pick_media:{telegram_id}:none")])
                keyboard.append([InlineKeyboardButton("❌ Отмена — не добавлять", callback_data=f"pick_media:{telegram_id}:cancel")])
                await update.message.reply_text(
                    f"Нашла несколько вариантов для *{title}* — какой?",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
                return

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
        _fetch_and_update_metadata(item_id, title, item_type, parsed.get("source_url"), lang=lang)
    )

    await _send_confirmation(update, item, action, status, lang)

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


def _split_ru_note(raw: str) -> tuple[str, str]:
    """Split 'title: note' or 'title - note' or 'title note' into (title_query, note_text).
    Returns (full_raw, '') when no separator found — caller does progressive search."""
    import re as _re
    m = _re.match(r'^(.+?)\s*[:\-–]\s*(.+)$', raw.strip(), _re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw.strip(), ""


async def _handle_ru_note(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str, telegram_id: int, lang: str):
    """Handle 'добавить к X [note]' — supports explicit separator or progressive title search."""
    title_query, note_text = _split_ru_note(raw)

    matches = database.find_items_fuzzy(title_query, telegram_id)

    if not matches and not note_text:
        # No separator found — try progressive search (trim words from end)
        words = raw.split()
        for split in range(len(words) - 1, 0, -1):
            candidate = " ".join(words[:split])
            matches = database.find_items_fuzzy(candidate, telegram_id)
            if matches:
                note_text = " ".join(words[split:]).strip()
                title_query = candidate
                break

    if not matches:
        msg = f"Не нашла ничего похожего на «{title_query}»." if lang == "ru" else f"Couldn't find anything matching \"{title_query}\"."
        await update.message.reply_text(msg)
        return

    item = matches[0]
    display_title = (item.get("title_ru") or item["title"]) if lang == "ru" else item["title"]

    if note_text:
        database.append_raw_message(item["id"], note_text)
        msg = f"Заметка добавлена к *{display_title}*. Обновляю summary..." if lang == "ru" else f"Note added to *{display_title}*. Updating summary..."
        await update.message.reply_text(msg, parse_mode="Markdown")
        context.application.create_task(_regenerate_summary(update, item["id"]))
    else:
        context.bot_data[f"awaiting_note_{telegram_id}"] = item["id"]
        msg = f"Что добавить к *{display_title}*?" if lang == "ru" else f"What note to add to *{display_title}*?"
        await update.message.reply_text(msg, parse_mode="Markdown")


async def _generate_summary_and_tags(item_id: str, title: str, messages: list[str]):
    """Generate summary + vibe tags from reflection messages. Called after Q2 is answered."""
    try:
        item = database.get_item(item_id)
        if not item:
            return
        lang = _get_lang(item.get("telegram_id")) if item.get("telegram_id") else "en"
        lang_name = "Russian" if lang == "ru" else "English"
        all_messages = list(item.get("raw_messages") or [])
        highlights, plain = ai_parser.generate_summary(title, all_messages, lang=lang)
        summary = json.dumps(highlights, ensure_ascii=False) if highlights else plain
        database.update_item(item_id, {"summary": summary})
        item["summary"] = summary

        # Generate vibe tags in user's language
        import anthropic as anth, os as _os
        _client = anth.Anthropic(api_key=_os.getenv("ANTHROPIC_API_KEY"))
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": f"""Based on this reflection about "{title}": {summary}

Generate 2-4 vibe tags as a JSON array. Reply in {lang_name}.

Mix two types:
1. Tone/feel of the content (e.g. dark, funny, slow burn, intense, cozy, disturbing) — infer from what you know about it if not mentioned
2. Emotional experience from their words — only from what they actually said

Rules:
- 2-4 tags total, no overlap
- Short, lowercase
- JSON only, no markdown fences."""}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        tags = json.loads(raw)
        database.update_item(item_id, {"vibe_tags": tags})

        # For RU users: copy to _ru columns (no translation needed — content is already in RU)
        if lang == "ru":
            ru_copy: dict = {}
            if highlights:
                ru_copy["highlights_ru"] = highlights
            if summary:
                ru_copy["summary_ru"] = summary
            if tags:
                ru_copy["vibe_tags_ru"] = tags
            if ru_copy:
                database.update_item(item_id, ru_copy)
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
        lang = _get_lang(item.get("telegram_id")) if item.get("telegram_id") else "en"
        raw = item.get("raw_messages") or []
        if not raw:
            return
        highlights, plain = ai_parser.generate_summary(item["title"], raw, lang=lang)
        database.update_item(item_id, {"summary": json.dumps(highlights, ensure_ascii=False) if highlights else plain})
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


async def _send_reflection_question_from_callback(query, telegram_id: int, item_id: str, title: str, item_type: str, messages: list[str], lang: str = "en"):
    try:
        question = ai_parser.get_reflection_question(title, item_type, messages, question_number=1, lang=lang)
        await query.message.reply_text(question)
    except Exception:
        pass


async def _fetch_and_update_metadata(item_id: str, title: str, item_type: str, source_url: str | None = None, tmdb_id: int | None = None, lang: str = "en", kp_id: int | None = None, creator: str | None = None):
    try:
        data = await metadata.fetch_metadata(title, item_type, source_url, tmdb_id=tmdb_id, lang=lang, kp_id=kp_id, creator=creator)
        if data:
            # For RU entries: allow title update so English canonical gets stored
            # (KP metadata resolves English via TMDB fallback)
            # For EN entries: don't overwrite title (it's already correct from parser)
            if lang != "ru":
                data.pop("title", None)
            database.update_item(item_id, data)
        elif item_type == "book":
            # No metadata found for book — delete the item rather than keep an empty entry
            database.delete_item(item_id)
    except Exception:
        pass


async def _send_confirmation(update: Update, item: dict, action: str, status: str, lang: str = "en"):
    import os as _os
    if lang == "ru":
        status_labels = {
            "want": "Добавлено в список желаний",
            "in_progress": "Сейчас читаю/смотрю",
            "done": "Отмечено как завершённое",
            "abandoned": "Отмечено как брошенное",
        }
    else:
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

    # Append app link only for want-list additions
    if status == "want":
        tid = item.get("telegram_id")
        app_base = _os.getenv("APP_URL", "").rstrip("/")
        if tid and app_base:
            url = f"{app_base}?user={tid}"
            link_text = "Открыть список" if lang == "ru" else "Open Want List"
            msg += f"\n[{link_text}]({url})"

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)


async def _ask_feeling(update: Update, telegram_id: int, item_id: str):
    lang = _get_lang(telegram_id)
    labels = _feeling_labels(lang)
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"feeling:{item_id}:{key}")]
        for key, label in labels.items()
    ]
    database.set_session_state(telegram_id, "awaiting_feeling", item_id)
    prompt = "Последний шаг — как бы ты это описал(а)?" if lang == "ru" else "Last step — how would you sum it up?"
    await update.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(keyboard))


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
        lang = _get_lang(telegram_id)
        labels = _feeling_labels(lang)
        revisit_labels = _revisit_labels(lang)
        keyboard = [[
            InlineKeyboardButton(label, callback_data=f"revisit:{item_id}:{key}")
            for key, label in revisit_labels.items()
        ]]
        database.set_session_state(telegram_id, "awaiting_feeling", item_id)
        revisit_q = "Пересмотришь/перечитаешь?" if lang == "ru" else "Would you revisit it?"
        await query.edit_message_text(
            f"{labels.get(feeling, feeling)} — записал!\n\n{revisit_q}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ── Would revisit ──
    elif data.startswith("revisit:"):
        _, item_id, revisit = data.split(":")
        database.update_item(item_id, {"would_revisit": revisit})
        database.set_session_state(telegram_id, "awaiting_quote", item_id)
        lang = _get_lang(telegram_id)
        revisit_labels = _revisit_labels(lang)
        if lang == "ru":
            quote_prompt = f"{revisit_labels.get(revisit, revisit)}!\n\nЕсть цитата или фраза, которая запомнилась? (или отправь . чтобы пропустить)"
        else:
            quote_prompt = f"{REVISIT_LABELS.get(revisit, revisit)}!\n\nAny quote or line that stuck with you? (or send . to skip)"
        await query.edit_message_text(quote_prompt)

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

    # ── Media disambiguation picker ──
    elif data.startswith("pick_media:"):
        _, tg_id_str, choice = data.split(":", 2)
        tg_id = int(tg_id_str)

        pending = context.bot_data.pop(f"pending_{tg_id}", None)
        if not pending:
            await query.edit_message_text("Session expired, please try again.")
            return

        parsed = pending["parsed"]
        item_type = pending["item_type"]
        status = pending["status"]
        subtype = pending.get("subtype")
        original_text = pending["text"]
        candidates = pending["candidates"]
        pick_lang = pending.get("lang", "en")

        if choice == "cancel":
            msg = "Окей, не добавляю." if pick_lang == "ru" else "Got it, nothing added."
            await query.edit_message_text(msg)
            return

        chosen = None
        if choice != "none" and choice.isdigit():
            idx = int(choice)
            if 0 <= idx < len(candidates):
                chosen = candidates[idx]

        final_title = chosen["title"] if chosen else parsed["title"]

        from datetime import date
        today = date.today().isoformat()
        item_data = {
            "type": item_type,
            "title": final_title,
            "creator": (chosen.get("creator") if chosen else None) or parsed.get("creator"),
            "status": status,
            "raw_messages": [original_text],
            "source_url": parsed.get("source_url"),
            "telegram_id": tg_id,
        }
        if subtype:
            item_data["subtype"] = subtype
        if status == "in_progress":
            item_data["started_at"] = today
        if status == "done":
            item_data["finished_at"] = today

        existing = database.find_existing_item(final_title, item_type, tg_id)
        if existing:
            # Don't demote a finished/abandoned item back to want
            if existing.get("status") in ("done", "abandoned") and status == "want":
                existing_title = existing.get("title", final_title)
                if pick_lang == "ru":
                    await query.edit_message_text(f"*{existing_title}* уже у тебя в библиотеке как завершённое. Хочешь добавить заметку?", parse_mode="Markdown")
                else:
                    await query.edit_message_text(f"*{existing_title}* is already in your library as finished. Want to add a note?", parse_mode="Markdown")
                return
            item_id = existing["id"]
            update_data = {k: v for k, v in item_data.items() if k not in ("type", "title", "telegram_id")}
            if original_text not in (existing.get("raw_messages") or []):
                update_data["raw_messages"] = (existing.get("raw_messages") or []) + [original_text]
            database.update_item(item_id, update_data)
            item = existing
        else:
            item = database.save_item(item_data)
            item_id = item["id"]

        chosen_tmdb_id = chosen.get("tmdb_id") if chosen else None
        chosen_kp_id = chosen.get("kp_id") if chosen else None
        context.application.create_task(
            _fetch_and_update_metadata(item_id, final_title, item_type, parsed.get("source_url"), tmdb_id=chosen_tmdb_id, lang=pick_lang, kp_id=chosen_kp_id, creator=chosen.get("creator") if chosen else None)
        )

        type_emoji = {"book": "📚", "film": "🎬", "show": "📺", "other": "✦"}
        emoji = type_emoji.get(item_type, "✦")
        year_str = f" ({chosen['year']})" if chosen and chosen.get("year") else ""
        if pick_lang == "ru":
            status_labels = {
                "want": "Добавлено в список желаний",
                "in_progress": "Сейчас смотрю/читаю",
                "done": "Отмечено как завершённое",
                "abandoned": "Отмечено как брошенное",
            }
        else:
            status_labels = {
                "want": "Added to Want List",
                "in_progress": "Currently watching/reading",
                "done": "Marked as done",
                "abandoned": "Marked as abandoned",
            }
        await query.edit_message_text(
            f"{emoji} *{final_title}*{year_str}\n_{status_labels.get(status, 'Saved')}_",
            parse_mode="Markdown"
        )

        if status in ("done", "abandoned"):
            initial_messages = [original_text]
            database.set_session_state(tg_id, "reflecting", item_id, {
                "reflection_count": 0,
                "reflection_messages": initial_messages,
            })
            context.application.create_task(
                _send_reflection_question_from_callback(query, tg_id, item_id, final_title, item_type, initial_messages, pick_lang)
            )


async def _finish_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int, item_id: str):
    database.set_session_state(telegram_id, "idle")
    item = database.get_item(item_id)
    if not item:
        return

    lang = _get_lang(telegram_id)
    raw = item.get("raw_messages") or []
    if raw:
        highlights, plain = ai_parser.generate_summary(item["title"], raw, lang=lang)
        summary_to_save = json.dumps(highlights, ensure_ascii=False) if highlights else plain
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

    import os as _os
    app_base = _os.getenv("APP_URL", "").rstrip("/")
    if app_base:
        url = f"{app_base}?user={telegram_id}"
        link_text = "Открыть в Content Palace" if lang == "ru" else "View in Content Palace"
        msg += f"\n\n[{link_text}]({url})"

    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    if item.get("summary"):
        context.application.create_task(_generate_and_save_tags(item_id, item))


async def _generate_and_save_tags(item_id: str, item: dict):
    import anthropic as anth
    import json as _json
    import os

    item_full = database.get_item(item_id)
    user = database.get_user(item_full.get("telegram_id")) if item_full else None
    lang = user.get("lang", "en") if user else "en"
    lang_name = "Russian" if lang == "ru" else "English"

    _client = anth.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": f"""Based on this reflection about "{item['title']}": {item['summary']}

Generate 2-4 vibe tags as a JSON array. Reply in {lang_name}.

Mix two types:
1. Tone/feel of the content (e.g. dark, funny, slow burn) — infer from what you know about it
2. Emotional experience from their words — only from what they actually said

Rules: 2-4 tags, no overlap, short lowercase. JSON only, no markdown fences."""}]
    )
    tags = []
    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        tags = _json.loads(raw)
        database.update_item(item_id, {"vibe_tags": tags})
        item["vibe_tags"] = tags
    except Exception:
        pass

    # Handle cross-language storage
    try:
        raw_summary = item_full.get("summary", "") if item_full else ""
        try:
            fresh_highlights = _json.loads(raw_summary) if raw_summary and raw_summary.startswith("[") else []
        except Exception:
            fresh_highlights = []

        if lang == "ru":
            # Content already in Russian — copy to _ru columns, translate to EN for base columns
            ru_copy: dict = {}
            if fresh_highlights:
                ru_copy["highlights_ru"] = fresh_highlights
            if raw_summary:
                ru_copy["summary_ru"] = raw_summary
            if tags:
                ru_copy["vibe_tags_ru"] = tags
            if ru_copy:
                database.update_item(item_id, ru_copy)
        else:
            # Content in English — translate to Russian and save to _ru columns
            translated = ai_parser.translate_content(
                highlights=fresh_highlights,
                summary=raw_summary,
                vibe_tags=tags,
                target_lang="ru",
            )
            if translated:
                ru_update: dict = {}
                if translated.get("highlights"):
                    ru_update["highlights_ru"] = translated["highlights"]
                if translated.get("summary"):
                    ru_update["summary_ru"] = translated["summary"]
                if translated.get("vibe_tags"):
                    ru_update["vibe_tags_ru"] = translated["vibe_tags"]
                if ru_update:
                    database.update_item(item_id, ru_update)
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
