"""Where moodle's personal settings come from."""
import os
import unittest

from fakemoodle import cleanup, load


class Settings(unittest.TestCase):
    def load(self, config="", **env):
        m = load(config, **env)
        self.addCleanup(cleanup, m)
        return m

    def test_no_config_uses_generic_folders(self):
        m = self.load(MOODLE_NOTES=None, MOODLE_FILES=None)
        self.assertEqual(m.NOTES, os.path.expanduser("~/.local/share/moodle/notes"))
        self.assertEqual(m.FILES, os.path.expanduser("~/.local/share/moodle/files"))

    def test_config_sets_folders(self):
        m = self.load('notes = "~/a"\nfiles = "/b"\n', MOODLE_NOTES=None, MOODLE_FILES=None)
        self.assertEqual((m.NOTES, m.FILES), (os.path.expanduser("~/a"), "/b"))

    def test_environment_beats_config(self):
        self.assertEqual(self.load('notes = "/a"\n', MOODLE_NOTES="/env").NOTES, "/env")

    def test_broken_config_stops_with_a_message(self):
        with self.assertRaises(SystemExit) as e:
            load("notes = \n")
        self.assertIn("config.toml", str(e.exception))


if __name__ == "__main__":
    unittest.main()
