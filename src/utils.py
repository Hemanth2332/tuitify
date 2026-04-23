from __future__ import annotations

import re
from typing import Any


def parse_duration(text: str | None) -> int | None:
    if not text:
        return None

    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return None

    values = [int(part) for part in parts]
    if len(values) == 2:
        return values[0] * 60 + values[1]
    if len(values) == 3:
        return values[0] * 3600 + values[1] * 60 + values[2]
    return None


def normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"\(.*?\)", "", normalized)
    normalized = re.sub(r"\[.*?\]", "", normalized)

    junk_words = (
        "official video",
        "lyrics",
        "lyric video",
        "audio",
        "hd",
        "4k",
        "video",
    )
    for word in junk_words:
        normalized = normalized.replace(word, "")

    normalized = re.sub(r"[^a-z0-9 ]", "", normalized)
    return " ".join(normalized.split())


def is_real_song(track: dict[str, Any]) -> bool:
    title = str(track.get("title", "")).lower()
    banned_keywords = (
        "mix",
        "playlist",
        "full album",
        "1 hour",
        "2 hour",
        "live",
        "stream",
        "radio",
        "24/7",
        "compilation",
        "best of",
        "loop",
        "extended",
    )

    if any(keyword in title for keyword in banned_keywords):
        return False

    duration = track.get("duration")
    return not duration or duration <= 600


def parse_recommendations(data: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    items = _safe_secondary_results(data)
    if not items:
        return results

    for item in items:
        track = _parse_lockup_item(item) or _parse_compact_item(item)
        if not track:
            continue

        results.append(track)
        if len(results) >= limit:
            break

    return results


def clean_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    cleaned: list[dict[str, Any]] = []

    for track in tracks:
        track_id = track.get("id")
        title = str(track.get("title", ""))
        if not track_id or not title:
            continue

        normalized = normalize_title(title)
        if track_id in seen_ids or normalized in seen_titles:
            continue
        if not is_real_song(track):
            continue

        seen_ids.add(track_id)
        seen_titles.add(normalized)
        cleaned.append(track)

    return cleaned


def _safe_secondary_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return (
            data["contents"]["twoColumnWatchNextResults"]["secondaryResults"][
                "secondaryResults"
            ]["results"]
        )
    except KeyError:
        return []


def _parse_lockup_item(item: dict[str, Any]) -> dict[str, Any] | None:
    lockup = item.get("lockupViewModel")
    if not lockup:
        return None

    video_id = lockup.get("contentId")
    title = (
        lockup.get("metadata", {})
        .get("lockupMetadataViewModel", {})
        .get("title", {})
        .get("content")
    )
    duration = _parse_lockup_duration(lockup)
    return _build_track(video_id=video_id, title=title, duration=duration)


def _parse_lockup_duration(lockup: dict[str, Any]) -> int | None:
    overlays = (
        lockup.get("contentImage", {})
        .get("thumbnailViewModel", {})
        .get("overlays", [])
    )
    for overlay in overlays:
        badge = overlay.get("thumbnailBottomOverlayViewModel")
        if not badge:
            continue
        badges = badge.get("badges", [])
        if not badges:
            continue
        duration_text = badges[0].get("thumbnailBadgeViewModel", {}).get("text")
        return parse_duration(duration_text)
    return None


def _parse_compact_item(item: dict[str, Any]) -> dict[str, Any] | None:
    compact = item.get("compactVideoRenderer")
    if not compact:
        return None

    video_id = compact.get("videoId")
    title_runs = compact.get("title", {}).get("runs", [])
    title = "".join(part.get("text", "") for part in title_runs) or None
    duration_text = compact.get("lengthText", {}).get("simpleText")
    duration = parse_duration(duration_text)
    return _build_track(video_id=video_id, title=title, duration=duration)


def _build_track(
    video_id: str | None, title: str | None, duration: int | None
) -> dict[str, Any] | None:
    if not video_id or not title:
        return None
    return {
        "id": video_id,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "duration": duration,
    }
