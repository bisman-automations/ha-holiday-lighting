"""What theme music a holiday plays. No Home Assistant imports."""

from __future__ import annotations


def music_request(holiday_name: str, music: str | None) -> tuple[str, str | None]:
    """The Music Assistant media id and type for a holiday's theme music.

    Blank: a playlist found by the holiday's name ("Halloween music").
    A URI ("spotify://playlist/...", "library://playlist/12") or a link
    plays as it is, and Music Assistant works out the type. Anything else is
    a playlist name to search for.
    """
    chosen = (music or "").strip()
    if not chosen:
        return f"{holiday_name.strip()} music", "playlist"
    if "://" in chosen:
        return chosen, None
    return chosen, "playlist"
