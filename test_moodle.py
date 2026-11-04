"""Where moodle's personal settings come from. Run: python3 -m unittest"""
import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))


def load(config="", **env):
    """A fresh copy of the moodle script with this config file and environment."""
    d = tempfile.mkdtemp()
    if config:
        with open(os.path.join(d, "config.toml"), "w") as f:
            f.write(config)
    clean = {k: v for k, v in os.environ.items() if not k.startswith("MOODLE_")}
    with mock.patch.dict(os.environ, dict(clean, MOODLE_CONFIG=d, **env), clear=True):
        loader = importlib.machinery.SourceFileLoader("moodle_cli", os.path.join(HERE, "moodle"))
        spec = importlib.util.spec_from_loader("moodle_cli", loader)
        m = importlib.util.module_from_spec(spec)
        loader.exec_module(m)
    return m


class Settings(unittest.TestCase):
    def test_no_config_uses_generic_folders(self):
        m = load()
        self.assertEqual(m.NOTES, os.path.expanduser("~/.local/share/moodle/notes"))
        self.assertEqual(m.FILES, os.path.expanduser("~/.local/share/moodle/files"))

    def test_config_sets_folders(self):
        m = load('notes = "~/a"\nfiles = "/b"\n')
        self.assertEqual((m.NOTES, m.FILES), (os.path.expanduser("~/a"), "/b"))

    def test_environment_beats_config(self):
        self.assertEqual(load('notes = "/a"\n', MOODLE_NOTES="/env").NOTES, "/env")

    def test_broken_config_stops_with_a_message(self):
        with self.assertRaises(SystemExit) as e:
            load("notes = \n")
        self.assertIn("config.toml", str(e.exception))


if __name__ == "__main__":
    unittest.main()
