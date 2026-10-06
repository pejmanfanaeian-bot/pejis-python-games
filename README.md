# Peji's Python Games

A collection of games I built and collected while learning Python — headlined by **Peji's Game Hub**, a full desktop game application written in a single Python file using only the standard library.

## 🎮 Peji's Game Hub — `Pejis_favorits.py`

A tkinter desktop app (~3,800 lines, 160+ functions, zero third-party dependencies) featuring:

- **Five games in one hub**
  - **Hangman** — with a hand-drawn canvas gallows
  - **Number Game** — guess the number with higher/lower feedback
  - **Word Challenge** — guess the word with progressive hints
  - **Math Game** — generated algebra, pattern, and multiplication problems
  - **Memory Match** — card-matching memory game
- **Intelligence test** — score 90%+ to unlock **Brainiac** mode
- **Local user accounts** — register/login with passwords hashed using **SHA-256** (`hashlib`); credentials are never stored in plain text
- **Persistent personal bests** — per-game records saved to a local `users.json` file and reloaded between sessions
- **Procedurally generated sound** — effects and melodies synthesized in code as in-memory WAV tones (`wave` + `struct`) and played asynchronously with `threading` — no audio files needed

### Run it

```bash
python Pejis_favorits.py
```

Requires Python 3.10+ (developed on Python 3.14, Windows). Everything is standard library — `tkinter`, `json`, `hashlib`, `wave`, `threading` — so there's nothing to install. On first run it creates `users.json` next to the script to store accounts and best scores (this file is intentionally excluded from the repo).

## 🔢 Bagels — `bagels.py`

The classic deductive logic game: guess a secret number from Pico / Fermi / Bagels clues.

*Bagels is by Al Sweigart, from [The Big Book of Small Python Projects](https://inventwithpython.com/bigbookpython/) — included here as a practice piece, with credit to its author.*

## About

Built by Pejman Fanaeian as part of my ongoing programming studies (Python, and now Rust). The Game Hub started as a learning project and grew into the largest single-file program I've written — game logic, user management, sound synthesis, and UI polish all in one place.
