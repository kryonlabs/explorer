#!/bin/sh
# Package the native build without installing it on the build machine.
set -eu
umask 022
cd "$(dirname "$0")/.."
program=$PWD/build/explorer-desktop
version=${1:-$(cat VERSION)}
dpkg --validate-version "$version"
if [ "$(dpkg --print-architecture)" != amd64 ]; then
    printf '%s\n' 'Explorer: this package target requires an amd64 build host.' >&2
    exit 1
fi
work=$(mktemp -d "$PWD/build/explorer-deb.XXXXXXXX")
trap 'rm -r -- "$work"' EXIT
package=$work/debian/explorer
share=$package/usr/share
lib=$package/usr/lib/kryon/explorer
mkdir -p "$package/DEBIAN" "$package/usr/bin" "$share/applications" "$share/kryon/explorer"
install -m 755 "$program" "$package/usr/bin/explorer"
cp -R "$program.assets" "$share/kryon/explorer/assets"
chmod -R a+rX "$share/kryon/explorer/assets"
install -m 644 "$program.title" "$share/kryon/explorer/app.title"
cat > "$share/applications/explorer.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Explorer
Comment=Ziran file manager
Exec=/usr/bin/explorer
Icon=system-file-manager
Terminal=false
Categories=Utility;FileManager;Core;
DESKTOP
cat > "$work/debian/control" <<'CONTROL'
Source: explorer
Section: utils
Priority: optional
Maintainer: Kryon Labs <waozi@proton.me>

Package: explorer
Architecture: amd64
Description: Explorer file manager
CONTROL
elf=$package/usr/bin/explorer
set -- -e"$elf"
if readelf -d "$program" | grep -q 'Shared library: \[libkryonavif.so\]'; then
    codec=$(env -u LD_LIBRARY_PATH ldd "$program" | awk '$1 == "libkryonavif.so" && $2 == "=>" { print $3 }')
    test -f "$codec"
    mkdir -p "$lib" "$share/doc/explorer"
    install -m 644 "$codec" "$lib/"
    avif=$(scripts/ziran.sh pkg path libavif --offline --locked)
    aom=$(scripts/ziran.sh pkg path libaom --offline --locked)
    dav1d=$(scripts/ziran.sh pkg path dav1d --offline --locked)
    install -m 644 "$avif/LICENSE" "$share/doc/explorer/libavif-LICENSE"
    install -m 644 "$aom/LICENSE" "$share/doc/explorer/libaom-LICENSE"
    install -m 644 "$aom/PATENTS" "$share/doc/explorer/libaom-PATENTS"
    install -m 644 "$dav1d/COPYING" "$share/doc/explorer/dav1d-COPYING"
    old_rpath=$(readelf -d "$elf" | sed -n '/(RUNPATH)\|(RPATH)/s/.*\[\(.*\)\].*/\1/p')
    cat > "$work/relocate.cmake" <<'CMAKE'
file(RPATH_CHANGE FILE "${PROGRAM}" OLD_RPATH "${OLD_RPATH}" NEW_RPATH "$ORIGIN/../lib/kryon/explorer")
CMAKE
    cmake -DPROGRAM="$elf" -DOLD_RPATH="$old_rpath" -P "$work/relocate.cmake"
    set -- "$@" --ignore-missing-info -l"$lib" -e"$lib/libkryonavif.so"
fi
depends=$(cd "$work" && dpkg-shlibdeps -O -xexplorer "$@")
case "$depends" in
    shlibs:Depends=*) depends=${depends#shlibs:Depends=} ;;
    *) printf '%s\n' 'Explorer: could not determine package dependencies.' >&2; exit 1 ;;
esac
cat > "$package/DEBIAN/control" <<EOF
Package: explorer
Version: $version
Architecture: amd64
Section: utils
Priority: optional
Maintainer: Kryon Labs <waozi@proton.me>
Depends: $depends
Description: Explorer file manager
 Browse and manage files with a Kryon desktop interface.
EOF
output=$PWD/build/explorer-linux-amd64.deb
dpkg-deb --root-owner-group -Zxz --build "$package" "$work/explorer.deb"
mv -f "$work/explorer.deb" "$output"
printf '%s\n' "$output"
