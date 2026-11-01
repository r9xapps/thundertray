"""Tests the unread count. Usage: python3 tests/test_unread.py (needs PyQt6)."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import thundertray

INBOX = thundertray.FOLDER_FLAG_INBOX
VIRTUAL = thundertray.FOLDER_FLAG_VIRTUAL


class CountUnread(unittest.TestCase):
    def count(self, folders):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory, "folderCache.json")
            path.write_text(json.dumps(folders))
            return thundertray.count_unread(path)

    def test_sums_inboxes_only(self):
        self.assertEqual(self.count({
            "/a/INBOX.msf": {"flags": INBOX | 0x4, "totalUnreadMsgs": 3},
            "/b/INBOX.msf": {"flags": INBOX | 0x4, "totalUnreadMsgs": 2},
            "/a/Archive.msf": {"flags": 0x4, "totalUnreadMsgs": 50},
            "/a/Junk.msf": {"flags": 0x40000000, "totalUnreadMsgs": 50},
        }), 5)

    def test_unified_inbox_is_not_double_counted(self):
        self.assertEqual(self.count({
            "/a/INBOX.msf": {"flags": INBOX, "totalUnreadMsgs": 3},
            "/smart/Inbox.msf": {"flags": INBOX | VIRTUAL, "totalUnreadMsgs": 3},
        }), 3)

    def test_includes_pending_messages(self):
        self.assertEqual(self.count({"/a": {"flags": INBOX, "totalUnreadMsgs": 3, "pendingUnreadMsgs": 2}}), 5)
        self.assertEqual(self.count({"/a": {"flags": INBOX, "totalUnreadMsgs": 3, "pendingUnreadMsgs": -1}}), 2)

    def test_unknown_or_missing_counts_are_zero(self):
        self.assertEqual(self.count({"/a": {"flags": INBOX, "totalUnreadMsgs": -1}}), 0)
        self.assertEqual(self.count({"/a": {"flags": INBOX}}), 0)
        self.assertEqual(self.count({"/a": {"flags": INBOX, "totalUnreadMsgs": 0, "pendingUnreadMsgs": -4}}), 0)
        self.assertEqual(self.count({"/server": {"totalMsgs": 1}}), 0)
        self.assertEqual(self.count({}), 0)


class FindFolderCache(unittest.TestCase):
    def test_picks_most_recently_saved_profile_across_roots(self):
        with tempfile.TemporaryDirectory() as home:
            old = pathlib.Path(home, ".thunderbird/old.default/folderCache.json")
            new = pathlib.Path(home, f".var/app/{thundertray.FLATPAK_ID}/.thunderbird/new.default/folderCache.json")
            for path, stamp in ((old, 1000), (new, 2000)):
                path.parent.mkdir(parents=True)
                path.write_text("{}")
                os.utime(path, (stamp, stamp))
            with mock.patch.dict(os.environ, {"HOME": home}):
                self.assertEqual(thundertray.find_folder_cache(), str(new))

    def test_returns_none_without_a_profile(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home}):
            self.assertIsNone(thundertray.find_folder_cache())


if __name__ == "__main__":
    unittest.main()
