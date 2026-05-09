from __future__ import annotations

from typing import Any

import requests
import yt_dlp


YOUTUBE_NEXT_API = "https://www.youtube.com/youtubei/v1/next"
YTMUSIC_SEARCH_API = "https://music.youtube.com/youtubei/v1/search"
YTMUSIC_CLIENT = {
    "clientName": "WEB_REMIX",
    "clientVersion": "1.20240101.01.00",
}
YTMUSIC_SONG_FILTER = "EgWKAQIIAWoKEAkQBRAKEAMQBA%3D%3D"


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

    def search_songs(self, query: str, num_results: int | None = None) -> list[dict[str, Any]]:
        count = num_results if num_results is not None else self.default_results
        payload = {
            "context": {"client": YTMUSIC_CLIENT},
            "query": query,
            "params": YTMUSIC_SONG_FILTER,
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            YTMUSIC_SEARCH_API,
            json=payload,
            headers=headers,
            params={"prettyPrint": "false"},
            timeout=20,
        )
        response.raise_for_status()
        return self._parse_song_search_results(response.json(), limit=count)

    def search_media_details(
        self,
        query: str,
        num_results: int | None = None,
        media_type: str = "music",
    ) -> list[dict[str, Any]]:
        if media_type == "music":
            return self.search_songs(query=query, num_results=num_results)

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
    def _parse_song_search_results(
        data: dict[str, Any], limit: int
    ) -> list[dict[str, Any]]:
        contents = (
            data.get("contents", {})
            .get("tabbedSearchResultsRenderer", {})
            .get("tabs", [])
        )
        if not contents:
            return []

        sections = (
            contents[0]
            .get("tabRenderer", {})
            .get("content", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        if not sections:
            return []

        items = (
            sections[-1]
            .get("musicShelfRenderer", {})
            .get("contents", [])
        )

        results: list[dict[str, Any]] = []
        for item in items:
            renderer = item.get("musicResponsiveListItemRenderer", {})
            track = YouTubeService._parse_ytmusic_song_item(renderer)
            if not track:
                continue
            results.append(track)
            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _parse_ytmusic_song_item(
        renderer: dict[str, Any],
    ) -> dict[str, Any] | None:
        video_id = (
            renderer.get("playlistItemData", {}).get("videoId")
            or renderer.get("overlay", {})
            .get("musicItemThumbnailOverlayRenderer", {})
            .get("content", {})
            .get("musicPlayButtonRenderer", {})
            .get("playNavigationEndpoint", {})
            .get("watchEndpoint", {})
            .get("videoId")
        )
        if not video_id:
            return None

        flex_columns = renderer.get("flexColumns", [])
        if len(flex_columns) < 2:
            return None

        title_runs = (
            flex_columns[0]
            .get("musicResponsiveListItemFlexColumnRenderer", {})
            .get("text", {})
            .get("runs", [])
        )
        title = "".join(run.get("text", "") for run in title_runs).strip()
        if not title:
            return None

        meta_runs = (
            flex_columns[1]
            .get("musicResponsiveListItemFlexColumnRenderer", {})
            .get("text", {})
            .get("runs", [])
        )
        meta_parts = [
            run.get("text", "").strip()
            for run in meta_runs
            if run.get("text", "").strip() and run.get("text", "").strip() != "•"
        ]

        artist_name = meta_parts[0] if meta_parts else "Unknown artist"
        album_name = meta_parts[1] if len(meta_parts) > 2 else None
        duration_text = meta_parts[-1] if meta_parts else None
        duration_seconds = YouTubeService._parse_duration_text(duration_text)

        thumbnails = (
            renderer.get("thumbnail", {})
            .get("musicThumbnailRenderer", {})
            .get("thumbnail", {})
            .get("thumbnails", [])
        )
        thumbnail = thumbnails[-1].get("url") if thumbnails else None

        return {
            "id": video_id,
            "title": title,
            "thumbnail": thumbnail,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "total_play_time": YouTubeService._format_duration(duration_seconds),
            "duration": duration_seconds,
            "artist_name": artist_name,
            "album_name": album_name,
            "source": "ytmusic_song",
        }

    @staticmethod
    def _parse_duration_text(text: str | None) -> int | None:
        if not text:
            return None

        parts = text.split(":")
        if not all(part.isdigit() for part in parts):
            return None

        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return total

    @staticmethod
    def _format_duration(total_seconds: int | None) -> str:
        if not total_seconds or total_seconds < 0:
            return "00:00"

        hours, rem = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(rem, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
