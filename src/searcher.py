from __future__ import annotations

import yt_dlp


class YoutubeSearcher:
    def __init__(self, default_results: int = 10):
        self.default_results = default_results
        self.ydl_opts = {
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

    def search(self, query: str, num_results: int | None = None) -> list[dict]:
        count = num_results if num_results is not None else self.default_results
        search_query = f"ytsearch{count}:{query}"

        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            try:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries", [])
                return [entry for entry in entries if entry]
            except Exception as error:
                print(f"Search error: {error}")
                return []

    @staticmethod
    def _format_duration(total_seconds: int | None) -> str:
        if not total_seconds or total_seconds < 0:
            return "00:00"

        hours, rem = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(rem, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def search_media_details(self, query: str, num_results: int | None = None) -> list[dict]:
        entries = self.search(query=query, num_results=num_results)
        results: list[dict] = []

        for entry in entries:
            duration_seconds = entry.get("duration")
            artist_name = (
                entry.get("artist")
                or entry.get("uploader")
                or entry.get("channel")
                or entry.get("creator")
                or "Unknown artist"
            )

            results.append(
                {
                    "title": entry.get("title", "Unknown title"),
                    "thumbnail": entry.get("thumbnail"),
                    "url": entry.get("webpage_url"),
                    "total_play_time": self._format_duration(duration_seconds),
                    "artist_name": artist_name,
                }
            )

        return results


if __name__ == "__main__":
    searcher = YoutubeSearcher(default_results=10)
    results = searcher.search_media_details("music little light")

    for index, entry in enumerate(results, start=1):
        print(entry)
