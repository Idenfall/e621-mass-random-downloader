
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from tqdm.asyncio import tqdm_asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import random
import threading
import json
import os
import time
import io

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = None
    ImageTk = None

try:
    from pypresence import Presence
except ImportError:  # pragma: no cover
    Presence = None

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────

BASE_URL = "https://e621.net"

USER_AGENTS = [
    "e621-downloader/1.2 (by votrepseudo on e621)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

LIMIT_PER_PAGE = 320
VIDEO_EXTS = {".webm", ".mp4", ".mov"}

# Discord Rich Presence
# Set DISCORD_RP_APP_ID environment variable to your Discord application's client ID (as a string).
# Example (PowerShell): $env:DISCORD_RP_APP_ID='123456789012345678'
DISCORD_RP_APP_ID = os.getenv("DISCORD_RP_APP_ID", "1479887230335189164").strip()


class DiscordRichPresence:
    def __init__(self, app_id: str, logger=None):
        self.app_id = app_id
        self.logger = logger
        self.rpc = None
        self.connected = False
        self.start_time = int(time.time())

    def start(self):
        if not Presence:
            if self.logger:
                self.logger("[RichPresence] pypresence not installed; rich presence disabled.")
            return
        if not self.app_id:
            if self.logger:
                self.logger("[RichPresence] DISCORD_RP_APP_ID not set; rich presence disabled.")
            return
        try:
            self.rpc = Presence(self.app_id)
            self.rpc.connect()
            self.connected = True
            self.update(state="Idle", details="Waiting to start")
            if self.logger:
                self.logger("[RichPresence] connected to Discord.")
        except Exception as e:
            if self.logger:
                self.logger(f"[RichPresence] init failed: {e}")

    def update(self, *, state: str = None, details: str = None, large_image: str = "default", small_image: str = "download"):
        if not self.connected or not self.rpc:
            return
        try:
            self.rpc.update(
                state=state,
                details=details,
                large_image=large_image,
                small_image=small_image,
                start=self.start_time,
            )
        except Exception as e:
            if self.logger:
                self.logger(f"[RichPresence] update failed: {e}")

    def stop(self):
        if not self.connected or not self.rpc:
            return
        try:
            self.rpc.clear()
            self.rpc.close()
        except Exception as e:
            if self.logger:
                self.logger(f"[RichPresence] stop failed: {e}")
        finally:
            self.connected = False


class E621DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("e621 Random Downloader v2")
        self.root.geometry("1020x680")

        # Apply UI theme matching e621's dark/orange palette
        self.apply_e621_theme()

        self.running = False
        self.session = None
        self.loop = None
        self.stop_requested = False

        self.create_widgets()

        # Discord Rich Presence (optional)
        self.rich_presence = DiscordRichPresence(DISCORD_RP_APP_ID, logger=self.log)
        self.rich_presence.start()


    def create_widgets(self):
        # Layout: left side is controls+log, right side is preview
        root_frame = ttk.Frame(self.root, padding="12")
        root_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(root_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right_frame = ttk.Frame(root_frame, width=320)
        right_frame.grid(row=0, column=1, sticky="nsew")

        root_frame.columnconfigure(0, weight=1)
        root_frame.columnconfigure(1, weight=0)
        root_frame.rowconfigure(0, weight=1)

        # Controls (left)
        # Tags
        ttk.Label(left_frame, text="Tags :").grid(row=0, column=0, sticky="w", pady=5)
        self.tags_var = tk.StringVar(value="twink rating:e")
        ttk.Entry(left_frame, textvariable=self.tags_var, width=55).grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        # Nombre
        ttk.Label(left_frame, text="Number :").grid(row=1, column=0, sticky="w", pady=5)
        self.count_var = tk.IntVar(value=60)
        ttk.Spinbox(left_frame, from_=10, to=5000, increment=10, textvariable=self.count_var, width=12).grid(row=1, column=1, sticky="w")

        # Score min
        ttk.Label(left_frame, text="Score ≥ :").grid(row=2, column=0, sticky="w", pady=5)
        self.min_score_var = tk.IntVar(value=10)
        ttk.Spinbox(left_frame, from_=-100, to=1000, increment=5, textvariable=self.min_score_var, width=12).grid(row=2, column=1, sticky="w")

        # Dossier
        ttk.Label(left_frame, text="Output Folder :").grid(row=3, column=0, sticky="w", pady=5)
        self.output_var = tk.StringVar(value=str(Path("e621_downloads").resolve()))
        ttk.Entry(left_frame, textvariable=self.output_var, width=55).grid(row=3, column=1, sticky="ew")
        ttk.Button(left_frame, text="Browse", command=self.choose_folder).grid(row=3, column=2, padx=8)

        # Options
        self.skip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_frame, text="Ignore existing files", variable=self.skip_var).grid(row=4, column=1, sticky="w", pady=8)

        # Boutons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=12, sticky="ew")

        self.start_btn = ttk.Button(btn_frame, text="START", command=self.start)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ttk.Button(btn_frame, text="STOP", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        self.bypass_btn = ttk.Button(btn_frame, text="Bypass / Retry", command=self.fake_bypass_attempt, state="disabled")
        self.bypass_btn.pack(side="left", padx=10)

        # Log
        self.log_text = scrolledtext.ScrolledText(
            left_frame,
            height=20,
            state="normal",
            font=("Consolas", 10),
            background="#1b1b1b",
            foreground="#e8e8e8",
            insertbackground="#e8e8e8",
            highlightthickness=0,
            bd=0,
        )
        self.log_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=10)
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(6, weight=1)

        # Preview (right)
        ttk.Label(right_frame, text="Preview", font=(None, 12, "bold")).pack(anchor="nw")
        self.preview_label = ttk.Label(right_frame, text="No preview", anchor="center")
        self.preview_label.pack(fill="both", expand=True, pady=8)

        self.preview_image = None  # keep reference to prevent GC


    def apply_e621_theme(self):
        """Apply an e621-like dark theme (dark background + orange accents)."""
        try:
            style = ttk.Style(self.root)
            style.theme_use("clam")
        except tk.TclError:
            style = ttk.Style()

        bg = "#0b1018"          # main background (dark blue/black)
        fg = "#e8e8e8"          # text
        entry_bg = "#111827"    # entry/background fields (dark navy)
        button_bg = "#121b2c"   # button background (dark blue)
        accent = "#ff9900"      # e621 orange

        style.configure(".", background=bg, foreground=fg, fieldbackground=entry_bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TButton", background=button_bg, foreground=fg, borderwidth=0, relief="flat")
        style.configure("TCheckbutton", background=bg, foreground=fg, borderwidth=0, relief="flat")
        style.configure("TEntry", fieldbackground=entry_bg, background=bg, foreground=fg, borderwidth=0, relief="flat")
        style.configure("TSpinbox", fieldbackground=entry_bg, background=bg, foreground=fg, borderwidth=0, relief="flat")

        # Accent for active/hover states + disabled state styling
        style.map(
            "TButton",
            background=[
                ("disabled", "#070b11"),
                ("active", accent),
                ("pressed", accent),
            ],
            foreground=[
                ("disabled", "#777777"),
                ("active", "#111111"),
                ("pressed", "#111111"),
            ],
        )

        self.root.configure(background=bg)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def set_preview_text(self, text: str):
        """Update the preview pane with text (clears image)."""
        self.preview_label.configure(text=text, image="")

    def set_preview_image(self, pil_image):
        """Set preview pane image from a PIL Image."""
        if not ImageTk:
            return
        self.preview_image = ImageTk.PhotoImage(pil_image)
        self.preview_label.configure(image=self.preview_image, text="")

    def update_preview_from_bytes(self, data: bytes):
        """Try to render image preview from raw bytes."""
        if not Image:
            return
        try:
            img = Image.open(io.BytesIO(data))
            img.thumbnail((320, 320), Image.LANCZOS)
            self.set_preview_image(img)
        except Exception:
            # Not an image, ignore
            pass

    def update_presence(self, downloaded: int, total: int, tags: str):
        """Update Discord Rich Presence status (no-op if RPC not running)."""
        if not getattr(self, "rich_presence", None) or not self.rich_presence.connected:
            return
        state = f"Tags: {tags}" if tags else "Downloading"
        details = f"{downloaded}/{total} downloaded"
        self.rich_presence.update(state=state, details=details)

    def update_stats(self, downloaded_count: int, tags: str):
        """Update any UI stats after a download session completes."""
        self.log(f"Stats: downloaded {downloaded_count} files for tags '{tags}'")

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def fake_bypass_attempt(self):
        if not self.running:
            self.log("→ Rien en cours...")
            return

        # Update presence to indicate panic/bypass attempt
        self.rich_presence.update(state="Panic", details="Bypass attempt")

        self.log("!!! ATTEMPT TO BYPASS (not magic) !!!")
        self.log("→ User-Agent change...")
        self.log("→ Increased delays...")
        self.log("→ Simulating new connection...")

        if self.session and not self.session.closed:
            new_ua = random.choice(USER_AGENTS)
            self.session.headers.update({"User-Agent": new_ua})
            self.log(f"New User-Agent → {new_ua}")

        self.log("→ Resume (if real IP ban → VPN or proxy required)")

    async def fetch_json(self, url, params=None):
        async with self.session.get(url, params=params, timeout=22) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"HTTP {resp.status} → {text[:160]}")
            return await resp.json()

    async def download_file(self, file_url: str, dest: Path):
        try:
            # update preview to show current download
            self.root.after(0, lambda: self.set_preview_text(f"Downloading {dest.name} ..."))

            async with self.session.get(file_url, timeout=60) as resp:
                if resp.status != 200:
                    self.log(f"Échec {resp.status} → {dest.name}")
                    return False

                dest.parent.mkdir(parents=True, exist_ok=True)
                total_size = int(resp.headers.get("content-length", 0))

                data = bytearray()
                async with aiofiles.open(dest, "wb") as f:
                    if total_size == 0:
                        chunk = await resp.read()
                        await f.write(chunk)
                        data.extend(chunk)
                    else:
                        with tqdm_asyncio(
                            total=total_size,
                            unit="B", unit_scale=True, unit_divisor=1024,
                            leave=False,
                            desc=dest.name[:32],
                        ) as pbar:
                            while True:
                                chunk = await resp.content.read(96 * 1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                                data.extend(chunk)
                                pbar.update(len(chunk))

                # Try to update preview (only if it looks like an image)
                if Path(dest).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    self.root.after(0, lambda d=bytes(data): self.update_preview_from_bytes(d))

                return True

        except Exception as e:
            self.log(f"Download error {dest.name} → {e}")
            return False

    async def main_download_logic(self):
        self.stop_requested = False
        output_dir = Path(self.output_var.get()).expanduser().resolve()
        tags = self.tags_var.get().strip()
        count = self.count_var.get()
        min_score = self.min_score_var.get()
        skip_existing = self.skip_var.get()

        self.log(f"Startup → {count} files | Tags: {tags}")
        self.log(f"Score ≥ {min_score} | Output Folder: {output_dir}")

        downloaded = 0
        page = 1
        search_tags = f"{tags} order:random"

        pbar_global = tqdm_asyncio(total=count, desc="Progression", unit=" fichier")

        while downloaded < count and not self.stop_requested:
            params = {
                "tags": search_tags,
                "limit": min(LIMIT_PER_PAGE, count - downloaded),
                "page": page,
            }
            if min_score > -500:
                params["score"] = f">{min_score}"

            try:
                data = await self.fetch_json(f"{BASE_URL}/posts.json", params)
                posts = data.get("posts", [])

                if not posts:
                    self.log("→ No more results (end of random search)")
                    break

                tasks = []

                for post in posts:
                    if self.stop_requested or downloaded >= count:
                        break

                    file_url = post.get("file", {}).get("url")
                    if not file_url:
                        continue

                    ext = Path(file_url).suffix.lower()
                    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"} | VIDEO_EXTS:
                        continue

                    post_id = post["id"]
                    filename = f"{post_id}{ext}"
                    destination = output_dir / filename

                    if skip_existing and destination.exists():
                        downloaded += 1
                        pbar_global.update(1)
                        self.update_presence(downloaded, count, tags)
                        continue

                    tasks.append(self.download_file(file_url, destination))

                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, bool) and res:
                            downloaded += 1
                            pbar_global.update(1)
                            self.update_presence(downloaded, count, tags)

                page += 1
                await asyncio.sleep(random.uniform(2.2, 6.0))

            except Exception as e:
                self.log(f"Erreur page {page} : {e}")
                await asyncio.sleep(10)

        pbar_global.close()
        self.log(f"\nFIN → {downloaded} / {count} downloaded files")
        self.stop_requested = False

    async def download_coroutine(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": random.choice(USER_AGENTS)}
        )
        try:
            await self.main_download_logic()
        finally:
            if self.session and not self.session.closed:
                await self.session.close()

    def run_async_in_thread(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.download_coroutine())
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Fatal error in asyncio thread : {e}"))
        finally:
            self.loop.close()
            # Get tags and count for stats update
            tags = self.tags_var.get().strip()
            count = self.count_var.get()
            self.root.after(0, lambda: self.finish_ui(count, tags))

    def finish_ui(self, downloaded_count=0, tags=""):
        # Update stats before finishing
        if downloaded_count > 0:
            self.update_stats(downloaded_count, tags)
        
        self.running = False
        self.start_btn["state"] = "normal"
        self.stop_btn["state"] = "disabled"
        self.bypass_btn["state"] = "disabled"

        # Update Discord presence to idle state
        self.rich_presence.update(state="Idle", details="Awaiting next download")

        self.log("→ Interface ready for a new session")

    def start(self):
        if self.running:
            return

        self.running = True
        self.start_btn["state"] = "disabled"
        self.stop_btn["state"] = "normal"
        self.bypass_btn["state"] = "normal"
        self.log_text.delete("1.0", tk.END)
        self.log("Starting download...")

        # Update presence
        tags = self.tags_var.get().strip()
        self.rich_presence.update(state=f"Searching [{tags}]" if tags else "Searching", details=f"0/{self.count_var.get()} downloaded")

        threading.Thread(target=self.run_async_in_thread, daemon=True).start()

    def stop(self):
        if not self.running:
            return
        self.stop_requested = True
        self.rich_presence.update(state="Stopping", details="Waiting for current page")
        self.log("→ Stop requested... (wait for current page to finish)")


def main():
    root = tk.Tk()
    app = E621DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
