#!/usr/bin/env python3
"""Tray icon for Thunderbird on KDE Plasma (Wayland).

Wayland does not let an ordinary app hide another app's window, so the window
handling lives in the "thundertray" KWin script. This program is the icon: it
triggers the script's shortcuts, and the script reports back with SetState.

Thunderbird has no API for the unread count, so it comes from folderCache.json
in the profile. Thunderbird saves that file about a minute after a change.
"""

import glob
import json
import os
import shutil
import subprocess
import sys

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBus, QDBusConnection, QDBusMessage
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

SERVICE = "org.thundertray.Tray"
PATH = "/Tray"
FLATPAK_ID = "org.mozilla.Thunderbird"
PROFILE_ROOTS = (
    "~/.thunderbird",
    "~/.config/thunderbird",
    f"~/.var/app/{FLATPAK_ID}/.thunderbird",
    f"~/.var/app/{FLATPAK_ID}/config/thunderbird",
)
UNREAD_POLL_MS = 5000
# From Thunderbird's nsMsgFolderFlags.idl.
FOLDER_FLAG_INBOX = 0x1000
FOLDER_FLAG_VIRTUAL = 0x20


def find_folder_cache():
    """Returns the most recently saved folderCache.json, which is the profile in use."""
    paths = []
    for root in PROFILE_ROOTS:
        paths += glob.glob(os.path.join(glob.escape(os.path.expanduser(root)), "*", "folderCache.json"))
    return max(paths, key=os.path.getmtime, default=None)


def count_unread(path):
    """Sums unread mail across real inboxes. Unified Folders are virtual, and skipped to avoid double counting."""
    with open(path, encoding="utf-8") as f:
        folders = json.load(f)
    total = 0
    for folder in folders.values():
        flags = folder.get("flags", 0)
        if flags & FOLDER_FLAG_INBOX and not flags & FOLDER_FLAG_VIRTUAL:
            # The stored count is -1 until known, and pending can be negative.
            total += max(0, folder.get("totalUnreadMsgs", 0)) + folder.get("pendingUnreadMsgs", 0)
    return max(0, total)


def thunderbird_command():
    if shutil.which("thunderbird"):
        return ["thunderbird"]
    if shutil.which("flatpak"):
        installed = subprocess.run(["flatpak", "info", FLATPAK_ID], capture_output=True)
        if installed.returncode == 0:
            return ["flatpak", "run", FLATPAK_ID]
    return None


def invoke_shortcut(name):
    """Runs a shortcut registered by the KWin script. Returns False on failure."""
    message = QDBusMessage.createMethodCall(
        "org.kde.kglobalaccel", "/component/kwin", "org.kde.kglobalaccel.Component", "invokeShortcut"
    )
    message.setArguments([name])
    reply = QDBusConnection.sessionBus().call(message, QDBus.CallMode.Block, 2000)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        print(f"thundertray: cannot reach the KWin script: {reply.errorMessage()}", file=sys.stderr)
        return False
    return True


@pyqtClassInfo("D-Bus Interface", SERVICE)
class Tray(QObject):
    def __init__(self):
        super().__init__()
        self.windows = 0
        self.hidden = 0
        self.unread = 0
        self.cache_stamp = None

        self.menu = QMenu()
        self.toggle_action = self.menu.addAction("Open Thunderbird", self.toggle)
        self.quit_action = self.menu.addAction("Quit Thunderbird", lambda: invoke_shortcut("ThunderTray Quit"))
        self.menu.addSeparator()
        self.menu.addAction("Exit ThunderTray", self.Quit)

        self.icon = QSystemTrayIcon()
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.on_activated)
        self.check_unread()
        self.update_ui()
        self.icon.show()

        self.unread_timer = QTimer(self)
        self.unread_timer.timeout.connect(self.check_unread)
        self.unread_timer.start(UNREAD_POLL_MS)

    @staticmethod
    def find_icon(has_unread):
        # Status icons, so they are monochrome and follow the panel's colors like
        # the rest of the tray. Breeze's "unread" is a plain closed envelope, and
        # "unread-new" adds a star to it.
        names = ("mail-unread-new", "mail-mark-unread-new") if has_unread else ("mail-unread", "mail-message")
        for name in names:
            if QIcon.hasThemeIcon(name):
                return QIcon.fromTheme(name)
        return QIcon.fromTheme("mail-client")

    def check_unread(self):
        path = find_folder_cache()
        try:
            stamp = (path, os.path.getmtime(path)) if path else None
            if stamp == self.cache_stamp:
                return
            unread = count_unread(path) if path else 0
        except (OSError, ValueError, AttributeError, TypeError) as error:
            # Keep the last count, and retry at the next poll.
            print(f"thundertray: cannot read {path}: {error}", file=sys.stderr)
            return
        self.cache_stamp = stamp
        if unread != self.unread:
            self.unread = unread
            self.update_ui()

    def update_ui(self):
        running = self.windows > 0
        if not running:
            tooltip, action = "Thunderbird is not running", "Open Thunderbird"
        elif self.hidden == self.windows:
            tooltip, action = "Thunderbird is in the tray", "Show Thunderbird"
        else:
            tooltip, action = "Thunderbird is open", "Hide Thunderbird"
        # With Thunderbird closed, the saved count may be out of date.
        has_unread = running and self.unread > 0
        if has_unread:
            tooltip += f"\n{self.unread} unread"
        self.icon.setIcon(self.find_icon(has_unread))
        self.icon.setToolTip(tooltip)
        self.toggle_action.setText(action)
        self.quit_action.setEnabled(running)

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle()

    def toggle(self):
        if self.windows > 0:
            invoke_shortcut("ThunderTray Toggle")
            return
        command = thunderbird_command()
        if command is None:
            self.icon.showMessage("ThunderTray", "Could not find Thunderbird to start it.")
            return
        QProcess.startDetached(command[0], command[1:])

    @pyqtSlot(str)
    def SetState(self, state):
        """Called by the KWin script with "<window count> <hidden count>"."""
        self.windows, self.hidden = (int(n) for n in state.split())
        self.update_ui()

    @pyqtSlot()
    def Quit(self):
        # With the icon gone there is no way back to a hidden window.
        invoke_shortcut("ThunderTray Show")
        QTimer.singleShot(0, QApplication.quit)


def print_unread():
    path = find_folder_cache()
    if path is None:
        print("no folderCache.json found yet (Thunderbird writes it after first use)")
    else:
        print(f"{count_unread(path)} unread, from {path}")


def main():
    if "--unread" in sys.argv:
        print_unread()
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("ThunderTray")
    app.setDesktopFileName("thundertray")
    app.setQuitOnLastWindowClosed(False)

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        sys.exit("thundertray: no D-Bus session bus")
    if not bus.registerService(SERVICE):
        print("thundertray: already running", file=sys.stderr)
        return 0

    tray = Tray()
    bus.registerObject(PATH, tray, QDBusConnection.RegisterOption.ExportAllSlots)
    invoke_shortcut("ThunderTray Sync")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
