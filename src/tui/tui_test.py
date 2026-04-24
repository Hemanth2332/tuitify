from __future__ import annotations

import io
from typing import Any

from textual import work
from textual.widgets import ListItem
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, HorizontalScroll
from textual.widgets import Footer, Header, Input, ListView, ProgressBar, Select, Static
from textual_image.widget import Image
from rich.text import Text

import requests

from src.radio import RadioEngine
from src.searcher import YoutubeSearcher
from src.yt_stream_player import YTStreamVLC


class Tuitify(App):

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("i", "focus_input", "Focus Input"),
        Binding("space", "toggle_pause", "Play/Pause"),
        Binding("left", "seek_backward", "Back 10s", show=False),
        Binding("right", "seek_forward", "Forward 10s", show=False),
        Binding("up", "cursor_up", "Cursor Up"),
        Binding("down", "cursor_down", "Cursor Down")
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-layout {
        height: 1fr;
        width: 100%;
    }

    #top-panels {
        height: 1fr;
        width: 100%;
    }

    .panel {
        border: round #3c3f46;
        padding: 1;
        width: 1fr;
        height: 1fr;
    }

    .search-result-view{
        margin-top: 1;
        border: round #56B6C6;
    }

    .search-results-shell {
        margin-top: 2;
        height: 1fr;
        border: round #2f3238;
        overflow-x: auto;
        overflow-y: hidden;
        scrollbar-gutter: stable;
        scrollbar-color: #56B6C6;
    }

    .search-results {
        height: 1fr;
        width: auto;
        min-width: 100%;
        border: none;
        overflow-x: hidden;
        overflow-y: auto;
    }

    #search-controls {
        height: auto;
        width: 100%;
    }

    #media-select {
        width: 14;
        margin-right: 1;
    }

    #search-input {
        width: 1fr;
    }

    .art-frame {
        border: round #3c3f46;
        width: 100%;
        height: 50%;
        align: center middle;
        background: #111418;
        overflow: hidden;
    }

    #album-art {
        width: auto;
        height: 100%;
    }

    ListItem {
        height: auto;
        padding: 0 1;
        width: auto;
        min-width: 100%;
    }

    .result-line{
        text-wrap: nowrap;
        width: auto;
        height: 1;
        color: #d7dae0;
    }

    ListItem.--highlight {
        background: #2b313a;
    }

    ListItem.--highlight .result-line {
        text-style: bold;
    }

    """

    def __init__(self) -> None:
        super().__init__()

        self.searcher = YoutubeSearcher(default_results=25)
        self.player = YTStreamVLC()

        self.search_results: list[dict[str, Any]] = []
        self.current_track: dict[str, Any] | None = None
        self.current_duration_seconds: int = 0
        self.playback_nonce = 0


    def compose(self):
        yield Header(name="Tuitify", show_clock=True)

        with Vertical(id="main-layout"):
            with Horizontal(id="top-panels"):
                # Search Panel
                with VerticalScroll(classes="panel"):
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
                with Vertical(classes="panel"):
                    yield Static("Player")

                    with Container(id="art-frame", classes="art-frame"):
                        yield Image(id="album-art")

                    yield Static("Title", id="title")
                    yield Static("Artist", id="artist")
                    yield ProgressBar(total=100, id="progress")
                    yield Static("0:00 / 0:00", id="time")

        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh_player_progress)
        self.action_focus_input()

    # Key Bindings
    def action_quit(self) -> None:
        self.playback_nonce += 1
        self.current_track = None
        self.player.stop()
        self.exit()

    def action_toggle_pause(self) -> None:
        if not self.current_track:
            return
        self.player.toggle_pause()

    def action_seek_backward(self) -> None:
        self._seek_relative_ms(-10_000)

    def action_seek_forward(self) -> None:
        self._seek_relative_ms(10_000)

    def action_focus_input(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cursor_up(self) -> None:
        list_view = self.query_one("#search-results", ListView)
        if not list_view.children:
            return
        if not list_view.has_focus:
            list_view.focus()
        if list_view.index is None:
            list_view.index = 0
            return
        list_view.move_cursor_up()

    def action_cursor_down(self) -> None:
        list_view = self.query_one("#search-results", ListView)
        if not list_view.children:
            return
        if not list_view.has_focus:
            list_view.focus()
        if list_view.index is None:
            list_view.index = 0
            return
        list_view.move_cursor_down()



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
        query = self.query_one("#search-input", Input).value
        self.query_one("#search-input", Input).clear()

        if not query.strip():
            self.notify("Enter a query", "warning")
            return

        mode = str(self.query_one("#media-select", Select).value or "music").lower()
        prefix = "music" if mode == "music" else "podcast"
        full_query = f"{prefix} {query}".strip()

        self.search_results = self.searcher.search_media_details(full_query)
        self.render_search_results()

        self.query_one("#search-results", ListView).focus()

    def render_search_results(self):
        results_view = self.query_one("#search-results", ListView)
        results_view.clear()

        for idx, track in enumerate(self.search_results, start=1):
            title = str(track.get("title", "Unknown Title"))
            channel = str(
                track.get("artist_name")
                or track.get("channel")
                or track.get("uploader")
                or track.get("creator")
                or ""
            )

            if len(title) > 30:
                title = title[:27] + "..."

            duration = track.get("duration")
            if duration:
                duration_str = str(track.get("total_play_time") or "00:00")
            else:
                duration_str = "LIVE"

            line = Text()
            line.append(f"{idx:>2}  ", style="bold #56B6C6")
            line.append(title, style="bold")
            if channel:
                line.append("  ")
                line.append("│ ", style="dim")
                line.append(channel, style="dim")
            line.append("  ")
            line.append("│ ", style="dim")
            line.append(duration_str, style="bold #98C379")

            display_text = line

            list_item = ListItem(
                Static(
                    display_text,
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
        self._set_current_track(track)
        self._playback_session(nonce, track)

    @work(exclusive=True, thread=True, group="playback")
    def _playback_session(self, nonce: int, track: dict[str, Any]) -> None:
        if nonce != self.playback_nonce:
            return

        try:
            self.player.play_track(track, retry_on_error=True)
        except Exception as error:
            self.call_from_thread(
                self.notify, f"Playback failed: {error}", severity="error"
            )

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


    

if __name__ == "__main__":
    Tuitify().run()
