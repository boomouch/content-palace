import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

TMDB_TOKEN = os.getenv("TMDB_READ_TOKEN")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
OL_BASE = "https://openlibrary.org"
KP_TOKEN = os.getenv("KINOPOISK_API_KEY")
KP_BASE = "https://api.poiskkino.dev"
GB_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")
GB_BASE = "https://www.googleapis.com/books/v1/volumes"


async def fetch_kp_candidates(title: str, limit: int = 3) -> list[dict]:
    """Search Kinopoisk (poiskkino.dev) by title. Returns top results for disambiguation."""
    if not KP_TOKEN:
        return []
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{KP_BASE}/v1.4/movie/search",
                headers={"X-API-KEY": KP_TOKEN},
                params={"query": title, "limit": limit, "page": 1},
                timeout=8,
            )
            docs = resp.json().get("docs", [])
        candidates = []
        for r in docs:
            candidates.append({
                "kp_id": r["id"],
                "title": r.get("name") or r.get("alternativeName") or r.get("enName") or title,
                "title_en": r.get("enName") or r.get("alternativeName"),
                "year": r.get("year"),
                "is_series": r.get("isSeries", False),
            })
        return candidates
    except Exception:
        return []


async def fetch_kp_metadata(title: str, item_type: str, kp_id: int | None = None) -> dict:
    """Fetch full metadata from Kinopoisk for a film or show."""
    if not KP_TOKEN:
        return {}
    try:
        if not kp_id:
            candidates = await fetch_kp_candidates(title, limit=1)
            if not candidates:
                return {}
            kp_id = candidates[0]["kp_id"]

        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{KP_BASE}/v1.4/movie/{kp_id}",
                headers={"X-API-KEY": KP_TOKEN},
                timeout=8,
            )
            r = resp.json()

        if not r.get("id"):
            return {}

        # Director: find person with enProfession == "director"
        persons = r.get("persons") or []
        director = next(
            (p.get("name") or p.get("enName") for p in persons if p.get("enProfession") == "director"),
            None
        )

        genres_ru = [g["name"].lower() for g in (r.get("genres") or []) if g.get("name")]

        name_ru = r.get("name")  # Russian title (primary on Kinopoisk)
        name_en = r.get("enName") or r.get("alternativeName")

        # Fetch English title, description, and genres from TMDB using KP's embedded TMDB ID
        tmdb_id_from_kp = (r.get("externalId") or {}).get("tmdb")
        description_en = None
        genres_en: list = []  # stay empty if TMDB unavailable — don't store Russian in EN field
        if tmdb_id_from_kp:
            endpoint_tmdb = "tv" if r.get("isSeries") else "movie"
            title_key_tmdb = "name" if r.get("isSeries") else "title"
            try:
                async with httpx.AsyncClient() as http:
                    tmdb_resp = await http.get(
                        f"{TMDB_BASE}/{endpoint_tmdb}/{tmdb_id_from_kp}",
                        headers={"Authorization": f"Bearer {TMDB_TOKEN}"},
                        params={"language": "en-US"},
                        timeout=5,
                    )
                    tmdb_data = tmdb_resp.json()
                if not name_en:
                    name_en = tmdb_data.get(title_key_tmdb) or None
                description_en = tmdb_data.get("overview") or None
                genres_en = [g["name"].lower() for g in tmdb_data.get("genres", [])]
            except Exception:
                pass

        result = {
            "external_id": str(kp_id),
            "external_source": "kinopoisk",
            "title": name_en or name_ru or title,  # English canonical
            "title_ru": name_ru,                    # ALWAYS set Russian title
            "creator": director,
            "year": r.get("year"),
            "description": description_en,           # English from TMDB (None if TMDB unavailable)
            "description_ru": r.get("description") or r.get("shortDescription"),  # Russian from KP
            "cover_url": (r.get("poster") or {}).get("url"),
            "genres": genres_en or [],               # English from TMDB (empty if unavailable)
            "genres_ru": genres_ru,                  # Russian from KP
            "metadata_raw": r,
        }
        return result
    except Exception:
        return {}


async def fetch_tmdb_candidates(title: str, item_type: str, limit: int = 3, lang: str = "en", original_title: str | None = None) -> list[dict]:
    """Return top TMDB results for disambiguation.
    For RU users, searches with both the original RU title and the EN title to maximise coverage."""
    import re
    clean_title = re.sub(r'\s+\d{4}$', '', title.strip())
    endpoint = "movie" if item_type == "film" else "tv"
    title_key = "title" if item_type == "film" else "name"
    date_key = "release_date" if item_type == "film" else "first_air_date"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    tmdb_lang = "ru-RU" if lang == "ru" else "en-US"

    # Build list of search queries — for RU users try original Russian title first
    queries = [clean_title]
    if original_title and original_title.lower() != clean_title.lower():
        orig_clean = re.sub(r'\s+\d{4}$', '', original_title.strip())
        queries = [orig_clean, clean_title]  # Russian first, English fallback

    try:
        seen_ids: set = set()
        candidates = []
        async with httpx.AsyncClient() as http:
            for query in queries:
                resp = await http.get(
                    f"{TMDB_BASE}/search/{endpoint}",
                    headers=headers,
                    params={"query": query, "language": tmdb_lang, "page": 1},
                    timeout=8,
                )
                for r in resp.json().get("results", []):
                    if r["id"] in seen_ids:
                        continue
                    seen_ids.add(r["id"])
                    raw_date = r.get(date_key, "")
                    year = int(raw_date[:4]) if raw_date else None
                    candidates.append({
                        "tmdb_id": r["id"],
                        "title": r.get(title_key, title),
                        "year": year,
                    })
                    if len(candidates) >= limit:
                        break
                if len(candidates) >= limit:
                    break
        return candidates
    except Exception:
        return []


async def fetch_metadata(title: str, item_type: str, source_url: str | None = None, tmdb_id: int | None = None, lang: str = "en", kp_id: int | None = None) -> dict:
    """Fetch metadata for a given title and type. Returns enriched data dict."""
    if item_type == "book":
        return await _fetch_book(title, lang=lang)
    elif item_type in ("film", "show"):
        if lang == "ru":
            return await fetch_kp_metadata(title, item_type, kp_id=kp_id)
        return await _fetch_tmdb(title, item_type, tmdb_id=tmdb_id)
    elif source_url and ("youtube.com" in source_url or "youtu.be" in source_url):
        return await _fetch_youtube(source_url, title)
    elif item_type == "other":
        tmdb_data = await _fetch_tmdb_cover_only(title)
        ddg_data = await _fetch_ddg(title)
        return {**ddg_data, **tmdb_data}  # TMDB cover wins if both found
    return {}


async def _fetch_ddg(title: str) -> dict:
    """DuckDuckGo instant answer — grab description and try to infer subtype."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://api.duckduckgo.com/",
                params={"q": title, "format": "json", "no_html": "1", "no_redirect": "1"},
                timeout=5,
                headers={"User-Agent": "ContentPalaceBot/1.0"}
            )
            data = resp.json()

        result: dict = {}

        abstract = data.get("Abstract") or data.get("AbstractText") or ""
        if abstract:
            result["description"] = abstract[:500]

        # Infer subtype from DDG category/source
        subtype = None
        source = (data.get("AbstractSource") or "").lower()
        entity_type = (data.get("Type") or "").lower()
        if "youtube" in source or "youtube" in abstract.lower():
            subtype = "youtube"
        elif "podcast" in abstract.lower() or "podcast" in source:
            subtype = "podcast"
        elif "newsletter" in abstract.lower():
            subtype = "newsletter"
        elif "documentary" in abstract.lower():
            subtype = "documentary"
        if subtype:
            result["subtype"] = subtype

        return result
    except Exception:
        return {}


async def _fetch_tmdb_ru(tmdb_id: int, endpoint: str, title_key: str) -> tuple[str | None, str | None, list[str]]:
    """Fetch Russian title, description, and genres for a TMDB item."""
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{TMDB_BASE}/{endpoint}/{tmdb_id}",
                headers=headers,
                params={"language": "ru-RU"},
                timeout=5,
            )
            data = resp.json()
        title_ru = data.get(title_key) or None
        description_ru = data.get("overview") or None
        genres_ru = [g["name"].lower() for g in data.get("genres", [])]
        return title_ru, description_ru, genres_ru
    except Exception:
        return None, None, []


async def _fetch_tmdb(title: str, item_type: str, tmdb_id: int | None = None) -> dict:
    endpoint = "movie" if item_type == "film" else "tv"
    title_key = "title" if item_type == "film" else "name"
    date_key = "release_date" if item_type == "film" else "first_air_date"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}

    if tmdb_id:
        # Fetch directly by ID — no search needed
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{TMDB_BASE}/{endpoint}/{tmdb_id}",
                headers=headers,
                params={"language": "en-US"},
                timeout=8,
            )
            top = resp.json()
        if not top.get("id"):
            return {}
    else:
        results = []
        # Try EN first, fall back to RU (handles titles logged in Russian)
        for lang_code in ["en-US", "ru-RU"]:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{TMDB_BASE}/search/{endpoint}",
                    headers=headers,
                    params={"query": title, "language": lang_code, "page": 1}
                )
                results = resp.json().get("results", [])
            if results:
                break

        if not results:
            return {}

        top = results[0]
        tmdb_id = top["id"]

    cover_url = f"{TMDB_IMG}{top['poster_path']}" if top.get("poster_path") else None

    # Fetch RU localization in parallel with other detail calls
    if item_type == "film":
        creator, genres, (title_ru, description_ru, genres_ru) = await asyncio.gather(
            _get_tmdb_director(tmdb_id),
            _get_tmdb_genres(tmdb_id, "movie"),
            _fetch_tmdb_ru(tmdb_id, endpoint, title_key),
        )
        result = {
            "external_id": str(tmdb_id),
            "external_source": "tmdb",
            "title": top.get(title_key, title),
            "creator": creator,
            "year": int(top[date_key][:4]) if top.get(date_key) else None,
            "description": top.get("overview"),
            "cover_url": cover_url,
            "genres": genres,
            "metadata_raw": top,
        }
    else:
        creator, genres, (title_ru, description_ru, genres_ru) = await asyncio.gather(
            _get_tmdb_show_creator(tmdb_id),
            _get_tmdb_genres(tmdb_id, "tv"),
            _fetch_tmdb_ru(tmdb_id, endpoint, title_key),
        )
        result = {
            "external_id": str(tmdb_id),
            "external_source": "tmdb",
            "title": top.get(title_key, title),
            "creator": creator,
            "year": int(top[date_key][:4]) if top.get(date_key) else None,
            "description": top.get("overview"),
            "cover_url": cover_url,
            "genres": genres,
            "metadata_raw": top,
        }

    # Only store RU if it's actually different
    if title_ru and title_ru != result["title"]:
        result["title_ru"] = title_ru
    if description_ru:
        result["description_ru"] = description_ru
    if genres_ru:
        result["genres_ru"] = genres_ru

    return result


async def _get_tmdb_director(movie_id: int) -> str | None:
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TMDB_BASE}/movie/{movie_id}/credits", headers=headers)
        crew = resp.json().get("crew", [])
    directors = [p["name"] for p in crew if p.get("job") == "Director"]
    return directors[0] if directors else None


async def _get_tmdb_show_creator(show_id: int) -> str | None:
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TMDB_BASE}/tv/{show_id}", headers=headers)
        created_by = resp.json().get("created_by", [])
    return created_by[0]["name"] if created_by else None


async def _get_tmdb_genres(item_id: int, endpoint: str) -> list[str]:
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TMDB_BASE}/{endpoint}/{item_id}", headers=headers)
        genres = resp.json().get("genres", [])
    return [g["name"].lower() for g in genres]


async def _fetch_tmdb_cover_only(title: str) -> dict:
    """Try TMDB TV search to get cover art, description, and subtype for 'other' type content."""
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{TMDB_BASE}/search/tv",
                headers=headers,
                params={"query": title, "language": "en-US", "page": 1}
            )
            results = resp.json().get("results", [])
        if not results:
            return {}

        top = results[0]
        out: dict = {}
        if top.get("poster_path"):
            out["cover_url"] = f"{TMDB_IMG}{top['poster_path']}"
        if top.get("overview"):
            out["description"] = top["overview"]

        # Fetch show details to check network (detect YouTube shows)
        async with httpx.AsyncClient() as http:
            detail_resp = await http.get(f"{TMDB_BASE}/tv/{top['id']}", headers=headers, timeout=5)
            detail = detail_resp.json()

        networks = [n.get("name", "").lower() for n in detail.get("networks", [])]
        if any("youtube" in n for n in networks):
            out["subtype"] = "youtube"

        return out
    except Exception:
        return {}


async def _fetch_youtube(url: str, title: str) -> dict:
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=5
            )
            data = resp.json()
        return {
            "external_source": "youtube",
            "title": data.get("title", title),
            "creator": data.get("author_name"),
            "cover_url": data.get("thumbnail_url"),
        }
    except Exception:
        return {}


def _is_cyrillic(s: str) -> bool:
    """Return True if string is predominantly Cyrillic (i.e. Russian text)."""
    if not s:
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04FF')
    return cyrillic / len(s) > 0.3


def _is_bad_ol_title(s: str) -> bool:
    """Detect transliterated or low-quality OpenLibrary titles that aren't real English."""
    if not s:
        return False
    # Diacritics from Czech/Slovak/Polish transliterations (e.g. "Zaščita Lužina")
    if any(c in s for c in 'šžčŠŽČāēīūñ'):
        return True
    # OL sometimes returns "Title (Russian Edition)" or similar junk
    sl = s.lower()
    return any(p in sl for p in ('russian edition', 'russian language', 'russian text', 'in russian'))


async def _fetch_google_books(title: str, author: str | None = None, lang_restrict: str | None = None) -> dict:
    """Fetch book metadata from Google Books API. Uses intitle: for precision."""
    try:
        q = f"intitle:{title}"
        if author:
            q += f"+inauthor:{author}"
        params: dict = {
            "q": q,
            "maxResults": 1,
            "fields": "items/volumeInfo(title,authors,publishedDate,description,imageLinks,categories)",
        }
        if GB_KEY:
            params["key"] = GB_KEY
        if lang_restrict:
            params["langRestrict"] = lang_restrict
        async with httpx.AsyncClient() as http:
            resp = await http.get(GB_BASE, params=params, timeout=8)
            items = resp.json().get("items", [])
        if not items:
            return {}
        info = items[0].get("volumeInfo", {})
        cover_url = (info.get("imageLinks") or {}).get("thumbnail")
        if cover_url:
            cover_url = cover_url.replace("zoom=1", "zoom=3").replace("&edge=curl", "")
        authors = info.get("authors", [])
        raw_date = info.get("publishedDate", "")
        year = int(raw_date[:4]) if raw_date and raw_date[:4].isdigit() else None
        description = (info.get("description") or "").strip()
        return {
            "external_source": "google_books",
            "title": info.get("title", title),
            "creator": authors[0] if authors else None,
            "year": year,
            "description": description[:500] if description else None,
            "cover_url": cover_url,
            "genres": [c.lower() for c in (info.get("categories") or [])[:5]],
        }
    except Exception:
        return {}


async def _fetch_book(title: str, lang: str = "en") -> dict:
    """Fetch book metadata. Always stores both EN and RU fields so language toggle works."""
    if lang == "ru":
        # Step 1: find the Russian edition to get author + Russian metadata
        gb_ru = await _fetch_google_books(title, lang_restrict="ru")
        author = gb_ru.get("creator")
        # Trust gb_ru title only if it's Cyrillic — Google Books sometimes stores
        # transliterated titles (e.g. "Zaščita Lužina") even for Russian editions
        gb_ru_title = gb_ru.get("title", "")
        if gb_ru_title and not _is_cyrillic(gb_ru_title):
            gb_ru = {}  # discard — not a real Russian edition result
        title_ru = gb_ru.get("title") or title  # fall back to what user typed

        # Step 2: search for English edition in parallel — OL often has English titles for translated works
        gb_en, ol = await asyncio.gather(
            _fetch_google_books(title, author=author, lang_restrict="en"),
            _fetch_book_openlibrary(title),
        )

        # If GB-EN returned a Cyrillic/Russian title or same as Russian title,
        # it found the same Russian book — discard it, no English edition on GB
        gb_en_title = gb_en.get("title", "")
        if _is_cyrillic(gb_en_title) or gb_en_title.lower() == title_ru.lower():
            gb_en = {}

        # OL may return English title for Russian classics (e.g. "Братья Карамазовы" → "The Brothers Karamazov")
        ol_title = ol.get("title", "")
        if _is_cyrillic(ol_title) or _is_bad_ol_title(ol_title):
            ol = {}  # OL returned Russian or a transliteration — not useful as English source

        title_en = gb_en.get("title") or ol.get("title")

        result: dict = {
            "external_id": ol.get("external_id"),
            "external_source": "google_books",
            "title": title_en or title_ru,              # English if found, else Russian
            "title_ru": title_ru,                        # ALWAYS set for toggle to work
            "creator": author or ol.get("creator"),
            "year": gb_en.get("year") or gb_ru.get("year") or ol.get("year"),
            "cover_url": gb_en.get("cover_url") or gb_ru.get("cover_url") or ol.get("cover_url"),
            "description": gb_en.get("description") or ol.get("description"),  # English only
            # Only store RU description if it's actually in Russian
            "description_ru": gb_ru.get("description") if _is_cyrillic(gb_ru.get("description") or "") else None,
            "genres": ol.get("genres") or gb_en.get("genres") or [],            # English
            "genres_ru": gb_ru.get("genres") or [],                              # Russian
            "metadata_raw": ol.get("metadata_raw"),
        }
        # If title_en matched title_ru (same text), keep title_ru anyway for explicit RU toggle
        return {k: v for k, v in result.items() if v is not None and v != []}

    # EN users: OL + GB in parallel, merge
    ol, gb = await asyncio.gather(
        _fetch_book_openlibrary(title),
        _fetch_google_books(title),
    )
    return {k: v for k, v in {
        "external_id": ol.get("external_id"),
        "external_source": ol.get("external_source") or gb.get("external_source"),
        "title": ol.get("title") or gb.get("title") or title,
        "creator": ol.get("creator") or gb.get("creator"),
        "year": ol.get("year") or gb.get("year"),
        "cover_url": ol.get("cover_url") or gb.get("cover_url"),
        "description": ol.get("description") or gb.get("description"),
        "genres": ol.get("genres") or gb.get("genres") or [],
        "metadata_raw": ol.get("metadata_raw"),
    }.items() if v is not None and v != []}


async def _fetch_book_openlibrary(title: str) -> dict:
    """Fetch book metadata from OpenLibrary."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{OL_BASE}/search.json",
                params={"title": title, "limit": 1, "fields": "key,title,author_name,first_publish_year,cover_i,subject"},
                timeout=8,
            )
            data = resp.json()
    except Exception:
        return {}

    results = data.get("docs", [])
    if not results:
        return {}

    top = results[0]
    cover_id = top.get("cover_i")
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
    authors = top.get("author_name", [])
    subjects = top.get("subject", [])[:5]

    description = None
    work_key = top.get("key")
    if work_key:
        try:
            async with httpx.AsyncClient() as http:
                work_resp = await http.get(f"{OL_BASE}{work_key}.json", timeout=5)
                work_data = work_resp.json()
                raw_desc = work_data.get("description")
                if isinstance(raw_desc, dict):
                    description = raw_desc.get("value")
                elif isinstance(raw_desc, str):
                    description = raw_desc
                if description:
                    description = description[:500]
        except Exception:
            pass

    return {
        "external_id": work_key,
        "external_source": "openlibrary",
        "title": top.get("title", title),
        "creator": authors[0] if authors else None,
        "year": top.get("first_publish_year"),
        "cover_url": cover_url,
        "description": description,
        "genres": [s.lower() for s in subjects],
        "metadata_raw": top,
    }
