from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .memory import SongHistorySummary


@dataclass(slots=True)
class ScoreBreakdown:
    youtube_score: float
    similarity_bonus: float
    negative_penalty: float
    recently_played_penalty: float
    recently_skipped_penalty: float
    final_score: float


class RecommendationScorer:
    """Combines candidate rank, memory similarity, and recency penalties."""

    def __init__(
        self,
        positive_weight: float = 1.2,
        negative_weight: float = 0.9,
        recent_play_window: timedelta = timedelta(minutes=30),
        recent_skip_window: timedelta = timedelta(hours=12),
    ) -> None:
        self.positive_weight = positive_weight
        self.negative_weight = negative_weight
        self.recent_play_window = recent_play_window
        self.recent_skip_window = recent_skip_window

    def score(
        self,
        *,
        youtube_score: float,
        positive_similarity: float,
        negative_similarity: float,
        history: SongHistorySummary,
        now: datetime | None = None,
    ) -> ScoreBreakdown:
        now = now or datetime.now(UTC)

        similarity_bonus = positive_similarity * self.positive_weight
        negative_penalty = negative_similarity * self.negative_weight

        recently_played_penalty = 0.0
        if history.last_played_at is not None:
            age = now - history.last_played_at
            if age <= self.recent_play_window:
                recently_played_penalty = 0.4 + min(history.play_count, 3) * 0.2

        recently_skipped_penalty = 0.0
        if history.last_skipped_at is not None:
            age = now - history.last_skipped_at
            if age <= self.recent_skip_window:
                recently_skipped_penalty = 0.5 + min(history.skip_count, 3) * 0.25

        final_score = (
            youtube_score
            + similarity_bonus
            - negative_penalty
            - recently_played_penalty
            - recently_skipped_penalty
        )

        return ScoreBreakdown(
            youtube_score=youtube_score,
            similarity_bonus=similarity_bonus,
            negative_penalty=negative_penalty,
            recently_played_penalty=recently_played_penalty,
            recently_skipped_penalty=recently_skipped_penalty,
            final_score=final_score,
        )
