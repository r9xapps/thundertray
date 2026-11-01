# ThunderTray

Minimize Thunderbird to the system tray on KDE Plasma 6, including on Wayland.

Thunderbird has no minimize-to-tray on Linux, and tools like Birdtray can't hide its window on native Wayland. ThunderTray does the hiding with a small KWin script, because the compositor can, and adds a tray icon that matches your Plasma theme.

## Install

Run this in a terminal such as Konsole:

```sh
curl -fsSL https://raw.githubusercontent.com/r9xapps/thundertray/main/install.sh | sh
```

Or, if you'd rather read the code first:

```sh
git clone https://github.com/r9xapps/thundertray.git
cd thundertray
./install.sh
```

The icon starts right away and at every login. Run the same command again to update.

### Requirements

- KDE Plasma 6
- Thunderbird, installed as a system package or from Flatpak
- Python 3 and PyQt6

On Fedora, the installer offers to install PyQt6 for you with `sudo dnf install python3-pyqt6`. On other distributions, install PyQt6 with your package manager first. ThunderTray has been used on Fedora 44 only.

## Usage

Minimize Thunderbird and it leaves the taskbar and Alt-Tab.

**Left-click the icon** to:

- bring Thunderbird back if it's hidden
- hide it if it's focused
- bring it to the front if it's behind other windows
- start it if it isn't running

**Right-click the icon** for Show/Hide, Quit Thunderbird and Exit ThunderTray.

**Unread mail** adds a small star to the envelope, and hovering shows the count.

**For a keyboard shortcut**, go to System Settings > Keyboard > Shortcuts, then under KWin find "ThunderTray: Show or hide Thunderbird".

## Limitations

- **The X button still quits Thunderbird.** KWin can't intercept it. The icon stays and a click restarts Thunderbird, but you won't get new mail alerts while it's closed. The [Minimize on Close](https://addons.thunderbird.net/thunderbird/addon/minimize-on-close/) add-on can make X minimize instead, if it supports your Thunderbird version.
- **The unread count can lag by about a minute.** It comes from `folderCache.json` in your profile, which Thunderbird only saves about a minute after a change.
- **Only inboxes are counted.** Mail that filters move to other folders isn't included, and neither is Junk.
- **Thunderbird doesn't start at login.** Only the icon does.
- **If the tray app crashes,** windows already hidden stay hidden until you reopen ThunderTray from the app menu and click the icon. While it isn't running, minimizing works as normal.

## Uninstall

```sh
curl -fsSL https://raw.githubusercontent.com/r9xapps/thundertray/main/uninstall.sh | sh
```

This also brings back any hidden windows.

## How it works

- `kwin-script/` runs inside KWin. It takes minimized Thunderbird windows off the taskbar and switcher, and registers shortcuts for showing and hiding them.
- `thundertray.py` is the tray icon. It triggers those shortcuts over D-Bus, and the script reports window state back the same way.

The script only hides a window while the tray app is running, so a window can't get stranded with no way back.

Run the tests with:

```sh
node tests/test_kwin_script.js
python3 tests/test_unread.py
```

## License

[MIT](LICENSE)
