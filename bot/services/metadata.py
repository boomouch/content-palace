import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TMDB_TOKEN = os.getenv("TMDB_READ_TOKEN")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"
OL_BASE = "https://openlibrary.org"


async def fetch_metadata(title: str, item_type: str) -> dict:
    """Fetch metadata for a given title and type. Returns enriched data dict."""
    if item_type == "book":
        return await _fetch_book(title)
    elif item_type in ("film", "show"):
        return await _fetch_tmdb(title, item_type)
    return {}


async def _fetch_tmdb(title: str, item_type: str) -> dict:
    endpoint = "movie" if item_type == "film" else "tv"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}

    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"{TMDB_BASE}/search/{endpoint}",
            headers=headers,
            params={"query": title, "language": "en-US", "page": 1}
        )
        data = resp.json()

    results = data.get("results", [])
    if not results:
        return {}

    top = results[0]
    cover_url = f"{TMDB_IMG}{top['poster_path']}" if top.get("poster_path") else None

    if item_type == "film":
        return {
            "external_id": str(top["id"]),
            "external_source": "tmdb",
            "title": top.get("title", title),
            "creator": await _get_tmdb_director(top["id"]),
            "year": int(top["release_date"][:4]) if top.get("release_date") else None,
            "description": top.get("overview"),
            "cover_url": cover_url,
            "genres": await _get_tmdb_genres(top["id"], "movie"),
            "metadata_raw": top,
        }
    else:
        return {
            "external_id": str(top["id"]),
            "external_source": "tmdb",
            "title": top.get("name", title),
            "creator": top.get("origin_country", [None])[0],
            "year": int(top["first_air_date"][:4]) if top.get("first_air_date") else None,
            "description": top.get("overview"),
            "cover_url": cover_url,
            "genres": await _get_tmdb_genres(top["id"], "tv"),
            "metadata_raw": top,
        }


async def _get_tmdb_director(movie_id: int) -> str | None:
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TMDB_BASE}/movie/{movie_id}/credits", headers=headers)
        crew = resp.json().get("crew", [])
    directors = [p["name"] for p in crew if p.get("job") == "Director"]
    return directors[0] if directors else None


async def _get_tmdb_genres(item_id: int, endpoint: str) -> list[str]:
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{TMDB_BASE}/{endpoint}/{item_id}", headers=headers)
        genres = resp.json().get("genres", [])
    return [g["name"].lower() for g in genres]


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

    # Fetch description from the work record
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
                    description = description[:500]  # cap length
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
