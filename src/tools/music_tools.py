import json
import logging

from langchain_core.tools import tool

from src.db.database import run_query_safe

logger = logging.getLogger(__name__)


def _safe_int(value: str, name: str = "ID") -> tuple[int | None, str | None]:
    try:
        return int(value), None
    except (ValueError, TypeError):
        return None, f"Invalid {name} '{value}'. Please provide a numeric value."


@tool
def get_albums_by_artist(artist_name: str) -> str:
    """Get all albums by an artist. Uses fuzzy matching on artist name."""
    logger.info("Tool: get_albums_by_artist | artist=%s", artist_name)
    result = run_query_safe(
        "SELECT al.AlbumId, al.Title AS AlbumTitle, ar.Name AS ArtistName "
        "FROM Album al JOIN Artist ar ON al.ArtistId = ar.ArtistId "
        "WHERE ar.Name LIKE :pattern "
        "ORDER BY ar.Name, al.Title",
        {"pattern": f"%{artist_name}%"},
    )
    rows = json.loads(result)
    if not rows:
        return f"No albums found for artist matching '{artist_name}'."
    return result


@tool
def get_songs_by_artist(artist_name: str) -> str:
    """Get songs by an artist. Returns total count and a sample of up to 20 tracks."""
    logger.info("Tool: get_songs_by_artist | artist=%s", artist_name)
    count_result = run_query_safe(
        "SELECT COUNT(*) AS total FROM Track t "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "WHERE ar.Name LIKE :pattern",
        {"pattern": f"%{artist_name}%"},
    )
    total = json.loads(count_result)[0]["total"]
    if total == 0:
        return f"No songs found for artist matching '{artist_name}'."

    sample = run_query_safe(
        "SELECT t.TrackId, t.Name AS TrackName, a.Title AS Album, "
        "ar.Name AS Artist, t.UnitPrice "
        "FROM Track t "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "WHERE ar.Name LIKE :pattern "
        "ORDER BY t.TrackId LIMIT 20",
        {"pattern": f"%{artist_name}%"},
    )
    rows = json.loads(sample)
    return json.dumps({"total_count": total, "sample": rows})


@tool
def get_songs_by_genre(genre_name: str) -> str:
    """Get representative songs by genre. Returns one track per artist (up to 10 artists) for diversity."""
    logger.info("Tool: get_songs_by_genre | genre=%s", genre_name)
    result = run_query_safe(
        "SELECT t.TrackId, t.Name AS TrackName, ar.Name AS ArtistName, "
        "a.Title AS AlbumTitle, g.Name AS Genre, t.UnitPrice "
        "FROM ( "
        "  SELECT t2.TrackId, "
        "  ROW_NUMBER() OVER (PARTITION BY ar2.ArtistId ORDER BY t2.TrackId) AS rn "
        "  FROM Track t2 "
        "  JOIN Album a2 ON t2.AlbumId = a2.AlbumId "
        "  JOIN Artist ar2 ON a2.ArtistId = ar2.ArtistId "
        "  JOIN Genre g2 ON t2.GenreId = g2.GenreId "
        "  WHERE g2.Name LIKE :pattern "
        ") ranked "
        "JOIN Track t ON ranked.TrackId = t.TrackId "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "JOIN Genre g ON t.GenreId = g.GenreId "
        "WHERE ranked.rn = 1 "
        "ORDER BY t.TrackId "
        "LIMIT 10",
        {"pattern": f"%{genre_name}%"},
    )
    rows = json.loads(result)
    if not rows:
        return f"No songs found for genre matching '{genre_name}'."
    return result


@tool
def search_songs_by_title(title: str) -> str:
    """Search for songs by title. Uses fuzzy matching. Returns up to 10 results."""
    logger.info("Tool: search_songs_by_title | title=%s", title)
    result = run_query_safe(
        "SELECT t.TrackId, t.Name AS TrackName, ar.Name AS Artist, "
        "a.Title AS Album, t.UnitPrice, g.Name AS Genre "
        "FROM Track t "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "JOIN Genre g ON t.GenreId = g.GenreId "
        "WHERE t.Name LIKE :pattern "
        "ORDER BY t.TrackId LIMIT 10",
        {"pattern": f"%{title}%"},
    )
    rows = json.loads(result)
    if not rows:
        return f"No songs found matching title '{title}'."
    return result


@tool
def get_track_details(track_id: str) -> str:
    """Get complete details for a specific track by its numeric ID."""
    logger.info("Tool: get_track_details | track_id=%s", track_id)
    tid, err = _safe_int(track_id, "Track ID")
    if err:
        return err

    result = run_query_safe(
        "SELECT t.TrackId, t.Name AS TrackName, ar.Name AS Artist, "
        "a.Title AS Album, g.Name AS Genre, m.Name AS MediaType, "
        "t.Composer, t.Milliseconds, t.Bytes, t.UnitPrice "
        "FROM Track t "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "JOIN Genre g ON t.GenreId = g.GenreId "
        "JOIN MediaType m ON t.MediaTypeId = m.MediaTypeId "
        "WHERE t.TrackId = :tid",
        {"tid": tid},
    )
    rows = json.loads(result)
    if not rows:
        return f"No track found with ID {tid}."
    return result


@tool
def list_genres() -> str:
    """List all available music genres in the catalog."""
    logger.info("Tool: list_genres")
    result = run_query_safe(
        "SELECT g.GenreId, g.Name AS Genre, COUNT(t.TrackId) AS TrackCount "
        "FROM Genre g JOIN Track t ON g.GenreId = t.GenreId "
        "GROUP BY g.GenreId, g.Name "
        "ORDER BY TrackCount DESC"
    )
    rows = json.loads(result)
    if not rows:
        return "No genres found."
    return result


@tool
def list_artists(genre_name: str = "") -> str:
    """List artists in the catalog. Optionally filter by genre name.
    Returns up to 50 artists with their album count."""
    logger.info("Tool: list_artists | genre=%s", genre_name)
    if genre_name:
        result = run_query_safe(
            "SELECT DISTINCT ar.ArtistId, ar.Name AS Artist, "
            "COUNT(DISTINCT al.AlbumId) AS AlbumCount "
            "FROM Artist ar "
            "JOIN Album al ON ar.ArtistId = al.ArtistId "
            "JOIN Track t ON al.AlbumId = t.AlbumId "
            "JOIN Genre g ON t.GenreId = g.GenreId "
            "WHERE g.Name LIKE :pattern "
            "GROUP BY ar.ArtistId, ar.Name "
            "ORDER BY ar.Name "
            "LIMIT 50",
            {"pattern": f"%{genre_name}%"},
        )
        rows = json.loads(result)
        if not rows:
            return f"No artists found for genre matching '{genre_name}'."
    else:
        result = run_query_safe(
            "SELECT ar.ArtistId, ar.Name AS Artist, "
            "COUNT(al.AlbumId) AS AlbumCount "
            "FROM Artist ar "
            "JOIN Album al ON ar.ArtistId = al.ArtistId "
            "GROUP BY ar.ArtistId, ar.Name "
            "ORDER BY ar.Name "
            "LIMIT 50"
        )
        rows = json.loads(result)
        if not rows:
            return "No artists found."
    return result


music_tools = [
    get_albums_by_artist,
    get_songs_by_artist,
    get_songs_by_genre,
    search_songs_by_title,
    get_track_details,
    list_genres,
    list_artists,
]
