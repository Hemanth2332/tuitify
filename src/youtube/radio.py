from __future__ import annotations

import random
from typing import Any

from .utils import clean_tracks, normalize_title, parse_recommendations, track_signature
from .service import YouTubeService

class RadioEngine:
    """Manages queue + recommendation-based continuation."""

    def __init__(
        self,
        service: YouTubeService | None = None,
        history_limit: int = 20,
        recommendation_limit: int = 30,
        exploration_rate: float = 0.2,
    ):
        self.service = service or YouTubeService()
        self.history_limit = history_limit
        self.recommendation_limit = recommendation_limit
        self.exploration_rate = exploration_rate
        self.history: list[dict[str, Any]] = []
        self.queue: list[dict[str, Any]] = []

    def mark_played(self, track: dict[str, Any]) -> None:
        self.history.append(track)
        if len(self.history) > self.history_limit:
            self.history.pop(0)
        self.queue = [
            queued_track
            for queued_track in self.queue
            if track_signature(queued_track) != track_signature(track)
        ]

    def fetch_next_from_seed(self, seed: dict[str, Any]) -> list[dict[str, Any]]:
        video_id = seed.get("id")
        if not video_id:
            return []

        recommendations = self._fetch_related_recommendations(seed)
        recommendations = clean_tracks(recommendations)

        seen_ids = {track.get("id") for track in self.history}
        queued_ids = {
            track.get("id") for track in self.queue if track.get("id")
        }
        recent_signatures = {track_signature(track) for track in self.history}
        queued_signatures = {track_signature(track) for track in self.queue}
        seen_ids.add(video_id)
        recent_signatures.add(track_signature(seed))
        filtered = [
            track
            for track in recommendations
            if track.get("id")
            and track["id"] not in seen_ids
            and track["id"] not in queued_ids
            and track_signature(track) not in recent_signatures
            and track_signature(track) not in queued_signatures
        ]
        seed_title = normalize_title(str(seed.get("title") or ""))
        return [
            track
            for track in filtered
            if normalize_title(str(track.get("title") or "")) != seed_title
        ]

    def _fetch_related_recommendations(self, seed: dict[str, Any]) -> list[dict[str, Any]]:
        video_id = seed.get("id")
        if not video_id:
            return []

        related: list[dict[str, Any]] = []

        for query in self._build_related_queries(seed):
            try:
                related.extend(
                    self.service.search_songs(
                        query=query,
                        num_results=max(self.recommendation_limit // 2, 8),
                    )
                )
            except Exception:
                continue
            if len(related) >= self.recommendation_limit * 2:
                break

        try:
            data = self.service.fetch_recommendations(video_id)
        except Exception:
            data = None

        if data is not None:
            related.extend(
                parse_recommendations(data, limit=self.recommendation_limit)
            )

        return related

    def _build_related_queries(self, seed: dict[str, Any]) -> list[str]:
        artist_name = " ".join(str(seed.get("artist_name") or "").split())
        title = normalize_title(str(seed.get("title") or ""))
        album_name = " ".join(str(seed.get("album_name") or "").split())

        queries = [
            " ".join(part for part in (artist_name, title) if part).strip(),
            " ".join(part for part in (title, album_name) if part).strip(),
            title,
        ]

        seen: set[str] = set()
        unique_queries: list[str] = []
        for query in queries:
            normalized_query = " ".join(query.lower().split())
            if not normalized_query or normalized_query in seen:
                continue
            seen.add(normalized_query)
            unique_queries.append(query)

        return unique_queries

    def choose_next(
        self, candidates: list[dict[str, Any]], seed: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        if not candidates:
            return None

        related_tracks = candidates
        same_artist_related: list[dict[str, Any]] = []
        style_related: list[dict[str, Any]] = []

        if seed and related_tracks:
            seed_artist = str(seed.get("artist_name") or "").strip().lower()
            for track in related_tracks:
                track_artist = str(track.get("artist_name") or "").strip().lower()
                if seed_artist and track_artist == seed_artist:
                    same_artist_related.append(track)
                else:
                    style_related.append(track)
        else:
            style_related = related_tracks

        if style_related and same_artist_related:
            pool = style_related if random.random() < 0.2 else same_artist_related
        else:
            pool = style_related or same_artist_related or related_tracks or candidates
        ranked = sorted(
            pool,
            key=lambda track: self._score_track(track, seed=seed),
            reverse=True,
        )
        top_window = ranked[: min(10, len(ranked))]
        if random.random() < self.exploration_rate:
            return random.choice(ranked)
        return random.choice(top_window)

    def next_track(self, seed: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if seed is None:
            if not self.history:
                return None
            seed = self.history[-1]

        candidates = self.fetch_next_from_seed(seed)
        next_song = self.choose_next(candidates, seed=seed)
        if next_song:
            self.queue.append(next_song)
        return next_song

    @staticmethod
    def _score_track(track: dict[str, Any], seed: dict[str, Any] | None = None) -> float:
        score = random.random() * 3.0
        duration = track.get("duration")
        if duration and 120 <= duration <= 320:
            score += 1.0
        if track.get("source") == "ytmusic_song":
            score += 2.0
        if seed:
            seed_artist = str(seed.get("artist_name") or "").strip().lower()
            track_artist = str(track.get("artist_name") or "").strip().lower()
            if seed_artist and track_artist == seed_artist:
                score += 1.5
        return score
