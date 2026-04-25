from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import vlc

from .service import YouTubeService


class YTStreamVLC:
    """Small VLC wrapper that plays one YouTube track to completion."""

    def __init__(
        self,
        service: YouTubeService | None = None,
        poll_interval: float = 1.0,
    ):
        self.service = service or YouTubeService()
        self.poll_interval = poll_interval
        self.instance = vlc.Instance("--no-video")
        self.player = self.instance.media_player_new()

    def play_track(
        self,
        track: dict[str, Any],
        retry_on_error: bool = True,
        max_retries: int = 3,
        prefetched_stream_url: str | None = None,
        on_near_end: Callable[[], None] | None = None,
        near_end_seconds: int = 12,
    ) -> str:
        video_url = track.get("url")
        if not video_url:
            raise ValueError("Track must include a 'url'.")

        attempts = 0
        resume_position_ms = 0
        known_duration = track.get("duration")
        use_prefetched_stream = bool(prefetched_stream_url)

        while True:
            try:
                if use_prefetched_stream and prefetched_stream_url:
                    stream_url = prefetched_stream_url
                    use_prefetched_stream = False
                else:
                    stream_url, _duration = self.service.get_stream_info(video_url)
                self._start_stream(stream_url, resume_position_ms)
                return self._monitor_until_finished(
                    known_duration_seconds=known_duration,
                    on_near_end=on_near_end,
                    near_end_seconds=near_end_seconds,
                )
            except Exception:
                attempts += 1
                if not retry_on_error or attempts > max_retries:
                    raise
                resume_position_ms = max(self.player.get_time(), 0)
                time.sleep(1)

    def _start_stream(self, stream_url: str, resume_position_ms: int) -> None:
        media = self.instance.media_new(stream_url)
        self.player.set_media(media)
        self.player.play()
        time.sleep(1)
        if resume_position_ms > 0:
            self.player.set_time(resume_position_ms)

    def _monitor_until_finished(
        self,
        known_duration_seconds: int | None = None,
        on_near_end: Callable[[], None] | None = None,
        near_end_seconds: int = 12,
    ) -> str:
        near_end_triggered = False
        while True:
            state = self.player.get_state()
            if state == vlc.State.Ended:
                return "ended"
            if state == vlc.State.Stopped:
                return "stopped"
            if state == vlc.State.Error:
                raise RuntimeError("Playback error")

            if on_near_end and not near_end_triggered:
                current_time = self.player.get_time()
                duration_ms = self._resolve_duration_ms(known_duration_seconds)
                if duration_ms and current_time >= 0:
                    remaining_ms = duration_ms - current_time
                    if remaining_ms <= near_end_seconds * 1000:
                        near_end_triggered = True
                        on_near_end()

            time.sleep(self.poll_interval)

    def _resolve_duration_ms(self, known_duration_seconds: int | None) -> int | None:
        if known_duration_seconds and known_duration_seconds > 0:
            return known_duration_seconds * 1000

        live_length_ms = self.player.get_length()
        if live_length_ms and live_length_ms > 0:
            return live_length_ms
        return None

    def stop(self) -> None:
        self.player.stop()

    def toggle_pause(self) -> None:
        self.player.pause()

    def current_time_ms(self) -> int:
        return max(self.player.get_time(), 0)

    def total_length_ms(self) -> int:
        return max(self.player.get_length(), 0)
