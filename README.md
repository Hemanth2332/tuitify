<div align="center">
  <img src="images/logo.png" alt="Tuitify Logo" width="200"/>
</div>

<p align="center">
  <strong>A Terminal-based music player powered by YouTube.</strong>
</p>

---

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-0.10.22+-green.svg)](https://github.com/astral-sh/uv)
[![license](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![VLC](https://img.shields.io/badge/VLC-0.0.1-orange.svg)](https://www.videolan.org/vlc/)

## Overview

**Tuitify** is a terminal-first music streaming application built for users who want a fast, keyboard-driven listening experience without leaving the command line. It combines YouTube-powered music discovery, seamless playback, and radio-style autoplay recommendations into a lightweight TUI (Text User Interface) that feels like a minimal Spotify for the terminal.

Users can search for music or podcasts, instantly stream audio using VLC-backed playback, and continue listening through an automatically generated recommendation queue based on the currently playing track. Album artwork, progress tracking, next-up previews, playback controls, and keyboard shortcuts make the experience smooth, responsive, and practical for daily use.

![UI](images/screenshot_1.png)

## Features

- **Global Search**: Instantly find songs, albums, or podcasts.
- **Smart Radio Engine**: Automatically seeds recommendations based on your current track for non-stop playback.
- **High-Quality Audio**: Uses `yt-dlp` and `vlc` for reliable and high-quality streaming.
- **Keyboard Centric**: Optimized for efficiency with customizable keybindings.
- **Album Art**: Real-time display of track artwork in your terminal.

## Getting Started

### Prerequisites
- **Python 3.12+**
- **VLC Media Player**: Ensure VLC is installed on your system as it's the core playback engine.


### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Hemanth2332/tuitify.git
   cd tuitify
   ```

2. Install dependencies (using `uv` or `pip`):
   ```bash
   uv sync
   # or
   pip install .
   ```

### Running the App

Simply run the `main.py` file:
```bash
python main.py
```

## 🎮 Controls

- `i`: Focus search input
- `Enter`: Search / Play selected track
- `Space`: Play / Pause
- `n`: Skip to next track
- `←` / `→`: Seek backward/forward (10s)
- `q`: Quit Tuitify

## 🛠️ Project Structure

- `src/tui/`: Main TUI application logic and layout.
- `src/youtube/`: YouTube service, streaming player, and recommendation engine.
- `src/search/`: Search-specific wrappers.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
