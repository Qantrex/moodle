"""Due dates are in Europe/Vienna whatever time zone the machine runs in."""
import os
import time
import unittest
from unittest import mock

from base import MoodleCase
from fakemoodle import NOW, cleanup, load

LATE_EVENING_UTC = 1793835000          # 2026-11-04 23:30 UTC = 2026-11-05 00:30 in Vienna


class MachineInUTC(MoodleCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"TZ": "UTC"})
        patcher.start()
        time.tzset()
        self.addCleanup(time.tzset)
        self.addCleanup(patcher.stop)

    def test_day_and_time_are_vienna(self):
        self.assertEqual(self.m.day(LATE_EVENING_UTC), "2026-11-05")
        self.assertEqual(self.m.when(LATE_EVENING_UTC), "Thu 05.11.2026 00:30")

    def test_summer_time(self):
        self.assertEqual(self.m.when(1782864000), "Wed 01.07.2026 02:00")     # 00:00 UTC, CEST = UTC+2

    def test_list_shows_vienna_time(self):
        _, out, _ = self.run_cli("list")
        line = [x for x in out.splitlines() if "Test Kapitel 3" in x][0]
        self.assertTrue(line.startswith("05.11.2026 00:30"), line)

    def test_note_due_property(self):
        self.run_cli("add", "1004")
        note = self.read("notes", "SEW", "Test Kapitel 3", "Test Kapitel 3.md")
        self.assertIn("due: 2026-11-05", note)
        self.assertIn("type: test", note)
        self.assertIn("updated: 2026-11-04", note)


class Settings(unittest.TestCase):
    def test_pinned_clock(self):
        m = load()
        self.addCleanup(cleanup, m)
        with mock.patch.dict(os.environ, m._env):
            self.assertEqual(m.now_ts(), NOW)

    def test_other_zone(self):
        m = load(MOODLE_TZ="America/New_York")
        self.addCleanup(cleanup, m)
        self.assertEqual(m.day(LATE_EVENING_UTC), "2026-11-04")

    def test_config_zone(self):
        m = load('timezone = "UTC"\n')
        self.addCleanup(cleanup, m)
        self.assertEqual(m.when(LATE_EVENING_UTC), "Wed 04.11.2026 23:30")


if __name__ == "__main__":
    unittest.main()
