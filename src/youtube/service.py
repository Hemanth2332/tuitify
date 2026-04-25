from __future__ import annotations

from typing import Any

import requests
import yt_dlp


YOUTUBE_NEXT_API = "https://www.youtube.com/youtubei/v1/next"


class YouTubeService:
    """Central place for YouTube search, stream, and recommendations."""

    def __init__(self, default_results: int = 30):
        self.default_results = default_results
        self._ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android"],
                }
            },
        }

    def search(self, query: str, num_results: int | None = None) -> list[dict[str, Any]]:
        count = num_results if num_results is not None else self.default_results
        search_query = f"ytsearch{count}:{query}"

        with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get("entries", [])
            return [entry for entry in entries if entry]

    def search_media_details(
        self, query: str, num_results: int | None = None
    ) -> list[dict[str, Any]]:
        entries = self.search(query=query, num_results=num_results)
        return [self._to_media_detail(entry) for entry in entries]

    def get_stream_info(self, video_url: str) -> tuple[str, int | None]:
        with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info["url"], info.get("duration")

    def fetch_recommendations(
        self, video_id: str, timeout: int = 20
    ) -> dict[str, Any]:
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                }
            },
            "videoId": video_id,
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            YOUTUBE_NEXT_API,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _to_media_detail(entry: dict[str, Any]) -> dict[str, Any]:
        duration_seconds = entry.get("duration")
        artist_name = (
            entry.get("artist")
            or entry.get("uploader")
            or entry.get("channel")
            or entry.get("creator")
            or "Unknown artist"
        )
        video_id = entry.get("id") or entry.get("video_id")
        url = entry.get("webpage_url")

        return {
            "id": video_id,
            "title": entry.get("title", "Unknown title"),
            "thumbnail": entry.get("thumbnail"),
            "url": url,
            "total_play_time": YouTubeService._format_duration(duration_seconds),
            "duration": duration_seconds,
            "artist_name": artist_name,
        }

    @staticmethod
    def _format_duration(total_seconds: int | None) -> str:
        if not total_seconds or total_seconds < 0:
            return "00:00"

        hours, rem = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(rem, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
