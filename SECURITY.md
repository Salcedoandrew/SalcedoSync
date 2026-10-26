# Security Policy

## Supported versions

Only the latest release of this edition is supported with security fixes
(currently `v1.5.1-mod`). Older releases, and the upstream
[shitan198u/immich-go-gui](https://github.com/shitan198u/immich-go-gui)
project, are covered by their own maintainers, not by this edition.

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

Use GitHub's private vulnerability reporting for this repository:
**Security tab → Report a vulnerability**. That opens a private advisory
visible only to the maintainer.

If private reporting is unavailable, open a regular issue with no technical
details and ask the maintainer for a private channel.

Please include, where you can:

- What you found and where (file, feature, or workflow, with steps to reproduce)
- The impact — for example, whether an API key, local file, or server could be exposed
- The version you tested (release tag or commit)

## What happens next

This is a single-maintainer project, so response is best-effort. The
maintainer will confirm the report, work on a fix, and publish it in a
release. Please hold off on public disclosure until a fix is released so
users have a chance to update.

## Please don't

- Test against someone else's Immich server, or probe this project's infrastructure.
- Include a working exploit in a public issue or discussion.
