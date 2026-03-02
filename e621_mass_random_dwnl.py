
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from tqdm.asyncio import tqdm_asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import random
import threading


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


class E621DownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("e621 Random Downloader v2")
        self.root.geometry("820x680")

        self.running = False
        self.session = None
        self.loop = None
        self.stop_requested = False

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root, padding="12")
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Tags
        ttk.Label(frame, text="Tags :").grid(row=0, column=0, sticky="w", pady=5)
        self.tags_var = tk.StringVar(value="twink rating:e")
        ttk.Entry(frame, textvariable=self.tags_var, width=55).grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        # Nombre
        ttk.Label(frame, text="Number :").grid(row=1, column=0, sticky="w", pady=5)
        self.count_var = tk.IntVar(value=60)
        ttk.Spinbox(frame, from_=10, to=5000, increment=10, textvariable=self.count_var, width=12).grid(row=1, column=1, sticky="w")

        # Score min
        ttk.Label(frame, text="Score ≥ :").grid(row=2, column=0, sticky="w", pady=5)
        self.min_score_var = tk.IntVar(value=10)
        ttk.Spinbox(frame, from_=-100, to=1000, increment=5, textvariable=self.min_score_var, width=12).grid(row=2, column=1, sticky="w")

        # Dossier
        ttk.Label(frame, text="Output Folder :").grid(row=3, column=0, sticky="w", pady=5)
        self.output_var = tk.StringVar(value=str(Path("e621_downloads").resolve()))
        ttk.Entry(frame, textvariable=self.output_var, width=55).grid(row=3, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.choose_folder).grid(row=3, column=2, padx=8)

        # Options
        self.skip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Ignore existing files", variable=self.skip_var).grid(row=4, column=1, sticky="w", pady=8)

        # Boutons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=12, sticky="ew")

        self.start_btn = ttk.Button(btn_frame, text="START", command=self.start)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ttk.Button(btn_frame, text="STOP", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        self.bypass_btn = ttk.Button(btn_frame, text="Bypass / Retry", command=self.fake_bypass_attempt, state="disabled")
        self.bypass_btn.pack(side="left", padx=10)

        # Log
        self.log_text = scrolledtext.ScrolledText(frame, height=20, state="normal", font=("Consolas", 10))
        self.log_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=10)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(6, weight=1)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def fake_bypass_attempt(self):
        if not self.running:
            self.log("→ Rien en cours...")
            return

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
            async with self.session.get(file_url, timeout=60) as resp:
                if resp.status != 200:
                    self.log(f"Échec {resp.status} → {dest.name}")
                    return False

                dest.parent.mkdir(parents=True, exist_ok=True)
                total_size = int(resp.headers.get("content-length", 0))

                async with aiofiles.open(dest, "wb") as f:
                    if total_size == 0:
                        await f.write(await resp.read())
                        return True

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
                            pbar.update(len(chunk))

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
                        continue

                    tasks.append(self.download_file(file_url, destination))

                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, bool) and res:
                            downloaded += 1
                            pbar_global.update(1)

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
            self.root.after(0, self.finish_ui)

    def finish_ui(self):
        self.running = False
        self.start_btn["state"] = "normal"
        self.stop_btn["state"] = "disabled"
        self.bypass_btn["state"] = "disabled"
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

        threading.Thread(target=self.run_async_in_thread, daemon=True).start()

    def stop(self):
        if not self.running:
            return
        self.stop_requested = True
        self.log("→ Stop requested... (wait for current page to finish)")


def main():
    root = tk.Tk()
    app = E621DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()