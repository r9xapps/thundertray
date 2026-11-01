#!/bin/sh
# Removes ThunderTray for the current user.
set -u

if [ -e /.flatpak-info ]; then
    echo "This shell is inside a Flatpak sandbox. Run this from a terminal app such as Konsole instead." >&2
    exit 1
fi

# Quit restores hidden windows, which must happen while the script is loaded.
gdbus call --session --dest org.thundertray.Tray --object-path /Tray \
    --method org.thundertray.Tray.Quit >/dev/null 2>&1

kwriteconfig6 --file kwinrc --group Plugins --key thundertrayEnabled --delete
gdbus call --session --dest org.kde.KWin --object-path /Scripting \
    --method org.kde.kwin.Scripting.unloadScript thundertray >/dev/null 2>&1
kpackagetool6 --type=KWin/Script --remove thundertray >/dev/null 2>&1
gdbus call --session --dest org.kde.KWin --object-path /KWin \
    --method org.kde.KWin.reconfigure >/dev/null 2>&1

rm -f "$HOME/.local/bin/thundertray" \
    "$HOME/.local/share/applications/thundertray.desktop" \
    "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/thundertray.desktop"
echo "ThunderTray removed."
