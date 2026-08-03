from __future__ import annotations

import random
from typing import Any

from .utils import (
    clean_tracks,
    normalize_title,
    parse_recommendations,
    title_token_set,
    track_signature,
)
from .service import YouTubeService

class RadioEngine:
    """Manages queue + recommendation-based continuation."""

    def __init__(
        self,
        service: YouTubeService | None = None,
        history_limit: int = 80,
        recommendation_limit: int = 60,
        exploration_rate: float = 0.15,
        artist_cooldown: int = 3,
        title_cooldown: int = 25,
        album_cooldown: int = 2,
    ):
        self.service = service or YouTubeService()
        self.history_limit = history_limit
        self.recommendation_limit = recommendation_limit
        self.exploration_rate = exploration_rate
        self.artist_cooldown = artist_cooldown
        self.title_cooldown = title_cooldown
        self.album_cooldown = album_cooldown
        self.history: list[dict[str, Any]] = []
        self.queue: list[dict[str, Any]] = []

    def mark_played(self, track: dict[str, Any]) -> None:
        if self.history and track_signature(self.history[-1]) == track_signature(track):
            return
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
        title = " ".join(str(seed.get("title") or "").split())
        
        recent_artists = [
            self._artist_key(track)
            for track in reversed(self.history[-5:])
            if self._artist_key(track)
        ]
        session_artist = next(
            (artist for artist in recent_artists if artist and artist != artist_name.lower()),
            "",
        )

        queries = []
        if artist_name:
            queries.extend([
                f"{artist_name} tracks",
                f"{artist_name} radio",
            ])
            if session_artist:
                queries.append(f"{artist_name} {session_artist}")
        elif title:
            queries.append(f"{title} similar songs")

        tags = seed.get("tags") or []
        useful_tags = [
            t for t in tags
            if len(t) > 3
            and t.lower() not in ("music", "video", "audio", "official", "lyric", "lyrics", "cover", "song")
            and artist_name.lower() not in t.lower()
        ]
        if useful_tags:
            import random
            selected = random.sample(useful_tags, min(2, len(useful_tags)))
            for tag in selected:
                queries.append(f"{tag} music")

        seen: set[str] = set()
        unique_queries: list[str] = []
        for query in queries:
            normalized_query = " ".join(query.lower().split())
            if not normalized_query or normalized_query in seen:
                continue
            seen.add(normalized_query)
            unique_queries.append(query)

        return unique_queries

    def build_queue(
        self, seed: dict[str, Any], limit: int = 10
    ) -> list[dict[str, Any]]:
        candidates = self.fetch_next_from_seed(seed)
        if not candidates:
            return []

        planned: list[dict[str, Any]] = []
        available = list(candidates)
        while available and len(planned) < limit:
            ranked = sorted(
                available,
                key=lambda track: self._score_track(track, seed=seed, upcoming=planned),
                reverse=True,
            )
            selection_window = ranked[: min(5, len(ranked))]
            if random.random() < self.exploration_rate:
                next_track = random.choice(ranked[: min(12, len(ranked))])
            else:
                next_track = random.choice(selection_window)
            planned.append(next_track)
            selected_signature = track_signature(next_track)
            available = [
                track
                for track in available
                if track_signature(track) != selected_signature
            ]

        self.queue = list(planned)
        return planned

    def choose_next(
        self, candidates: list[dict[str, Any]], seed: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        if not candidates:
            return None
        ranked = sorted(
            candidates,
            key=lambda track: self._score_track(track, seed=seed),
            reverse=True,
        )
        top_window = ranked[: min(5, len(ranked))]
        if random.random() < self.exploration_rate:
            return random.choice(ranked[: min(12, len(ranked))])
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
    def _artist_key(track: dict[str, Any]) -> str:
        return str(track.get("artist_name") or "").strip().lower()

    @staticmethod
    def _album_key(track: dict[str, Any]) -> str:
        return " ".join(str(track.get("album_name") or "").split()).strip().lower()

    def _score_track(
        self,
        track: dict[str, Any],
        seed: dict[str, Any] | None = None,
        upcoming: list[dict[str, Any]] | None = None,
    ) -> float:
        score = random.random() * 3.0
        duration = track.get("duration")
        if duration and 120 <= duration <= 320:
            score += 1.0
        if track.get("source") == "ytmusic_song":
            score += 2.0

        if seed:
            seed_artist = self._artist_key(seed)
            track_artist = self._artist_key(track)
            if seed_artist and track_artist == seed_artist:
                score += 0.35

            seed_album = self._album_key(seed)
            track_album = self._album_key(track)
            if seed_album and track_album and seed_album == track_album:
                score += 0.5

            seed_title_tokens = title_token_set(str(seed.get("title") or ""))
            track_title_tokens = title_token_set(str(track.get("title") or ""))
            if seed_title_tokens and track_title_tokens:
                overlap = len(seed_title_tokens & track_title_tokens)
                if overlap >= max(2, min(len(seed_title_tokens), len(track_title_tokens))):
                    score -= 3.25
                elif overlap:
                    score -= overlap * 0.6

        recent_history = self.history[-self.title_cooldown :]
        recent_artists = {
            self._artist_key(item)
            for item in recent_history[-self.artist_cooldown :]
            if self._artist_key(item)
        }
        recent_titles = {
            normalize_title(str(item.get("title") or ""))
            for item in recent_history
        }
        recent_albums = {
            self._album_key(item)
            for item in recent_history[-self.album_cooldown :]
            if self._album_key(item)
        }

        track_artist = self._artist_key(track)
        track_title = normalize_title(str(track.get("title") or ""))
        track_album = self._album_key(track)

        if track_artist and track_artist in recent_artists:
            score -= 4.25
        if track_title and track_title in recent_titles:
            score -= 6.0
        if track_album and track_album in recent_albums:
            score -= 2.25

        if upcoming:
            queued_artists = {
                self._artist_key(item)
                for item in upcoming[-self.artist_cooldown :]
                if self._artist_key(item)
            }
            queued_titles = {
                normalize_title(str(item.get("title") or ""))
                for item in upcoming
            }
            if track_artist and track_artist in queued_artists:
                score -= 3.0
            if track_title and track_title in queued_titles:
                score -= 7.0

            if upcoming and track_artist:
                last_planned_artist = self._artist_key(upcoming[-1])
                if last_planned_artist == track_artist:
                    score -= 3.0

        return score

