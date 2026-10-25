# SalcedoSync

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![immich-go](https://img.shields.io/badge/immich--go-0.32.0%20tested-blueviolet.svg)](https://github.com/simulot/immich-go)

A macOS app that uploads photos to your [Immich](https://immich.app/) server, with
album choices, optional built-in compression and in-app progress. It drives
[immich-go](https://github.com/simulot/immich-go) under the hood.

This edition is by Andrew Salcedo. It is based on
[shitan198u/immich-go-gui](https://github.com/shitan198u/immich-go-gui), the
original Immich-Go GUI by shitan198u. Full credit for the original app, its
design and its documentation goes to that project.

## What's different in this edition

- **Album choices inline.** Upload > From Folder asks one question, "Where should
  these go in Immich?": just upload, add to an existing album, create a new
  album, or make albums from folder names (the same four choices as Immich Upload).
- **Server album dropdown.** Existing albums are loaded from your Immich server,
  searchable, with a Refresh button.
- **No Dry Run button and no confirm dialog.** Run Command starts right away.
- **Uploads run inside the app.** No Terminal window. A progress panel shows
  each stage, counts for uploaded, already in Immich, skipped and errors, and a
  Cancel button that stops immich-go cleanly.
- **Compression tick box, matching Immich Upload.** Optional; JPEG/PNG/WebP/GIF
  photos are compressed with caesiumclt at quality 80 into a temp copy, keeping
  EXIF/GPS and file dates. Originals are never changed and the temp copy is
  deleted afterwards.
- **Album list loads over https first** for plain http domain addresses (fast
  behind proxies such as Cloudflare), with plain-English errors.
- **Security and reliability fixes from a code audit:**
  1. The API key is never forwarded when a server redirects.
  2. No fallback to unencrypted http after an https/TLS failure.
  3. Connection tests and the pre-run server check run in the background, so
     the window never freezes.
  4. A bare web address such as `photos.example.com` means https (local names
     and IP addresses still use http).
  5. Bad numbers in settings or advanced options show a clear error or fall
     back to the default instead of crashing a run.
  6. Profile names from `profiles.toml` are validated before being used as
     folder paths.

See [CHANGELOG.md](CHANGELOG.md) for details.

## Install (macOS, Apple silicon)

1. Download the DMG from
   [Releases](https://github.com/Salcedoandrew/SalcedoSync/releases/latest).
2. Open it and drag the app to **Applications**.
3. The app is not signed by Apple, so macOS blocks the first launch. Either
   right-click the app and choose **Open**, or run:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/SalcedoSync.app"
   ```

## Run from source

```bash
git clone https://github.com/Salcedoandrew/SalcedoSync.git
cd SalcedoSync
uv sync --dev
uv run python app.py
uv run pytest
```

## Documentation

The original project's documentation still applies to everything outside the
changes above: [shitan198u.github.io/immich-go-gui](https://shitan198u.github.io/immich-go-gui/).

## How this was made

This edition was written with help from AI coding assistants, and directed and
tested by Andrew Salcedo.

## Support the original author

If Immich-Go GUI saves you time, consider supporting shitan198u:
[GitHub Sponsors](https://github.com/sponsors/shitan198u) ·
[Buy Me a Coffee](https://www.buymeacoffee.com/shivashitan)

## License

[MIT License](LICENSE.txt), as in the original project.
