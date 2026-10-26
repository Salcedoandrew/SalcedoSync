#!/usr/bin/env python3
"""Render GitHub release notes from CHANGELOG.md.

Usage:
    python scripts/release_notes.py <version> [--changelog PATH] [--output PATH]

The version is the release version without the leading 'v', e.g.
``1.5.2-mod``. The script takes the matching ``## <version>`` section
out of CHANGELOG.md and wraps it in the stable release body (install
steps, Features, Credits) so a tagged release gets its notes
automatically instead of an empty body.

Exits non-zero when CHANGELOG.md has no section for the version, so a
release build fails loudly instead of publishing blank notes.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING_RE = re.compile(r"^##\s+(?P<version>\S+)")
LINK_VERSION_RE = re.compile(r"^\[(?P<version>[^\]]+)\]")


def _heading_version(line: str) -> str | None:
    """Return the version named by a ``## ...`` heading, or None."""
    match = HEADING_RE.match(line)
    if not match:
        return None
    version = match.group("version")
    link = LINK_VERSION_RE.match(version)
    if link:
        version = link.group("version")
    return version.rstrip(")")


def _section(changelog: str, version: str) -> tuple[str, str | None]:
    """Return (body, previous version) for the ``## <version>`` section."""
    lines = changelog.splitlines()
    start = None
    previous = None
    for i, line in enumerate(lines):
        found = _heading_version(line)
        if found is None:
            continue
        if start is None and found == version:
            start = i
            continue
        if start is not None:
            previous = found
            body = "\n".join(lines[start + 1 : i]).strip()
            return body, previous
    if start is None:
        raise ValueError(f"No '## {version}' section in CHANGELOG.md")
    body = "\n".join(lines[start + 1 :]).strip()
    return body, None


def render_release_notes(version: str, changelog: str) -> str:
    """Render the full release body for *version* from the changelog text."""
    body, previous = _section(changelog, version)
    since = f" since {previous}" if previous else ""
    return f"""> **Install (Apple Silicon Macs only)**
> 1. Download **SalcedoSync-{version}-arm64.dmg** below, open it, and drag **SalcedoSync** to **Applications**.
> 2. The app isn't signed by Apple, so macOS blocks the first launch. Right-click the app and choose **Open**, or run:
>    `xattr -dr com.apple.quarantine /Applications/SalcedoSync.app`
> 3. On first launch macOS asks to let SalcedoSync use your saved Immich key in the Keychain. Enter your Mac password and choose **Always Allow**.

## What's new{since}

{body}

## Features

- Upload a folder of photos and videos to your Immich server with [immich-go](https://github.com/simulot/immich-go).
- Choose where they go: just upload, add to an existing album (picked from a searchable list of your albums), create a new album, or make albums from folder names.
- Uploads run inside the app with a progress panel, counts, and a Cancel button. No Terminal window.
- Optional compression that keeps your photo metadata.
- Update check, profiles, and the original app's Archive, Stack and Monitor tools.

## Credits

SalcedoSync is based on [shitan198u/immich-go-gui](https://github.com/shitan198u/immich-go-gui) (MIT License). Full credit for the original app goes to shitan198u.
This edition by Andrew Salcedo.

This edition was written with help from AI coding assistants, and directed and tested by Andrew Salcedo.

**Note:** Apple Silicon (arm64) only.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="release version, e.g. 1.5.2-mod")
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        help="path to CHANGELOG.md (default: CHANGELOG.md)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="where to write the notes ('-' for stdout, default)",
    )
    args = parser.parse_args(argv)

    changelog_path = Path(args.changelog)
    try:
        text = changelog_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {changelog_path}: {exc}", file=sys.stderr)
        return 1
    try:
        notes = render_release_notes(args.version, text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.output == "-":
        print(notes, end="")
    else:
        Path(args.output).write_text(notes, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
