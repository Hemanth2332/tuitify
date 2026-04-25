from textual.binding import Binding


BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("i", "focus_input", "Focus Input", show=True),
        Binding("space", "toggle_pause", "Play/Pause", show=True),
        Binding("n", "next_track", "Next", show=True),
        Binding("left", "seek_backward", "← Back 10s", show=True),
        Binding("right", "seek_forward", "→ Forward 10s", show=True),
        Binding("up", "cursor_up", "Cursor Up", show=True),
        Binding("down", "cursor_down", "Cursor Down", show=True),
    ]