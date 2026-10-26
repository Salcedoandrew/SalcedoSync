<p align="center"><img src="docs/assets/salcedosync.png" alt="SalcedoSync icon" width="128"></p>

# SalcedoSync

### Upload photos to Immich from your Mac — with album choices, built-in compression and in-app progress. 📸

[![GitHub release](https://img.shields.io/github/v/release/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![immich-go](https://img.shields.io/badge/immich--go-0.32.0%20tested-blueviolet.svg)](https://github.com/simulot/immich-go)
[![GitHub stars](https://img.shields.io/github/stars/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/network/members)
[![Last commit](https://img.shields.io/github/last-commit/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/commits/salcedo-mod)
[![GitHub issues](https://img.shields.io/github/issues/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/Salcedoandrew/SalcedoSync)](https://github.com/Salcedoandrew/SalcedoSync/pulls)

[About](#-about) | [Features](#-features) | [Technologies](#-main-technologies) | [Requirements](#-requirements) | [Install](#-install) | [Run from source](#-run-from-source) | [Troubleshooting](#-troubleshooting) | [License](#-license)

## 🎯 About

Tired of uploading photos to Immich from the Terminal? 😩 SalcedoSync puts the whole upload in a friendly Mac app — pick a folder, choose where it goes, and watch the progress live. No Terminal window, no command line. ✨

It drives [immich-go](https://github.com/simulot/immich-go) under the hood, so your photos land in Immich exactly the way immich-go puts them there — with album choices, optional compression and a progress panel built in. 🚀

This edition is by **Andrew Salcedo**. It is based on [shitan198u/immich-go-gui](https://github.com/shitan198u/immich-go-gui), the original Immich-Go GUI by shitan198u. Full credit for the original app, its design and its documentation goes to that project. 🙏

## ✨ Features

- 🖼️ **Album choices inline.** Upload > From Folder asks one question, "Where should these go in Immich?": just upload, add to an existing album, create a new album, or make albums from folder names (the same four choices as Immich Upload).
- 🔍 **Server album dropdown.** Existing albums are loaded from your Immich server, searchable, with a Refresh button.
- ⚡ **No Dry Run button and no confirm dialog.** Run Command starts right away.
- 📊 **Uploads run inside the app.** No Terminal window. A progress panel shows each stage, counts for uploaded, already in Immich, skipped and errors, and a Cancel button that stops immich-go cleanly.
- 🗜️ **Compression tick box, matching Immich Upload.** Optional; JPEG/PNG/WebP/GIF photos are compressed with caesiumclt at quality 80 into a temp copy, keeping EXIF/GPS and file dates. Originals are never changed and the temp copy is deleted afterwards.
- 🌐 **Album list loads over https first** for plain http domain addresses (fast behind proxies such as Cloudflare), with plain-English errors.
- 🔒 **Security and reliability fixes from a code audit:**
  1. The API key is never forwarded when a server redirects.
  2. No fallback to unencrypted http after an https/TLS failure.
  3. Connection tests and the pre-run server check run in the background, so the window never freezes.
  4. A bare web address such as `photos.example.com` means https (local names and IP addresses still use http).
  5. Bad numbers in settings or advanced options show a clear error or fall back to the default instead of crashing a run.
  6. Profile names from `profiles.toml` are validated before being used as folder paths.

See [CHANGELOG.md](CHANGELOG.md) for details.

## 🎬 See it in action

![Demo of the original Immich-Go GUI this edition is based on](docs/assets/immich-demo.gif)

The upload flow is the same as the original app, plus the album choices above.

## 🚀 Main Technologies

<img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" alt="Python logo" width="48" height="48"> <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/qt/qt-original.svg" alt="Qt logo" width="48" height="48">

**See more**

- [Python 3.13](https://www.python.org/) — the app is written in Python.
- [PySide6 / Qt](https://www.qt.io/) — the desktop UI.
- [Nuitka](https://nuitka.net/) — compiles the app into the standalone Mac binary.
- [immich-go](https://github.com/simulot/immich-go) — the uploader that talks to your Immich server.
- [caesiumclt](https://github.com/Lymphatus/caesium-clt) — the compression tool behind the tick box.
- [uv](https://docs.astral.sh/uv/) — dependency and virtual-environment management.

## ✅ Requirements

Before starting 🏁, make sure you have:

- 🍎 **A Mac with Apple silicon** (arm64) — the DMG is Apple silicon only.
- 🖼️ **An Immich server** and an **API key** for it (create one in Immich under Account Settings → API Keys).
- 🐍 **Python 3.13 and [uv](https://docs.astral.sh/uv/)** — only if you run from source instead of the DMG.

## 📦 Install

1. Download the DMG from [Releases](https://github.com/Salcedoandrew/SalcedoSync/releases/latest).
2. Open it and drag the app to **Applications**.
3. The app is not signed by Apple, so macOS blocks the first launch. Either right-click the app and choose **Open**, or run:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/SalcedoSync.app"
   ```

## 🏁 Run from source

```
# Clone this project
$ git clone https://github.com/Salcedoandrew/SalcedoSync.git

# Access
$ cd SalcedoSync

# Install dependencies
$ uv sync --dev

# Run the app
$ uv run python app.py
```

## 🎮 Scripts

- `uv run pytest` — runs the test suite (core coverage must stay at 75% or above).
- `uv run python app.py --self-test` — runs the packaged self-test entrypoint.
- `uv run ty check core/` — type-checks the core package.
- `uv run python scripts/sync_version.py --check` — checks the version is synced across code, docs and packaging.
- `uv run python scripts/sync_test_count.py --check` — checks the documented test count matches pytest.

## 🐛 Troubleshooting

**macOS asks for your password when the app reads the saved API key.** 🔑 The key lives in macOS Keychain, and macOS asks you to authorize each app that reads it. Click **Always Allow** on the prompt. If it keeps asking, open Keychain Access, find `immich-go-gui`, Get Info → Access Control → **Allow all applications to access this item**. Or, in the app, switch Secret Storage on the Config tab from OS Keyring to Local secrets file — the key is then stored in `secrets.toml` instead of Keychain.

**"Couldn't load your albums."** 🌐 The app could not reach your Immich server, or the server was too slow to answer. Check the server URL in Configuration, make sure the server is up, and try **Refresh**. A 401/403 means Immich rejected the API key — check it on the Config tab.

Full troubleshooting and FAQ: [shitan198u.github.io/immich-go-gui](https://shitan198u.github.io/immich-go-gui/) (user guide → Troubleshooting / FAQ).

## 📚 Documentation

The original project's documentation still applies to everything outside the changes above: [shitan198u.github.io/immich-go-gui](https://shitan198u.github.io/immich-go-gui/).

## 🤖 How this was made

This edition was written with help from AI coding assistants, and directed and tested by Andrew Salcedo.

## 💛 Support the original author

If Immich-Go GUI saves you time, consider supporting shitan198u: [GitHub Sponsors](https://github.com/sponsors/shitan198u) · [Buy Me a Coffee](https://www.buymeacoffee.com/shivashitan)

## 📝 License

This project is licensed under the [MIT License](LICENSE.txt), as in the original project.

Made with ❤️ by [Andrew Salcedo](https://github.com/Salcedoandrew)

[Back to top](#salcedosync)
