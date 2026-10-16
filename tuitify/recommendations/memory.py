from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingEncoder


@dataclass(slots=True)
class MemoryMatch:
    song_id: str
    title: str
    artist: str
    similarity: float
    positive: bool
    played_at: datetime


@dataclass(slots=True)
class SongHistorySummary:
    play_count: int = 0
    skip_count: int = 0
    replay_count: int = 0
    last_played_at: datetime | None = None
    last_skipped_at: datetime | None = None


class RecommendationMemory:
    """SQLite-backed listening history and semantic memory store."""

    def __init__(
        self,
        database_path: str | Path,
        encoder: EmbeddingEncoder | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.encoder = encoder or EmbeddingEncoder()
        self._initialize_database()

    def store_event(
        self,
        track: dict[str, Any],
        completion: float,
        replay_count: int = 0,
        played_at: datetime | None = None,
        favorited: bool = False,
        skipped_after_seconds: int | None = None,
    ) -> bool:
        played_at = played_at or datetime.now(UTC)
        title = str(track.get("title") or "")
        artist = str(track.get("artist_name") or "")
        tags = track.get("tags") or []
        if isinstance(tags, list):
            tags_text = json.dumps([str(tag) for tag in tags], ensure_ascii=True)
        else:
            tags_text = json.dumps([str(tags)], ensure_ascii=True)

        classification = self._classify_event(
            completion=completion,
            replay_count=replay_count,
            favorited=favorited,
            skipped_after_seconds=skipped_after_seconds,
        )
        if classification is None:
            return False

        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO listening_history (
                    song_id,
                    title,
                    artist,
                    completion,
                    replay_count,
                    played_at,
                    tags,
                    positive
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(track.get("id") or ""),
                    title,
                    artist,
                    float(completion),
                    int(replay_count),
                    played_at.isoformat(),
                    tags_text,
                    1 if classification else 0,
                ),
            )

            embedding = self.encoder.encode_track(track)
            connection.execute(
                """
                INSERT INTO memory_embeddings (
                    song_id,
                    title,
                    artist,
                    embedding,
                    completion,
                    replay_count,
                    played_at,
                    positive
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(track.get("id") or ""),
                    title,
                    artist,
                    json.dumps(embedding),
                    float(completion),
                    int(replay_count),
                    played_at.isoformat(),
                    1 if classification else 0,
                ),
            )
            connection.commit()
        return True

    def similar_memories(
        self,
        track: dict[str, Any],
        positive: bool,
        limit: int = 5,
    ) -> list[MemoryMatch]:
        embedding = self.encoder.encode_track(track)

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT song_id, title, artist, embedding, played_at, positive
                FROM memory_embeddings
                WHERE positive = ?
                """,
                (1 if positive else 0,),
            ).fetchall()

        matches: list[MemoryMatch] = []
        for song_id, title, artist, raw_embedding, played_at, row_positive in rows:
            similarity = self.encoder.cosine_similarity(
                embedding,
                json.loads(raw_embedding),
            )
            matches.append(
                MemoryMatch(
                    song_id=str(song_id or ""),
                    title=str(title or ""),
                    artist=str(artist or ""),
                    similarity=similarity,
                    positive=bool(row_positive),
                    played_at=datetime.fromisoformat(str(played_at)),
                )
            )

        matches.sort(key=lambda item: item.similarity, reverse=True)
        return matches[:limit]

    def song_summary(
        self,
        track: dict[str, Any],
        *,
        now: datetime | None = None,
        recent_window: timedelta = timedelta(hours=24),
    ) -> SongHistorySummary:
        now = now or datetime.now(UTC)
        cutoff = now - recent_window
        song_id = str(track.get("id") or "")
        title = str(track.get("title") or "")
        artist = str(track.get("artist_name") or "")

        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT completion, replay_count, played_at, positive
                FROM listening_history
                WHERE
                    song_id = ?
                    OR (title = ? AND artist = ?)
                ORDER BY played_at DESC
                """,
                (song_id, title, artist),
            ).fetchall()

        summary = SongHistorySummary()
        for completion, replay_count, played_at_text, positive in rows:
            played_at = datetime.fromisoformat(str(played_at_text))
            if summary.last_played_at is None:
                summary.last_played_at = played_at
            if played_at < cutoff:
                continue

            summary.play_count += 1
            summary.replay_count += int(replay_count or 0)
            if not positive:
                summary.skip_count += 1
                if summary.last_skipped_at is None:
                    summary.last_skipped_at = played_at

        return summary

    def has_memories(self) -> bool:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM memory_embeddings"
            ).fetchone()
        return bool(row and row[0])

    def _initialize_database(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS listening_history (
                    id INTEGER PRIMARY KEY,
                    song_id TEXT,
                    title TEXT,
                    artist TEXT,
                    completion REAL,
                    replay_count INTEGER,
                    played_at TEXT,
                    tags TEXT,
                    positive INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id INTEGER PRIMARY KEY,
                    song_id TEXT,
                    title TEXT,
                    artist TEXT,
                    embedding TEXT,
                    completion REAL,
                    replay_count INTEGER,
                    played_at TEXT,
                    positive INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_song_id ON listening_history(song_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_positive ON memory_embeddings(positive)"
            )
            connection.commit()

    @staticmethod
    def _classify_event(
        *,
        completion: float,
        replay_count: int,
        favorited: bool,
        skipped_after_seconds: int | None,
    ) -> bool | None:
        if completion >= 0.8 or favorited or replay_count > 0:
            return True
        if skipped_after_seconds is not None and skipped_after_seconds <= 15:
            return False
        return None
