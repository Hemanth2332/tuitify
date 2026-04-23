from __future__ import annotations

import io
from typing import Any

import requests
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, ProgressBar, Static
from textual_image.widget import Image

from src.radio import RadioEngine
from src.searcher import YoutubeSearcher
from src.yt_stream_player import YTStreamVLC


class Tuitify(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_search", "Search"),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Previous Panel", show=False),
        Binding("a", "add_selected_to_queue", "Add to Queue"),
        Binding("d", "remove_selected_from_queue", "Remove"),
        Binding("space", "toggle_play_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "previous_track", "Previous"),
        Binding("r", "toggle_radio_mode", "Toggle Mode"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-layout {
        height: 1fr;
        width: 100%;
    }

    .panel {
        border: round #3c3f46;
        padding: 1;
        height: 1fr;
    }

    #search-panel { width: 2fr; }
    #queue-panel { width: 2fr; }
    #player-panel { width: 3fr; }

    .panel-title {
        text-style: bold;
        color: #8ab4f8;
        padding-bottom: 1;
    }

    #search-input {
        margin-bottom: 1;
    }

    #search-results, #up-next-list {
        height: 1fr;
        border: round #2f3238;
    }

    #now-playing-line {
        margin-bottom: 1;
        color: #b0b7c3;
    }

    #art-frame {
        border: round #4b5563;
        align: center middle;
        height: 14;
        margin-bottom: 1;
        overflow: hidden hidden;
        background: #111418;
    }

    #album-art {
        width: auto;
        height: 100%;
    }

    #track-title {
        text-style: bold;
        padding-top: 1;
    }

    #track-artist {
        color: #b0b7c3;
        padding-bottom: 1;
    }

    #mode-label {
        padding-top: 1;
        color: #7dd3fc;
    }

    #controls {
        padding-top: 1;
        color: #c7d2fe;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.searcher = YoutubeSearcher(default_results=30)
        self.player = YTStreamVLC()
        self.radio = RadioEngine()

        self.search_results: list[dict[str, Any]] = []
        self.queue: list[dict[str, Any]] = []
        self.history: list[dict[str, Any]] = []

        self.current_track: dict[str, Any] | None = None
        self.current_duration_seconds: int = 0
        self.mode_radio = True

        self.playback_nonce = 0
        self.skip_requested = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="search-panel", classes="panel"):
                yield Static("Search", classes="panel-title")
                yield Input(
                    placeholder="Search music or podcast and press Enter",
                    id="search-input",
                )
                yield ListView(id="search-results")

            with Vertical(id="queue-panel", classes="panel"):
                yield Static("Queue", classes="panel-title")
                yield Static("Now Playing: -", id="now-playing-line")
                yield Static("Up Next")
                yield ListView(id="up-next-list")

            with Vertical(id="player-panel", classes="panel"):
                yield Static("Player", classes="panel-title")
                with Container(id="art-frame"):
                    yield Image(id="album-art")
                yield Static("Nothing playing", id="track-title")
                yield Static("-", id="track-artist")
                yield ProgressBar(total=100, id="progress")
                yield Static("0:00 / 0:00", id="time-label")
                yield Static("Mode: RADIO", id="mode-label")
                yield Static("[⏮] [⏯] [⏭]", id="controls")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh_player_progress)
        self.query_one("#search-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-input":
            return

        query = event.value.strip()
        if not query:
            self.notify("Enter a search query first.", severity="warning")
            return

        self._run_search(query)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "search-results":
            track = self._safe_get(self.search_results, event.index)
            if track:
                self.start_playback(track)
        elif event.list_view.id == "up-next-list":
            track = self._safe_get(self.queue, event.index)
            if not track:
                return
            self.queue.pop(event.index)
            self._render_queue()
            self.start_playback(track)

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cursor_down(self) -> None:
        self._focused_list_action("action_cursor_down")

    def action_cursor_up(self) -> None:
        self._focused_list_action("action_cursor_up")

    def action_add_selected_to_queue(self) -> None:
        if self.query_one("#search-results", ListView).has_focus:
            track = self._get_selected_from_results()
            if track:
                self.queue.append(track)
                self._render_queue()
                self.notify("Added to queue.")

    def action_remove_selected_from_queue(self) -> None:
        queue_view = self.query_one("#up-next-list", ListView)
        if not queue_view.has_focus or queue_view.index is None:
            return
        if 0 <= queue_view.index < len(self.queue):
            self.queue.pop(queue_view.index)
            self._render_queue()

    def action_toggle_play_pause(self) -> None:
        self.player.toggle_pause()

    def action_next_track(self) -> None:
        self.skip_requested = True
        self.player.stop()

    def action_previous_track(self) -> None:
        if len(self.history) < 2:
            return
        self.history.pop()
        previous_track = self.history.pop()
        self.start_playback(previous_track)

    def action_toggle_radio_mode(self) -> None:
        self.mode_radio = not self.mode_radio
        mode = "RADIO" if self.mode_radio else "MANUAL"
        self.query_one("#mode-label", Static).update(f"Mode: {mode}")
        self.notify(f"Switched to {mode} mode.")

    @work(exclusive=True, thread=True)
    def _run_search(self, query: str) -> None:
        try:
            results = self.searcher.search_media_details(query=query, num_results=30)
        except Exception as error:
            self.call_from_thread(
                self.notify, f"Search failed: {error}", severity="error"
            )
            return

        self.call_from_thread(self._apply_search_results, results)

    def _apply_search_results(self, results: list[dict[str, Any]]) -> None:
        self.search_results = results
        self._render_search_results()
        if results:
            self.notify(f"Found {len(results)} results.")
        else:
            self.notify("No results found for that query.", severity="warning")

    def start_playback(self, track: dict[str, Any]) -> None:
        self.playback_nonce += 1
        nonce = self.playback_nonce
        self.skip_requested = False
        self._playback_session(nonce, track)

    @work(exclusive=True, thread=True, group="playback")
    def _playback_session(self, nonce: int, seed_track: dict[str, Any]) -> None:
        current_track = seed_track
        prefetched_stream_for_current: str | None = None

        while nonce == self.playback_nonce:
            self.call_from_thread(self._set_current_track, current_track)

            next_track: dict[str, Any] | None = None
            next_stream_url: str | None = None

            def prefetch_next_track_stream() -> None:
                nonlocal next_track, next_stream_url
                if next_track is None:
                    next_track = self._resolve_next_track(current_track)
                if not next_track or next_stream_url:
                    return
                try:
                    next_stream_url, _duration = self.player.service.get_stream_info(
                        next_track["url"]
                    )
                except Exception:
                    next_stream_url = None

            try:
                end_state = self.player.play_track(
                    current_track,
                    prefetched_stream_url=prefetched_stream_for_current,
                    on_near_end=prefetch_next_track_stream,
                    near_end_seconds=12,
                )
            except Exception as error:
                self.call_from_thread(
                    self.notify, f"Playback failed: {error}", severity="error"
                )
                return

            if nonce != self.playback_nonce:
                return

            if end_state == "ended":
                self.radio.mark_played(current_track)
                self.history.append(current_track)
            elif end_state == "stopped" and not self.skip_requested:
                return

            self.skip_requested = False
            if next_track is None:
                next_track = self._resolve_next_track(current_track)
            if not next_track:
                return

            current_track = next_track
            prefetched_stream_for_current = next_stream_url

    def _resolve_next_track(
        self, current_track: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.mode_radio:
            return self.radio.next_track(seed=current_track)

        if not self.queue:
            return None
        next_track = self.queue.pop(0)
        self.call_from_thread(self._render_queue)
        return next_track

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
        art_widget = self.query_one("#album-art", Image)
        art_widget.image = image_data

    def _set_current_track(self, track: dict[str, Any]) -> None:
        self.current_track = track
        self.current_duration_seconds = int(track.get("duration") or 0)

        self.query_one("#now-playing-line", Static).update(
            f"Now Playing: {track.get('title', 'Unknown')}"
        )
        self.query_one("#track-title", Static).update(
            str(track.get("title", "Unknown title"))
        )
        self.query_one("#track-artist", Static).update(
            str(track.get("artist_name", "Unknown artist"))
        )
        self.query_one("#time-label", Static).update(
            "0:00 / " + track.get("total_play_time", "0:00")
        )

        thumbnail_url = track.get("thumbnail")
        if thumbnail_url:
            self._load_artwork(str(thumbnail_url))
        else:
            self._set_artwork(None)

    def _refresh_player_progress(self) -> None:
        if not self.current_track:
            return

        elapsed_ms = self.player.current_time_ms()
        duration_ms = self.player.total_length_ms()
        if duration_ms <= 0 and self.current_duration_seconds > 0:
            duration_ms = self.current_duration_seconds * 1000
        if duration_ms <= 0:
            return

        progress = self.query_one("#progress", ProgressBar)
        progress.update(total=duration_ms, progress=min(elapsed_ms, duration_ms))

        elapsed_text = self._format_ms(elapsed_ms)
        total_text = self._format_ms(duration_ms)
        self.query_one("#time-label", Static).update(f"{elapsed_text} / {total_text}")

    def _render_search_results(self) -> None:
        results_list = self.query_one("#search-results", ListView)
        items = [self._track_to_list_item(track) for track in self.search_results]
        results_list.clear()
        if items:
            results_list.extend(items)
            results_list.index = 0
        else:
            results_list.append(ListItem(Label("No results found")))

    def _render_queue(self) -> None:
        queue_view = self.query_one("#up-next-list", ListView)
        items = [self._track_to_list_item(track, show_artist=False) for track in self.queue]
        queue_view.clear()
        if items:
            queue_view.extend(items)
            queue_view.index = 0
        else:
            queue_view.append(ListItem(Label("Queue is empty")))

    def _get_selected_from_results(self) -> dict[str, Any] | None:
        results_view = self.query_one("#search-results", ListView)
        if results_view.index is None:
            return None
        return self._safe_get(self.search_results, results_view.index)

    def _focused_list_action(self, action_name: str) -> None:
        if self.query_one("#up-next-list", ListView).has_focus:
            getattr(self.query_one("#up-next-list", ListView), action_name)()
            return
        if self.query_one("#search-results", ListView).has_focus:
            getattr(self.query_one("#search-results", ListView), action_name)()
            return
        self.query_one("#search-results", ListView).focus()
        getattr(self.query_one("#search-results", ListView), action_name)()

    @staticmethod
    def _track_to_list_item(
        track: dict[str, Any], show_artist: bool = True
    ) -> ListItem:
        title = str(track.get("title", "Unknown title"))
        artist = str(track.get("artist_name", "Unknown artist"))
        duration = str(track.get("total_play_time", "0:00"))
        if show_artist:
            text = f"{title} - {artist} ({duration})"
        else:
            text = f"{title} ({duration})"
        return ListItem(Label(text))

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
