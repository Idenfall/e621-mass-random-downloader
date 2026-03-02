# e621 mass Random Downloader

Modern, asynchronous, multi-file downloader for **e621.net** with a clean Tkinter GUI.

Downloads random posts according to your tags, with score filtering, video support (.webm/.mp4/.mov), skip-existing files logic, and a fake "Bypass ban" button for psychological comfort 😄

Written in Python 3.11+ — uses asyncio + aiohttp + tqdm progress bars — thread-safe GUI.

---

## Screenshot

(Add a real screenshot here – recommended size ~820×680 px)

![GUI Screenshot](screenshot.png)

---

## Features

- Random post selection (order:random)
- Supports images (.jpg .jpeg .png .gif .webp)
- Supports videos (.webm .mp4 .mov)
- Minimum score filter (GUI field OR directly in tags: score:>N)
- Skip already downloaded files (filename = post ID)
- Concurrent asynchronous downloads
- Per-file tqdm progress bars
- Polite random delays between pages (2.2–6 seconds)
- Rotating realistic User-Agents
- Graceful stop (finishes current page)
- Fake "Bypass / Retry" button:
  - Rotates User-Agent
  - Logs fake reassuring messages
  - Does NOT bypass real IP bans
- Folder selection via native dialog
- Scrollable log window

---

## Requirements

Python 3.11 or newer

Install dependencies:

pip install aiohttp aiofiles tqdm

---

## Installation

git clone https://github.com/YOUR_USERNAME/e621-random-downloader.git
cd e621-random-downloader

# Recommended: create a virtual environment
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
# venv\Scripts\activate

pip install aiohttp aiofiles tqdm

---

## Usage

python e621_random.py

---

## How to Use – Examples

Goal: Classic twink content
Tags: twink rating:e
Count: 150
Min Score: 20
Notes: Most common entry point

Goal: High-quality bara
Tags: bara muscular male_only rating:e
Count: 80
Min Score: 70
Notes: Focus on well-rated art

Goal: Specific character
Tags: undertale sans rating:e
Count: 60
Min Score: 40
Notes: Character-focused explicit

Goal: Only videos
Tags: twink rating:e (type:webm OR type:mp4)
Count: 30
Min Score: 15
Notes: Videos are slower – lower count advised

Goal: Recent popular
Tags: furry rating:e age:<2w
Count: 200
Min Score: 50
Notes: Last two weeks

Goal: Exclude categories
Tags: male rating:e -human -feral -scalie
Count: 250
Min Score: 35
Notes: -tag = exclude

Goal: Multiple species (OR)
Tags: (dragon wolf fox tiger horse) twink rating:e
Count: 120
Min Score: 25
Notes: Use parentheses

Goal: Strict quality filter
Tags: rating:e score:>150 favcount:>100
Count: 50
Min Score: 150
Notes: Extremely popular only

Goal: Classic furry
Tags: furry anthro rating:e -human
Count: 300
Min Score: 40
Notes: Standard furry search

---

## Quick Tag Syntax Reminders

Multi-word tags → "my little pony" or twilight_sparkle
Exclude → -tag
Optional → ~tag
Age filters → age:>3d  age:<1y  age:<2w
You can put score:>… directly in tags or use the GUI field

---

## Interface Buttons

DÉMARRER
→ Start downloading

STOP
→ Graceful stop (finishes current page)

Bypass / Retry
→ Fake unban simulation
→ Picks new random User-Agent
→ Logs fake comforting messages
→ Does NOT bypass real IP bans

---

## Real Ban Situation?

If you get rate-limited or banned:

- Change IP (VPN, mobile hotspot, proxy)
- Wait 12–48 hours
- Reduce count & speed

---

## Important Notes & Legal Reminder

- No authentication / API key → only public posts are accessible
- Heavy usage can trigger temporary IP bans
- Delays + UA rotation included, but no guarantee against bans
- Respect site rules — do not redistribute content without permission
- Not affiliated with e621.net

---

## Possible Future Improvements

- SOCKS5 / HTTP proxy support
- Tag blacklist field in GUI
- Failed download auto-retry
- Thumbnail preview
- Pause / resume queue
- Better rate-limit / ban detection

---

## License

MIT License (see LICENSE file)

---

Made with too much coffee and way too many 429 / 502 / 403 errors.

Happy (and responsible) downloading.
