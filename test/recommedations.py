import requests
import json
import re

# ==============================
# CONFIG
# ==============================
VIDEO_ID = "RMbFjeVonyg"
LIMIT = 10

# ==============================
# FETCH DATA
# ==============================
def fetch_recommendations(video_id):
    url = "https://www.youtube.com/youtubei/v1/next"

    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00"
            }
        },
        "videoId": video_id
    }

    headers = {
        "Content-Type": "application/json"
    }

    res = requests.post(url, json=payload, headers=headers)
    return res.json()


# ==============================
# HELPERS
# ==============================
def parse_duration(text):
    if not text:
        return None
    parts = list(map(int, text.split(":")))
    if len(parts) == 2:
        return parts[0]*60 + parts[1]
    if len(parts) == 3:
        return parts[0]*3600 + parts[1]*60 + parts[2]
    return None


def normalize(title):
    title = title.lower()

    # remove brackets
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"\[.*?\]", "", title)

    # remove common junk
    junk = [
        "official video", "lyrics", "lyric video",
        "audio", "hd", "4k", "video"
    ]
    for j in junk:
        title = title.replace(j, "")

    # clean chars
    title = re.sub(r"[^a-z0-9 ]", "", title)

    return " ".join(title.split())


def is_real_song(track):
    title = track["title"].lower()

    banned = [
        "mix", "playlist", "full album", "1 hour", "2 hour",
        "live", "stream", "radio", "24/7",
        "compilation", "best of", "loop", "extended"
    ]

    if any(k in title for k in banned):
        return False

    # duration filter
    if track.get("duration"):
        if track["duration"] > 600:  # >10 min
            return False

    return True


# ==============================
# PARSER
# ==============================
def parse_recommendations(data, limit=30):
    results = []

    try:
        items = data["contents"]["twoColumnWatchNextResults"] \
                    ["secondaryResults"]["secondaryResults"]["results"]
    except KeyError:
        return results

    for item in items:
        video_id = None
        title = None
        duration = None

        # Case 1: lockupViewModel
        if "lockupViewModel" in item:
            v = item["lockupViewModel"]

            video_id = v.get("contentId")

            title = v.get("metadata", {}) \
                     .get("lockupMetadataViewModel", {}) \
                     .get("title", {}) \
                     .get("content")

            overlays = v.get("contentImage", {}) \
                        .get("thumbnailViewModel", {}) \
                        .get("overlays", [])

            for o in overlays:
                badge = o.get("thumbnailBottomOverlayViewModel")
                if badge:
                    badges = badge.get("badges", [])
                    if badges:
                        duration_text = badges[0]["thumbnailBadgeViewModel"].get("text")
                        duration = parse_duration(duration_text)

        # Case 2: compactVideoRenderer
        elif "compactVideoRenderer" in item:
            v = item["compactVideoRenderer"]

            video_id = v.get("videoId")
            title = "".join([r["text"] for r in v["title"]["runs"]])

            duration_text = v.get("lengthText", {}).get("simpleText")
            duration = parse_duration(duration_text)

        if not video_id or not title:
            continue

        results.append({
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration": duration
        })

        if len(results) >= limit:
            break

    return results


# ==============================
# DEDUP + FILTER
# ==============================
def clean_tracks(tracks):
    seen_ids = set()
    seen_titles = set()

    clean = []

    for t in tracks:
        vid = t["id"]
        norm = normalize(t["title"])

        # 🔥 remove duplicates
        if vid in seen_ids or norm in seen_titles:
            continue

        # 🔥 remove junk
        if not is_real_song(t):
            continue

        seen_ids.add(vid)
        seen_titles.add(norm)

        clean.append(t)

    return clean


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    data = fetch_recommendations(VIDEO_ID)

    raw_tracks = parse_recommendations(data, limit=10)

    final_tracks = clean_tracks(raw_tracks)[1:LIMIT+1]

    print(json.dumps(final_tracks, indent=2))