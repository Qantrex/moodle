"""Shared test case: a fresh script copy + fake Moodle per test, and a token-secrecy check on every run."""
import os
import unittest

from fakemoodle import TOKEN, FakeMoodle, cleanup, load, run


class MoodleCase(unittest.TestCase):
    config = ""
    env = {}

    def setUp(self):
        self.m = load(self.config, **self.env)
        self.addCleanup(cleanup, self.m)
        self.fake = FakeMoodle()

    def run_cli(self, *argv, ok=True):
        code, out, err = run(self.m, self.fake, *argv)
        self.assertNotIn(TOKEN, out + err, "the token leaked into the output")
        if ok:
            self.assertEqual(code, 0, "moodle %s failed:\n%s%s" % (" ".join(argv), out, err))
        return code, out, err

    def path(self, *parts):
        return os.path.join(self.m._tmp, *parts)

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()
