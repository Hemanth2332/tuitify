from __future__ import annotations

import random
from typing import Any

from .utils import clean_tracks, parse_recommendations
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

    def fetch_next_from_seed(self, seed: dict[str, Any]) -> list[dict[str, Any]]:
        video_id = seed.get("id")
        if not video_id:
            return []

        try:
            data = self.service.fetch_recommendations(video_id)
        except Exception:
            return []

        recommendations = parse_recommendations(data, limit=self.recommendation_limit)
        recommendations = clean_tracks(recommendations)

        seen_ids = {track.get("id") for track in self.history}
        seen_ids.add(video_id)
        return [
            track for track in recommendations if track.get("id") and track["id"] not in seen_ids
        ]

    def choose_next(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None

        ranked = sorted(candidates, key=self._score_track, reverse=True)
        if random.random() < self.exploration_rate:
            return random.choice(ranked)
        return ranked[0]

    def next_track(self, seed: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if seed is None:
            if not self.history:
                return None
            seed = self.history[-1]

        candidates = self.fetch_next_from_seed(seed)
        next_song = self.choose_next(candidates)
        if next_song:
            self.queue.append(next_song)
        return next_song

    @staticmethod
    def _score_track(track: dict[str, Any]) -> float:
        score = random.random()
        duration = track.get("duration")
        if duration and 120 <= duration <= 320:
            score += 2.0
        return score
