"""Album destination choices, mirroring Immich Upload's dialog and flag mapping.

Immich Upload maps: none -> no album flag; existing/new -> --into-album NAME;
folder -> --folder-as-album FOLDER.
"""

from urllib.parse import urlsplit, urlunsplit

import requests

ALBUM_MODES = {
    "Just upload to Immich (no album)": "none",
    "Add to an existing album": "existing",
    "Create a new album": "new",
    "Make albums from folder names": "folder",
}


def album_flags_state(mode_label: str, existing: str, new: str) -> dict[str, str]:
    """Return the upload-folder tab_state keys the command builder understands."""
    mode = ALBUM_MODES.get(mode_label, "none")
    if mode == "existing":
        return {"folder-album": "NONE", "into-album": existing.strip()}
    if mode == "new":
        return {"folder-album": "NONE", "into-album": new.strip()}
    if mode == "folder":
        return {"folder-album": "FOLDER", "into-album": ""}
    return {"folder-album": "NONE", "into-album": ""}


class AlbumFetchError(Exception):
    """Plain-English reason the album list couldn't be loaded."""


def _https_first(server: str) -> list[str]:
    """Try https before a plain http domain URL (no port, not an IP).

    A domain behind a proxy such as Cloudflare answers http slowly and
    unreliably; https is the fast path. LAN URLs (IP or explicit port) are
    left alone.
    """
    u = urlsplit(server)
    host = u.hostname or ""
    is_ip = host.replace(".", "").isdigit() or ":" in host
    if u.scheme == "http" and u.port is None and not is_ip and host != "localhost":
        return [urlunsplit(u._replace(scheme="https")), server]
    return [server]


def fetch_album_names(server: str, api_key: str, verify_ssl: bool = True) -> list[str]:
    """GET /api/albums and return album names sorted case-insensitively.

    Raises AlbumFetchError with a message meant for the user.
    """
    last = AlbumFetchError("Couldn't reach your Immich server.")
    for base in _https_first(server.rstrip("/")):
        for _attempt in range(2):  # one retry on a timeout
            try:
                r = requests.get(
                    base + "/api/albums",
                    headers={"x-api-key": api_key, "Accept": "application/json"},
                    timeout=(10, 45),
                    verify=verify_ssl,
                )
            except requests.Timeout:
                last = AlbumFetchError(
                    f"Your Immich server ({base}) is taking too long to answer. "
                    "It may be busy or down. Try Refresh in a minute."
                )
                continue
            except requests.RequestException:
                last = AlbumFetchError(
                    f"Couldn't connect to your Immich server ({base}). "
                    "Check the server URL in Configuration and that the server is up."
                )
                break
            if r.status_code in (401, 403):
                raise AlbumFetchError(
                    "Immich rejected the API key. Check it in the Configuration tab."
                )
            if not r.ok:
                raise AlbumFetchError(
                    f"Immich returned an error ({r.status_code}) for the album list."
                )
            names = {a.get("albumName", "") for a in r.json()} - {""}
            return sorted(names, key=str.casefold)
    raise last
