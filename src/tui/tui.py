from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any

import requests
from textual import work
from textual.widgets import ListItem
from textual.app import App
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, HorizontalScroll
from textual.widgets import Footer, Header, Input, ListView, ProgressBar, Select, Static
from textual_image.widget import Image
from rich.text import Text

from src.youtube.radio import RadioEngine
from src.search.searcher import YoutubeSearcher
from src.youtube.player import YTStreamVLC

from .keybindings import BINDINGS

class Tuitify(App):

    BINDINGS = BINDINGS

    CSS_PATH = "styles.tcss"
    THEME_SETTINGS_PATH = Path(__file__).with_name("settings.json")

    def __init__(self) -> None:
        super().__init__()

        self.searcher = YoutubeSearcher(default_results=20)
        self.player = YTStreamVLC()
        self.radio = RadioEngine()

        self.search_results: list[dict[str, Any]] = []
        self.recommendation_queue: list[dict[str, Any]] = []
        self.recommendation_urls: list[str] = []
        self.current_track: dict[str, Any] | None = None
        self.current_duration_seconds: int = 0
        self.playback_nonce = 0
        self.search_in_progress = False
        self.search_cache: dict[str, list[dict[str, Any]]] = {}
        self.theme_names: list[str] = []


    def compose(self):
        yield Header(name="Tuitify", show_clock=True)

        with Vertical(id="main-layout"):
            with Horizontal(id="top-panels"):
                # Search Panel
                with VerticalScroll(id="search-panel", classes="panel"):
                    with Horizontal(id="search-controls"):
                        yield Select(
                            options=[("Music", "music"), ("Podcast", "podcast")],
                            value="music",
                            id="media-select",
                        )

                        yield Input(
                            placeholder="Search and press Enter",
                            id="search-input",
                        )
                    with HorizontalScroll(classes="search-results-shell"):
                        yield ListView(id="search-results", classes="search-results")

                # Player Panel
                with Vertical(id="player-panel", classes="panel"):
                    yield Static("Player")

                    with Container(id="art-frame", classes="art-frame"):
                        yield Image(id="album-art")

                    yield Static("Title", id="title")
                    yield Static("Artist", id="artist")
                    yield ProgressBar(total=100, id="progress")
                    
                    yield Static("0:00 / 0:00", id="time")
                    yield Static("Next Up: -", id="next-up")

        yield Footer()

    def on_mount(self) -> None:
        self._initialize_themes()
        self._restore_theme()
        self.set_interval(0.5, self._refresh_player_progress)
        self.action_focus_input()

    # Key Bindings
    def action_quit(self) -> None:
        self.playback_nonce += 1
        self.current_track = None
        self.recommendation_queue.clear()
        self.recommendation_urls = []
        self.player.stop()
        self._update_next_up_ui()
        self.exit()

    def action_toggle_pause(self) -> None:
        if not self.current_track:
            return
        self.player.toggle_pause()

    def action_next_track(self) -> None:
        if not self.current_track:
            return

        next_track = self._pop_recommendation()
        if not next_track:
            self.notify("No next recommendation ready.", severity="warning")
            return

        self.start_playback(next_track)

    def action_seek_backward(self) -> None:
        if self.query_one("#search-input", Input).has_focus:
            return
        self._seek_relative_ms(-10_000)

    def action_seek_forward(self) -> None:
        if self.query_one("#search-input", Input).has_focus:
            return
        self._seek_relative_ms(10_000)

    def action_focus_input(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cycle_theme(self) -> None:
        if not self.theme_names:
            self.notify("No themes available.", severity="warning")
            return

        current_theme = str(self.theme or "")
        if current_theme in self.theme_names:
            current_index = self.theme_names.index(current_theme)
            next_index = (current_index + 1) % len(self.theme_names)
        else:
            next_index = 0

        next_theme = self.theme_names[next_index]
        self.theme = next_theme
        self._save_theme(next_theme)
        self.notify(f"Theme: {next_theme}", severity="information")

    def action_cursor_up(self) -> None:
        if self.query_one("#search-input", Input).has_focus:
            return
        list_view = self.query_one("#search-results", ListView)
        if not list_view.children:
            return
        if not list_view.has_focus:
            list_view.focus()
        if list_view.index is None:
            list_view.index = 0
            return
        list_view.action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.query_one("#search-input", Input).has_focus:
            return
        list_view = self.query_one("#search-results", ListView)
        if not list_view.children:
            return
        if not list_view.has_focus:
            list_view.focus()
        if list_view.index is None:
            list_view.index = 0
            return
        list_view.action_cursor_down()



    # Player functions
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.action_search()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "search-results":
            return

        if event.index is None:
            return

        track = self._safe_get(self.search_results, event.index)
        if track:
            self.start_playback(track)

    # Search function
    def action_search(self):
        if self.search_in_progress:
            self.notify("Search already in progress...", severity="warning")
            return

        query = self.query_one("#search-input", Input).value

        if not query.strip():
            self.notify("Enter a query", "warning")
            return

        mode = str(self.query_one("#media-select", Select).value or "music").lower()
        prefix = "music" if mode == "music" else "podcast"
        full_query = f"{prefix} {query}".strip()
        cache_key = " ".join(full_query.lower().split())

        cached_results = self.search_cache.get(cache_key)
        if cached_results is not None:
            self.search_results = cached_results
            self.render_search_results()
            self.query_one("#search-results", ListView).focus()
            self.notify(
                f"Loaded {len(cached_results)} cached results",
                severity="information",
            )
            return

        self._run_search(full_query)

    @work(exclusive=True, thread=True, group="search")
    def _run_search(self, query: str) -> None:
        self.search_in_progress = True
        self.call_from_thread(self._set_search_loading, True)
        started_at = time.perf_counter()
        try:
            results = self.searcher.search_media_details(query)
        except Exception as error:
            self.call_from_thread(
                self.notify, f"Search failed: {error}", severity="error"
            )
            results = []

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        self.call_from_thread(self._set_search_results, query, results, elapsed_ms)
        self.search_in_progress = False

    def _set_search_loading(self, is_loading: bool) -> None:
        results_view = self.query_one("#search-results", ListView)
        media_type = "Music" if str(self.query_one("#media-select", Select).value) == "music" else "Podcast"

        if is_loading:
            results_view.clear()
            results_view.append(
                ListItem(
                    Static(
                        f"Searching {media_type.lower()} ... please wait",
                        classes="result-line",
                    )
                )
            )
        else:
            results_view.clear()

    def _set_search_results(
        self, query: str, results: list[dict[str, Any]], elapsed_ms: int
    ) -> None:
        self._set_search_loading(False)
        self.search_results = results
        cache_key = " ".join(query.lower().split())
        self.search_cache[cache_key] = results
        if len(self.search_cache) > 30:
            oldest_key = next(iter(self.search_cache))
            self.search_cache.pop(oldest_key, None)
        self.render_search_results()
        self.query_one("#search-results", ListView).focus()
        self.notify(
            f"Loaded {len(results)} results in {elapsed_ms} ms",
            severity="information",
        )

    def render_search_results(self):
        results_view = self.query_one("#search-results", ListView)
        results_view.clear()
        title_width = 44
        channel_width = 28

        for idx, track in enumerate(self.search_results, start=1):
            title = str(track.get("title", "Unknown Title"))
            channel = str(
                track.get("artist_name")
                or track.get("channel")
                or track.get("uploader")
                or track.get("creator")
                or ""
            )

            duration = track.get("duration")
            if duration:
                duration_str = str(track.get("total_play_time") or "00:00")
            else:
                duration_str = "LIVE"

            display_title = title if len(title) <= title_width else title[: title_width - 3] + "..."
            display_channel = (
                channel if len(channel) <= channel_width else channel[: channel_width - 3] + "..."
            )

            line = Text()
            line.append(f"{idx:>2}  ", style="bold #56B6C6")
            line.append(f"{display_title:<{title_width}}", style="bold")
            line.append("  | ", style="dim")
            line.append(f"{display_channel:<{channel_width}}", style="dim")
            line.append("  | ", style="dim")
            line.append(duration_str, style="bold #98C379")

            list_item = ListItem(
                Static(
                    line,
                    classes="result-line",
                    expand=False,
                )
            )
            results_view.append(list_item)

        if results_view.children:
            results_view.index = 0

    def start_playback(self, track: dict[str, Any]) -> None:
        self.playback_nonce += 1
        nonce = self.playback_nonce
        self.player.stop()
        self._playback_session(nonce, track)

    @work(exclusive=True, thread=True, group="playback")
    def _playback_session(self, nonce: int, track: dict[str, Any]) -> None:
        current_track = track

        while nonce == self.playback_nonce:
            self.call_from_thread(self._set_current_track, current_track)
            self._seed_recommendations(current_track, limit=10)

            try:
                end_state = self.player.play_track(current_track, retry_on_error=True)
            except Exception as error:
                self.call_from_thread(
                    self.notify, f"Playback failed: {error}", severity="error"
                )
                return

            if nonce != self.playback_nonce:
                return

            if end_state != "ended":
                return

            self.radio.mark_played(current_track)
            next_track = self._pop_recommendation()
            if not next_track:
                next_track = self.radio.next_track(seed=current_track)

            if not next_track:
                return

            current_track = next_track

    def _set_current_track(self, track: dict[str, Any]) -> None:
        self.current_track = track
        self.current_duration_seconds = int(track.get("duration") or 0)

        self.query_one("#title", Static).update(str(track.get("title", "Unknown title")))
        self.query_one("#artist", Static).update(str(track.get("artist_name") or "-"))
        total_time = (
            "LIVE"
            if not track.get("duration")
            else str(track.get("total_play_time") or "0:00")
        )
        self.query_one("#time", Static).update(f"0:00 / {total_time}")

        thumbnail_url = track.get("thumbnail")
        if thumbnail_url:
            self._load_artwork(str(thumbnail_url))
        else:
            self._set_artwork(None)
        self._update_next_up_ui()

    @work(exclusive=True, thread=True, group="artwork")
    def _load_artwork(self, image_url: str) -> None:
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
        except Exception:
            image_data = None

        self.call_from_thread(self._set_artwork, image_data)

    def _set_artwork(self, image_data: io.BytesIO | None) -> None:
        self.query_one("#album-art", Image).image = image_data

    def _seed_recommendations(self, seed_track: dict[str, Any], limit: int = 10) -> None:
        candidates = self.radio.fetch_next_from_seed(seed_track)
        seeded: list[dict[str, Any]] = []

        for candidate in candidates:
            if len(seeded) >= limit:
                break

            duration_seconds = int(candidate.get("duration") or 0)
            if duration_seconds < 120:
                continue

            candidate_url = candidate.get("url")
            if not candidate_url:
                candidate_id = candidate.get("id")
                if not candidate_id:
                    continue
                candidate_url = f"https://www.youtube.com/watch?v={candidate_id}"
                candidate["url"] = candidate_url
            candidate_id = str(candidate.get("id") or "")
            if candidate_id and not candidate.get("thumbnail"):
                candidate["thumbnail"] = f"https://i.ytimg.com/vi/{candidate_id}/hqdefault.jpg"

            if not candidate.get("total_play_time"):
                candidate["total_play_time"] = self._format_seconds(duration_seconds)
            if not candidate.get("artist_name"):
                candidate["artist_name"] = "Recommended"

            seeded.append(candidate)

        self.recommendation_queue = seeded
        self.recommendation_urls = [str(track.get("url", "")) for track in seeded]
        self.call_from_thread(self._update_next_up_ui)

    def _pop_recommendation(self) -> dict[str, Any] | None:
        if not self.recommendation_queue:
            return None

        next_track = self.recommendation_queue.pop(0)
        self.recommendation_urls = [str(track.get("url", "")) for track in self.recommendation_queue]
        return next_track

    def _update_next_up_ui(self) -> None:
        next_up_widget = self.query_one("#next-up", Static)
        if not self.recommendation_queue:
            next_up_widget.update("Next Up: -")
            return

        next_track = self.recommendation_queue[0]
        next_title = str(next_track.get("title") or "Unknown title")
        next_artist = str(next_track.get("artist_name") or "Recommended")
        next_up_widget.update(f"Next Up: {next_title} | {next_artist}")

    def _refresh_player_progress(self) -> None:
        if not self.current_track:
            return

        elapsed_ms = self.player.current_time_ms()
        duration_ms = self.player.total_length_ms()
        if duration_ms <= 0 and self.current_duration_seconds > 0:
            duration_ms = self.current_duration_seconds * 1000
        if duration_ms <= 0:
            return

        self.query_one("#progress", ProgressBar).update(
            total=duration_ms, progress=min(elapsed_ms, duration_ms)
        )
        self.query_one("#time", Static).update(
            f"{self._format_ms(elapsed_ms)} / {self._format_ms(duration_ms)}"
        )

    def _seek_relative_ms(self, delta_ms: int) -> None:
        if not self.current_track:
            return

        try:
            current_ms = self.player.current_time_ms()
            length_ms = self.player.total_length_ms()
            target_ms = max(current_ms + int(delta_ms), 0)
            if length_ms > 0:
                target_ms = min(target_ms, length_ms - 250)
            # python-vlc: MediaPlayer.set_time expects milliseconds.
            self.player.player.set_time(target_ms)
        except Exception:
            return

    @staticmethod
    def _safe_get(items: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
        if 0 <= index < len(items):
            return items[index]
        return None

    @staticmethod
    def _format_ms(value: int) -> str:
        total_seconds = max(int(value // 1000), 0)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _format_seconds(value: int) -> str:
        total_seconds = max(int(value), 0)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _initialize_themes(self) -> None:
        available = getattr(self, "available_themes", None)
        names: list[str] = []
        if isinstance(available, dict):
            names = sorted([str(name) for name in available.keys() if name])
        elif isinstance(available, (list, tuple, set)):
            names = sorted([str(name) for name in available if name])

        if not names:
            names = ["textual-dark", "textual-light"]
        self.theme_names = names

    def _restore_theme(self) -> None:
        settings = self._load_settings()
        theme_name = settings.get("theme")
        if not isinstance(theme_name, str):
            return
        if theme_name not in self.theme_names:
            return

        self.theme = theme_name

    def _save_theme(self, theme_name: str) -> None:
        settings = self._load_settings()
        settings["theme"] = theme_name
        self._write_settings(settings)

    def _load_settings(self) -> dict[str, Any]:
        path = self.THEME_SETTINGS_PATH
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    def _write_settings(self, settings: dict[str, Any]) -> None:
        path = self.THEME_SETTINGS_PATH
        try:
            path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        except Exception:
            self.notify("Could not save theme settings.", severity="warning")
