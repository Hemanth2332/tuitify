import random
from recommedations import fetch_recommendations, parse_recommendations, clean_tracks

class RadioEngine:
    def __init__(self):
        self.history = []
        self.queue = []

    def mark_played(self, track):
        self.history.append(track)

        # keep last 20 songs
        if len(self.history) > 20:
            self.history.pop(0)

    def fetch_next_from_seed(self, seed):
        data = fetch_recommendations(seed["id"])
        recs = parse_recommendations(data, limit=30)
        recs = clean_tracks(recs)

        # remove already played
        seen_ids = {t["id"] for t in self.history}
        recs = [r for r in recs if r["id"] not in seen_ids]

        return recs

    def choose_next(self, candidates):
        if not candidates:
            return None

        # 🎯 scoring
        def score(t):
            s = 0

            # prefer normal song duration
            if t.get("duration") and 120 <= t["duration"] <= 320:
                s += 2

            # randomness → avoids loops
            s += random.random()

            return s

        candidates.sort(key=score, reverse=True)

        # 🎲 exploration (20%)
        if random.random() < 0.2:
            return random.choice(candidates)

        return candidates[0]

    def next_track(self):
        if not self.history:
            return None

        last_song = self.history[-1]

        candidates = self.fetch_next_from_seed(last_song)
        next_song = self.choose_next(candidates)

        if next_song:
            self.queue.append(next_song)

        return next_song
    
if __name__ == "__main__":
    engine = RadioEngine()

    # seed
    engine.mark_played({
        "id": "RMbFjeVonyg",
        "title": "Seed Track"
    })

    for i in range(2):
        next_song = engine.next_track()

        if not next_song:
            print("No recommendations found")
            break

        print(f"\n🎵 Playing: {next_song['title']}")
        print(next_song["url"])

        # 🔥 ONLY AFTER FULL PLAY
        engine.mark_played(next_song)