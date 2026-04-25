from __future__ import annotations

from typing import Any

from src.youtube.service import YouTubeService


class YoutubeSearcher:
    """Search-focused wrapper used by CLI and UI layers."""

    def __init__(self, default_results: int = 30):
        self._service = YouTubeService(default_results=default_results)

    def search(self, query: str, num_results: int | None = None) -> list[dict[str, Any]]:
        return self._service.search(query=query, num_results=num_results)

    def search_media_details(
        self, query: str, num_results: int | None = None
    ) -> list[dict[str, Any]]:
        return self._service.search_media_details(query=query, num_results=num_results)
