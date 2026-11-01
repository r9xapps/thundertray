#!/bin/sh
# Installs ThunderTray for the current user. Re-run it to upgrade.
#
# Works from a checkout, or on its own:
#   curl -fsSL https://raw.githubusercontent.com/r9xapps/thundertray/main/install.sh | sh
#
# Everything is inside main so that a truncated download runs nothing.
set -eu

TARBALL=https://github.com/r9xapps/thundertray/archive/refs/heads/main.tar.gz

kwin() {
    gdbus call --session --dest org.kde.KWin "$@" >/dev/null 2>&1
}

# Runs the installer from a downloaded copy, when there is no checkout to use.
install_from_download() {
    command -v curl >/dev/null || { echo "Missing required tool: curl" >&2; exit 1; }
    command -v tar >/dev/null || { echo "Missing required tool: tar" >&2; exit 1; }
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    echo "Downloading ThunderTray..."
    curl -fsSL "$TARBALL" | tar -xz -C "$tmp" --strip-components=1
    # stdin is this script when run through a pipe, so keep it from later commands.
    sh "$tmp/install.sh" </dev/null
}

install_python_deps() {
    if python3 -c 'import PyQt6.QtWidgets, PyQt6.QtDBus' 2>/dev/null; then
        return
    fi
    if ! command -v dnf >/dev/null; then
        echo "PyQt6 is missing. Install it with your package manager, then run this again." >&2
        exit 1
    fi
    echo "Installing python3-pyqt6 (needs sudo)..."
    sudo dnf install -y python3-pyqt6
}

# Checks the links ThunderTray depends on, which only work on a live session.
check() {
    label=$1
    shift
    if "$@" >/dev/null 2>&1; then
        echo "ok:   $label"
    else
        echo "FAIL: $label"
        status=1
    fi
}

script_loaded() {
    gdbus call --session --dest org.kde.KWin --object-path /Scripting \
        --method org.kde.kwin.Scripting.isScriptLoaded thundertray | grep -q true
}

shortcuts_registered() {
    gdbus call --session --dest org.kde.kglobalaccel --object-path /component/kwin \
        --method org.kde.kglobalaccel.Component.shortcutNames default | grep -q "ThunderTray Toggle"
}

tray_running() {
    gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.GetNameOwner org.thundertray.Tray
}

main() {
    if [ -e /.flatpak-info ]; then
        echo "This shell is inside a Flatpak sandbox (an editor's terminal, for example)." >&2
        echo "Run this from a terminal app such as Konsole instead." >&2
        exit 1
    fi

    src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    if [ ! -f "$src/kwin-script/metadata.json" ]; then
        install_from_download
        return
    fi

    bin="$HOME/.local/bin/thundertray"
    apps="$HOME/.local/share/applications"
    autostart="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

    for tool in kpackagetool6 kwriteconfig6 gdbus python3; do
        command -v "$tool" >/dev/null || {
            echo "Missing required tool: $tool (ThunderTray needs KDE Plasma 6)" >&2
            exit 1
        }
    done

    install_python_deps

    # Stop any running copy. This also brings back windows it has hidden.
    gdbus call --session --dest org.thundertray.Tray --object-path /Tray \
        --method org.thundertray.Tray.Quit >/dev/null 2>&1 || true

    kwin --object-path /Scripting --method org.kde.kwin.Scripting.unloadScript thundertray || true
    kpackagetool6 --type=KWin/Script --upgrade "$src/kwin-script" >/dev/null 2>&1 ||
        kpackagetool6 --type=KWin/Script --install "$src/kwin-script" >/dev/null
    kwriteconfig6 --file kwinrc --group Plugins --key thundertrayEnabled true
    kwin --object-path /KWin --method org.kde.KWin.reconfigure || true

    mkdir -p "$(dirname "$bin")" "$apps" "$autostart"
    install -m 755 "$src/thundertray.py" "$bin"
    cat > "$apps/thundertray.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ThunderTray
Comment=Minimize Thunderbird to the system tray
Exec=$bin
Icon=thunderbird
Categories=Network;Email;
EOF
    cp "$apps/thundertray.desktop" "$autostart/thundertray.desktop"

    nohup "$bin" >/dev/null 2>&1 &
    sleep 2

    status=0
    check "KWin script loaded" script_loaded
    check "KWin shortcuts registered" shortcuts_registered
    check "tray icon running" tray_running
    echo "mail: $("$bin" --unread 2>&1 | tail -n 1)"

    if [ "$status" -ne 0 ]; then
        echo "Install finished with problems. Log out and back in, then run this again." >&2
        exit 1
    fi
    echo "Done. Minimize Thunderbird and it moves to the tray."
}

main
