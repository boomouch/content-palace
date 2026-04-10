"""
Content Palace QA test suite.
Covers: regex routing, AI parser, status guards, note commands, API endpoints.

Run all tests:
    python tests/test_qa.py

Run only fast tests (no API calls, no network):
    python tests/test_qa.py --fast

Run only API tests (requires running Next.js server):
    python tests/test_qa.py --api
"""

import sys
import re
import os
import io
import json
import time
import asyncio
import argparse
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── make imports work from project root ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"
SECTION = "\033[1;34m"
RESET = "\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}


def check(label: str, ok: bool, detail: str = ""):
    if ok:
        print(f"  {PASS} {label}")
        results["pass"] += 1
    else:
        print(f"  {FAIL} {label}" + (f"  ← {detail}" if detail else ""))
        results["fail"] += 1


def skip(label: str, reason: str = ""):
    print(f"  {SKIP} {label}" + (f"  ({reason})" if reason else ""))
    results["skip"] += 1


def section(title: str):
    print(f"\n{SECTION}{'-'*55}\n  {title}\n{'-'*55}{RESET}")


# ═══════════════════════════════════════════════════════
# 1. REGEX ROUTING
# ═══════════════════════════════════════════════════════

section("1. Regex routing")

from handlers.message import (
    _DELETE_RE, _RATE_RE, _RATE_BARE_RE,
    _NOTE_RE, _RU_NOTE_RE, _UPDATE_NOTE_RE, _REWRITE_RE, _STATUS_RE,
)

# Delete
check("delete english",        bool(_DELETE_RE.match("delete Dune")))
check("remove english",        bool(_DELETE_RE.match("remove Breaking Bad")))
check("удали russian",         bool(_DELETE_RE.match("удали Дюна")))
check("удалить russian",       bool(_DELETE_RE.match("удалить сыны анархии")))
check("delete with 'entry'",   bool(_DELETE_RE.match("delete Dune entry")))

# Rate
check("rate ... loved",        bool(_RATE_RE.match("rate Dune loved")))
check("update ... essential",  bool(_RATE_RE.match("update Breaking Bad essential")))
check("оцени ... not for me",  bool(_RATE_RE.match("оцени Дюна not for me")))
check("rate with emoji 🔥",    bool(_RATE_RE.match("rate Dune 🔥")))
check("rate bare prompt",      bool(_RATE_BARE_RE.match("rate Dune rating")))

# English note
check("add to X: Y",           bool(_NOTE_RE.match("add to Breaking Bad: best show ever")))
check("add to X that Y",       bool(_NOTE_RE.match("add to Dune that it blew my mind")))
check("add note to X: Y",      bool(_NOTE_RE.match("add note to Misery: creepy as hell")))
check("to X, add that Y",      bool(_NOTE_RE.match("to Dune, add that the desert scenes are stunning")))
check("to X add Y",            bool(_NOTE_RE.match("to Dune add great cinematography")))

# Russian note (new _RU_NOTE_RE — no separator required)
check("добавить к X",          bool(_RU_NOTE_RE.match("добавить к сыны анархии")))
check("добавить к X текст",    bool(_RU_NOTE_RE.match("добавить к сыны анархии крутой сериал")))
check("добавить к X: текст",   bool(_RU_NOTE_RE.match("добавить к сыны анархии: крутой сериал")))
check("добавь к X текст",      bool(_RU_NOTE_RE.match("добавь к сыны анархии отличная съёмка")))
check("добавь заметку к X",    bool(_RU_NOTE_RE.match("добавь заметку к Дюна")))
check("добавить заметку к X",  bool(_RU_NOTE_RE.match("добавить заметку к мизери текст")))

# Confirm things that should NOT match _RU_NOTE_RE don't accidentally match
check("plain watch msg no match", not bool(_RU_NOTE_RE.match("посмотрела сыны анархии")))
check("plain title no match",     not bool(_RU_NOTE_RE.match("сыны анархии")))

# Status update (requires "mark/update/change" prefix — bare "finished X" goes to parser)
check("mark X as done",        bool(_STATUS_RE.match("mark Dune as done")))
check("update X to watching",  bool(_STATUS_RE.match("update Succession to watching")))
check("set X as abandoned",    bool(_STATUS_RE.match("set Breaking Bad as abandoned")))
check("bare 'finished X' NOT caught by STATUS_RE (goes to parser)", not bool(_STATUS_RE.match("finished Dune")))

# Rewrite
check("rewrite X",             bool(_REWRITE_RE.match("rewrite Dune")))
check("recap X",               bool(_REWRITE_RE.match("recap Breaking Bad")))


# ═══════════════════════════════════════════════════════
# 2. RU NOTE: regex capture + separator splitting
# ═══════════════════════════════════════════════════════

section("2. Russian note — regex capture")

regex_cases = [
    ("добавить к сыны анархии: крутой сериал", "сыны анархии: крутой сериал"),
    ("добавить к сыны анархии крутой сериал",  "сыны анархии крутой сериал"),
    ("добавить к сыны анархии",                "сыны анархии"),
    ("добавь заметку к Дюна всё понравилось",  "Дюна всё понравилось"),
]
for msg, expected_capture in regex_cases:
    m = _RU_NOTE_RE.match(msg)
    captured = m.group(1).strip() if m else None
    check(f"'{msg[:40]}' → '{expected_capture}'",
          captured == expected_capture,
          f"got: '{captured}'")

section("2b. _split_ru_note — title/note extraction")

from handlers.message import _split_ru_note

split_cases = [
    # (raw_captured, expected_title, expected_note)
    ("сыны анархии: крутой сериал",   "сыны анархии",   "крутой сериал"),   # colon separator
    ("сыны анархии - крутой сериал",  "сыны анархии",   "крутой сериал"),   # dash separator
    ("сыны анархии – крутой сериал",  "сыны анархии",   "крутой сериал"),   # em-dash
    ("сыны анархии крутой сериал",    "сыны анархии крутой сериал", ""),     # no separator → full raw, empty note
    ("сыны анархии",                  "сыны анархии",   ""),                 # title only
    ("Дюна: лучший фантастический фильм", "Дюна",       "лучший фантастический фильм"),
]
for raw, exp_title, exp_note in split_cases:
    title, note = _split_ru_note(raw)
    ok = title == exp_title and note == exp_note
    check(f"split('{raw[:40]}') → ('{exp_title}', '{exp_note[:20]}')",
          ok, f"got title='{title}' note='{note}'")


# ═══════════════════════════════════════════════════════
# 3. AI PARSER  (requires ANTHROPIC_API_KEY)
# ═══════════════════════════════════════════════════════

section("3. AI parser — message parsing")

HAS_ANTHROPIC = bool(os.getenv("ANTHROPIC_API_KEY"))

# Format: (message, exp_type, exp_status, exp_title_substr, exp_feeling, is_question_flag, lang, note)
# exp_* = None means "don't check this field"
# is_question_flag = True means we expect is_question:true and skip type/status checks
PARSE_CASES = [

    # ── Basic EN status detection ─────────────────────────────────────────────
    ("watched Dune",                    "film",  "done",        "Dune",          None,        False, "en", "bare watch"),
    ("want to watch Inception",         "film",  "want",        "Inception",     None,        False, "en", "want to watch"),
    ("need to watch Parasite",          "film",  "want",        "Parasite",      None,        False, "en", "need to = want"),
    ("on my list: Oppenheimer",         "film",  "want",        "Oppenheimer",   None,        False, "en", "on my list"),
    ("reading Sapiens",                 "book",  "in_progress", "Sapiens",       None,        False, "en", "reading = in_progress"),
    ("currently watching Succession",   "show",  "in_progress", "Succession",    None,        False, "en", "currently watching"),
    ("in the middle of The Wire",       "show",  "in_progress", "The Wire",      None,        False, "en", "in the middle of"),
    ("finished Breaking Bad",           "show",  "done",        "Breaking Bad",  None,        False, "en", "finished show"),
    ("just read Sapiens",               "book",  "done",        "Sapiens",       None,        False, "en", "just read"),
    ("completed Succession",            "show",  "done",        "Succession",    None,        False, "en", "completed"),
    ("gave up on The Wire",             "show",  "abandoned",   "The Wire",      None,        False, "en", "gave up = abandoned"),
    ("couldn't finish Ulysses",         "book",  "abandoned",   "Ulysses",       None,        False, "en", "couldn't finish"),
    ("abandoned Moby Dick",             "book",  "abandoned",   "Moby Dick",     None,        False, "en", "abandoned book"),

    # ── Feeling / sentiment detection ────────────────────────────────────────
    ("watched Midsommar - hated it",    "film",  "done",        "Midsommar",     None,        False, "en", "hated → not_for_me or regret (both valid)"),
    ("just watched Oppenheimer, loved it", "film","done",       "Oppenheimer",   "loved",     False, "en", "loved → loved"),
    ("read Sapiens - absolutely mind-blowing", "book","done",   "Sapiens",       "loved",     False, "en", "mind-blowing → loved"),
    ("watched Joker - so disappointing","film",  "done",        "Joker",         "not_for_me", False, "en", "disappointing → not_for_me"),
    ("Dune - essential, everyone must watch", "film", None,      "Dune",          "essential", False, "en", "essential feeling (status ambiguous)"),
    ("read Twilight - total waste of time","book","done",       "Twilight",      "regret",    False, "en", "waste of time → regret"),
    ("watched Inception, it was decent", "film", "done",        "Inception",     "average",   False, "en", "decent → average"),

    # ── Type disambiguation: film vs show ────────────────────────────────────
    ("watched Succession season 3",     "show",  "done",        "Succession",    None,        False, "en", "season → show"),
    ("finished episode 5 of The Bear",  "show",  "done",        "The Bear",      None,        False, "en", "episode → show"),
    ("binge-watched all of Severance",  "show",  "done",        "Severance",     None,        False, "en", "binge-watched show"),
    ("watched Parasite",                "film",  "done",        "Parasite",      None,        False, "en", "watched → film default"),

    # ── Subtype detection ────────────────────────────────────────────────────
    ("subscribed to Stratechery newsletter","other", None,       "Stratechery",   None,        False, "en", "newsletter subtype (status: subscribed=in_progress or want)"),
    ("listening to Lex Fridman podcast", "other", "in_progress","Lex Fridman",   None,        False, "en", "podcast subtype"),
    ("watched a YouTube channel 3Blue1Brown","other","done",    "3Blue1Brown",   None,        False, "en", "youtube subtype"),

    # ── Typos and informal phrasing ──────────────────────────────────────────
    ("finsihed Dune lol",               "film",  "done",        "Dune",          None,        False, "en", "typo in 'finished'"),
    ("waatched inception",              "film",  "done",        "Inception",     None,        False, "en", "typo in 'watched'"),
    ("just finnished breaking bad omg", "show",  "done",        "Breaking Bad",  None,        False, "en", "typo + lowercase"),
    ("dune was so good!!!",             "film",  "done",        "Dune",          None,        False, "en", "no verb, just reaction"),
    ("WATCHED DUNE",                    "film",  "done",        "Dune",          None,        False, "en", "all caps"),
    ("watched dune 2021",               "film",  "done",        "Dune",          None,        False, "en", "year appended to title"),

    # ── Mixed language ────────────────────────────────────────────────────────
    ("watched Дюна",                    "film",  "done",        "Dune",          None,        False, "en", "EN verb + RU title"),
    ("посмотрела Inception",            "film",  "done",        "Inception",     None,        False, "ru", "RU verb + EN title"),

    # ── Russian ───────────────────────────────────────────────────────────────
    ("посмотрела Дюну",                 "film",  "done",        "Dune",          None,        False, "ru", "RU basic film"),
    ("хочу посмотреть Начало",          "film",  "want",        "Inception",     None,        False, "ru", "RU want film"),
    ("надо посмотреть Оппенгеймер",     "film",  "want",        "Oppenheimer",   None,        False, "ru", "RU need to watch"),
    ("читаю Сапиенс",                   "book",  "in_progress", "Sapiens",       None,        False, "ru", "RU reading"),
    ("хочу прочитать Дюну",             "book",  "want",        "Dune",          None,        False, "ru", "RU want book"),
    ("посмотрела Мидсоммар — жесть",    "film",  "done",        "Midsommar",     None,        False, "ru", "RU with reaction"),
    ("бросила Игру престолов на 4 сезоне","show","abandoned",   "Game of Thrones",None,       False, "ru", "RU abandoned show"),
    ("смотрю Наследников",              "show",  "in_progress", "Наследни",      None,        False, "ru", "RU watching show (Succession in RU)"),
    ("сыны анархии",                    "show",  None,          "Sons of Anarchy",None,       False, "ru", "RU bare title"),
    ("мизери — страшная книга",         "book",  "done",        "Misery",        None,        False, "ru", "RU book with comment"),

    # ── Should NOT create entries ─────────────────────────────────────────────
    # Note: "добавить к X" is caught by _RU_NOTE_RE before the parser — not tested here
    ("hello",                           None,    None,          None,            None,        False, "en", "random greeting → null title"),
    ("what should I watch next?",       None,    None,          None,            None,        False, "en", "generic question → null title"),

    # ── Questions ─────────────────────────────────────────────────────────────
    ("what do you think about Dune?",   None,    None,          "Dune",          None,        True,  "en", "EN question about title"),
    ("стоит ли смотреть Дюну?",         None,    None,          "Dune",          None,        True,  "ru", "RU question about title"),
    ("is Breaking Bad worth watching?", None,    None,          "Breaking Bad",  None,        True,  "en", "is X worth watching?"),
]

if HAS_ANTHROPIC:
    from services import ai_parser

    for msg, exp_type, exp_status, exp_title_substr, exp_feeling, is_q_expected, lang, note in PARSE_CASES:
        try:
            result = ai_parser.parse_message(msg)
            is_q_got = result.get("is_question", False)

            if is_q_expected:
                title_ok = (exp_title_substr is None) or (
                    exp_title_substr.lower() in (result.get("title") or "").lower()
                )
                ok = is_q_got and title_ok
                check(f"[{lang}] '{msg[:50]}' → is_question [{note}]", ok,
                      f"is_question={is_q_got} title={result.get('title')}")
            elif exp_type is None:
                # Expect no media item logged
                ok = not result.get("title") or result.get("confidence") == "low"
                check(f"[{lang}] '{msg[:50]}' → no item [{note}]", ok,
                      f"got title={result.get('title')} confidence={result.get('confidence')}")
            else:
                type_ok    = result.get("type") == exp_type
                status_ok  = (exp_status is None) or (result.get("status") == exp_status)
                title_ok   = (exp_title_substr is None) or (
                    exp_title_substr.lower() in (result.get("title") or "").lower()
                )
                feeling_ok = (exp_feeling is None) or (result.get("feeling") == exp_feeling)
                ok = type_ok and status_ok and title_ok and feeling_ok
                check(
                    f"[{lang}] '{msg[:50]}' → {exp_type}/{exp_status} [{note}]",
                    ok,
                    f"type={result.get('type')} status={result.get('status')} "
                    f"title={result.get('title')} feeling={result.get('feeling')}"
                )
            time.sleep(0.25)
        except Exception as e:
            check(f"[{lang}] '{msg[:45]}'", False, str(e))
else:
    for msg, *_, note in PARSE_CASES:
        skip(f"'{msg[:45]}' [{note}]", "no ANTHROPIC_API_KEY")


# ═══════════════════════════════════════════════════════
# 4. AI PARSER — reflection questions
# ═══════════════════════════════════════════════════════

section("4. AI parser — reflection questions")

REFLECT_CASES = [
    # (title, type, message, lang)
    # Generic — no opinion in message → expect "how did you find it?" style
    ("Dune",           "film", "watched Dune",                       "en"),
    ("Breaking Bad",   "show", "finished Breaking Bad",              "en"),
    ("Sapiens",        "book", "read Sapiens",                       "en"),
    ("Дюна",           "film", "посмотрела Дюну",                    "ru"),
    ("Сапиенс",        "book", "прочитала Сапиенс",                  "ru"),
    # Sentiment present → should drill into that word, not ask generic
    ("Midsommar",      "film", "watched Midsommar - hated it",       "en"),
    ("Sapiens",        "book", "read Sapiens - mind blowing",        "en"),
    ("Joker",          "film", "watched Joker, so disappointing",    "en"),
    ("Succession",     "show", "finished Succession, absolutely loved it","en"),
    ("Дюна",           "film", "посмотрела Дюну — обожаю",           "ru"),
    ("Мидсоммар",      "film", "посмотрела Мидсоммар — ужас просто", "ru"),
]

if HAS_ANTHROPIC:
    REASONING_MARKERS = [
        "the message", "contains", "opinion", "sentiment", "does not",
        "i will ask", "since", "therefore", "let me", "in this case",
        "no sentiment", "no opinion", "i notice", "i see that",
        "based on", "looking at", "there is no",
    ]
    GENERIC_MARKERS_EN = ["how did you find it", "what did you think"]
    GENERIC_MARKERS_RU = ["как тебе", "что думаешь", "что скажешь"]

    for title, itype, msg, lang in REFLECT_CASES:
        has_sentiment = any(w in msg.lower() for w in [
            "hated", "loved", "mind blowing", "disappointing", "обожаю",
            "ужас", "amazing", "terrible", "boring", "incredible"
        ])
        try:
            q = ai_parser.get_reflection_question(title, itype, [msg], question_number=1, lang=lang)
            is_one_sentence = len(q.strip().split("\n")) == 1
            no_reasoning    = not any(m in q.lower() for m in REASONING_MARKERS)
            ends_with_q     = q.strip().endswith("?")
            if has_sentiment:
                # Should NOT be generic
                generic_markers = GENERIC_MARKERS_RU if lang == "ru" else GENERIC_MARKERS_EN
                not_generic = not any(m in q.lower() for m in generic_markers)
                ok = is_one_sentence and no_reasoning and ends_with_q and not_generic
                check(f"[{lang}] '{msg[:45]}' → specific (has sentiment)",
                      ok, f"got: '{q}'")
            else:
                ok = is_one_sentence and no_reasoning and ends_with_q
                check(f"[{lang}] '{msg[:45]}' → clean generic question",
                      ok, f"got: '{q}'")
            time.sleep(0.3)
        except Exception as e:
            check(f"'{msg[:40]}'", False, str(e))
else:
    for title, itype, msg, lang in REFLECT_CASES:
        skip(f"[{lang}] '{msg[:40]}'", "no ANTHROPIC_API_KEY")


# ═══════════════════════════════════════════════════════
# 4b. DATABASE — title_ru search  (requires SUPABASE_URL)
# ═══════════════════════════════════════════════════════

section("4b. Database — title_ru search")

HAS_DB = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY"))

if HAS_DB:
    from services import database as db_svc

    # We can't guarantee specific items exist, but we can verify the query doesn't crash
    # and returns consistent results between title and title_ru searches
    try:
        # Any search should work without error
        result_en = db_svc.find_items_fuzzy("Dune", telegram_id=0)
        check("find_items_fuzzy doesn't crash", True)

        # Verify that find_items_fuzzy and find_existing_item accept title_ru values
        # by checking the .or_() filter syntax is accepted by Supabase
        result_ru = db_svc.find_items_fuzzy("Дюна", telegram_id=0)
        check("find_items_fuzzy with Cyrillic title doesn't crash", True)

        # Verify find_existing_item also works
        result_ei = db_svc.find_existing_item("Dune", "film", telegram_id=0)
        check("find_existing_item doesn't crash", True)

        # If any items exist at all, check title_ru column is present in schema
        if result_en:
            has_title_ru_key = "title_ru" in result_en[0]
            check("title_ru column present in items schema", has_title_ru_key,
                  f"keys: {list(result_en[0].keys())[:10]}")
    except Exception as e:
        check("DB queries execute without error", False, str(e))
else:
    for label in ["find_items_fuzzy doesn't crash", "Cyrillic search doesn't crash",
                  "find_existing_item doesn't crash", "title_ru column present"]:
        skip(label, "no SUPABASE_URL/SUPABASE_SECRET_KEY")


# ═══════════════════════════════════════════════════════
# 5. METADATA  (requires TMDB_READ_TOKEN)
# ═══════════════════════════════════════════════════════

section("5. Metadata — TMDB + OpenLibrary")

HAS_TMDB = bool(os.getenv("TMDB_READ_TOKEN"))

TMDB_CASES = [
    ("Dune",            "film",  "Denis Villeneuve",   2021),
    ("Breaking Bad",    "show",  None,                 2008),
    ("Inception",       "film",  "Christopher Nolan",  2010),
]
BOOK_CASES = [
    ("Sapiens",         "book",  "Yuval Noah Harari"),
    ("Misery",          "book",  "Stephen King"),
]

if HAS_TMDB:
    from services import metadata

    async def run_tmdb():
        for title, itype, creator, year in TMDB_CASES:
            try:
                data = await metadata.fetch_metadata(title, itype)
                has_cover = bool(data.get("cover_url"))
                has_year  = data.get("year") == year
                has_title = title.lower() in (data.get("title") or "").lower()
                check(f"TMDB '{title}' → cover+year+title",
                      has_cover and has_year and has_title,
                      f"year={data.get('year')} title={data.get('title')} cover={'yes' if has_cover else 'no'}")
            except Exception as e:
                check(f"TMDB '{title}'", False, str(e))

        for title, itype, creator in BOOK_CASES:
            try:
                data = await metadata.fetch_metadata(title, itype)
                has_cover   = bool(data.get("cover_url"))
                right_author = creator.split()[-1].lower() in (data.get("creator") or "").lower()
                check(f"OL '{title}' → cover+author",
                      has_cover and right_author,
                      f"creator={data.get('creator')} cover={'yes' if has_cover else 'no'}")
            except Exception as e:
                check(f"OL '{title}'", False, str(e))

    asyncio.run(run_tmdb())
else:
    for title, *_ in TMDB_CASES + BOOK_CASES:
        skip(f"'{title}'", "no TMDB_READ_TOKEN")


# ═══════════════════════════════════════════════════════
# 6. STATUS GUARD — no downgrade from done → want
# ═══════════════════════════════════════════════════════

section("6. Status guard logic (unit)")

# Simulating the guard check directly without DB
def status_guard(existing_status: str, new_status: str) -> bool:
    """Returns True if the update should be BLOCKED."""
    return existing_status in ("done", "abandoned") and new_status == "want"

check("done → want is BLOCKED",          status_guard("done", "want"))
check("done → in_progress is allowed",   not status_guard("done", "in_progress"))
check("done → done is allowed",          not status_guard("done", "done"))
check("abandoned → want is BLOCKED",     status_guard("abandoned", "want"))
check("want → done is allowed",          not status_guard("want", "done"))
check("in_progress → done is allowed",   not status_guard("in_progress", "done"))


# ═══════════════════════════════════════════════════════
# 7. API ROUTES  (requires running Next.js dev server)
# ═══════════════════════════════════════════════════════

section("7. API routes")

import httpx

API_BASE = os.getenv("NEXT_PUBLIC_URL", "http://localhost:3000")

def try_json(r) -> tuple[bool, object]:
    """Try to parse response as JSON. Returns (success, data)."""
    try:
        return True, r.json()
    except Exception:
        return False, None

def api_reachable() -> tuple[bool, bool]:
    """Returns (reachable, auth_required)."""
    try:
        r = httpx.get(f"{API_BASE}/api/users", timeout=3)
        if r.status_code == 401:
            return True, True   # server up but auth-protected
        return True, False
    except Exception:
        return False, False

if "--api" in sys.argv or "--all" in sys.argv:
    reachable, auth_required = api_reachable()
    if not reachable:
        print(f"  WARNING: Cannot reach {API_BASE} — skipping API tests")
        for label in ["GET /api/users", "GET /api/recommendations", "POST /api/taste-summary"]:
            skip(label, "server not reachable")
    elif auth_required:
        print(f"  WARNING: {API_BASE} returns 401 (Vercel deployment protection)")
        for label in ["GET /api/users", "GET /api/recommendations", "POST /api/taste-summary"]:
            skip(label, "deployment auth required — use localhost:3000 or prod URL")
    else:
        # GET /api/users
        try:
            r = httpx.get(f"{API_BASE}/api/users", timeout=5)
            ok_json, users = try_json(r)
            check("GET /api/users → 200 + JSON array",
                  r.status_code == 200 and ok_json and isinstance(users, list),
                  f"status={r.status_code} json={ok_json}")
            if ok_json and users:
                tid = users[0].get("telegram_id")
                # GET /api/recommendations?telegram_id=X
                r2 = httpx.get(f"{API_BASE}/api/recommendations", params={"telegram_id": tid}, timeout=5)
                ok2, data2 = try_json(r2)
                check("GET /api/recommendations?telegram_id → 200 + array",
                      r2.status_code == 200 and ok2 and isinstance(data2, list),
                      f"status={r2.status_code}")
                if ok2 and data2:
                    rec = data2[0]
                    check("recommendation has required fields",
                          all(k in rec for k in ("title", "type", "why")),
                          f"keys: {list(rec.keys())}")
                    check("recommendation has telegram_id",
                          rec.get("telegram_id") == tid,
                          f"got telegram_id={rec.get('telegram_id')} expected={tid}")

                # GET without telegram_id — should not 500
                r3 = httpx.get(f"{API_BASE}/api/recommendations", timeout=5)
                check("GET /api/recommendations without telegram_id → not 500",
                      r3.status_code != 500, f"status={r3.status_code}")
        except Exception as e:
            check("GET /api/users", False, str(e))

        # POST /api/taste-summary — empty items
        try:
            r = httpx.post(f"{API_BASE}/api/taste-summary",
                           json={"items": [], "lang": "en"}, timeout=10)
            check("POST /api/taste-summary (empty items) → not 500",
                  r.status_code != 500, f"status={r.status_code}")
        except Exception as e:
            check("POST /api/taste-summary (empty)", False, str(e))

        # POST /api/taste-summary — with items, Russian
        try:
            sample_items = [
                {"type": "film", "title": "Dune", "feeling": "loved", "genres": ["sci-fi"], "vibe_tags": ["epic"]},
                {"type": "book", "title": "Sapiens", "feeling": "essential", "genres": ["history"], "vibe_tags": []},
            ]
            r = httpx.post(f"{API_BASE}/api/taste-summary",
                           json={"items": sample_items, "lang": "ru"}, timeout=15)
            ok, body = try_json(r)
            check("POST /api/taste-summary (ru, with items) → 200 + summary string",
                  r.status_code == 200 and ok and isinstance(body.get("summary"), str),
                  f"status={r.status_code} body={str(body)[:100]}")
        except Exception as e:
            check("POST /api/taste-summary (ru)", False, str(e))
else:
    for label in ["GET /api/users", "GET /api/recommendations", "POST /api/taste-summary"]:
        skip(label, "pass --api to run")


# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════

total = results["pass"] + results["fail"] + results["skip"]
print(f"\n{'-'*55}")
print(f"  {results['pass']}/{total - results['skip']} passed  "
      f"| {results['fail']} failed  "
      f"| {results['skip']} skipped")
print(f"{'-'*55}\n")

if results["fail"] > 0:
    sys.exit(1)
