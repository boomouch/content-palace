import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

TMDB_TOKEN = os.getenv("TMDB_READ_TOKEN")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
OL_BASE = "https://openlibrary.org"


async def fetch_tmdb_candidates(title: str, item_type: str, limit: int = 3, lang: str = "en") -> list[dict]:
    """Return top TMDB results for disambiguation. Strips trailing year from title before searching."""
    import re
    clean_title = re.sub(r'\s+\d{4}$', '', title.strip())
    endpoint = "movie" if item_type == "film" else "tv"
    title_key = "title" if item_type == "film" else "name"
    date_key = "release_date" if item_type == "film" else "first_air_date"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    tmdb_lang = "ru-RU" if lang == "ru" else "en-US"
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{TMDB_BASE}/search/{endpoint}",
                headers=headers,
                params={"query": clean_title, "language": tmdb_lang, "page": 1},
                timeout=8,
            )
            results = resp.json().get("results", [])
        candidates = []
        for r in results[:limit]:
            raw_date = r.get(date_key, "")
            year = int(raw_date[:4]) if raw_date else None
            candidates.append({
                "tmdb_id": r["id"],
                "title": r.get(title_key, title),
                "year": year,
            })
        return candidates
    except Exception:
        return []


async def fetch_metadata(title: str, item_type: str, source_url: str | None = None, tmdb_id: int | None = None) -> dict:
    """Fetch metadata for a given title and type. Returns enriched data dict."""
    if item_type == "book":
        return await _fetch_book(title)
    elif item_type in ("film", "show"):
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


async def _fetch_book(title: str) -> dict:
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{OL_BASE}/search.json",
            params={"title": title, "limit": 1, "fields": "key,title,author_name,first_publish_year,cover_i,subject"}
        )
        data = resp.json()

    results = data.get("docs", [])
    if not results:
        return {}

    top = results[0]
    cover_id = top.get("cover_i")
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else None
    authors = top.get("author_name", [])
    subjects = top.get("subject", [])[:5]

    # Fetch description — try OpenLibrary work record first, fall back to Google Books
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

    if not description:
        try:
            async with httpx.AsyncClient() as http:
                gb_resp = await http.get(
                    "https://www.googleapis.com/books/v1/volumes",
                    params={"q": f"intitle:{title}", "maxResults": 1, "fields": "items/volumeInfo/description"},
                    timeout=5
                )
                gb_items = gb_resp.json().get("items", [])
                if gb_items:
                    raw = gb_items[0].get("volumeInfo", {}).get("description", "")
                    if raw:
                        description = raw[:500]
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
