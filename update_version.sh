#!/bin/sh
set -eu
cd "$(dirname "$0")"
version=$(sed -n 's/^## \[\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\)\] - [0-9-]*$/\1/p' CHANGELOG.md | head -n 1)
if [ -z "$version" ]; then
    printf '%s\n' 'Explorer: add a dated numeric release to CHANGELOG.md first.' >&2
    exit 1
fi
printf '%s\n' "$version" > VERSION
