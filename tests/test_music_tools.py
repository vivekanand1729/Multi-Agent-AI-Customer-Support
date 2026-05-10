"""Tests for the 5 music catalog tools."""
import json
import pytest

from src.db.database import get_engine
from src.tools.music_tools import (
    get_albums_by_artist,
    get_songs_by_artist,
    get_songs_by_genre,
    get_track_details,
    search_songs_by_title,
)


@pytest.fixture(scope="module", autouse=True)
def db():
    get_engine()


# ── get_albums_by_artist ──────────────────────────────────────────────────────

class TestGetAlbumsByArtist:
    def test_found_acdc(self):
        result = get_albums_by_artist.invoke({"artist_name": "AC/DC"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_result_has_expected_fields(self):
        result = get_albums_by_artist.invoke({"artist_name": "AC/DC"})
        rows = json.loads(result)
        assert "AlbumTitle" in rows[0]
        assert "ArtistName" in rows[0]

    def test_not_found_returns_message(self):
        result = get_albums_by_artist.invoke({"artist_name": "NonExistentArtistXYZ123"})
        assert isinstance(result, str)
        assert "No albums found" in result

    def test_fuzzy_matching(self):
        # Partial name
        result = get_albums_by_artist.invoke({"artist_name": "Beatles"})
        assert isinstance(result, str)

    def test_valid_json_on_found(self):
        result = get_albums_by_artist.invoke({"artist_name": "Metallica"})
        rows = json.loads(result)
        assert isinstance(rows, list)


# ── get_songs_by_artist ───────────────────────────────────────────────────────

class TestGetSongsByArtist:
    def test_found_returns_count_and_sample(self):
        result = get_songs_by_artist.invoke({"artist_name": "AC/DC"})
        data = json.loads(result)
        assert "total_count" in data
        assert "sample" in data
        assert data["total_count"] > 0
        assert isinstance(data["sample"], list)

    def test_sample_max_20(self):
        result = get_songs_by_artist.invoke({"artist_name": "AC/DC"})
        data = json.loads(result)
        assert len(data["sample"]) <= 20

    def test_not_found_returns_message(self):
        result = get_songs_by_artist.invoke({"artist_name": "UnknownBandXYZ999"})
        assert "No songs found" in result

    def test_valid_json_on_found(self):
        result = get_songs_by_artist.invoke({"artist_name": "Metallica"})
        data = json.loads(result)
        assert isinstance(data, dict)


# ── get_songs_by_genre ────────────────────────────────────────────────────────

class TestGetSongsByGenre:
    def test_found_rock(self):
        result = get_songs_by_genre.invoke({"genre_name": "Rock"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_max_10_results(self):
        result = get_songs_by_genre.invoke({"genre_name": "Rock"})
        rows = json.loads(result)
        assert len(rows) <= 10

    def test_diversity_one_track_per_artist(self):
        result = get_songs_by_genre.invoke({"genre_name": "Rock"})
        rows = json.loads(result)
        artists = [r["ArtistName"] for r in rows]
        # All artist names should be unique (one track per artist)
        assert len(artists) == len(set(artists)), "Duplicate artists in genre sample"

    def test_determinism_same_results(self):
        result1 = get_songs_by_genre.invoke({"genre_name": "Jazz"})
        result2 = get_songs_by_genre.invoke({"genre_name": "Jazz"})
        assert result1 == result2

    def test_not_found_returns_message(self):
        result = get_songs_by_genre.invoke({"genre_name": "GenreXYZ999"})
        assert "No songs found" in result

    def test_valid_json_on_found(self):
        result = get_songs_by_genre.invoke({"genre_name": "Jazz"})
        rows = json.loads(result)
        assert isinstance(rows, list)


# ── search_songs_by_title ─────────────────────────────────────────────────────

class TestSearchSongsByTitle:
    def test_found_results(self):
        result = search_songs_by_title.invoke({"title": "Love"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_max_10_results(self):
        result = search_songs_by_title.invoke({"title": "the"})
        rows = json.loads(result)
        assert len(rows) <= 10

    def test_not_found_returns_message(self):
        result = search_songs_by_title.invoke({"title": "xyzabc999totally_unique"})
        assert "No songs found" in result

    def test_valid_json_on_found(self):
        result = search_songs_by_title.invoke({"title": "Rock"})
        rows = json.loads(result)
        assert isinstance(rows, list)


# ── get_track_details ─────────────────────────────────────────────────────────

class TestGetTrackDetails:
    def test_found_track_1(self):
        result = get_track_details.invoke({"track_id": "1"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0]["TrackId"] == 1

    def test_result_has_full_fields(self):
        result = get_track_details.invoke({"track_id": "1"})
        rows = json.loads(result)
        track = rows[0]
        for field in ["TrackId", "TrackName", "Artist", "Album", "Genre", "UnitPrice"]:
            assert field in track

    def test_not_found_returns_message(self):
        result = get_track_details.invoke({"track_id": "999999"})
        assert "No track found" in result

    def test_invalid_id_returns_error(self):
        result = get_track_details.invoke({"track_id": "abc"})
        assert "Invalid" in result

    def test_valid_json_on_found(self):
        result = get_track_details.invoke({"track_id": "100"})
        rows = json.loads(result)
        assert isinstance(rows, list)
