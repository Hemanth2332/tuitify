# 🎧 Terminal Music Player — TUI Design

## 🔥 Core Idea

> A **listening-first UI** — music flows naturally, not like a tool.

---

## 🎯 Layout Overview

```
┌───────────────┬───────────────┬──────────────────────┐
│   SEARCH      │    QUEUE      │      PLAYER          │
│               │               │                      │
│  query input  │ Now Playing   │    Album Art         │
│               │ ▶ Song A      │                      │
│ results list  │               │    Title             │
│               │ Up Next       │    Artist            │
│  Song 1       │ • Song B      │                      │
│  Song 2       │ • Song C      │ ███████░░░ 1:23/3:45 │
│  Song 3       │               │                      │
│               │               │ [⏮] [⏯] [⏭]         │
└───────────────┴───────────────┴──────────────────────┘
```

---

## 🧩 Panels

### 🔍 Search Panel (Left)

**Purpose:** Discovery + manual control

#### Components:

* Search input (top)
* Scrollable results list

#### Example:

```
Tum Hi Ho - Arijit Singh     4:22
Lo-fi mix                    1:02:11  (dimmed / filtered)
```

#### Keybindings:

* `/` → Focus search
* `Enter` → Play immediately
* `a` → Add to queue

---

### 🎧 Queue Panel (Center)

**Purpose:** Visualize playback flow

```
Now Playing
▶ Song A

Up Next
• Song B
• Song C
• Song D
```

#### Features:

* Shows autoplay pipeline
* Enables trust in radio mode

#### Keybindings:

* `j / k` → Navigate
* `Enter` → Play selected
* `d` → Remove from queue

---

### 🎵 Player Panel (Right)

**Purpose:** Playback + visual experience

```
[ Album Art ]

Little Light
Deep Dreem

████████░░░░░ 1:23 / 3:45

Mode: RADIO

[⏮] [⏯] [⏭]
```

#### Features:

* Album art (image rendering)
* Progress bar
* Metadata display
* Playback controls

---

## 🔥 Playback Modes

### 🟢 Radio Mode

```
Mode: RADIO (seed: Little Light)
```

* Auto-fetch next track
* Queue updates dynamically

---

### 🟡 Manual Mode

```
Mode: MANUAL
```

* Only plays user-added queue

---

## 🎛️ Navigation

### Global

* `Tab` → Switch panel
* `q` → Quit

---

### Search Panel

* `/` → Focus search
* `Enter` → Play
* `a` → Add to queue

---

### Queue Panel

* `j / k` → Move
* `Enter` → Play
* `d` → Remove

---

### Player Controls

* `Space` → Play / Pause
* `n` → Next
* `p` → Previous
* `r` → Toggle radio mode

---

## ⚡ Layout Structure (Textual)

```python
class App(App):
    def compose(self):
        yield Horizontal(
            SearchPanel(),
            QueuePanel(),
            PlayerPanel()
        )
```

---

## 🎨 Visual Polish

* Highlight current playing track
* Dim filtered/long tracks
* Animate progress bar
* Use bordered panel titles:

```
[ Search ]   [ Queue ]   [ Now Playing ]
```

---

## 🚀 Optional Enhancement

### Continue Listening Section

```
Continue Listening
------------------
• Song A (1:12)
• Song B (0:45)
```

---

## 🧠 Design Philosophy

* Keep it minimal
* Focus on flow, not features
* Let **Search + Queue + Player** form the core experience

---

## 🔥 Summary

* 🎯 Simple, modern layout
* ⚡ Optimized for radio playback
* 🎧 Built for immersion

> A terminal music player that feels like a real streaming app
