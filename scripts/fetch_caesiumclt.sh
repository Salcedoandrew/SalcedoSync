#!/usr/bin/env bash
# Fetch caesiumclt (libcaesium CLI) for bundling into the macOS app.
# Same pinned version + checksums as Immich Upload's build.sh.
set -euo pipefail
CV=v1.5.0
CC_arm64=9fc192ee1f7190d238ff8bf684ce502ceb652040544ee4a1b4bd10a6bf1b783e
CC_x86_64=a9e6dab8de3b3b024dd6bbf26fd99047355dad9235984faf8fa707b636b7e117
a="$(uname -m)"; ca=$a; [ "$a" = arm64 ] && ca=aarch64
eval sum=\$CC_$a
out="${1:-build/caesiumclt}"; mkdir -p "$(dirname "$out")"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
curl -sfL -o "$T/cc.tgz" "https://github.com/Lymphatus/caesium-clt/releases/download/$CV/caesiumclt-$CV-$ca-apple-darwin.tar.gz"
got=$(shasum -a 256 "$T/cc.tgz" | cut -d' ' -f1)
[ "$got" = "$sum" ] || { echo "Checksum mismatch ($got)"; exit 1; }
tar xzf "$T/cc.tgz" -C "$T" --strip-components 1 "caesiumclt-$CV-$ca-apple-darwin/caesiumclt"
install -m 755 "$T/caesiumclt" "$out"
echo "caesiumclt $CV ($a) -> $out"
