"""Album destination choices, mirroring Immich Upload's dialog and flag mapping.

Immich Upload maps: none -> no album flag; existing/new -> --into-album NAME;
folder -> --folder-as-album FOLDER.
"""

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


def fetch_album_names(
    server: str, api_key: str, verify_ssl: bool = True, timeout: float = 15
) -> list[str]:
    """GET /api/albums and return album names sorted case-insensitively."""
    r = requests.get(
        server.rstrip("/") + "/api/albums",
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=timeout,
        verify=verify_ssl,
    )
    r.raise_for_status()
    names = {a.get("albumName", "") for a in r.json()} - {""}
    return sorted(names, key=str.casefold)
