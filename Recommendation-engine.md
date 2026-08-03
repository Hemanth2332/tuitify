# Tuitify Personalized Recommendation Engine

## Goal

The objective is **not** to replace YouTube Music's recommendation engine.

Instead, Tuitify uses **YouTube Music Radio** to generate candidate songs and then **personalizes their order** based on the user's listening history.

This keeps the recommendations strong while allowing them to improve as the user continues listening.

---

# Design Philosophy

The recommendation system is split into three independent components.

```
                 YouTube Music
                       │
                       ▼
           Candidate Recommendations
                       │
        ┌──────────────┴──────────────┐
        │                             │
 Vector Similarity              Listening History
 (User Taste)                   (Recent Plays)
        │                             │
        └──────────────┬──────────────┘
                       ▼
               Recommendation Score
                       │
                       ▼
              Personalized Queue
```

Each component has a single responsibility.

| Component | Responsibility |
|-----------|----------------|
| YouTube Music Radio | Generate good candidate songs |
| sqlite-vec | Measure how similar a candidate is to the user's taste |
| SQLite | Prevent repetitive playback and store listening history |

---

# Why sqlite-vec?

The recommendation system is completely local.

Advantages:

- No external APIs
- Works offline
- Cross-platform
- Tiny footprint
- Distributed with the application
- Stored inside the same SQLite database

The recommendation engine should work on:

- Windows
- Linux
- macOS

without requiring additional services.

---

# Database Design

## Listening History

Stores every meaningful listening event.

```sql
CREATE TABLE listening_history (
    id INTEGER PRIMARY KEY,

    song_id TEXT,
    title TEXT,
    artist TEXT,

    completion REAL,
    replay_count INTEGER,

    played_at DATETIME,

    tags TEXT
);
```

This table answers questions like:

- When was this song played?
- How many times?
- Was it skipped?
- Was it replayed?

---

## User Memory (sqlite-vec)

Each meaningful listening event becomes an embedding.

```
Song

↓

Embedding

↓

sqlite-vec
```

Metadata:

```
song_id
title
artist
completion
replay_count
timestamp
positive
```

---

# What Gets Embedded?

Instead of embedding raw audio, embed the semantic metadata.

Example:

```
Title: Numb

Artist: Linkin Park

Tags:
rock
nu metal
alternative rock
2000s
official video
```

Generated with

```
all-MiniLM-L6-v2
```

Produces

```
384-dimensional embedding
```

---

# When Should Memories Be Stored?

Only meaningful interactions should be saved.

Positive memory

- Played more than 80%
- Favorited
- Replayed

Negative memory

- Skipped within first 15 seconds

Everything else is ignored to reduce noise.

---

# Recommendation Pipeline

## Step 1

Current song starts playing.

↓

## Step 2

YouTube Music Radio returns candidate songs.

Example

```
50 candidates
```

↓

## Step 3

For every candidate

```
Title

Artist

Tags
```

↓

Generate embedding.

↓

Search sqlite-vec.

↓

Return nearest listening memories.

---

# Similarity Search

The vector database answers one question only.

> **How similar is this candidate to music the user previously enjoyed?**

It does **not** decide whether the song should be played.

That decision belongs to the scoring layer.

---

# Listening History

SQLite answers questions like

```
Was this song played recently?

How many times?

Was it skipped?

When was it last played?
```

Example

```
Song

Numb

Last played

5 minutes ago
```

Even if similarity is high, the recommendation should receive a penalty.

---

# Recommendation Score

The final score combines three signals.

```
Final Score

=

YouTube Score

+

Similarity Bonus

-

Recently Played Penalty

-

Recently Skipped Penalty
```

Example

```
YouTube Score

0.82

Similarity

0.91

Recently Played

0.40 penalty

↓

Final

1.33
```

Candidates are sorted using the final score.

---

# Preventing Repetition

The vector database should never know whether a song was recently played.

SQLite handles this.

Example rule

```
if played within last 30 minutes:

    apply penalty
```

instead of removing the song completely.

This allows favorite songs to appear again naturally after some time.

---

# Positive and Negative Memory

Two types of memories exist.

Positive

```
Finished

Favorited

Replayed
```

Negative

```
Skipped quickly

Repeated skips
```

Candidate score

```
Similarity to Positive

-

Similarity to Negative
```

This helps avoid songs similar to ones the user consistently skips.

---

# Cold Start

New users have no listening history.

Recommendation flow

```
YouTube Radio

↓

Play directly
```

After enough listening events are collected, personalization gradually starts.

No manual setup is required.

---

# Folder Structure

```
src/

recommendations/

    embeddings.py

    memory.py

    scorer.py

    recommender.py
```

## embeddings.py

Responsible for

- loading MiniLM
- generating embeddings

---

## memory.py

Responsible for

- storing memories
- querying sqlite-vec

---

## scorer.py

Responsible for combining

- YouTube score
- similarity score
- penalties

into one recommendation score.

---

## recommender.py

Coordinates the entire recommendation pipeline.

---

# Why This Architecture?

The recommendation engine does **not** attempt to compete with YouTube Music.

Instead it learns the user's preferences over time and simply reorders YouTube's recommendations.

Benefits

- Lightweight
- Runs locally
- No cloud infrastructure
- Privacy friendly
- Improves automatically as the user listens
- Easy to extend with future features

---

# Future Improvements

Possible future enhancements include:

- Time-of-day preferences (morning, night, workout)
- Context-aware recommendations
- Artist affinity weighting
- Session-based personalization
- Diversity filtering to avoid repetitive artists
- User taste evolution over time
- Playlist-aware recommendations