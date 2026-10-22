from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tuitify.youtube.utils import normalize_artist_name, title_token_set

from .embeddings import EmbeddingEncoder
from .memory import RecommendationMemory
from .scorer import RecommendationScorer


class PersonalizedRecommender:
    """Reranks YouTube Radio candidates using local listening memories."""

    def __init__(
        self,
        database_path: str | Path,
        encoder: EmbeddingEncoder | None = None,
        memory: RecommendationMemory | None = None,
        scorer: RecommendationScorer | None = None,
    ) -> None:
        self.encoder = encoder or EmbeddingEncoder(onnx_model=False)
        self.memory = memory or RecommendationMemory(database_path, encoder=self.encoder)
        self.scorer = scorer or RecommendationScorer()

    def rank_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if not self.memory.has_memories():
            return list(candidates)

        total = len(candidates)
        ranked: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        for index, candidate in enumerate(candidates):
            youtube_score = 0.6 - (index / max(total, 1)) * 0.3

            positive_matches = self.memory.similar_memories(candidate, positive=True, limit=5)
            negative_matches = self.memory.similar_memories(candidate, positive=False, limit=5)

            positive_similarity = max(
                self._average_similarity(positive_matches),
                self._metadata_similarity(candidate, positive_matches),
            )
            negative_similarity = max(
                self._average_similarity(negative_matches),
                self._metadata_similarity(candidate, negative_matches),
            )
            history = self.memory.song_summary(candidate, now=now)
            breakdown = self.scorer.score(
                youtube_score=youtube_score,
                positive_similarity=positive_similarity,
                negative_similarity=negative_similarity,
                history=history,
                now=now,
            )

            enriched = dict(candidate)
            enriched["youtube_score"] = youtube_score
            enriched["positive_similarity"] = positive_similarity
            enriched["negative_similarity"] = negative_similarity
            enriched["recommendation_score"] = breakdown.final_score
            enriched["recommendation_breakdown"] = {
                "youtube_score": breakdown.youtube_score,
                "similarity_bonus": breakdown.similarity_bonus,
                "negative_penalty": breakdown.negative_penalty,
                "recently_played_penalty": breakdown.recently_played_penalty,
                "recently_skipped_penalty": breakdown.recently_skipped_penalty,
            }
            ranked.append(enriched)

        ranked.sort(
            key=lambda track: (
                float(track.get("recommendation_score") or 0.0),
                float(track.get("youtube_score") or 0.0),
            ),
            reverse=True,
        )
        return ranked

    def record_playback_event(
        self,
        track: dict[str, Any],
        *,
        completion: float,
        replay_count: int = 0,
        favorited: bool = False,
        skipped_after_seconds: int | None = None,
        played_at: datetime | None = None,
    ) -> bool:
        return self.memory.store_event(
            track,
            completion=completion,
            replay_count=replay_count,
            favorited=favorited,
            skipped_after_seconds=skipped_after_seconds,
            played_at=played_at,
        )

    @staticmethod
    def _average_similarity(matches: list[Any]) -> float:
        if not matches:
            return 0.0
        return sum(float(match.similarity) for match in matches) / len(matches)

    @staticmethod
    def _metadata_similarity(
        candidate: dict[str, Any],
        matches: list[Any],
    ) -> float:
        if not matches:
            return 0.0

        candidate_artist = normalize_artist_name(candidate.get("artist_name"))
        candidate_title_tokens = title_token_set(str(candidate.get("title") or ""))
        best = 0.0

        for match in matches:
            score = 0.0
            if candidate_artist and normalize_artist_name(match.artist) == candidate_artist:
                score += 0.95

            memory_title_tokens = title_token_set(match.title)
            if candidate_title_tokens and memory_title_tokens:
                overlap = len(candidate_title_tokens & memory_title_tokens)
                score += overlap / max(len(candidate_title_tokens | memory_title_tokens), 1)

            best = max(best, score)

        return min(best, 1.0)
