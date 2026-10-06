import random
import threading
import math
import tkinter as tk
import time
import json
import os
import hashlib
import io
import struct
import wave
try:
    import winsound
except Exception:
    winsound = None

BG = "#0f172a"
CARD = "#1e293b"
PRIMARY = "#6366f1"
HOVER = "#818cf8"
TEXT = "#e2e8f0"
SUBTLE = "#94a3b8"
ACCENT = "#f97316"
ACCENT_HOVER = "#fdba74"
ACCENT_TEXT = "#0f172a"
WIN_BANNER_BG = "#fde047"
WIN_BANNER_FG = "#0f172a"
HANGMAN_WORDS = [
    "python",
    "hangman",
    "computer",
    "science",
    "galaxy",
    "nebula",
    "quantum",
    "adventure",
    "volcano",
    "lantern",
    "puzzle",
    "mystery",
    "rocket",
    "thunder",
    "voyage",
    "algorithm",
    "keyboard",
    "network",
    "library",
    "serendipity",
]

score = 0
displayed_score = 0
score_anim_job = None
bg_cycle_job = None
score_pulse_job = None
score_label = None
win_banner = None
win_banner_job = None
BG_CYCLE_COLORS = ["#0f172a", "#2563eb", "#0ea5e9", "#14b8a6", "#fde047", "#f97316", "#0f172a"]
bg_targets = []

USERS_FILE = "users.json"
current_user = None
best_score_var = None


def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def save_best_score(username, iq_pct, h_score, n_score, w_score, m_score):
    users = load_users()
    if username not in users:
        return False
    profile = users[username]
    if iq_pct > profile.get("best_iq", 0):
        profile["best_iq"] = round(iq_pct, 1)
        profile["best_hangman"] = h_score
        profile["best_number"] = n_score
        profile["best_word"] = w_score
        profile["best_math"] = m_score
        save_users(users)
        if best_score_var is not None:
            best_score_var.set(f"Personal Best: {iq_pct:.1f}%")
        try:
            refresh_brainiac_btn()
        except Exception:
            pass
        return True
    return False


root = tk.Tk()
root.title("Game Hub")
root.state("zoomed")
root.configure(bg=BG)

score_var = tk.StringVar(value="Score: 0")


def _make_tone(freq, dur_ms, volume=0.5):
    """Generate a sine-wave tone as an in-memory WAV bytes object."""
    sample_rate = 44100
    n_samples = int(sample_rate * dur_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            val = volume * math.sin(2 * math.pi * freq * t)
            wf.writeframes(struct.pack("<h", int(val * 32767)))
    return buf.getvalue()


def _make_melody(notes, volume=0.5):
    """Generate a multi-note melody as an in-memory WAV bytes object.
    notes is a list of (freq_hz, duration_ms) tuples."""
    sample_rate = 44100
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for freq, dur_ms in notes:
            n_samples = int(sample_rate * dur_ms / 1000)
            for i in range(n_samples):
                t = i / sample_rate
                val = volume * math.sin(2 * math.pi * freq * t)
                wf.writeframes(struct.pack("<h", int(val * 32767)))
    return buf.getvalue()


def safe_beep(freq, dur_ms):
    """Play a tone through the speakers using in-memory WAV via winsound."""
    if winsound is not None:
        try:
            data = _make_tone(freq, dur_ms)
            winsound.PlaySound(data, winsound.SND_MEMORY)
            return
        except Exception:
            pass
    try:
        root.bell()
    except Exception:
        pass
    try:
        time.sleep(dur_ms / 1000.0)
    except Exception:
        pass


def _play_melody_async(notes, volume=0.5):
    """Play a multi-note melody asynchronously on a background thread."""
    def runner():
        if winsound is not None:
            try:
                data = _make_melody(notes, volume)
                winsound.PlaySound(data, winsound.SND_MEMORY)
                return
            except Exception:
                pass
        for _, dur in notes:
            try:
                root.bell()
            except Exception:
                pass
            time.sleep(dur / 1000.0)
    threading.Thread(target=runner, daemon=True).start()


def register_bg_target(widget):
    if widget not in bg_targets:
        bg_targets.append(widget)


def apply_bg_color(color):
    alive = []
    for widget in bg_targets:
        try:
            exists = widget.winfo_exists()
        except Exception:
            exists = False
        if not exists:
            continue
        try:
            widget.configure(bg=color)
        except Exception:
            pass
        else:
            alive.append(widget)
    # ensure root always matches even if not tracked elsewhere
    try:
        root.configure(bg=color)
    except Exception:
        pass
    bg_targets[:] = alive


def play_win_sound():
    _play_melody_async([(880, 140), (1040, 140), (1320, 180), (1560, 260)], volume=0.6)


def play_opening_music():
    _play_melody_async([(800, 140), (660, 200), (520, 260), (330, 700)], volume=0.5)


def play_correct_sound():
    _play_melody_async([(1200, 120)], volume=0.5)


def play_wrong_sound():
    _play_melody_async([(350, 180), (280, 260)], volume=0.5)


def play_lose_sound():
    _play_melody_async([(500, 200), (400, 200), (300, 200), (200, 500)], volume=0.5)


def play_tick_sound():
    _play_melody_async([(1000, 60)], volume=0.3)


def play_click_sound():
    _play_melody_async([(800, 50)], volume=0.3)


def start_bg_cycle():
    global bg_cycle_job

    palette_len = len(BG_CYCLE_COLORS)
    total_steps = palette_len * 2
    if bg_cycle_job is not None:
        try:
            root.after_cancel(bg_cycle_job)
        except Exception:
            pass
        bg_cycle_job = None

    def runner(index=0, remaining=total_steps):
        global bg_cycle_job
        color = BG_CYCLE_COLORS[index % palette_len]
        apply_bg_color(color)
        if remaining <= 0:
            apply_bg_color(BG)
            bg_cycle_job = None
            return
        bg_cycle_job = root.after(140, lambda: runner(index + 1, remaining - 1))

    runner()


def start_score_animation():
    global score_anim_job, displayed_score

    if score_anim_job is not None:
        return

    def animate_step():
        global score_anim_job, displayed_score
        if displayed_score >= score:
            score_anim_job = None
            return
        displayed_score += 1
        score_var.set(f"Score: {displayed_score}")
        score_anim_job = root.after(70, animate_step)

    animate_step()


def pulse_score_label():
    global score_pulse_job

    if score_label is None or not hasattr(score_label, "winfo_exists"):
        return
    if not score_label.winfo_exists():
        return
    if score_pulse_job is not None:
        try:
            root.after_cancel(score_pulse_job)
        except Exception:
            pass
        score_pulse_job = None

    frames = [
        (18, "#fbbf24"),
        (22, "#f97316"),
        (26, "#facc15"),
        (22, "#fb923c"),
        (18, "#fbbf24"),
        (16, TEXT),
    ]

    def step(index=0):
        global score_pulse_job
        if index >= len(frames):
            score_label.config(font=("Segoe UI", 16, "bold"), fg=TEXT)
            score_pulse_job = None
            return
        size, color = frames[index]
        score_label.config(font=("Segoe UI", size, "bold"), fg=color)
        score_pulse_job = root.after(90, lambda: step(index + 1))

    step()


def show_win_banner(message):
    global win_banner, win_banner_job

    if win_banner_job is not None:
        try:
            root.after_cancel(win_banner_job)
        except Exception:
            pass
        win_banner_job = None

    # Destroy previous banner toplevel if it still exists
    if win_banner is not None:
        try:
            if win_banner.winfo_exists():
                win_banner.destroy()
        except Exception:
            pass
        win_banner = None

    # Create a borderless, always-on-top Toplevel so it floats above game windows
    banner_win = tk.Toplevel(root)
    banner_win.overrideredirect(True)          # no title bar / border
    banner_win.attributes("-topmost", True)    # always on top
    banner_win.configure(bg=WIN_BANNER_BG)

    lbl = tk.Label(
        banner_win,
        text=f"🎉  WIN!  {message}  🎉",
        font=("Segoe UI", 18, "bold"),
        bg=WIN_BANNER_BG,
        fg=WIN_BANNER_FG,
        padx=36,
        pady=12,
    )
    lbl.pack()
    banner_win.update_idletasks()

    # Measure and centre horizontally over the root window
    bw = banner_win.winfo_reqwidth()
    bh = banner_win.winfo_reqheight()
    root_x = root.winfo_rootx()
    root_w = root.winfo_width()
    center_x = root_x + (root_w - bw) // 2

    win_banner = banner_win

    start_y = root.winfo_rooty() - bh - 10     # just above the visible area
    target_y = root.winfo_rooty() + 30          # slide down to 30 px below top
    total_steps = 14
    hold_ms = 1800

    def slide_in(step=0):
        global win_banner_job
        try:
            if not banner_win.winfo_exists():
                return
        except Exception:
            return
        if step > total_steps:
            win_banner_job = root.after(hold_ms, slide_out)
            return
        progress = step / total_steps
        y = int(start_y + (target_y - start_y) * progress)
        banner_win.geometry(f"{bw}x{bh}+{center_x}+{y}")
        win_banner_job = root.after(30, lambda: slide_in(step + 1))

    def slide_out(step=0):
        global win_banner_job
        try:
            if not banner_win.winfo_exists():
                win_banner_job = None
                return
        except Exception:
            win_banner_job = None
            return
        if step > total_steps:
            banner_win.destroy()
            win_banner_job = None
            return
        progress = step / total_steps
        y = int(target_y + (start_y - target_y) * progress)
        banner_win.geometry(f"{bw}x{bh}+{center_x}+{y}")
        win_banner_job = root.after(30, lambda: slide_out(step + 1))

    # Start off-screen and begin slide
    banner_win.geometry(f"{bw}x{bh}+{center_x}+{start_y}")
    slide_in()


def _save_user_score():
    """Persist the current score to users.json for the logged-in user."""
    if current_user is None:
        return
    try:
        users = load_users()
        if current_user in users:
            users[current_user]["score"] = score
            save_users(users)
    except Exception:
        pass


def add_score(points, celebrate=False, message=None):
    global score, displayed_score
    score = max(score + points, 0)
    if celebrate and points > 0:
        start_score_animation()
        start_bg_cycle()
        pulse_score_label()
        show_win_banner(message or f"+{points} points")
        play_win_sound()
    else:
        displayed_score = score
        score_var.set(f"Score: {displayed_score}")
    _save_user_score()


register_bg_target(root)


def build_word_hints(word):
    vowels = sorted({char for char in word if char in "aeiou"})
    unique_letters = sorted(set(word), key=lambda c: (-word.count(c), c))
    prefix = word[:2].upper() if len(word) >= 2 else word.upper()
    suffix = word[-2:].upper() if len(word) >= 2 else word.upper()
    middle_index = min(max(len(word) // 2, 0), len(word) - 1)
    middle_letter = word[middle_index].upper()
    hints = [
        f"Starts with '{prefix}'.",
        f"Ends with '{suffix}'.",
        f"Letter #{middle_index + 1} is '{middle_letter}'.",
        f"Contains vowels: {', '.join(v.upper() for v in vowels)}." if vowels else "Contains no standard vowels (A, E, I, O, U).",
    ]
    if unique_letters:
        letter = unique_letters[0]
        count = word.count(letter)
        hints.append(f"Letter '{letter.upper()}' appears {count} time(s).")
    else:
        hints.append("Letters repeat in interesting ways.")
    return hints[:5]


def make_btn(parent, text, cmd, width=18, variant="primary"):
    styles = {
        "primary": {"bg": PRIMARY, "fg": "white", "hover": HOVER,
                     "glow": "#a5b4fc", "shadow": "#4338ca"},
        "accent": {"bg": ACCENT, "fg": ACCENT_TEXT, "hover": ACCENT_HOVER,
                    "glow": "#fdba74", "shadow": "#c2410c"},
    }
    colors = styles.get(variant, styles["primary"])
    base_color = colors["bg"]
    hover_color = colors["hover"]
    text_color = colors["fg"]
    glow_color = colors["glow"]
    shadow_color = colors["shadow"]

    wrapper = tk.Frame(parent, bg=parent.cget("bg"))

    shadow = tk.Frame(wrapper, bg=shadow_color, height=4)
    shadow.pack(fill="x", padx=6)

    btn = tk.Button(
        wrapper,
        text=text,
        command=cmd,
        width=width,
        height=2,
        bg=base_color,
        fg=text_color,
        font=("Segoe UI", 12, "bold"),
        bd=0,
        activebackground=hover_color,
        activeforeground=text_color,
        cursor="hand2",
        relief="flat",
    )
    btn.pack()

    shimmer_job = [None]

    def shimmer(step=0):
        if not btn.winfo_exists():
            return
        cycle = ["#e2e8f0", glow_color, hover_color, glow_color, "#e2e8f0", base_color]
        if step >= len(cycle):
            btn.config(bg=hover_color)
            return
        btn.config(bg=cycle[step])
        shimmer_job[0] = btn.after(50, lambda: shimmer(step + 1))

    def on_enter(_event):
        btn.config(bg=hover_color, font=("Segoe UI", 13, "bold"))
        shadow.config(bg=glow_color, height=5)
        shimmer()

    def on_leave(_event):
        if shimmer_job[0] is not None:
            try:
                btn.after_cancel(shimmer_job[0])
            except Exception:
                pass
            shimmer_job[0] = None
        btn.config(bg=base_color, font=("Segoe UI", 12, "bold"))
        shadow.config(bg=shadow_color, height=4)

    def on_press(_event):
        btn.config(relief="sunken")
        shadow.config(height=2)

    def on_release(_event):
        btn.config(relief="flat")
        shadow.config(height=4)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.bind("<ButtonPress-1>", on_press)
    btn.bind("<ButtonRelease-1>", on_release)
    wrapper.btn = btn
    return wrapper


def make_card_window(title, width=520, height=320):
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    win.minsize(width, height)
    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2, 0)
    win.geometry(f"{width}x{height}+{x}+{y}")
    register_bg_target(win)

    card = tk.Frame(win, bg=CARD, padx=24, pady=24)
    card.pack(expand=True, fill="both", padx=20, pady=20)
    return win, card


def styled_label(parent, text=None, textvariable=None, font=("Segoe UI", 12), fg=TEXT):
    return tk.Label(parent, text=text, textvariable=textvariable, font=font, bg=CARD, fg=fg)


def styled_entry(parent):
    return tk.Entry(
        parent,
        font=("Segoe UI", 12),
        justify="center",
        bg="#f8fafc",
        fg="#0f172a",
        relief="flat",
        width=18,
    )


# ── How-to-Play Intro & End-of-Game Helpers ───────────────────────────────
GAME_INSTRUCTIONS = {
    "hangman": {
        "title": "💀  How to Play: Hangman",
        "text": (
            "A secret word is hidden behind underscores.\n\n"
            "• Type one letter at a time and press Guess.\n"
            "• Correct letters are revealed in the word.\n"
            "• Wrong letters add a body part to the hangman (9 max).\n"
            "• Use Hints to reveal clues — but each hint costs 1 point!\n"
            "• Solve the word before the hangman is complete to win.\n\n"
            "⭐ BONUS: Think you know the word? Type it in the\n"
            "'Guess the Word' box for +3 extra points!\n"
            "But be careful — a wrong guess costs 2 attempts,\n"
            "and using ANY hint disables the bonus.\n\n"
            "Score: up to 7 points (minus hints used) + 3 bonus."
        ),
    },
    "number": {
        "title": "🔢  How to Play: Number Game",
        "text": (
            "Three rounds of increasing difficulty!\n\n"
            "• Round 1 (Easy): guess 1–100 in 45 s, 7 attempts\n"
            "• Round 2 (Medium): guess 1–500 in 40 s, 9 attempts\n"
            "• Round 3 (Hard): guess 1–1000 in 35 s, 10 attempts\n\n"
            "After each guess you get a Hot / Warm / Cool / Cold / Freezing hint\n"
            "telling you how close you are.\n\n"
            "Score: up to 10 points per round (30 total)."
        ),
    },
    "word": {
        "title": "📝  How to Play: Word Challenge",
        "text": (
            "Guess the hidden word from a descriptive clue!\n\n"
            "• Round 1 (Easy): short words, 5 attempts\n"
            "• Round 2 (Medium): medium words, 4 attempts\n"
            "• Round 3 (Hard): long words, 3 attempts\n\n"
            "• Type your full word guess and press Guess.\n"
            "• Wrong guesses reveal some letters as a hint.\n"
            "• Use the Hint button for extra clues (costs 1 point each).\n\n"
            "Score: up to 10 points per round (30 total)."
        ),
    },
    "math": {
        "title": "🧮  How to Play: Math Game",
        "text": (
            "Three timed sections — 90 seconds each!\n\n"
            "• Section 1: Algebra  (solve for x)\n"
            "• Section 2: Patterns  (find the next number)\n"
            "• Section 3: Multiplication  (quick multiply)\n\n"
            "• Type your answer and press Submit.\n"
            "• Answer as many as you can before time runs out.\n"
            "• Each section is worth up to 10 points.\n\n"
            "Score: up to 30 points total."
        ),
    },
    "brainiac": {
        "title": "🧬  Brainiac",
        "text": (
            "The ULTIMATE challenge zone — only for 90%+ IQ scorers!\n\n"
            "A collection of elite mini-games that test your\n"
            "perception, reflexes, and mental precision.\n\n"
            "Select a game from the Brainiac menu to begin."
        ),
    },
    "ten_second": {
        "title": "⏱️  How to Play: 10-Second Test",
        "text": (
            "How accurately can you judge 10 seconds?\n\n"
            "• Press 'Start' to begin the test.\n"
            "• A clock will appear on screen — but it gives NO hints\n"
            "  about when 10 seconds have passed!\n"
            "• Click 'Stop' when YOU think exactly 10 seconds\n"
            "  have elapsed.\n\n"
            "• The closer you are to 10.00 s, the higher your score.\n"
            "• Perfect (within 0.2 s) = 10 pts\n"
            "• Within 0.5 s = 8 pts\n"
            "• Within 1.0 s = 6 pts\n"
            "• Within 2.0 s = 4 pts\n"
            "• Within 3.0 s = 2 pts\n"
            "• Otherwise = 0 pts\n\n"
            "Trust your inner clock. No counting out loud!"
        ),
    },
    "memory_match": {
        "title": "🧠  How to Play: Memory Match",
        "text": (
            "How sharp is your memory?\n\n"
            "• Each round shows a NAME and a SHAPE on screen\n"
            "  for a few seconds — memorise them!\n"
            "• Then the screen clears and you must pick the\n"
            "  correct name and shape from a grid of options.\n\n"
            "• 3 rounds with increasing difficulty:\n"
            "  Round 1 — 1 pair  (4 choices)\n"
            "  Round 2 — 2 pairs (6 choices)\n"
            "  Round 3 — 3 pairs (8 choices)\n\n"
            "• Each correct pick = points. Max 30 pts.\n"
            "• Pay close attention — the decoys look similar!"
        ),
    },
}


def show_how_to_play(game_key, on_play, on_exit):
    """Show a How-to-Play window. Calls on_play() or on_exit() when a button is pressed."""
    info = GAME_INSTRUCTIONS[game_key]
    win, card = make_card_window(info["title"], width=560, height=560)

    styled_label(card, text=info["title"], font=("Segoe UI", 18, "bold")).pack(pady=(0, 12))

    styled_label(
        card, text=info["text"],
        font=("Segoe UI", 11), fg=SUBTLE,
    ).pack(fill="both", expand=True, padx=10, pady=(0, 16))
    # make label wrap nicely
    card.winfo_children()[-1].config(wraplength=480, justify="left", anchor="nw")

    btn_row = tk.Frame(card, bg=CARD)
    btn_row.pack(fill="x", pady=(4, 0))

    def do_exit():
        win.destroy()
        if on_exit:
            on_exit()

    def do_play():
        win.destroy()
        on_play()

    make_btn(btn_row, "❌  Exit", do_exit, width=12).pack(side="left", padx=(10, 8))
    make_btn(btn_row, "🎮  Ready to Play!", do_play, width=16, variant="accent").pack(side="right", padx=(8, 10))

    win.protocol("WM_DELETE_WINDOW", do_exit)


def create_banner(parent):
    canvas = tk.Canvas(parent, height=60, bg="#020617", highlightthickness=0)
    canvas.pack(fill="x")

    start_x = -260
    title = "Peji's Games"

    glow = canvas.create_text(
        start_x,
        26,
        text=title,
        font=("Segoe UI", 22, "bold"),
        fill="#6366f1",
        anchor="w",
    )
    text = canvas.create_text(
        start_x,
        25,
        text=title,
        font=("Segoe UI", 22, "bold"),
        fill="#c7d2fe",
        anchor="w",
    )

    def animate():
        if not canvas.winfo_exists():
            return

        canvas.move(text, 1, 0)
        canvas.move(glow, 1, 0)

        x = canvas.coords(text)[0]
        if x > canvas.winfo_width():
            canvas.coords(text, start_x, 25)
            canvas.coords(glow, start_x, 26)

        canvas.after(10, animate)

    animate()


class HangmanCanvas:
    def __init__(self, parent):
        self.canvas = tk.Canvas(parent, width=220, height=260, bg=CARD, highlightthickness=0)
        self.canvas.pack(side="left", padx=(0, 10), pady=10)

        # draw gallows
        self.canvas.create_line(20, 240, 180, 240, fill=TEXT, width=4)  # base
        self.canvas.create_line(60, 240, 60, 20, fill=TEXT, width=4)    # pole
        self.canvas.create_line(60, 20, 140, 20, fill=TEXT, width=4)    # beam
        self.canvas.create_line(140, 20, 140, 44, fill=TEXT, width=2)   # rope

        self.parts_base = [None] * 9
        self.parts_items = [None] * 9

    # animation helpers use self.canvas
    def animate_circle(self, cx, cy, r, steps=15, delay=15, step=0, item=None):
        c = self.canvas
        if item is None:
            item = c.create_oval(cx, cy, cx, cy, outline=TEXT, width=2)
        if step >= steps:
            return
        frac = (step + 1) / steps
        rr = r * frac
        c.coords(item, cx - rr, cy - rr, cx + rr, cy + rr)
        c.after(delay, lambda: self.animate_circle(cx, cy, r, steps, delay, step + 1, item))

    def animate_line(self, x0, y0, x1, y1, steps=18, delay=12, step=0, item=None):
        c = self.canvas
        if item is None:
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=2)
        if step >= steps:
            c.coords(item, x0, y0, x1, y1)
            return
        frac = (step + 1) / steps
        nx = x0 + (x1 - x0) * frac
        ny = y0 + (y1 - y0) * frac
        c.coords(item, x0, y0, nx, ny)
        c.after(delay, lambda: self.animate_line(x0, y0, x1, y1, steps, delay, step + 1, item))

    def draw_part(self, index):
        c = self.canvas
        if index == 0:
            cx, cy, r = 140, 64, 20
            item = c.create_oval(cx - 1, cy - 1, cx + 1, cy + 1, outline=TEXT, width=3)
            self.parts_base[0] = ("oval", cx, cy, r)
            self.parts_items[0] = [item]
            self.animate_circle(cx, cy, r, item=item)
        elif index == 1:
            x0, y0, x1, y1 = 140, 84, 140, 150
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=4)
            self.parts_base[1] = ("line", x0, y0, x1, y1)
            self.parts_items[1] = [item]
            self.animate_line(x0, y0, x1, y1, steps=20, delay=10, item=item)
        elif index == 2:
            x0, y0, x1, y1 = 140, 100, 110, 120
            joint = c.create_oval(x0 - 3, y0 - 3, x0 + 3, y0 + 3, fill=TEXT, outline=TEXT)
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=3)
            self.parts_base[2] = ("line", x0, y0, x1, y1)
            self.parts_items[2] = [item, joint]
            self.animate_line(x0, y0, x1, y1, item=item)
        elif index == 3:
            x0, y0, x1, y1 = 140, 100, 170, 120
            joint = c.create_oval(x0 - 3, y0 - 3, x0 + 3, y0 + 3, fill=TEXT, outline=TEXT)
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=3)
            self.parts_base[3] = ("line", x0, y0, x1, y1)
            self.parts_items[3] = [item, joint]
            self.animate_line(x0, y0, x1, y1, item=item)
        elif index == 4:
            x0, y0, x1, y1 = 140, 150, 118, 190
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=3)
            self.parts_base[4] = ("line", x0, y0, x1, y1)
            self.parts_items[4] = [item]
            self.animate_line(x0, y0, x1, y1, item=item)
        elif index == 5:
            x0, y0, x1, y1 = 140, 150, 162, 190
            item = c.create_line(x0, y0, x0, y0, fill=TEXT, width=3)
            self.parts_base[5] = ("line", x0, y0, x1, y1)
            self.parts_items[5] = [item]
            self.animate_line(x0, y0, x1, y1, item=item)
        elif index == 6:
            # left eye
            cx, cy, r = 133, 60, 3
            item = c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=TEXT, outline=TEXT)
            self.parts_base[6] = ("oval", cx, cy, r)
            self.parts_items[6] = [item]
        elif index == 7:
            # right eye
            cx, cy, r = 147, 60, 3
            item = c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=TEXT, outline=TEXT)
            self.parts_base[7] = ("oval", cx, cy, r)
            self.parts_items[7] = [item]
        elif index == 8:
            # hair (three lines on top of head)
            items = []
            lines = [(135, 44, 130, 34), (140, 44, 140, 32), (145, 44, 150, 34)]
            for lx0, ly0, lx1, ly1 in lines:
                item = c.create_line(lx0, ly0, lx1, ly1, fill=TEXT, width=2)
                items.append(item)
            self.parts_base[8] = ("line", 140, 44, 140, 32)
            self.parts_items[8] = items

    def rotate_point(self, x, y, cx, cy, angle):
        s = math.sin(angle)
        c = math.cos(angle)
        x -= cx
        y -= cy
        nx = x * c - y * s
        ny = x * s + y * c
        return nx + cx, ny + cy

    def swing_and_fall(self):
        c = self.canvas
        px, py = 140, 44
        max_angle = math.radians(20)
        steps = 36

        primitives = []
        for base, items in zip(self.parts_base, self.parts_items):
            if base is None or not items:
                continue
            typ = base[0]
            animated_item = items[0]
            if typ == "oval":
                _, cx, cy, r = base
                primitives.append((typ, cx, cy, r, animated_item))
            elif typ == "line":
                _, x0, y0, x1, y1 = base
                primitives.append((typ, x0, y0, x1, y1, animated_item))

        # start sound just before swinging
        _play_melody_async([(900, 120), (700, 180), (560, 260), (360, 700)], volume=0.5)

        for i in range(steps):
            ang = max_angle * math.sin(i * 2 * math.pi / (steps / 2))
            for prim in primitives:
                if prim[0] == "oval":
                    _, cx, cy, r, item = prim
                    nx, ny = self.rotate_point(cx, cy, px, py, ang)
                    c.coords(item, nx - r, ny - r, nx + r, ny + r)
                else:
                    _, x0, y0, x1, y1, item = prim
                    nx0, ny0 = self.rotate_point(x0, y0, px, py, ang)
                    nx1, ny1 = self.rotate_point(x1, y1, px, py, ang)
                    c.coords(item, nx0, ny0, nx1, ny1)
            c.update()
            c.after(20)

        fall_steps = 24
        for i in range(fall_steps):
            drop = i * 6
            rot = math.radians(60) * (i / fall_steps)
            for prim in primitives:
                if prim[0] == "oval":
                    _, cx, cy, r, item = prim
                    nx, ny = self.rotate_point(cx, cy + drop, px, py, rot)
                    c.coords(item, nx - r, ny - r, nx + r, ny + r)
                else:
                    _, x0, y0, x1, y1, item = prim
                    nx0, ny0 = self.rotate_point(x0, y0 + drop, px, py, rot)
                    nx1, ny1 = self.rotate_point(x1, y1 + drop, px, py, rot)
                    c.coords(item, nx0, ny0, nx1, ny1)
            c.update()
            c.after(30)

    def trigger_fall(self):
        for i in range(9):
            if self.parts_base[i] is None:
                self.draw_part(i)
                self.canvas.update()
                self.canvas.after(80)
        self.swing_and_fall()


def open_hangman(test_callback=None):
    def _start_game():
        _run_hangman(test_callback)
    show_how_to_play("hangman", _start_game, on_exit=None)


def _run_hangman(test_callback=None):
    word = random.choice(HANGMAN_WORDS)
    hints = build_word_hints(word)
    max_hints = min(5, len(hints))
    hints_used = 0
    bonus_eligible = True
    guessed = set()
    wrong = []
    attempts = 9

    _win, card = make_card_window("Hangman", width=980, height=640)

    word_var = tk.StringVar()
    status_var = tk.StringVar(value=f"Attempts left: {attempts}")
    wrong_var = tk.StringVar(value="Wrong letters: None")
    hint_counter_var = tk.StringVar(value=f"Hints used: 0/{max_hints}")
    hint_helper_var = tk.StringVar(value=f"Use a hint to reveal info (max {max_hints}, costs 1 point each).")
    hint_text_var = tk.StringVar(value="Press the Hint button to reveal clues.")

    hangman = HangmanCanvas(card)

    info_frame = tk.Frame(card, bg=CARD, width=560)
    info_frame.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
    info_frame.pack_propagate(False)

    play_opening_music()

    entry = None
    guess_btn = None
    hint_btn = None
    hint_box = None
    guess_word_btn = None
    guess_word_entry = None
    guess_word_frame = None

    def update_display():
        display = " ".join(letter if letter in guessed else "_" for letter in word)
        word_var.set(display)
        wrong_var.set("Wrong letters: " + (" ".join(wrong) if wrong else "None"))

    def update_hint_box(text, append=False):
        if append and text:
            current = hint_text_var.get().strip()
            new_text = (current + "\n" + text) if current else text
            hint_text_var.set(new_text)
        else:
            hint_text_var.set(text or "")

    def finish(message, game_score=0):
        status_var.set(message)
        if entry is not None:
            entry.config(state="disabled")
        if guess_btn is not None:
            guess_btn.btn.config(state="disabled")
        if hint_btn is not None:
            hint_btn.btn.config(state="disabled")
        if guess_word_btn is not None:
            guess_word_btn.btn.config(state="disabled")
        if guess_word_entry is not None:
            guess_word_entry.config(state="disabled")
        try:
            lbl_status.lift()
        except Exception:
            pass
        try:
            _win.lift()
        except Exception:
            pass
        end_row = tk.Frame(info_frame, bg=CARD)
        end_row.pack(fill="x", pady=(10, 4))
        def play_again():
            _win.destroy()
            _run_hangman(test_callback)
        make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
        make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")
        if test_callback is not None:
            test_callback(game_score)

    def finalize_after():
        nonlocal attempts
        attempts = 0
        update_display()
        play_lose_sound()
        finish(f"You lose. The word was '{word}'.", game_score=0)

    def guess(_event=None):
        nonlocal attempts

        if entry is None or entry.cget("state") == "disabled":
            return

        letter = entry.get().strip().lower()
        entry.delete(0, tk.END)

        if len(letter) != 1 or not letter.isalpha():
            status_var.set("Enter one letter from A-Z.")
            return
        if letter in guessed or letter in wrong:
            status_var.set("You already tried that letter.")
            return

        if letter in word:
            guessed.add(letter)
            play_correct_sound()
            update_display()
            if all(l in guessed for l in word):
                points = 7
                add_score(points, celebrate=True, message="Hangman solved")
                finish(f"You win! +{points} points", game_score=max(7 - hints_used, 0))
        else:
            wrong.append(letter)
            play_wrong_sound()
            part_index = len(wrong) - 1
            hangman.draw_part(part_index)

            def after_anim():
                nonlocal attempts
                if part_index == 8:
                    card.after(300, hangman.swing_and_fall)
                    card.after(2000, finalize_after)
                else:
                    attempts -= 1
                    update_display()
                    if all(l in guessed for l in word):
                        points = 7
                        add_score(points, celebrate=True, message="Hangman solved")
                        finish(f"You win! +{points} points", game_score=max(7 - hints_used, 0))
                    elif attempts == 0:
                        finish(f"You lose. The word was '{word}'.", game_score=0)
                    else:
                        status_var.set(f"Attempts left: {attempts}")

            card.after(400, after_anim)

    def use_hint():
        nonlocal hints_used, bonus_eligible
        if hints_used >= max_hints:
            status_var.set("No hints left.")
            return
        bonus_eligible = False
        if guess_word_btn is not None:
            guess_word_btn.btn.config(state="disabled")
        if guess_word_entry is not None:
            guess_word_entry.config(state="disabled")
        hint_message = hints[hints_used % len(hints)]
        hints_used += 1
        hint_counter_var.set(f"Hints used: {hints_used}/{max_hints}")
        line = f"{hints_used}. {hint_message}"
        if hints_used == 1:
            hint_helper_var.set("Hints revealed:")
            update_hint_box(line)
        else:
            update_hint_box(line, append=True)
        add_score(-1)
        status_var.set("Hint revealed (-1 score).")
        if hints_used >= max_hints and hint_btn is not None:
            hint_btn.btn.config(state="disabled")

    lbl_title = styled_label(info_frame, text="Guess the hidden word", font=("Segoe UI", 14, "bold"))
    lbl_title.pack(pady=(0, 10))
    lbl_word = styled_label(info_frame, textvariable=word_var, font=("Consolas", 22, "bold"))
    lbl_word.pack(pady=10, fill="x")

    status_row = tk.Frame(info_frame, bg=CARD)
    status_row.pack(fill="x")
    lbl_wrong = styled_label(status_row, textvariable=wrong_var, fg=SUBTLE)
    lbl_wrong.pack(side="left", fill="both", expand=True)
    lbl_status = styled_label(status_row, textvariable=status_var)
    lbl_status.pack(side="right")
    lbl_status.config(wraplength=240, justify="right")

    entry = styled_entry(info_frame)
    entry.pack(fill="x", pady=(12, 6))
    entry.focus_set()
    entry.bind("<Return>", guess)

    button_row = tk.Frame(info_frame, bg=CARD)
    button_row.pack(fill="x", pady=(0, 6))

    hint_btn = make_btn(button_row, "Hint (-1 score)", use_hint, width=14)
    hint_btn.pack(side="left", padx=(0, 8))

    guess_btn = make_btn(button_row, "Guess", guess, width=12, variant="accent")
    guess_btn.pack(side="right")

    # ── Guess-the-Word bonus section ──
    guess_word_frame = tk.Frame(info_frame, bg="#1a2744", highlightbackground="#f97316",
                                highlightthickness=2, bd=0)
    guess_word_frame.pack(fill="x", pady=(8, 4), padx=4)

    gw_title = tk.Label(guess_word_frame, text="\u2b50  Guess the Word  (+3 bonus)",
                         font=("Segoe UI", 11, "bold"), bg="#1a2744", fg="#f97316")
    gw_title.pack(fill="x", padx=10, pady=(6, 2))

    gw_subtitle = tk.Label(guess_word_frame,
                            text="Type the full word for extra points! (disabled if hints used)",
                            font=("Segoe UI", 9), bg="#1a2744", fg=SUBTLE)
    gw_subtitle.pack(fill="x", padx=10, pady=(0, 4))

    gw_row = tk.Frame(guess_word_frame, bg="#1a2744")
    gw_row.pack(fill="x", padx=10, pady=(0, 8))

    guess_word_entry = styled_entry(gw_row)
    guess_word_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

    def guess_full_word(_event=None):
        nonlocal attempts
        if not bonus_eligible:
            status_var.set("Bonus not available \u2014 you used a hint.")
            return
        if guess_word_entry is None or guess_word_entry.cget("state") == "disabled":
            return
        typed = guess_word_entry.get().strip().lower()
        guess_word_entry.delete(0, tk.END)
        if not typed:
            status_var.set("Type the full word to guess.")
            return
        if typed == word.lower():
            # Correct! Reveal all letters and award bonus
            for ch in word:
                guessed.add(ch)
            update_display()
            play_correct_sound()
            bonus = 3
            points = 7 + bonus
            add_score(points, celebrate=True, message=f"Hangman solved + {bonus} bonus!")
            finish(f"\U0001f31f Amazing! +{points} pts (word guessed!)",
                   game_score=max(7 - hints_used, 0) + bonus)
        else:
            # Wrong guess — lose 2 attempts as penalty
            play_wrong_sound()
            penalty = min(2, attempts)
            for _ in range(penalty):
                if len(wrong) < 9:
                    wrong.append("*")
                    hangman.draw_part(len(wrong) - 1)
                    attempts -= 1
            update_display()
            if attempts <= 0:
                finish(f"Wrong word! The word was '{word}'.", game_score=0)
            else:
                status_var.set(f"Wrong word! Lost 2 attempts. ({attempts} left)")

    guess_word_entry.bind("<Return>", guess_full_word)

    guess_word_btn = make_btn(gw_row, "\u2b50 Guess Word", guess_full_word, width=14, variant="accent")
    guess_word_btn.pack(side="right")

    lbl_hint_counter = styled_label(info_frame, textvariable=hint_counter_var, fg=SUBTLE)
    lbl_hint_counter.pack(fill="x", pady=(4, 0))

    hint_helper_label = styled_label(info_frame, textvariable=hint_helper_var, fg=SUBTLE)
    hint_helper_label.config(wraplength=360, justify="left")
    hint_helper_label.pack(fill="x", pady=(0, 4))

    hint_panel = tk.Frame(
        info_frame,
        bg="#e0f2fe",  # very light background to guarantee contrast
        highlightbackground="#0ea5e9",
        highlightthickness=2,
        bd=1,
        relief="solid",
    )
    hint_panel.pack(fill="x", pady=(6, 6), padx=4)
    hint_panel.lift()

    lbl_hint_title = tk.Label(
        hint_panel,
        text="Hints",
        font=("Segoe UI", 11, "bold"),
        bg="#e0f2fe",
        fg="#0b1727",
        anchor="w",
    )
    lbl_hint_title.pack(fill="x", padx=10, pady=(6, 0))

    hint_box = tk.Label(
        hint_panel,
        textvariable=hint_text_var,
        bg="#ffffff",
        fg="#0b1727",
        font=("Segoe UI", 11, "bold"),
        anchor="nw",
        justify="left",
        wraplength=520,  # wider wrap to avoid cutting long hints
        padx=8,
        pady=6,
        bd=0,
        relief="flat",
    )
    hint_box.pack(fill="x", padx=10, pady=(4, 10))
    hint_box.lift()

    trigger_btn = make_btn(info_frame, "Trigger Fall", hangman.trigger_fall, width=12)
    trigger_btn.pack(pady=(4, 6))

    update_display()


def open_number(test_callback=None):
    def _start_game():
        _run_number(test_callback)
    show_how_to_play("number", _start_game, on_exit=None)


def _run_number(test_callback=None):
    rounds = [
        {"range": 100, "max_attempts": 7, "time": 45, "label": "Round 1: Easy (1–100)"},
        {"range": 500, "max_attempts": 9, "time": 40, "label": "Round 2: Medium (1–500)"},
        {"range": 1000, "max_attempts": 10, "time": 35, "label": "Round 3: Hard (1–1000)"},
    ]
    round_scores = []
    current = {"round": 0, "number": 0, "attempts": 0, "done": False}
    timer_job = {"id": None}
    pile_items = []  # list of canvas item ids in the pile

    PILE_W = 180
    PILE_H = 420
    BLOCK_H = 36
    FALL_STEPS = 14
    FALL_DELAY = 18

    _win, card = make_card_window("Number Game", width=980, height=640)
    play_opening_music()

    header = tk.Frame(card, bg=CARD)
    header.pack(fill="x", pady=(0, 6))
    round_var = tk.StringVar(value="")
    timer_var = tk.StringVar(value="")
    styled_label(header, textvariable=round_var, font=("Segoe UI", 14, "bold")).pack(side="left")
    styled_label(header, textvariable=timer_var, font=("Segoe UI", 13, "bold"), fg=ACCENT).pack(side="right")

    body = tk.Frame(card, bg=CARD)
    body.pack(fill="both", expand=True, pady=(0, 4))

    # left side: controls
    left = tk.Frame(body, bg=CARD)
    left.pack(side="left", fill="both", expand=True, padx=(10, 6))

    status_var = tk.StringVar(value="")
    attempts_var = tk.StringVar(value="")
    result_var = tk.StringVar(value="")

    styled_label(left, textvariable=attempts_var, font=("Segoe UI", 12), fg=SUBTLE).pack(pady=(0, 4))

    entry = styled_entry(left)
    entry.pack(fill="x", padx=40, pady=(4, 4))
    entry.focus_set()

    status_lbl = styled_label(left, textvariable=status_var, font=("Segoe UI", 12))
    status_lbl.pack(pady=(4, 4))

    result_lbl = styled_label(left, textvariable=result_var, font=("Segoe UI", 14, "bold"), fg=ACCENT)
    result_lbl.config(wraplength=500, justify="center")
    result_lbl.pack(pady=(10, 0), fill="x")

    # right side: guess pile canvas
    right = tk.Frame(body, bg=CARD)
    right.pack(side="right", fill="y", padx=(6, 10))

    styled_label(right, text="Guesses", font=("Segoe UI", 11, "bold"), fg=SUBTLE).pack(pady=(0, 2))
    pile_canvas = tk.Canvas(right, width=PILE_W, height=PILE_H, bg="#131c2e", highlightthickness=1, highlightbackground="#334155")
    pile_canvas.pack()

    def get_guess_color(guess_val, target, rng):
        diff = abs(guess_val - target)
        pct = diff / rng
        if pct <= 0.02:
            return "#ef4444"  # red/boiling
        elif pct <= 0.05:
            return "#f97316"  # orange/very hot
        elif pct <= 0.10:
            return "#eab308"  # yellow/hot
        elif pct <= 0.20:
            return "#a3e635"  # lime/warm
        elif pct <= 0.35:
            return "#38bdf8"  # sky/cool
        elif pct <= 0.50:
            return "#6366f1"  # indigo/cold
        else:
            return "#818cf8"  # light indigo/freezing

    def animate_fall(block_id, text_id, start_y, target_y, step=0):
        if step >= FALL_STEPS:
            pile_canvas.coords(block_id, 4, target_y, PILE_W - 4, target_y + BLOCK_H - 2)
            pile_canvas.coords(text_id, PILE_W // 2, target_y + BLOCK_H // 2)
            return
        progress = (step + 1) / FALL_STEPS
        eased = progress * progress  # ease-in
        cy = start_y + (target_y - start_y) * eased
        pile_canvas.coords(block_id, 4, cy, PILE_W - 4, cy + BLOCK_H - 2)
        pile_canvas.coords(text_id, PILE_W // 2, cy + BLOCK_H // 2)
        pile_canvas.after(FALL_DELAY, lambda: animate_fall(block_id, text_id, start_y, target_y, step + 1))

    def add_to_pile(guess_val, is_correct):
        if is_correct:
            color = "#22c55e"  # green for correct
        else:
            color = get_guess_color(guess_val, current["number"], rounds[current["round"]]["range"])
        n = len(pile_items)
        target_y = PILE_H - (n + 1) * BLOCK_H
        if target_y < 0:
            target_y = 0
        start_y = -BLOCK_H  # start above canvas
        direction = "▲" if guess_val < current["number"] else "▼"
        label = f"{guess_val}  {direction}" if not is_correct else f"✓ {guess_val} ✓"
        block = pile_canvas.create_rectangle(4, start_y, PILE_W - 4, start_y + BLOCK_H - 2, fill=color, outline="", width=0)
        text = pile_canvas.create_text(PILE_W // 2, start_y + BLOCK_H // 2, text=label, fill="#0f172a" if is_correct else "#ffffff", font=("Segoe UI", 13, "bold"))
        pile_items.append((block, text))
        animate_fall(block, text, start_y, target_y)

    def clear_pile():
        for block, text in pile_items:
            pile_canvas.delete(block)
            pile_canvas.delete(text)
        pile_items.clear()

    def proximity_hint(guess_val, target, rng):
        diff = abs(guess_val - target)
        pct = diff / rng
        direction = "low" if guess_val < target else "high"
        if pct <= 0.02:
            return f"Too {direction} — BOILING! 🔥"
        elif pct <= 0.05:
            return f"Too {direction} — Very hot!"
        elif pct <= 0.10:
            return f"Too {direction} — Hot"
        elif pct <= 0.20:
            return f"Too {direction} — Warm"
        elif pct <= 0.35:
            return f"Too {direction} — Cool"
        elif pct <= 0.50:
            return f"Too {direction} — Cold"
        else:
            return f"Too {direction} — Freezing! 🥶"

    def finish_all():
        current["done"] = True
        if timer_job["id"] is not None:
            try:
                _win.after_cancel(timer_job["id"])
            except Exception:
                pass
            timer_job["id"] = None
        entry.pack_forget()
        guess_btn.pack_forget()
        status_lbl.pack_forget()
        round_var.set("Number Game Complete!")
        timer_var.set("")
        attempts_var.set("")
        total = sum(round_scores)
        parts = [f"R{i + 1}: {s}/10" for i, s in enumerate(round_scores)]
        result_var.set("  |  ".join(parts) + f"\n\nTotal: {total}/30")
        end_row = tk.Frame(left, bg=CARD)
        end_row.pack(fill="x", pady=(12, 0))
        def play_again():
            _win.destroy()
            _run_number(test_callback)
        make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
        make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")
        add_score(total, celebrate=total >= 15, message=f"Number: {total}/30")
        if test_callback is not None:
            test_callback(total)

    def finish_round(won, pts):
        if timer_job["id"] is not None:
            try:
                _win.after_cancel(timer_job["id"])
            except Exception:
                pass
            timer_job["id"] = None
        round_scores.append(pts)
        r = current["round"]
        rnd = rounds[r]
        if won:
            play_correct_sound()
            status_var.set(f"Correct! The number was {current['number']}. +{pts} pts")
        else:
            play_lose_sound()
            status_var.set(f"Round over! The number was {current['number']}. +0 pts")
        entry.config(state="disabled")
        guess_btn.btn.config(state="disabled")
        if r + 1 < len(rounds):
            def next_round():
                start_round(r + 1)
            _win.after(1800, next_round)
        else:
            _win.after(1800, finish_all)

    def tick(remaining):
        if current["done"] or not _win.winfo_exists():
            return
        if remaining <= 0:
            finish_round(False, 0)
            return
        label = f"Time: {remaining}s"
        if remaining <= 5:
            label += " ⚠"
            play_tick_sound()
        timer_var.set(label)
        timer_job["id"] = _win.after(1000, lambda: tick(remaining - 1))

    def guess(_event=None):
        if current["done"] or entry.cget("state") == "disabled":
            return
        r = current["round"]
        rnd = rounds[r]
        raw_value = entry.get().strip()
        if not raw_value.isdigit():
            status_var.set("Please enter digits only.")
            return
        guess_value = int(raw_value)
        if not 1 <= guess_value <= rnd["range"]:
            status_var.set(f"Choose a number from 1 to {rnd['range']}.")
            return
        current["attempts"] += 1
        entry.delete(0, tk.END)
        att = current["attempts"]
        max_att = rnd["max_attempts"]
        attempts_var.set(f"Attempts: {att}/{max_att}")
        if guess_value == current["number"]:
            add_to_pile(guess_value, True)
            pts = max(max_att + 1 - att, 1)
            pts = min(pts, 10)
            finish_round(True, pts)
        elif att >= max_att:
            add_to_pile(guess_value, False)
            play_wrong_sound()
            finish_round(False, 0)
        else:
            add_to_pile(guess_value, False)
            play_wrong_sound()
            hint = proximity_hint(guess_value, current["number"], rnd["range"])
            status_var.set(f"{hint}  (Attempt {att}/{max_att})")

    entry.bind("<Return>", guess)

    guess_btn = make_btn(left, "Guess", guess, width=12, variant="accent")
    guess_btn.pack(pady=(4, 0))

    def start_round(idx):
        current["round"] = idx
        rnd = rounds[idx]
        current["number"] = random.randint(1, rnd["range"])
        current["attempts"] = 0
        clear_pile()
        round_var.set(rnd["label"])
        timer_var.set(f"Time: {rnd['time']}s")
        attempts_var.set(f"Attempts: 0/{rnd['max_attempts']}")
        status_var.set(f"Guess a number from 1 to {rnd['range']}")
        result_var.set("")
        entry.config(state="normal")
        entry.delete(0, tk.END)
        entry.focus_set()
        guess_btn.btn.config(state="normal")
        tick(rnd["time"])

    def on_close():
        current["done"] = True
        if timer_job["id"] is not None:
            try:
                _win.after_cancel(timer_job["id"])
            except Exception:
                pass
        _win.destroy()

    _win.protocol("WM_DELETE_WINDOW", on_close)
    start_round(0)


def open_word(test_callback=None):
    def _start_game():
        _run_word(test_callback)
    show_how_to_play("word", _start_game, on_exit=None)


def _run_word(test_callback=None):
    all_words = [
        {"word": "python", "clue": "A slithering reptile that also powers millions of lines of code worldwide"},
        {"word": "keyboard", "clue": "Your fingers dance across this device every day to turn thoughts into text"},
        {"word": "network", "clue": "An invisible web that lets machines across the globe whisper to each other"},
        {"word": "algorithm", "clue": "A recipe of logical steps that tells a computer exactly how to solve a problem"},
        {"word": "galaxy", "clue": "A vast spinning island of billions of stars floating through the cosmos"},
        {"word": "telescope", "clue": "Galileo used one to see Jupiter's moons; today they peer at the edge of the universe"},
        {"word": "volcano", "clue": "A mountain with a fiery temper that spews molten rock from deep within the Earth"},
        {"word": "orchestra", "clue": "Dozens of musicians playing strings, brass, and woodwinds together in harmony"},
        {"word": "dinosaur", "clue": "Gigantic creatures that ruled the Earth for over 160 million years before vanishing"},
        {"word": "compass", "clue": "A small magnetized needle that always points the way north for lost travelers"},
        {"word": "blueprint", "clue": "An architect draws this detailed plan before a single brick is laid"},
        {"word": "lightning", "clue": "A blinding flash that cracks across the sky carrying a billion volts of electricity"},
        {"word": "chocolate", "clue": "Made from roasted cacao beans, this sweet treat melts on your tongue"},
        {"word": "submarine", "clue": "A steel vessel that dives deep beneath the ocean waves to explore the abyss"},
        {"word": "avalanche", "clue": "A thundering wall of snow that races down a mountainside destroying everything in its path"},
        {"word": "labyrinth", "clue": "A twisting maze of passages where even the smartest minds can get hopelessly lost"},
        {"word": "satellite", "clue": "It orbits high above the Earth beaming TV signals and weather maps to the ground"},
        {"word": "cathedral", "clue": "A towering stone structure with stained glass windows built to inspire awe and worship"},
        {"word": "skeleton", "clue": "The bony framework hidden inside your body that gives you shape and lets you stand"},
        {"word": "hurricane", "clue": "A colossal spinning storm born over warm ocean waters that can flatten entire cities"},
        {"word": "detective", "clue": "Armed with a magnifying glass and sharp mind, this person hunts for clues to crack the case"},
        {"word": "treasure", "clue": "Pirates buried chests full of gold coins and jewels on secret islands long ago"},
        {"word": "elephant", "clue": "The largest land animal on Earth, famous for its trunk, tusks, and incredible memory"},
        {"word": "umbrella", "clue": "A folding canopy on a stick that keeps the rain from soaking you on a stormy day"},
        {"word": "migration", "clue": "Every year millions of birds fly thousands of miles to escape the winter cold"},
    ]

    # split words by difficulty (word length)
    easy_words = [w for w in all_words if len(w["word"]) <= 6]
    medium_words = [w for w in all_words if 7 <= len(w["word"]) <= 8]
    hard_words = [w for w in all_words if len(w["word"]) >= 9]

    rounds_config = [
        {"label": "Round 1: Easy", "pool": easy_words or all_words, "attempts": 5, "max_pts": 10},
        {"label": "Round 2: Medium", "pool": medium_words or all_words, "attempts": 4, "max_pts": 10},
        {"label": "Round 3: Hard", "pool": hard_words or all_words, "attempts": 3, "max_pts": 10},
    ]

    round_scores = []
    current_round = {"index": 0, "word": "", "data": None, "attempts": 0,
                     "hints_used": 0, "hints": [], "max_hints": 0,
                     "revealed": set(), "done": False, "game_done": False}
    anim_jobs = []
    tile_items = []

    _win, card = make_card_window("Word Challenge", width=1020, height=700)
    play_opening_music()

    # --- header ---
    round_var = tk.StringVar(value="")
    styled_label(card, textvariable=round_var, font=("Segoe UI", 16, "bold")).pack(pady=(0, 2))

    clue_var = tk.StringVar(value="")
    styled_label(card, textvariable=clue_var, font=("Segoe UI", 11, "italic"), fg=SUBTLE).pack(pady=(0, 2))

    length_var = tk.StringVar(value="")
    styled_label(card, textvariable=length_var, fg=SUBTLE).pack(pady=(0, 8))

    # --- letter tiles canvas ---
    TILE_SIZE = 44
    TILE_GAP = 6
    canvas_w = 900
    canvas_h = TILE_SIZE + 30
    tile_canvas = tk.Canvas(card, width=canvas_w, height=canvas_h, bg=CARD, highlightthickness=0)
    tile_canvas.pack(pady=(0, 8))

    tile_start_x = [0]  # mutable ref for current round layout

    def build_tiles(word):
        tile_canvas.delete("all")
        tile_items.clear()
        tiles_total_w = len(word) * (TILE_SIZE + TILE_GAP) - TILE_GAP
        sx = (canvas_w - tiles_total_w) // 2
        tile_start_x[0] = sx
        for i, ch in enumerate(word):
            x = sx + i * (TILE_SIZE + TILE_GAP)
            y = 10
            rect = tile_canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE,
                                                fill="#334155", outline="#475569", width=2)
            txt = tile_canvas.create_text(x + TILE_SIZE // 2, y + TILE_SIZE // 2,
                                          text="?", fill=SUBTLE, font=("Consolas", 18, "bold"))
            tile_items.append((rect, txt, ch))

    def pulse_tiles(step=0):
        if current_round["game_done"] or not _win.winfo_exists():
            return
        colors = ["#334155", "#3b4a5e", "#435568", "#3b4a5e"]
        color = colors[step % len(colors)]
        for rect, txt, ch in tile_items:
            if ch not in current_round["revealed"]:
                tile_canvas.itemconfig(rect, fill=color)
        job = _win.after(400, lambda: pulse_tiles(step + 1))
        anim_jobs.append(job)

    def flip_tile(index, phase=0):
        if index >= len(tile_items):
            return
        rect, txt, ch = tile_items[index]
        sx = tile_start_x[0]
        x = sx + index * (TILE_SIZE + TILE_GAP)
        y = 10
        cx = x + TILE_SIZE // 2
        phases = 6
        if phase <= phases // 2:
            progress = phase / (phases // 2)
            half_w = int((TILE_SIZE // 2) * (1 - progress))
            half_w = max(half_w, 1)
            tile_canvas.coords(rect, cx - half_w, y, cx + half_w, y + TILE_SIZE)
            tile_canvas.itemconfig(txt, text="")
            _win.after(35, lambda: flip_tile(index, phase + 1))
        elif phase <= phases:
            progress = (phase - phases // 2) / (phases // 2)
            half_w = int((TILE_SIZE // 2) * progress)
            half_w = max(half_w, 1)
            tile_canvas.coords(rect, cx - half_w, y, cx + half_w, y + TILE_SIZE)
            tile_canvas.itemconfig(rect, fill="#22c55e", outline="#16a34a")
            tile_canvas.itemconfig(txt, text=ch.upper(), fill="#ffffff", font=("Consolas", 18, "bold"))
            if phase < phases:
                _win.after(35, lambda: flip_tile(index, phase + 1))
            else:
                tile_canvas.coords(rect, x, y, x + TILE_SIZE, y + TILE_SIZE)

    def reveal_all_tiles(success):
        color = "#22c55e" if success else "#ef4444"
        outline = "#16a34a" if success else "#dc2626"
        for i, (rect, txt, ch) in enumerate(tile_items):
            tile_canvas.itemconfig(rect, fill=color, outline=outline)
            tile_canvas.itemconfig(txt, text=ch.upper(), fill="#ffffff")

    def shake_canvas(step=0):
        if step >= 8 or not _win.winfo_exists():
            tile_canvas.place_forget()
            tile_canvas.pack(pady=(0, 8))
            return
        offset = (6 if step % 2 == 0 else -6)
        tile_canvas.pack_forget()
        tile_canvas.place(relx=0.5, rely=0.22, anchor="center", x=offset)
        _win.after(40, lambda: shake_canvas(step + 1))

    def bounce_tile(index, step=0):
        if index >= len(tile_items):
            return
        rect, txt, ch = tile_items[index]
        sx = tile_start_x[0]
        x = sx + index * (TILE_SIZE + TILE_GAP)
        base_y = 10
        offsets = [-6, -10, -6, 0, 2, 0]
        if step >= len(offsets) or not _win.winfo_exists():
            tile_canvas.coords(rect, x, base_y, x + TILE_SIZE, base_y + TILE_SIZE)
            tile_canvas.coords(txt, x + TILE_SIZE // 2, base_y + TILE_SIZE // 2)
            return
        dy = offsets[step]
        tile_canvas.coords(rect, x, base_y + dy, x + TILE_SIZE, base_y + TILE_SIZE + dy)
        tile_canvas.coords(txt, x + TILE_SIZE // 2, base_y + TILE_SIZE // 2 + dy)
        _win.after(50, lambda: bounce_tile(index, step + 1))

    # --- status / hints ---
    status_var = tk.StringVar(value="")
    hint_counter_var = tk.StringVar(value="")
    hint_helper_var = tk.StringVar(value="")
    hint_text_var = tk.StringVar(value="Press the Hint button to reveal clues.")

    score_summary_var = tk.StringVar(value="")
    styled_label(card, textvariable=score_summary_var, font=("Segoe UI", 11), fg=ACCENT).pack(pady=(0, 2))

    lbl_hint_counter = styled_label(card, textvariable=hint_counter_var, fg=SUBTLE)
    lbl_hint_counter.pack(fill="x", pady=(2, 0))

    hint_helper_label = styled_label(card, textvariable=hint_helper_var, fg=SUBTLE)
    hint_helper_label.config(wraplength=360, justify="left")
    hint_helper_label.pack(fill="x", pady=(0, 2))

    hint_panel = tk.Frame(card, bg="#e0f2fe", highlightbackground="#0ea5e9",
                          highlightthickness=2, bd=1, relief="solid")
    hint_panel.pack(fill="x", pady=(4, 4), padx=4)
    hint_panel.lift()

    lbl_hint_title = tk.Label(hint_panel, text="Hints", font=("Segoe UI", 11, "bold"),
                              bg="#e0f2fe", fg="#0b1727", anchor="w")
    lbl_hint_title.pack(fill="x", padx=10, pady=(4, 0))

    hint_box = tk.Label(hint_panel, textvariable=hint_text_var, bg="#ffffff", fg="#0b1727",
                        font=("Segoe UI", 11, "bold"), anchor="nw", justify="left",
                        wraplength=520, padx=8, pady=4, bd=0, relief="flat")
    hint_box.pack(fill="x", padx=10, pady=(2, 6))
    hint_box.lift()

    entry = styled_entry(card)
    entry.pack(pady=(4, 0))
    entry.focus_set()

    button_row = tk.Frame(card, bg=CARD)
    button_row.pack(fill="x", pady=(6, 4))

    def update_hint_box(text, append=False):
        if append and text:
            cur = hint_text_var.get().strip()
            new_text = (cur + "\n" + text) if cur else text
            hint_text_var.set(new_text)
        else:
            hint_text_var.set(text or "")

    def finish_all():
        current_round["game_done"] = True
        entry.pack_forget()
        button_row.pack_forget()
        hint_panel.pack_forget()
        lbl_hint_counter.pack_forget()
        hint_helper_label.pack_forget()
        clue_var.set("")
        length_var.set("")
        round_var.set("Word Challenge Complete!")
        total = sum(round_scores)
        parts = [f"R{i + 1}: {s}/10" for i, s in enumerate(round_scores)]
        score_summary_var.set("  |  ".join(parts) + f"    Total: {total}/30")
        status_var.set("")
        end_row = tk.Frame(card, bg=CARD)
        end_row.pack(fill="x", pady=(8, 0), padx=10)
        def play_again():
            _win.destroy()
            _run_word(test_callback)
        make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
        make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")
        add_score(total, celebrate=total >= 15, message=f"Word: {total}/30")
        if test_callback is not None:
            test_callback(total)

    def finish_round(won, pts):
        round_scores.append(pts)
        current_round["done"] = True
        r = current_round["index"]
        word_now = current_round["word"]
        if won:
            play_correct_sound()
            current_round["revealed"].update(set(word_now))
            for i in range(len(word_now)):
                _win.after(i * 120, lambda idx=i: flip_tile(idx))
                _win.after(i * 120 + 250, lambda idx=i: bounce_tile(idx))
            anim_end = len(word_now) * 120 + 400
            status_var.set(f"Correct! The word was '{word_now}'. +{pts} pts")
        else:
            play_lose_sound()
            _win.after(300, lambda: reveal_all_tiles(False))
            anim_end = 800
            status_var.set(f"Round over! The word was '{word_now}'. +0 pts")
        entry.config(state="disabled")
        hint_btn.btn.config(state="disabled")
        guess_btn.btn.config(state="disabled")
        parts = [f"R{i + 1}: {s}" for i, s in enumerate(round_scores)]
        score_summary_var.set("  |  ".join(parts))
        if r + 1 < len(rounds_config):
            _win.after(anim_end + 1200, lambda: start_round(r + 1))
        else:
            _win.after(anim_end + 1200, finish_all)

    def guess(_event=None):
        if current_round["done"] or current_round["game_done"]:
            return
        if entry.cget("state") == "disabled":
            return
        player_guess = entry.get().strip().lower()
        if not player_guess:
            status_var.set("Type a full-word guess.")
            return
        entry.delete(0, tk.END)
        word_now = current_round["word"]
        att = current_round["attempts"]

        if player_guess == word_now:
            pts = max(att * 2, 2)
            pts = min(pts, rounds_config[current_round["index"]]["max_pts"])
            finish_round(True, pts)
            return

        # wrong guess — reveal matching letters
        new_revealed = set()
        for ch in player_guess:
            if ch in word_now and ch not in current_round["revealed"]:
                new_revealed.add(ch)
        current_round["revealed"].update(new_revealed)

        flip_delay = 0
        for i, (rect, txt, ch) in enumerate(tile_items):
            if ch in new_revealed:
                _win.after(flip_delay, lambda idx=i: flip_tile(idx))
                _win.after(flip_delay + 250, lambda idx=i: bounce_tile(idx))
                flip_delay += 120

        shake_canvas()

        current_round["attempts"] -= 1
        att = current_round["attempts"]
        if att <= 0:
            reveal_all_tiles(False)
            finish_round(False, 0)
        else:
            play_wrong_sound()
            matched = len(new_revealed)
            if matched > 0:
                status_var.set(f"Wrong word, but found {matched} letter(s)! Attempts left: {att}")
            else:
                status_var.set(f"Wrong guess. Attempts left: {att}")

    def use_hint():
        hu = current_round["hints_used"]
        mh = current_round["max_hints"]
        if hu >= mh:
            status_var.set("No hints left.")
            return
        hint_message = current_round["hints"][hu % len(current_round["hints"])]
        current_round["hints_used"] += 1
        hu = current_round["hints_used"]
        hint_counter_var.set(f"Hints used: {hu}/{mh}")
        line = f"{hu}. {hint_message}"
        if hu == 1:
            hint_helper_var.set("Hints revealed:")
            update_hint_box(line)
        else:
            update_hint_box(line, append=True)
        add_score(-1)
        status_var.set("Hint revealed (-1 score).")
        if hu >= mh:
            hint_btn.btn.config(state="disabled")

    hint_btn = make_btn(button_row, "Hint (-1 score)", use_hint, width=14)
    hint_btn.pack(side="left", padx=(0, 8))

    guess_btn = make_btn(button_row, "Guess", guess, width=12, variant="accent")
    guess_btn.pack(side="right")

    entry.bind("<Return>", guess)

    styled_label(card, textvariable=status_var).pack(pady=(2, 0))

    def start_round(idx):
        current_round["index"] = idx
        current_round["done"] = False
        rnd = rounds_config[idx]
        data = random.choice(rnd["pool"])
        word_now = data["word"]
        current_round["word"] = word_now
        current_round["data"] = data
        current_round["attempts"] = rnd["attempts"]
        current_round["revealed"] = set()
        h = build_word_hints(word_now)
        current_round["hints"] = h
        mh = min(5, len(h))
        current_round["max_hints"] = mh
        current_round["hints_used"] = 0

        round_var.set(f"{rnd['label']}  ({rnd['attempts']} attempts)")
        clue_var.set(data["clue"])
        length_var.set(f"Word length: {len(word_now)} letters")
        status_var.set(f"You have {rnd['attempts']} attempts.")
        hint_counter_var.set(f"Hints used: 0/{mh}")
        hint_helper_var.set(f"Use a hint to reveal info (max {mh}, costs 1 point each).")
        hint_text_var.set("Press the Hint button to reveal clues.")

        build_tiles(word_now)

        entry.config(state="normal")
        entry.delete(0, tk.END)
        entry.focus_set()
        guess_btn.btn.config(state="normal")
        hint_btn.btn.config(state="normal")

        pulse_tiles()

    start_round(0)


def _gen_algebra():
    kind = random.randint(0, 2)
    if kind == 0:
        a = random.randint(2, 9)
        x = random.randint(1, 12)
        b = random.randint(1, 20)
        c = a * x + b
        return f"{a}x + {b} = {c},  x = ?", x
    elif kind == 1:
        a = random.randint(2, 9)
        x = random.randint(2, 12)
        b = random.randint(1, a * x - 1)
        c = a * x - b
        return f"{a}x - {b} = {c},  x = ?", x
    else:
        a = random.randint(5, 50)
        x = random.randint(1, 50)
        b = x + a
        return f"x + {a} = {b},  x = ?", x


def _gen_pattern():
    kind = random.randint(0, 3)
    if kind == 0:
        start = random.randint(1, 20)
        step = random.randint(2, 10)
        seq = [start + i * step for i in range(5)]
    elif kind == 1:
        start = random.randint(1, 5)
        ratio = random.randint(2, 3)
        seq = [start * (ratio ** i) for i in range(5)]
    elif kind == 2:
        s = random.randint(1, 8)
        seq = [(s + i) ** 2 for i in range(5)]
    else:
        a, b = random.randint(1, 5), random.randint(1, 5)
        seq = [a, b]
        for _ in range(3):
            seq.append(seq[-1] + seq[-2])
    answer = seq[-1]
    display = ", ".join(str(n) for n in seq[:-1]) + ", ?"
    return f"What comes next:  {display}", answer


def _gen_multiplication():
    a = random.randint(2, 15)
    b = random.randint(2, 15)
    return f"{a} \u00d7 {b} = ?", a * b


def open_math(test_callback=None):
    def _start_game():
        _run_math(test_callback)
    show_how_to_play("math", _start_game, on_exit=None)


def _run_math(test_callback=None):
    sections = [
        ("Algebra", _gen_algebra),
        ("Patterns", _gen_pattern),
        ("Multiplication", _gen_multiplication),
    ]
    section_time = 90
    section_max = 10
    scores = [0, 0, 0]
    current = {"section": 0, "answer": None, "done": False}
    timer_job = {"id": None}

    _win, card = make_card_window("Math Game", width=700, height=520)
    play_opening_music()

    header = tk.Frame(card, bg=CARD)
    header.pack(fill="x", pady=(0, 6))

    section_var = tk.StringVar(value="")
    timer_var = tk.StringVar(value="")
    section_score_var = tk.StringVar(value="")

    styled_label(header, textvariable=section_var, font=("Segoe UI", 14, "bold")).pack(side="left")
    styled_label(header, textvariable=timer_var, font=("Segoe UI", 13, "bold"), fg=ACCENT).pack(side="right")
    styled_label(header, textvariable=section_score_var, font=("Segoe UI", 12), fg=SUBTLE).pack(
        side="right", padx=(0, 20)
    )

    question_var = tk.StringVar(value="")
    styled_label(card, textvariable=question_var, font=("Consolas", 18, "bold")).pack(pady=(20, 14))

    entry = styled_entry(card)
    entry.pack(fill="x", padx=60, pady=(0, 8))
    entry.focus_set()

    status_var = tk.StringVar(value="")
    status_lbl = styled_label(card, textvariable=status_var, font=("Segoe UI", 11))
    status_lbl.pack(pady=(0, 4))

    submit_btn = make_btn(card, "Submit", lambda: check_answer(), width=12, variant="accent")
    submit_btn.pack(pady=(0, 8))

    result_var = tk.StringVar(value="")
    result_lbl = styled_label(card, textvariable=result_var, font=("Segoe UI", 14, "bold"), fg=ACCENT)
    result_lbl.config(wraplength=600, justify="center")
    result_lbl.pack(pady=(10, 0), fill="x")

    def next_question():
        idx = current["section"]
        if idx >= len(sections) or current["done"]:
            return
        _, gen_fn = sections[idx]
        q, a = gen_fn()
        question_var.set(q)
        current["answer"] = a
        entry.delete(0, tk.END)
        entry.focus_set()

    def check_answer(_event=None):
        if current["done"]:
            return
        idx = current["section"]
        if idx >= len(sections):
            return
        raw = entry.get().strip()
        if not raw:
            return
        try:
            val = int(raw)
        except ValueError:
            status_var.set("Enter a number.")
            entry.delete(0, tk.END)
            return
        if val == current["answer"]:
            play_correct_sound()
            if scores[idx] < section_max:
                scores[idx] += 1
            section_score_var.set(f"Score: {scores[idx]}/{section_max}")
            status_var.set("Correct!")
        else:
            play_wrong_sound()
            status_var.set(f"Wrong! Answer was {current['answer']}")
        next_question()

    entry.bind("<Return>", check_answer)

    def tick(remaining):
        if current["done"] or not _win.winfo_exists():
            return
        if remaining <= 0:
            nxt = current["section"] + 1
            current["section"] = nxt
            if nxt >= len(sections):
                finish_game()
            else:
                start_section(nxt)
            return
        label = f"Time: {remaining}s"
        if remaining <= 5:
            label += " !"
            play_tick_sound()
        timer_var.set(label)
        timer_job["id"] = _win.after(1000, lambda: tick(remaining - 1))

    def start_section(idx):
        current["section"] = idx
        name, _ = sections[idx]
        section_var.set(f"Section {idx + 1}: {name}")
        section_score_var.set(f"Score: {scores[idx]}/{section_max}")
        timer_var.set(f"Time: {section_time}s")
        status_var.set("")
        next_question()
        tick(section_time)

    def finish_game():
        current["done"] = True
        total = sum(scores)
        entry.pack_forget()
        submit_btn.pack_forget()
        status_lbl.pack_forget()
        question_var.set("")
        section_var.set("Math Game Complete!")
        timer_var.set("")
        section_score_var.set("")
        parts = []
        for i, (name, _) in enumerate(sections):
            parts.append(f"{name}: {scores[i]}/{section_max}")
        result_var.set(
            "  |  ".join(parts) + f"\n\nTotal: {total}/{section_max * len(sections)}"
        )
        end_row = tk.Frame(card, bg=CARD)
        end_row.pack(fill="x", pady=(12, 0), padx=10)
        def play_again():
            _win.destroy()
            _run_math(test_callback)
        make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
        make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")
        add_score(total, celebrate=total >= 15, message=f"Math: {total}/{section_max * len(sections)}")
        if test_callback is not None:
            test_callback(total)

    def on_close():
        current["done"] = True
        if timer_job["id"] is not None:
            try:
                _win.after_cancel(timer_job["id"])
            except Exception:
                pass
        _win.destroy()

    _win.protocol("WM_DELETE_WINDOW", on_close)
    start_section(0)


# ── Brainiac (90%+ IQ required) ───────────────────────────────────────────
def open_brainiac():
    """Brainiac hub — select an elite mini-game."""
    _win, card = make_card_window("🧬  Brainiac", width=520, height=420)

    styled_label(card, text="🧬  Brainiac Zone", font=("Segoe UI", 20, "bold")).pack(pady=(0, 4))
    styled_label(
        card,
        text="Elite challenges for 90%+ minds.\nPick a game below.",
        font=("Segoe UI", 11), fg=SUBTLE,
    ).pack(pady=(0, 18))

    games_frame = tk.Frame(card, bg=CARD)
    games_frame.pack(fill="x", padx=20, pady=(0, 12))

    def launch_ten_second():
        _win.destroy()
        open_ten_second()

    make_btn(games_frame, "⏱️  10-Second Test", launch_ten_second, width=22, variant="accent").pack(pady=6)

    def launch_memory_match():
        _win.destroy()
        open_memory_match()

    make_btn(games_frame, "🧠  Memory Match", launch_memory_match, width=22, variant="accent").pack(pady=6)

    # Future games will be added here as more make_btn lines

    make_btn(card, "🚪  Close", lambda: _win.destroy(), width=12).pack(pady=(8, 0))


# ── 10-Second Test ────────────────────────────────────────────────────────
def open_ten_second():
    def _start_game():
        _run_ten_second()
    show_how_to_play("ten_second", _start_game, on_exit=None)


def _run_ten_second():
    _win, card = make_card_window("⏱️  10-Second Test", width=540, height=600)
    play_opening_music()

    state = {"running": False, "start_time": 0.0, "done": False, "anim_jobs": []}

    def cancel_anims():
        for job in state["anim_jobs"]:
            try:
                _win.after_cancel(job)
            except Exception:
                pass
        state["anim_jobs"].clear()

    # ── Big animated clock canvas ──
    clock_size = 300
    cx, cy = clock_size // 2, clock_size // 2
    clock_canvas = tk.Canvas(card, width=clock_size, height=clock_size,
                              bg=CARD, highlightthickness=0)
    clock_canvas.pack(pady=(4, 0))

    r = 120
    # Outer glow ring
    for i in range(3):
        clock_canvas.create_oval(cx - r - 12 + i*4, cy - r - 12 + i*4,
                                  cx + r + 12 - i*4, cy + r + 12 - i*4,
                                  outline="#191d3a", width=2)
    # Clock face with gradient-like rings
    clock_canvas.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
                              outline="#6366f1", width=2, fill="")
    clock_face = clock_canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                              outline="#4f46e5", width=3, fill="#0a0e1a")
    # Inner decorative ring
    clock_canvas.create_oval(cx - r + 15, cy - r + 15, cx + r - 15, cy + r - 15,
                              outline="#1e293b", width=1, fill="")

    # 12 subtle tick dots (no numbers — just dots for style)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        tx = cx + math.cos(a) * (r - 8)
        ty = cy + math.sin(a) * (r - 8)
        dot_r = 3 if i % 3 == 0 else 1.5
        clock_canvas.create_oval(tx - dot_r, ty - dot_r, tx + dot_r, ty + dot_r,
                                  fill="#334155", outline="")

    # Trailing ghost hands (for motion blur effect)
    ghost_hands = []
    ghost_colors = ["#4a2a10", "#7a4517", "#c06a20"]
    for gc in ghost_colors:
        gh = clock_canvas.create_line(cx, cy, cx, cy - r + 20,
                                       fill=gc, width=2)
        ghost_hands.append(gh)

    # Main hand
    hand = clock_canvas.create_line(cx, cy, cx, cy - r + 20,
                                     fill="#f97316", width=4, capstyle="round")

    # Center piece
    clock_canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8,
                              fill="#f97316", outline="#fbbf24", width=2)

    # Orbiting particle dots
    particles = []
    for i in range(8):
        p = clock_canvas.create_oval(0, 0, 0, 0, fill="#6366f1", outline="")
        particles.append(p)

    # ── Status area ──
    status_cvs = tk.Canvas(card, width=480, height=50, bg=CARD, highlightthickness=0)
    status_cvs.pack(pady=(4, 0))
    status_text = status_cvs.create_text(240, 16, text="🎯  Press Start when ready!",
                                          font=("Segoe UI", 13, "bold"), fill=TEXT)
    elapsed_text = status_cvs.create_text(240, 40, text="",
                                           font=("Segoe UI", 11), fill=SUBTLE)

    # ── Result area (hidden initially) ──
    result_cvs = tk.Canvas(card, width=480, height=120, bg=CARD, highlightthickness=0)

    btn_row = tk.Frame(card, bg=CARD)
    btn_row.pack(fill="x", padx=50, pady=(8, 6))

    # ── Animations ──
    def animate_particles():
        """Orbiting dots around the clock edge."""
        if not state["running"]:
            return
        try:
            if not _win.winfo_exists():
                return
        except Exception:
            return
        elapsed = time.time() - state["start_time"]
        for i, p in enumerate(particles):
            offset = i * (2 * math.pi / len(particles))
            speed = 0.8 + i * 0.1
            a = elapsed * speed + offset
            px = cx + math.cos(a) * (r + 6)
            py = cy + math.sin(a) * (r + 6)
            sz = 2.5 if i % 2 == 0 else 1.5
            clock_canvas.coords(p, px - sz, py - sz, px + sz, py + sz)
            # Color cycle
            colors = ["#6366f1", "#a855f7", "#22d3ee", "#f97316",
                       "#ef4444", "#10b981", "#facc15", "#ec4899"]
            clock_canvas.itemconfig(p, fill=colors[i % len(colors)])
        state["anim_jobs"].append(_win.after(40, animate_particles))

    def rotate_hand():
        """Spin clock hand with ghost trail — one rotation per 10s, no hints."""
        if not state["running"] or state["done"]:
            return
        try:
            if not _win.winfo_exists():
                return
        except Exception:
            return
        elapsed = time.time() - state["start_time"]
        angle = (elapsed / 10.0) * 2 * math.pi - math.pi / 2

        # Update ghost hands (trailing positions)
        for gi, gh in enumerate(ghost_hands):
            trail_offset = (gi + 1) * 0.12
            ga = angle - trail_offset
            gx = cx + math.cos(ga) * (r - 20)
            gy = cy + math.sin(ga) * (r - 20)
            clock_canvas.coords(gh, cx, cy, gx, gy)

        # Main hand
        hx = cx + math.cos(angle) * (r - 20)
        hy = cy + math.sin(angle) * (r - 20)
        clock_canvas.coords(hand, cx, cy, hx, hy)

        # Pulse the outer ring color based on elapsed
        cycle = (elapsed % 2.0) / 2.0
        if cycle < 0.5:
            clock_canvas.itemconfig(clock_face, outline="#6366f1")
        else:
            clock_canvas.itemconfig(clock_face, outline="#4f46e5")

        # Show running elapsed (no hint about 10s target)
        status_cvs.itemconfig(elapsed_text,
                               text=f"⏱  {elapsed:.1f}s elapsed")

        state["anim_jobs"].append(_win.after(30, rotate_hand))

    def start_test():
        if state["running"] or state["done"]:
            return
        state["running"] = True
        state["start_time"] = time.time()
        status_cvs.itemconfig(status_text,
                               text="⚡  Counting in your head... press Stop at 10s!")
        status_cvs.itemconfig(elapsed_text, text="")
        start_btn.btn.config(state="disabled")
        stop_btn.btn.config(state="normal")
        # Start all animations
        rotate_hand()
        animate_particles()

    def stop_test():
        if not state["running"] or state["done"]:
            return
        state["running"] = False
        state["done"] = True
        elapsed = time.time() - state["start_time"]
        cancel_anims()

        # Hide particles
        for p in particles:
            clock_canvas.coords(p, 0, 0, 0, 0)

        stop_btn.btn.config(state="disabled")
        start_btn.btn.config(state="disabled")

        diff = abs(elapsed - 10.0)
        if diff <= 0.2:
            pts, grade, grade_color = 10, "🌟 PERFECT!", "#facc15"
        elif diff <= 0.5:
            pts, grade, grade_color = 8, "🎯 Excellent!", "#22d3ee"
        elif diff <= 1.0:
            pts, grade, grade_color = 6, "👏 Great!", "#a855f7"
        elif diff <= 2.0:
            pts, grade, grade_color = 4, "👍 Good", "#10b981"
        elif diff <= 3.0:
            pts, grade, grade_color = 2, "😐 Okay", "#f97316"
        else:
            pts, grade, grade_color = 0, "😬 Way off!", "#ef4444"

        direction = "early ⏪" if elapsed < 10.0 else "late ⏩"

        # Update status
        status_cvs.itemconfig(status_text,
                               text=f"Stopped at {elapsed:.2f}s  ({diff:.2f}s {direction})")
        status_cvs.itemconfig(elapsed_text, text="")

        # ── Animated result reveal ──
        result_cvs.pack(pady=(4, 0))
        result_cvs.delete("all")

        # Accuracy bar
        bar_x, bar_w = 40, 400
        bar_y, bar_h = 15, 14
        result_cvs.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
                                     fill="#1e293b", outline="")
        # Accuracy: 1.0 = perfect, 0.0 = 10s off
        accuracy = max(0.0, 1.0 - diff / 10.0)
        # Bar color based on accuracy
        if accuracy >= 0.95:
            bar_color = "#facc15"
        elif accuracy >= 0.8:
            bar_color = "#22d3ee"
        elif accuracy >= 0.6:
            bar_color = "#10b981"
        elif accuracy >= 0.3:
            bar_color = "#f97316"
        else:
            bar_color = "#ef4444"
        acc_bar = result_cvs.create_rectangle(bar_x, bar_y, bar_x, bar_y + bar_h,
                                               fill=bar_color, outline="")
        result_cvs.create_text(bar_x + bar_w + 20, bar_y + bar_h // 2,
                                text=f"{accuracy * 100:.0f}%",
                                font=("Segoe UI", 10, "bold"), fill=bar_color)

        # Grade + points
        grade_item = result_cvs.create_text(240, 55, text="",
                                              font=("Segoe UI", 22, "bold"),
                                              fill=grade_color)
        pts_item = result_cvs.create_text(240, 90, text="",
                                            font=("Segoe UI", 15, "bold"),
                                            fill=ACCENT)

        # Animate accuracy bar fill
        def fill_bar(current_w):
            target_w = bar_w * accuracy
            if current_w >= target_w:
                # Now reveal grade
                result_cvs.itemconfig(grade_item, text=grade)
                # Count up points
                animate_pts(0)
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            current_w = min(current_w + 8, target_w)
            result_cvs.coords(acc_bar, bar_x, bar_y,
                               bar_x + current_w, bar_y + bar_h)
            state["anim_jobs"].append(_win.after(20, lambda: fill_bar(current_w)))

        def animate_pts(current):
            if current > pts:
                # Show play again / exit
                show_end_buttons()
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            result_cvs.itemconfig(pts_item, text=f"+{current} points")
            if current < pts:
                state["anim_jobs"].append(
                    _win.after(80, lambda: animate_pts(current + 1)))
            else:
                state["anim_jobs"].append(_win.after(300, show_end_buttons))

        def show_end_buttons():
            add_score(pts, celebrate=pts >= 6, message=f"10s Test: {elapsed:.2f}s")
            end_row = tk.Frame(card, bg=CARD)
            end_row.pack(fill="x", pady=(6, 0), padx=40)

            def play_again():
                _win.destroy()
                _run_ten_second()

            make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
            make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")

        # Kick off animation chain
        state["anim_jobs"].append(_win.after(300, lambda: fill_bar(0)))

    start_btn = make_btn(btn_row, "▶️  Start", start_test, width=14, variant="accent")
    start_btn.pack(side="left", padx=(0, 10))

    stop_btn = make_btn(btn_row, "⏹️  Stop", stop_test, width=14)
    stop_btn.pack(side="right")
    stop_btn.btn.config(state="disabled")

    def on_close():
        state["done"] = True
        state["running"] = False
        cancel_anims()
        _win.destroy()

    _win.protocol("WM_DELETE_WINDOW", on_close)


# ── Memory Match ──────────────────────────────────────────────────────────
def open_memory_match():
    def _start_game():
        _run_memory_match()
    show_how_to_play("memory_match", _start_game, on_exit=None)


def _run_memory_match():
    _win, card = make_card_window("🧠  Memory Match", width=640, height=660)
    play_opening_music()

    ALL_NAMES = [
        "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George",
        "Hannah", "Ivan", "Julia", "Kevin", "Laura", "Mason", "Nina",
        "Oscar", "Peji", "Quinn", "Ruby", "Sam", "Tina", "Uma", "Victor",
    ]
    SHAPE_TYPES = ["circle", "square", "triangle", "line", "star", "diamond"]
    SHAPE_COLORS = ["#f97316", "#6366f1", "#22d3ee", "#a855f7", "#ef4444",
                    "#10b981", "#facc15", "#ec4899"]

    # Round configs: (num_pairs, num_choices, memorise_seconds, points_per_correct)
    ROUNDS = [
        (1, 4, 4, 5),   # Round 1: 1 pair, 4 choices, 4 s
        (2, 6, 5, 3),   # Round 2: 2 pairs, 6 choices, 5 s
        (3, 8, 6, 2),   # Round 3: 3 pairs, 8 choices, 6 s
    ]

    state = {"round": 0, "total_score": 0, "anim_jobs": []}

    # ── Header with animated progress bar ──
    header = tk.Canvas(card, width=580, height=70, bg=CARD, highlightthickness=0)
    header.pack(pady=(0, 4))
    header.create_text(290, 18, text="🧠  Memory Match",
                       font=("Segoe UI", 18, "bold"), fill=TEXT)
    info_text = header.create_text(290, 45, text="Round 1 / 3",
                                    font=("Segoe UI", 11), fill=SUBTLE)
    # Progress bar background
    pb_x, pb_y, pb_w, pb_h = 90, 60, 400, 6
    header.create_rectangle(pb_x, pb_y, pb_x + pb_w, pb_y + pb_h,
                            fill="#1e293b", outline="")
    progress_bar = header.create_rectangle(pb_x, pb_y, pb_x, pb_y + pb_h,
                                            fill="#6366f1", outline="")

    def update_progress():
        frac = state["round"] / len(ROUNDS)
        header.coords(progress_bar, pb_x, pb_y, pb_x + pb_w * frac, pb_y + pb_h)

    # Area where memorise / recall content goes
    content = tk.Frame(card, bg=CARD)
    content.pack(expand=True, fill="both")

    def draw_shape(canvas, shape, color, cx, cy, size):
        """Draw a shape on a canvas with glow."""
        s = size // 2
        # Draw glow circle behind shape
        canvas.create_oval(cx - s - 4, cy - s - 4, cx + s + 4, cy + s + 4,
                           fill="", outline=color, width=2, dash=(3, 3))
        if shape == "circle":
            canvas.create_oval(cx - s, cy - s, cx + s, cy + s, fill=color, outline="")
        elif shape == "square":
            canvas.create_rectangle(cx - s, cy - s, cx + s, cy + s, fill=color, outline="")
        elif shape == "triangle":
            canvas.create_polygon(
                cx, cy - s, cx - s, cy + s, cx + s, cy + s,
                fill=color, outline=""
            )
        elif shape == "line":
            canvas.create_line(cx - s, cy, cx + s, cy, fill=color, width=5,
                               capstyle="round")
        elif shape == "star":
            pts = []
            for i in range(5):
                a = math.radians(i * 72 - 90)
                pts.extend([cx + math.cos(a) * s, cy + math.sin(a) * s])
                a2 = math.radians(i * 72 + 36 - 90)
                pts.extend([cx + math.cos(a2) * s * 0.4, cy + math.sin(a2) * s * 0.4])
            canvas.create_polygon(pts, fill=color, outline="")
        elif shape == "diamond":
            canvas.create_polygon(
                cx, cy - s, cx + s, cy, cx, cy + s, cx - s, cy,
                fill=color, outline=""
            )

    def cancel_anims():
        for job in state["anim_jobs"]:
            try:
                _win.after_cancel(job)
            except Exception:
                pass
        state["anim_jobs"].clear()

    def clear_content():
        cancel_anims()
        for w in content.winfo_children():
            w.destroy()

    # ── Animated countdown ring ──
    def make_countdown_ring(parent, total_secs, on_done):
        """Big animated countdown ring with pulsing number."""
        ring_size = 120
        rcx, rcy = ring_size // 2, ring_size // 2
        ring_r = 48
        ring_cvs = tk.Canvas(parent, width=ring_size, height=ring_size,
                             bg=CARD, highlightthickness=0)
        ring_cvs.pack(pady=(4, 6))

        # Background ring
        ring_cvs.create_oval(rcx - ring_r, rcy - ring_r, rcx + ring_r, rcy + ring_r,
                             outline="#1e293b", width=6)
        # Foreground arc (will be updated)
        arc_item = ring_cvs.create_arc(rcx - ring_r, rcy - ring_r,
                                        rcx + ring_r, rcy + ring_r,
                                        start=90, extent=-360,
                                        style="arc", outline="#6366f1", width=6)
        # Number in center
        num_text = ring_cvs.create_text(rcx, rcy, text=str(total_secs),
                                         font=("Segoe UI", 28, "bold"), fill="#facc15")

        timer = {"remaining": total_secs, "pulse": 0}

        def tick():
            timer["remaining"] -= 1
            rem = timer["remaining"]
            if rem <= 0:
                on_done()
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            # Update arc
            frac = rem / total_secs
            ring_cvs.itemconfig(arc_item, extent=-360 * frac)
            # Color change: green → yellow → red
            if frac > 0.5:
                ring_cvs.itemconfig(arc_item, outline="#22d3ee")
            elif frac > 0.25:
                ring_cvs.itemconfig(arc_item, outline="#facc15")
            else:
                ring_cvs.itemconfig(arc_item, outline="#ef4444")
            # Pulse number
            ring_cvs.itemconfig(num_text, text=str(rem))
            timer["pulse"] += 1
            sz = 28 + (4 if timer["pulse"] % 2 == 0 else 0)
            ring_cvs.itemconfig(num_text, font=("Segoe UI", sz, "bold"))
            state["anim_jobs"].append(_win.after(1000, tick))

        state["anim_jobs"].append(_win.after(1000, tick))
        return ring_cvs

    # ── Dramatic round intro splash ──
    def show_round_splash(rnd, callback):
        """3-2-1 countdown splash before round starts."""
        clear_content()
        splash_cvs = tk.Canvas(content, width=580, height=200,
                                bg=CARD, highlightthickness=0)
        splash_cvs.pack(expand=True)

        round_names = ["🟢  ROUND 1  —  Warm Up", "🟡  ROUND 2  —  Getting Harder",
                        "🔴  ROUND 3  —  Ultimate Challenge"]
        round_colors = ["#22d3ee", "#facc15", "#ef4444"]

        splash_cvs.create_text(290, 50, text=round_names[rnd],
                                font=("Segoe UI", 20, "bold"),
                                fill=round_colors[rnd])

        count_text = splash_cvs.create_text(290, 120, text="3",
                                              font=("Segoe UI", 48, "bold"),
                                              fill="#ffffff")

        def do_count(n):
            if n <= 0:
                callback()
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            splash_cvs.itemconfig(count_text, text=str(n))
            # Scale effect
            sizes = {3: 48, 2: 56, 1: 64}
            splash_cvs.itemconfig(count_text,
                                   font=("Segoe UI", sizes.get(n, 48), "bold"))
            colors = {3: "#22d3ee", 2: "#facc15", 1: "#ef4444"}
            splash_cvs.itemconfig(count_text, fill=colors.get(n, "#ffffff"))
            state["anim_jobs"].append(_win.after(700, lambda: do_count(n - 1)))

        state["anim_jobs"].append(_win.after(300, lambda: do_count(3)))

    # ── Animated card reveal for memorise phase ──
    def reveal_pairs_animated(targets, mem_time):
        """Reveal each pair one at a time with a slide-in effect, then start countdown."""
        clear_content()

        header.itemconfig(info_text,
                          text=f"Round {state['round'] + 1} / {len(ROUNDS)}  —  Score: {state['total_score']}")
        update_progress()

        # "MEMORISE" banner
        banner_cvs = tk.Canvas(content, width=580, height=36,
                                bg=CARD, highlightthickness=0)
        banner_cvs.pack(pady=(0, 2))
        # Glowing text
        banner_cvs.create_text(290, 18, text="⚡  MEMORISE THESE  ⚡",
                                font=("Segoe UI", 15, "bold"), fill="#facc15")

        # Countdown ring
        def on_time_up():
            num_pairs = len(targets)
            num_choices = ROUNDS[state["round"]][1]
            show_recall(targets, num_choices)

        make_countdown_ring(content, mem_time, on_time_up)

        # Container for pairs — they'll appear one by one
        pairs_frame = tk.Frame(content, bg=CARD)
        pairs_frame.pack(fill="x", padx=16, pady=(0, 4))

        pair_widgets = []
        for t in targets:
            pair_frame = tk.Frame(pairs_frame, bg="#151d30", padx=14, pady=10)
            pair_widgets.append((pair_frame, t))

        def reveal_next(idx):
            if idx >= len(pair_widgets):
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            pf, t = pair_widgets[idx]
            pf.pack(pady=6, padx=20, fill="x")

            # Left side: emoji + name
            left = tk.Frame(pf, bg="#151d30")
            left.pack(side="left", padx=(6, 16))
            tk.Label(left, text="👤", font=("Segoe UI Emoji", 18),
                     bg="#151d30").pack(side="left", padx=(0, 6))
            tk.Label(left, text=t["name"], font=("Segoe UI", 17, "bold"),
                     fg="#c7d2fe", bg="#151d30").pack(side="left")

            # Right side: shape in a glowing canvas
            shape_cvs = tk.Canvas(pf, width=70, height=70,
                                   bg="#0d1117", highlightthickness=0)
            shape_cvs.pack(side="right", padx=(16, 6))
            draw_shape(shape_cvs, t["shape"], t["color"], 35, 35, 44)

            # Stagger reveals
            if idx + 1 < len(pair_widgets):
                state["anim_jobs"].append(
                    _win.after(600, lambda: reveal_next(idx + 1)))

        # Start revealing after a short delay
        state["anim_jobs"].append(_win.after(400, lambda: reveal_next(0)))

    def start_round():
        rnd = state["round"]
        if rnd >= len(ROUNDS):
            show_final()
            return

        num_pairs, num_choices, mem_time, _ = ROUNDS[rnd]

        # Pick target pairs
        chosen_names = random.sample(ALL_NAMES, num_pairs)
        available_shapes = random.sample(SHAPE_TYPES, min(num_pairs, len(SHAPE_TYPES)))
        if num_pairs > len(SHAPE_TYPES):
            available_shapes = [random.choice(SHAPE_TYPES) for _ in range(num_pairs)]
        chosen_colors = random.sample(SHAPE_COLORS, num_pairs)
        targets = []
        for i in range(num_pairs):
            targets.append({
                "name": chosen_names[i],
                "shape": available_shapes[i],
                "color": chosen_colors[i],
            })

        # Show dramatic splash first, then memorise phase
        show_round_splash(rnd, lambda: reveal_pairs_animated(targets, mem_time))

    def show_recall(targets, num_choices):
        """Show the recall phase — pick correct names and shapes."""
        rnd = state["round"]
        _, _, _, pts_per = ROUNDS[rnd]
        clear_content()

        # Dramatic transition banner
        recall_banner = tk.Canvas(content, width=580, height=40,
                                   bg=CARD, highlightthickness=0)
        recall_banner.pack(pady=(0, 6))
        recall_banner.create_text(290, 20, text="🔒  TIME'S UP — What do you remember?",
                                   font=("Segoe UI", 14, "bold"), fill="#22d3ee")

        num_pairs = len(targets)
        correct_names = set(t["name"] for t in targets)
        correct_shapes = set((t["shape"], t["color"]) for t in targets)

        # Build decoy names
        remaining_names = [n for n in ALL_NAMES if n not in correct_names]
        decoy_names = random.sample(remaining_names, num_choices - num_pairs)
        all_names = list(correct_names) + decoy_names
        random.shuffle(all_names)

        # Build decoy shapes — make sure decoys are truly unique from correct
        all_possible = [(s, c) for s in SHAPE_TYPES for c in SHAPE_COLORS]
        all_possible = [sc for sc in all_possible if sc not in correct_shapes]
        decoy_shapes = random.sample(all_possible, num_choices - num_pairs)
        all_shapes = list(correct_shapes) + decoy_shapes
        random.shuffle(all_shapes)

        # Track which INDEX is correct (position-based, not value-based)
        correct_name_indices = set()
        for i, nm in enumerate(all_names):
            if nm in correct_names:
                correct_name_indices.add(i)

        correct_shape_indices = set()
        for i, sc in enumerate(all_shapes):
            if sc in correct_shapes:
                correct_shape_indices.add(i)

        # Track selections by index
        name_sel_idx = set()
        shape_sel_idx = set()
        name_btns = {}
        shape_borders = {}
        shape_canvases = {}

        # ── NAME GRID ──
        name_header = tk.Canvas(content, width=580, height=28,
                                 bg=CARD, highlightthickness=0)
        name_header.pack(anchor="w", padx=16, pady=(4, 2))
        name_header.create_text(10, 14,
                                text=f"👤  Pick {num_pairs} name{'s' if num_pairs > 1 else ''}:",
                                font=("Segoe UI", 12, "bold"), fill=TEXT, anchor="w")

        name_grid = tk.Frame(content, bg=CARD)
        name_grid.pack(fill="x", padx=20, pady=(0, 10))

        def toggle_name(idx, btn_widget):
            if idx in name_sel_idx:
                name_sel_idx.discard(idx)
                btn_widget.config(bg="#334155", fg=TEXT,
                                  relief="flat", bd=0)
            else:
                if len(name_sel_idx) >= num_pairs:
                    btn_widget.config(bg="#ef4444")
                    state["anim_jobs"].append(
                        _win.after(300, lambda b=btn_widget: b.config(bg="#334155")))
                    return
                name_sel_idx.add(idx)
                btn_widget.config(bg="#6366f1", fg="#ffffff",
                                  relief="solid", bd=1)

        cols = 4
        for i, nm in enumerate(all_names):
            r, c = divmod(i, cols)
            b = tk.Button(name_grid, text=nm, font=("Segoe UI", 11, "bold"),
                          bg="#334155", fg=TEXT, activebackground="#475569",
                          activeforeground="#ffffff",
                          relief="flat", bd=0, padx=10, pady=8, cursor="hand2")
            b.config(command=lambda idx=i, btn=b: toggle_name(idx, btn))
            b.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
            name_btns[i] = b
        for c_idx in range(cols):
            name_grid.columnconfigure(c_idx, weight=1)

        # ── SHAPE GRID ──
        shape_header = tk.Canvas(content, width=580, height=28,
                                  bg=CARD, highlightthickness=0)
        shape_header.pack(anchor="w", padx=16, pady=(4, 2))
        shape_header.create_text(10, 14,
                                 text=f"🔷  Pick {num_pairs} shape{'s' if num_pairs > 1 else ''}:",
                                 font=("Segoe UI", 12, "bold"), fill=TEXT, anchor="w")

        shape_grid = tk.Frame(content, bg=CARD)
        shape_grid.pack(fill="x", padx=20, pady=(0, 8))

        def toggle_shape(idx, border_frame, cvs):
            if idx in shape_sel_idx:
                shape_sel_idx.discard(idx)
                border_frame.config(bg="#0f172a")
                cvs.config(bg="#0f172a")
            else:
                if len(shape_sel_idx) >= num_pairs:
                    border_frame.config(bg="#ef4444")
                    state["anim_jobs"].append(
                        _win.after(300, lambda bf=border_frame: bf.config(bg="#0f172a")))
                    return
                shape_sel_idx.add(idx)
                border_frame.config(bg="#6366f1")
                cvs.config(bg="#1a1040")

        cols_s = 4
        for i, (sh, col) in enumerate(all_shapes):
            r, c = divmod(i, cols_s)
            border = tk.Frame(shape_grid, bg="#0f172a", padx=3, pady=3)
            border.grid(row=r, column=c, padx=5, pady=5)
            cvs = tk.Canvas(border, width=60, height=60, bg="#0f172a",
                           highlightthickness=0, cursor="hand2")
            cvs.pack()
            draw_shape(cvs, sh, col, 30, 30, 38)
            cvs.bind("<Button-1>",
                     lambda e, idx=i, bf=border, cv=cvs: toggle_shape(idx, bf, cv))
            shape_borders[i] = border
            shape_canvases[i] = cvs
        for c_idx in range(cols_s):
            shape_grid.columnconfigure(c_idx, weight=1)

        # ── SUBMIT with counter ──
        submit_row = tk.Frame(content, bg=CARD)
        submit_row.pack(fill="x", padx=20, pady=(4, 0))

        pick_info = tk.Label(submit_row, text=f"Selected: 0/{num_pairs} names, 0/{num_pairs} shapes",
                             font=("Segoe UI", 10), bg=CARD, fg=SUBTLE)
        pick_info.pack(side="left", padx=(4, 0))

        def refresh_counter():
            pick_info.config(
                text=f"Selected: {len(name_sel_idx)}/{num_pairs} names, "
                     f"{len(shape_sel_idx)}/{num_pairs} shapes")
            try:
                if _win.winfo_exists():
                    state["anim_jobs"].append(_win.after(200, refresh_counter))
            except Exception:
                pass

        refresh_counter()

        def submit_round():
            cancel_anims()

            # Disable all buttons to prevent further clicks
            for btn in name_btns.values():
                btn.config(state="disabled")
            for cvs in shape_canvases.values():
                cvs.unbind("<Button-1>")

            # Score: compare selected indices vs correct indices
            name_correct = len(name_sel_idx & correct_name_indices)
            shape_correct = len(shape_sel_idx & correct_shape_indices)

            round_score = (name_correct + shape_correct) * pts_per
            state["total_score"] += round_score

            # ── Reveal correct answers ──
            # Names: green = correct & selected, red = selected & wrong, outline green = correct & not selected
            for i, btn in name_btns.items():
                btn.config(state="normal")
                is_correct = i in correct_name_indices
                was_selected = i in name_sel_idx
                if is_correct and was_selected:
                    btn.config(bg="#10b981", fg="#ffffff")   # green: correct pick
                elif is_correct and not was_selected:
                    btn.config(bg="#065f46", fg="#6ee7b7")   # dark green: missed answer
                elif not is_correct and was_selected:
                    btn.config(bg="#ef4444", fg="#ffffff")    # red: wrong pick
                else:
                    btn.config(bg="#1e293b", fg="#475569")    # dimmed: irrelevant
                btn.config(state="disabled")

            # Shapes: same logic with border colors
            for i, border in shape_borders.items():
                is_correct = i in correct_shape_indices
                was_selected = i in shape_sel_idx
                if is_correct and was_selected:
                    border.config(bg="#10b981")               # green
                elif is_correct and not was_selected:
                    border.config(bg="#065f46")               # dark green: missed
                elif not is_correct and was_selected:
                    border.config(bg="#ef4444")               # red: wrong pick
                else:
                    border.config(bg="#0f172a")               # dimmed

            # Update pick_info with results
            total_possible = num_pairs * 2
            got = name_correct + shape_correct
            name_icon = "✅" if name_correct == num_pairs else "❌"
            shape_icon = "✅" if shape_correct == num_pairs else "❌"
            pick_info.config(
                text=f"{name_icon} Names: {name_correct}/{num_pairs}   "
                     f"{shape_icon} Shapes: {shape_correct}/{num_pairs}   "
                     f"+{round_score} pts",
                fg="#facc15" if got == total_possible else
                   "#22d3ee" if got > 0 else "#ef4444")

            # Replace submit button with Next/Final
            for w in submit_row.winfo_children():
                if isinstance(w, tk.Frame) and hasattr(w, 'btn'):
                    w.destroy()

            state["round"] += 1
            update_progress()

            if state["round"] < len(ROUNDS):
                make_btn(submit_row, "➡️  Next Round", start_round, width=14,
                        variant="accent").pack(side="right")
            else:
                make_btn(submit_row, "🏆  See Results", show_final, width=14,
                        variant="accent").pack(side="right")

        make_btn(submit_row, "✅  Submit", submit_round, width=12,
                variant="accent").pack(side="right")

    def show_final():
        """Show final score with dramatic reveal and Play Again / Exit."""
        clear_content()
        final = min(state["total_score"], 30)

        if final >= 28:
            grade, grade_color = "🧠 Photographic Memory!", "#facc15"
        elif final >= 22:
            grade, grade_color = "🌟 Excellent Recall!", "#22d3ee"
        elif final >= 16:
            grade, grade_color = "👏 Great Memory!", "#a855f7"
        elif final >= 10:
            grade, grade_color = "👍 Not Bad!", "#10b981"
        else:
            grade, grade_color = "😬 Keep Practising!", "#ef4444"

        final_cvs = tk.Canvas(content, width=580, height=260,
                               bg=CARD, highlightthickness=0)
        final_cvs.pack(expand=True)

        final_cvs.create_text(290, 30, text="🏆  GAME OVER  🏆",
                               font=("Segoe UI", 14, "bold"), fill=SUBTLE)

        # Big score circle
        sc_cx, sc_cy, sc_r = 290, 120, 55
        final_cvs.create_oval(sc_cx - sc_r, sc_cy - sc_r,
                               sc_cx + sc_r, sc_cy + sc_r,
                               fill="#151d30", outline="#6366f1", width=3)
        score_text = final_cvs.create_text(sc_cx, sc_cy - 8,
                                            text="0",
                                            font=("Segoe UI", 32, "bold"),
                                            fill=ACCENT)
        final_cvs.create_text(sc_cx, sc_cy + 24,
                               text="/ 30",
                               font=("Segoe UI", 12), fill=SUBTLE)

        grade_text = final_cvs.create_text(290, 210, text="",
                                            font=("Segoe UI", 18, "bold"),
                                            fill=grade_color)

        # Animated score count-up
        def count_up_final(current):
            if current > final:
                return
            try:
                if not _win.winfo_exists():
                    return
            except Exception:
                return
            final_cvs.itemconfig(score_text, text=str(current))
            if current == final:
                final_cvs.itemconfig(grade_text, text=grade)
            else:
                state["anim_jobs"].append(
                    _win.after(60, lambda: count_up_final(current + 1)))

        state["anim_jobs"].append(_win.after(500, lambda: count_up_final(0)))

        add_score(final, celebrate=final >= 20, message=f"Memory Match: {final}/30")

        end_row = tk.Frame(content, bg=CARD)
        end_row.pack(pady=(8, 0))

        def play_again():
            _win.destroy()
            _run_memory_match()

        make_btn(end_row, "🔄  Play Again", play_again, width=13).pack(side="left", padx=(0, 6))
        make_btn(end_row, "🚪  Exit", lambda: _win.destroy(), width=10).pack(side="right")

    # Kick off round 1
    start_round()

    def on_close():
        cancel_anims()
        _win.destroy()

    _win.protocol("WM_DELETE_WINDOW", on_close)


def start_intelligence_test():
    test_scores = {"hangman": None, "number": None, "word": None, "math": None}
    max_scores = {"hangman": 10, "number": 30, "word": 30, "math": 30}

    win, card = make_card_window("Intelligence Test", width=720, height=620)

    styled_label(card, text="Intelligence Test", font=("Segoe UI", 20, "bold")).pack(pady=(0, 4))
    styled_label(
        card,
        text="Play all 4 games. Your combined performance determines your Intelligence %.",
        font=("Segoe UI", 11),
        fg=SUBTLE,
    ).pack(pady=(0, 16))

    game_frame = tk.Frame(card, bg=CARD)
    game_frame.pack(fill="x", padx=10, pady=6)

    hangman_status = tk.StringVar(value="Not played")
    number_status = tk.StringVar(value="Not played")
    word_status = tk.StringVar(value="Not played")
    math_status = tk.StringVar(value="Not played")

    result_var = tk.StringVar(value="")
    detail_var = tk.StringVar(value="")

    btn_refs = {}

    def check_all_done():
        if all(v is not None for v in test_scores.values()):
            show_iq_results()

    def show_iq_results():
        h_pct = (test_scores["hangman"] / max_scores["hangman"]) * 100
        n_pct = (test_scores["number"] / max_scores["number"]) * 100
        w_pct = (test_scores["word"] / max_scores["word"]) * 100
        m_pct = (test_scores["math"] / max_scores["math"]) * 100
        iq_pct = (h_pct + n_pct + w_pct + m_pct) / 4

        if iq_pct >= 90:
            grade = "Genius"
        elif iq_pct >= 75:
            grade = "Excellent"
        elif iq_pct >= 60:
            grade = "Above Average"
        elif iq_pct >= 40:
            grade = "Average"
        elif iq_pct >= 20:
            grade = "Below Average"
        else:
            grade = "Needs Practice"

        detail_var.set(
            f"Hangman: {h_pct:.0f}%  |  Number: {n_pct:.0f}%  |  Word: {w_pct:.0f}%  |  Math: {m_pct:.0f}%"
        )
        result_var.set(f"Intelligence Score:  {iq_pct:.1f}%  --  {grade}")
        play_win_sound()
        start_bg_cycle()
        if current_user is not None:
            is_new_best = save_best_score(
                current_user, iq_pct,
                test_scores["hangman"], test_scores["number"], test_scores["word"],
                test_scores["math"],
            )
            if is_new_best:
                result_var.set(
                    f"Intelligence Score:  {iq_pct:.1f}%  --  {grade}  (NEW BEST!)"
                )

    def on_hangman_done(game_score):
        test_scores["hangman"] = max(game_score, 0)
        hangman_status.set(f"Done  {test_scores['hangman']} / {max_scores['hangman']}")
        btn_refs["hangman"].btn.config(state="disabled")
        check_all_done()

    def on_number_done(game_score):
        test_scores["number"] = max(game_score, 0)
        number_status.set(f"Done  {test_scores['number']} / {max_scores['number']}")
        btn_refs["number"].btn.config(state="disabled")
        check_all_done()

    def on_word_done(game_score):
        test_scores["word"] = max(game_score, 0)
        word_status.set(f"Done  {test_scores['word']} / {max_scores['word']}")
        btn_refs["word"].btn.config(state="disabled")
        check_all_done()

    def on_math_done(game_score):
        test_scores["math"] = max(game_score, 0)
        math_status.set(f"Done  {test_scores['math']} / {max_scores['math']}")
        btn_refs["math"].btn.config(state="disabled")
        check_all_done()

    for name, key, status_local, open_fn, callback in [
        ("Hangman", "hangman", hangman_status, open_hangman, on_hangman_done),
        ("Number Game", "number", number_status, open_number, on_number_done),
        ("Word Game", "word", word_status, open_word, on_word_done),
        ("Math Game", "math", math_status, open_math, on_math_done),
    ]:
        row = tk.Frame(game_frame, bg=CARD)
        row.pack(fill="x", pady=8, padx=6)
        styled_label(row, text=name, font=("Segoe UI", 13, "bold")).pack(side="left")
        styled_label(row, textvariable=status_local, fg=SUBTLE, font=("Segoe UI", 11)).pack(
            side="left", padx=(16, 0)
        )
        btn = make_btn(
            row,
            "Play",
            lambda fn=open_fn, cb=callback: fn(test_callback=cb),
            width=10,
            variant="accent",
        )
        btn.pack(side="right")
        btn_refs[key] = btn

    tk.Frame(card, bg=SUBTLE, height=1).pack(fill="x", padx=20, pady=(16, 10))

    detail_label = styled_label(card, textvariable=detail_var, font=("Segoe UI", 11), fg=SUBTLE)
    detail_label.config(wraplength=600, justify="center")
    detail_label.pack(pady=(10, 4), fill="x")

    result_label = styled_label(card, textvariable=result_var, font=("Segoe UI", 16, "bold"), fg=ACCENT)
    result_label.config(wraplength=600, justify="center")
    result_label.pack(pady=(4, 10), fill="x")


create_banner(root)

# ── Shared navigation variables ────────────────────────────────────────────
welcome_var = tk.StringVar(value="")
best_score_var = tk.StringVar(value="")
login_status_var = tk.StringVar(value="")


def show_main(username):
    global current_user, score, displayed_score
    current_user = username
    login_frame.pack_forget()
    main_frame.pack(expand=True, fill="both")
    center.lift()
    welcome_var.set(f"Welcome, {username}!")
    users = load_users()
    profile = users.get(username, {})
    # Restore saved score
    score = profile.get("score", 0)
    displayed_score = score
    score_var.set(f"Score: {score}")
    best = profile.get("best_iq", 0)
    if best > 0:
        best_score_var.set(f"Personal Best: {best}%")
    else:
        best_score_var.set("No intelligence test taken yet")
    refresh_brainiac_btn()


def do_logout():
    global current_user, score, displayed_score
    _save_user_score()
    current_user = None
    score = 0
    displayed_score = 0
    score_var.set("Score: 0")
    main_frame.pack_forget()
    login_frame.pack(expand=True)
    login_user_entry.delete(0, tk.END)
    login_pass_entry.delete(0, tk.END)
    login_status_var.set("")


def do_login(_event=None):
    username = login_user_entry.get().strip()
    password = login_pass_entry.get().strip()
    if not username or not password:
        login_status_var.set("Enter both username and password.")
        return
    users = load_users()
    if username not in users:
        login_status_var.set("User not found. Register first.")
        return
    if users[username]["password_hash"] != hash_password(password):
        login_status_var.set("Wrong password.")
        return
    login_status_var.set("")
    show_main(username)


def do_register():
    username = login_user_entry.get().strip()
    password = login_pass_entry.get().strip()
    if not username or not password:
        login_status_var.set("Enter both username and password.")
        return
    if len(password) < 3:
        login_status_var.set("Password must be at least 3 characters.")
        return
    users = load_users()
    if username in users:
        login_status_var.set("Username already taken.")
        return
    users[username] = {
        "password_hash": hash_password(password),
        "best_iq": 0,
        "best_hangman": 0,
        "best_number": 0,
        "best_word": 0,
        "best_math": 0,
        "score": 0,
    }
    save_users(users)
    login_status_var.set("Registered! You can now log in.")


# ── Login Frame ────────────────────────────────────────────────────────────
login_frame = tk.Frame(root, bg=BG)
register_bg_target(login_frame)

login_card = tk.Frame(login_frame, bg=CARD, padx=40, pady=40)
login_card.pack(expand=True)

tk.Label(
    login_card, text="Welcome to Peji's Game Hub",
    font=("Segoe UI", 22, "bold"), bg=CARD, fg=TEXT,
).pack(pady=(0, 4))
tk.Label(
    login_card, text="Log in or register to track your Intelligence scores",
    font=("Segoe UI", 11), bg=CARD, fg=SUBTLE,
).pack(pady=(0, 24))

tk.Label(login_card, text="Username", font=("Segoe UI", 11), bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
login_user_entry = styled_entry(login_card)
login_user_entry.pack(fill="x", pady=(2, 10))

tk.Label(login_card, text="Password", font=("Segoe UI", 11), bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
login_pass_entry = tk.Entry(
    login_card, font=("Segoe UI", 12), justify="center",
    bg="#f8fafc", fg="#0f172a", relief="flat", width=18, show="*",
)
login_pass_entry.pack(fill="x", pady=(2, 16))

tk.Label(
    login_card, textvariable=login_status_var,
    font=("Segoe UI", 10), bg=CARD, fg=ACCENT, wraplength=300,
).pack(pady=(0, 10))

login_btn_row = tk.Frame(login_card, bg=CARD)
login_btn_row.pack(fill="x")
make_btn(login_btn_row, "Log In", do_login, width=12).pack(side="left", padx=(0, 8))
make_btn(login_btn_row, "Register", do_register, width=12, variant="accent").pack(side="right")
login_user_entry.bind("<Return>", do_login)
login_pass_entry.bind("<Return>", do_login)

# ── Main Frame (hidden until login) ───────────────────────────────────────
main_frame = tk.Frame(root, bg=BG)
register_bg_target(main_frame)

# Background canvas for interactive characters
main_canvas = tk.Canvas(main_frame, bg=BG, highlightthickness=0)
main_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

# Center container on top of canvas
center = tk.Frame(main_frame, bg=BG)
center.place(relx=0.5, rely=0.52, anchor="center")
center.lift()
register_bg_target(center)

welcome_label = tk.Label(center, textvariable=welcome_var, font=("Segoe UI", 14), bg=BG, fg=ACCENT)
welcome_label.pack(pady=(10, 0))
register_bg_target(welcome_label)

best_label = tk.Label(center, textvariable=best_score_var, font=("Segoe UI", 11), bg=BG, fg=SUBTLE)
best_label.pack(pady=(2, 0))
register_bg_target(best_label)

title_label = tk.Label(
    center,
    text="🎮 Game Hub 🎮",
    font=("Segoe UI", 32, "bold"),
    bg=BG,
    fg=TEXT,
)
title_label.pack(pady=(10, 4))
register_bg_target(title_label)

subtitle_label = tk.Label(
    center,
    text="Pick a game and build your score.",
    font=("Segoe UI", 13),
    bg=BG,
    fg=SUBTLE,
)
subtitle_label.pack(pady=(0, 20))
register_bg_target(subtitle_label)

btn_frame = tk.Frame(center, bg=BG)
btn_frame.pack(pady=10)
register_bg_target(btn_frame)

# Row 1 — four game buttons side by side
_game_btns = [
    ("💀  Hangman", open_hangman),
    ("🔢  Number Game", open_number),
    ("📝  Word Game", open_word),
    ("🧮  Math Game", open_math),
]
for col, (txt, cmd) in enumerate(_game_btns):
    make_btn(btn_frame, txt, cmd, width=14).grid(row=0, column=col, padx=6, pady=6)

# Row 2 — Intelligence Test and Brainiac side by side
_iq_btn = make_btn(btn_frame, "🧠  Intelligence Test", start_intelligence_test, variant="accent", width=18)
_iq_btn.grid(row=1, column=0, columnspan=2, padx=6, pady=(10, 4))

_brainiac_btn = make_btn(btn_frame, "🔒  Brainiac (90%+)", lambda: open_brainiac(), width=18)
_brainiac_btn.grid(row=1, column=2, columnspan=2, padx=6, pady=(10, 4))
_brainiac_btn.btn.config(state="disabled")  # locked by default

# Tooltip for Brainiac button
_brainiac_tip = None

def _show_brainiac_tip(_event):
    global _brainiac_tip
    if _brainiac_tip is not None:
        return
    tip = tk.Toplevel(root)
    tip.overrideredirect(True)
    tip.attributes("-topmost", True)
    tip.configure(bg="#1e293b")
    border = tk.Frame(tip, bg="#6366f1", padx=2, pady=2)
    border.pack()
    lbl = tk.Label(
        border,
        text="🔒  Score 90%+ on the Intelligence Test to unlock Brainiac!",
        font=("Segoe UI", 10, "bold"),
        bg="#1e293b", fg="#fde047",
        padx=10, pady=6,
    )
    lbl.pack()
    tip.update_idletasks()
    x = _brainiac_btn.winfo_rootx() + _brainiac_btn.winfo_width() // 2 - tip.winfo_reqwidth() // 2
    y = _brainiac_btn.winfo_rooty() - tip.winfo_reqheight() - 6
    tip.geometry(f"+{x}+{y}")
    _brainiac_tip = tip

def _hide_brainiac_tip(_event):
    global _brainiac_tip
    if _brainiac_tip is not None:
        try:
            _brainiac_tip.destroy()
        except Exception:
            pass
        _brainiac_tip = None

_brainiac_btn.btn.bind("<Enter>", _show_brainiac_tip, add="+")
_brainiac_btn.btn.bind("<Leave>", _hide_brainiac_tip, add="+")


def refresh_brainiac_btn():
    """Enable the Brainiac button only if the current user has 90%+ IQ (or is admin)."""
    if current_user is None:
        _brainiac_btn.btn.config(state="disabled")
        return
    # Admin override — peji can always access everything
    is_admin = (current_user == "peji")
    users = load_users()
    best = users.get(current_user, {}).get("best_iq", 0)
    if best >= 90 or is_admin:
        _brainiac_btn.btn.config(state="normal")
        try:
            _brainiac_btn.btn.config(text="🧬  Brainiac")
        except Exception:
            pass
    else:
        _brainiac_btn.btn.config(state="disabled")
        try:
            _brainiac_btn.btn.config(text="🔒  Brainiac (90%+)")
        except Exception:
            pass

# Score + logout in a horizontal bar below the buttons
bottom_bar = tk.Frame(center, bg=BG)
bottom_bar.pack(pady=(6, 10))
register_bg_target(bottom_bar)

score_label = tk.Label(
    bottom_bar,
    textvariable=score_var,
    bg=BG,
    fg=TEXT,
    font=("Segoe UI", 16, "bold"),
)
score_label.pack(side="left", padx=(0, 24))
register_bg_target(score_label)

make_btn(bottom_bar, "🚪  Log Out", lambda: do_logout(), width=10).pack(side="left")


# ── Interactive Characters System ─────────────────────────────────────────
class InteractiveCharacter:
    CHARACTERS = ["👾", "🤖", "👻", "🐸", "🎃", "🐱", "🐶", "🦊",
                  "🐧", "🐵", "👽", "🦄", "🐲", "🎭", "🤡", "💩"]
    REACTIONS = ["run", "jump", "spin", "grow", "shake", "teleport"]

    # Each character emoji gets a unique signature melody
    CHAR_MELODIES = {
        "👾": [(440, 80), (520, 80), (660, 100)],           # alien invader – ascending
        "🤖": [(200, 60), (800, 60), (200, 60), (800, 80)], # robot – beep boop
        "👻": [(900, 120), (700, 140), (500, 200)],          # ghost – descending wail
        "🐸": [(300, 50), (500, 50), (300, 50), (500, 50)],  # frog – ribbit ribbit
        "🎃": [(350, 100), (300, 120), (250, 150)],          # pumpkin – spooky low
        "🐱": [(1000, 80), (1200, 100), (1400, 80)],         # cat – high meow
        "🐶": [(600, 60), (600, 60), (800, 100)],            # dog – bark bark
        "🦊": [(700, 70), (900, 70), (700, 70)],             # fox – playful yip
        "🐧": [(500, 90), (550, 90), (500, 90)],             # penguin – waddle beep
        "🐵": [(800, 50), (1000, 50), (800, 50), (1000, 60)],# monkey – chatter
        "👽": [(1200, 60), (400, 80), (1200, 60)],           # alien – theremin
        "🦄": [(660, 100), (880, 100), (1100, 120), (1320, 140)], # unicorn – sparkle arp
        "🐲": [(200, 120), (250, 100), (300, 80), (200, 200)],    # dragon – roar
        "🎭": [(440, 80), (440, 80), (660, 120)],            # theatre – dramatic
        "🤡": [(1000, 40), (800, 40), (1000, 40), (600, 60)],# clown – silly honk
        "💩": [(150, 80), (180, 80), (150, 120)],             # poop – low blurp
    }

    def __init__(self, canvas):
        self.canvas = canvas
        self.char = random.choice(self.CHARACTERS)
        self.x = 0
        self.y = 0
        self.item = None
        self.animating = False
        self.alive = True
        self.speed_x = random.choice([-0.3, -0.2, 0.2, 0.3])
        self.speed_y = random.choice([-0.2, -0.1, 0.1, 0.2])
        self.idle_job = None
        self.melody = self.CHAR_MELODIES.get(self.char, [(440, 80), (520, 80)])

    GLOW_COLORS = ["#1e3a5f", "#2d1b4e", "#1b3d2f", "#3d2b1b", "#1b2d3d",
                    "#3d1b2d", "#2b3d1b", "#1b1b3d", "#3d3d1b", "#1b3d3d"]

    def spawn(self):
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            w, h = 1200, 700
        margin = 60
        self.x = random.randint(margin, max(w - margin, margin + 1))
        self.y = random.randint(margin, max(h - margin, margin + 1))
        glow_color = random.choice(self.GLOW_COLORS)
        r = 28
        self.glow = self.canvas.create_oval(
            self.x - r, self.y - r, self.x + r, self.y + r,
            fill=glow_color, outline="", width=0)
        self.item = self.canvas.create_text(
            self.x, self.y, text=self.char,
            font=("Segoe UI Emoji", 28), anchor="center",
            fill="#ffffff")
        self.canvas.tag_bind(self.item, "<Enter>", self._on_hover)
        self.canvas.tag_bind(self.glow, "<Enter>", self._on_hover)
        self.start_idle()

    def _move_to(self, x, y):
        """Move both glow and text to given coords."""
        self.x = x
        self.y = y
        r = 28
        try:
            self.canvas.coords(self.item, x, y)
            self.canvas.coords(self.glow, x - r, y - r, x + r, y + r)
        except Exception:
            pass

    def start_idle(self):
        """Gentle floating drift."""
        if not self.alive:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return
        if self.animating:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.x += self.speed_x
        self.y += self.speed_y
        if self.x < 30 or self.x > w - 30:
            self.speed_x *= -1
        if self.y < 30 or self.y > h - 30:
            self.speed_y *= -1
        self._move_to(self.x, self.y)
        self.idle_job = self.canvas.after(50, self.start_idle)

    def _play_my_sound(self):
        """Play this character's unique signature melody."""
        _play_melody_async(self.melody, volume=0.25)

    def _on_hover(self, _event):
        if self.animating:
            return
        self.animating = True
        if self.idle_job is not None:
            try:
                self.canvas.after_cancel(self.idle_job)
            except Exception:
                pass
            self.idle_job = None
        self._play_my_sound()
        reaction = random.choice(self.REACTIONS)
        if reaction == "run":
            self._do_run()
        elif reaction == "jump":
            self._do_jump()
        elif reaction == "spin":
            self._do_spin()
        elif reaction == "grow":
            self._do_grow()
        elif reaction == "shake":
            self._do_shake()
        elif reaction == "teleport":
            self._do_teleport()

    def _finish_anim(self):
        """After animation cycle completes, fade out then destroy."""
        self._fade_out()

    def _fade_out(self, step=0):
        """Shrink font + glow to nothing over several frames, then destroy & respawn."""
        if not self.alive:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:
            return
        total_steps = 10
        if step >= total_steps:
            self.destroy()
            _respawn_one_character()
            return
        # Shrink font from 28 down to 0
        font_size = max(1, int(28 * (1 - step / total_steps)))
        glow_r = max(1, int(28 * (1 - step / total_steps)))
        try:
            self.canvas.itemconfig(self.item, font=("Segoe UI Emoji", font_size))
            self.canvas.coords(self.glow,
                               self.x - glow_r, self.y - glow_r,
                               self.x + glow_r, self.y + glow_r)
        except Exception:
            pass
        self.canvas.after(40, lambda: self._fade_out(step + 1))

    def _do_run(self):
        """Run off screen, then finish animation."""
        w = self.canvas.winfo_width()
        dx = 12 if self.x < w / 2 else -12
        dy = random.choice([-3, -1, 0, 1, 3])
        scared_faces = ["😱", "🏃", "💨", "😨"]

        def step(count=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if count > 40:
                self.canvas.itemconfig(self.item, text=self.char)
                self._finish_anim()
                return
            self._move_to(self.x + dx, self.y + dy)
            if count < 4:
                self.canvas.itemconfig(self.item, text=random.choice(scared_faces))
            self.canvas.after(16, lambda: step(count + 1))

        step()

    def _do_jump(self):
        """Jump up and bounce back down."""
        base_y = self.y
        offsets = [0, -8, -18, -30, -42, -50, -54, -50, -42, -30, -18, -8, 0, 4, 0]

        def step(i=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if i >= len(offsets):
                self._move_to(self.x, base_y)
                self.canvas.itemconfig(self.item, text=self.char)
                self._finish_anim()
                return
            self._move_to(self.x, base_y + offsets[i])
            if i < 3:
                self.canvas.itemconfig(self.item, text="😮")
            elif offsets[i] == min(offsets):
                self.canvas.itemconfig(self.item, text="🤩")
            self.canvas.after(35, lambda: step(i + 1))

        step()

    def _do_spin(self):
        """Spin by cycling through characters rapidly."""
        spin_chars = ["🌀", "💫", "✨", "⭐", "💫", "🌀", "✨"]
        total = 14
        base_x, base_y = self.x, self.y

        def step(i=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if i >= total:
                self._move_to(base_x, base_y)
                self.canvas.itemconfig(self.item, text=self.char)
                self._finish_anim()
                return
            self.canvas.itemconfig(self.item, text=spin_chars[i % len(spin_chars)])
            angle = (i / total) * 2 * math.pi
            nx = base_x + math.cos(angle) * 15
            ny = base_y + math.sin(angle) * 15
            self._move_to(nx, ny)
            self.canvas.after(60, lambda: step(i + 1))

        step()

    def _do_grow(self):
        """Grow big then shrink back, looking surprised."""
        sizes = [28, 32, 38, 44, 50, 44, 38, 32, 28]
        faces = ["😲", "😲", "🤯", "🤯", "🤯", "😲", "😲", self.char, self.char]

        def step(i=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if i >= len(sizes):
                self.canvas.itemconfig(self.item, text=self.char, font=("Segoe UI Emoji", 28))
                self._finish_anim()
                return
            self.canvas.itemconfig(self.item, text=faces[i],
                                   font=("Segoe UI Emoji", sizes[i]))
            self.canvas.after(80, lambda: step(i + 1))

        step()

    def _do_shake(self):
        """Shake violently and show angry face."""
        offsets = [5, -5, 6, -6, 4, -4, 3, -3, 2, -2, 1, -1, 0]
        faces = ["😡", "🤬", "😤", "😡", "🤬", "😤", "😡", "😤", "😡", "😤", "😡", "😤", self.char]
        base_x = self.x

        def step(i=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if i >= len(offsets):
                self._move_to(base_x, self.y)
                self.canvas.itemconfig(self.item, text=self.char)
                self._finish_anim()
                return
            self._move_to(base_x + offsets[i], self.y)
            self.canvas.itemconfig(self.item, text=faces[i])
            self.canvas.after(50, lambda: step(i + 1))

        step()

    def _do_teleport(self):
        """Flash and reappear at a random spot."""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        flash_chars = ["✨", "💫", "⚡", "💥", "✨"]

        def step(i=0):
            if not self.alive or not self.canvas.winfo_exists():
                return
            if i < len(flash_chars):
                self.canvas.itemconfig(self.item, text=flash_chars[i])
                if i == 2:
                    nx = random.randint(60, max(w - 60, 61))
                    ny = random.randint(60, max(h - 60, 61))
                    self._move_to(nx, ny)
                self.canvas.after(80, lambda: step(i + 1))
            else:
                self.canvas.itemconfig(self.item, text=self.char)
                self._finish_anim()

        step()

    def destroy(self):
        self.alive = False
        if self.idle_job is not None:
            try:
                self.canvas.after_cancel(self.idle_job)
            except Exception:
                pass
        try:
            self.canvas.delete(self.item)
        except Exception:
            pass
        try:
            self.canvas.delete(self.glow)
        except Exception:
            pass


characters = []
NUM_CHARACTERS = 14


def _respawn_one_character():
    """Spawn a fresh replacement character after one fades out."""
    try:
        if not main_canvas.winfo_exists():
            return
    except Exception:
        return
    used = [ch.char for ch in characters if ch.alive]
    c = InteractiveCharacter(main_canvas)
    # pick an unused emoji if possible
    available = [e for e in InteractiveCharacter.CHARACTERS if e not in used]
    if available:
        c.char = random.choice(available)
        c.melody = InteractiveCharacter.CHAR_MELODIES.get(c.char, [(440, 80), (520, 80)])
    c.spawn()
    characters.append(c)


def spawn_characters():
    for ch in characters:
        ch.destroy()
    characters.clear()
    used_chars = []
    for _ in range(NUM_CHARACTERS):
        c = InteractiveCharacter(main_canvas)
        # avoid duplicate emojis
        while c.char in used_chars and len(used_chars) < len(InteractiveCharacter.CHARACTERS):
            c.char = random.choice(InteractiveCharacter.CHARACTERS)
        c.melody = InteractiveCharacter.CHAR_MELODIES.get(c.char, [(440, 80), (520, 80)])
        used_chars.append(c.char)
        c.spawn()
        characters.append(c)


def clear_characters():
    for ch in characters:
        ch.destroy()
    characters.clear()


# spawn characters when main frame is shown
_orig_show_main = show_main


def show_main_with_chars(username):
    _orig_show_main(username)
    root.after(300, spawn_characters)


show_main = show_main_with_chars

# clear characters on logout
_orig_do_logout = do_logout


def do_logout_with_chars():
    clear_characters()
    _orig_do_logout()


do_logout = do_logout_with_chars

# rebind logout button after it's created
# (handled below when the button is created)

# ── Start with login screen ───────────────────────────────────────────────
login_frame.pack(expand=True)
login_user_entry.focus_set()

root.mainloop()
