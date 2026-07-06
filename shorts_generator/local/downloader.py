"""Local YouTube download via yt-dlp.

Returns a local mp4 path so the rest of the local pipeline can read it
directly off disk.
"""

import os
import re
import shutil
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Optional

from ..config import LOCAL_OUTPUT_DIR


def _import_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "yt-dlp is required for --mode local. Install it with:\n"
            "    pip install -r requirements-local.txt"
        ) from e

    return yt_dlp


def _format_for(fmt: str) -> str:
    """Flexible yt-dlp format selector.

    The previous selector was too strict because it required mp4 video
    and m4a audio. Some YouTube videos do not expose that exact combination.
    """
    try:
        height = int(fmt)
    except ValueError:
        height = 720

    return (
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]/best"
    )


def _get_writable_cookiefile() -> Optional[str]:
    """Copy Render's read-only secret cookie file to /tmp.

    Render secret files live in /etc/secrets and are read-only.
    yt-dlp may try to update the cookie jar, so we copy it to /tmp first.
    """
    source_cookiefile = os.getenv("YTDLP_COOKIES_FILE")

    print(f"[download/local] YTDLP_COOKIES_FILE={source_cookiefile}", flush=True)

    if not source_cookiefile:
        print("[download/local] no cookies file configured", flush=True)
        return None

    if not os.path.exists(source_cookiefile):
        raise RuntimeError(
            f"YTDLP_COOKIES_FILE is set, but the file does not exist: {source_cookiefile}"
        )

    size = os.path.getsize(source_cookiefile)
    print(f"[download/local] source cookies size={size} bytes", flush=True)

    with open(source_cookiefile, "r", encoding="utf-8", errors="ignore") as f:
        first_line = f.readline().strip()

    print(f"[download/local] cookies first line={first_line}", flush=True)

    writable_cookiefile = "/tmp/cookies.txt"
    shutil.copyfile(source_cookiefile, writable_cookiefile)
    os.chmod(writable_cookiefile, 0o600)

    print(f"[download/local] using writable cookies file: {writable_cookiefile}", flush=True)

    return writable_cookiefile


def _extract_youtube_video_id(source: str) -> Optional[str]:
    """Best-effort extraction of a YouTube video id from a URL."""
    parsed = urlparse(source)
    host = (parsed.netloc or "").lower()

    if host.startswith("www."):
        host = host[4:]

    if host in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.lstrip("/").split("/", 1)[0]
        return video_id or None

    if "youtube.com" in host:
        if parsed.path.startswith("/watch"):
            qs = parse_qs(parsed.query)
            video_id = qs.get("v", [""])[0]
            return video_id or None

        match = re.search(r"/(?:shorts|embed|live)/([^/?#&]+)", parsed.path)
        if match:
            return match.group(1)

    return None


def _resolve_local_path(source: str) -> Optional[str]:
    """Return a local filesystem path if the input already points at one."""
    parsed = urlparse(source)

    if parsed.scheme == "file":
        raw_path = unquote(parsed.path)

        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            raw_path = f"//{parsed.netloc}{raw_path}"

        candidate = Path(raw_path).expanduser()

        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

        raise RuntimeError(f"Local file URL does not exist: {source}")

    if parsed.scheme in ("http", "https"):
        return None

    candidate = Path(source).expanduser()

    if candidate.exists() and candidate.is_file():
        return str(candidate.resolve())

    if any(sep in source for sep in (os.sep, "/")) or source.startswith("~") or source.startswith("."):
        raise RuntimeError(f"Local file path does not exist: {source}")

    return None


def _existing_download(out_dir: str, video_id: str) -> Optional[str]:
    """Return a cached download path if we already have this YouTube id."""
    for ext in (".mp4", ".mkv", ".webm"):
        candidate = os.path.join(out_dir, f"source_{video_id}{ext}")

        if os.path.exists(candidate):
            return candidate

    return None


def download_youtube_local(
    video_url: str,
    fmt: str = "720",
    out_dir: Optional[str] = None
) -> str:
    """Download a remote URL or return a local file path unchanged."""

    local_path = _resolve_local_path(video_url)

    if local_path:
        print(f"[download/local] using local file: {local_path}", flush=True)
        return local_path

    yt_dlp = _import_ytdlp()

    out_dir = out_dir or LOCAL_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    video_id = _extract_youtube_video_id(video_url)

    if video_id:
        cached = _existing_download(out_dir, video_id)

        if cached:
            print(f"[download/local] reusing cached download: {cached}", flush=True)
            return cached

    print(f"[download/local] {video_url} @ {fmt}p → {out_dir}/", flush=True)

    ydl_opts = {
        "format": _format_for(fmt),
        "outtmpl": os.path.join(out_dir, "source_%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }

    cookies_file = _get_writable_cookiefile()

    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        path = ydl.prepare_filename(info)

        if not os.path.exists(path):
            stem, _ = os.path.splitext(path)

            for ext in (".mp4", ".mkv", ".webm"):
                candidate = stem + ext

                if os.path.exists(candidate):
                    path = candidate
                    break

    print(f"[download/local] ready: {path}", flush=True)

    return path
