"""Note writing: atomic, keeps file modes, leaves non-UTF-8 files alone; front-matter helpers."""
import os
import unittest
from unittest import mock

from base import MoodleCase

NOTE = ("notes", "SEW", "Aufgabe 1 - REST API", "Aufgabe 1 - REST API.md")


class Writing(MoodleCase):
    def test_failed_write_keeps_the_old_note(self):
        self.run_cli("add", "1001")
        before = self.read(*NOTE)
        self.fake.assigns[11][0]["duedate"] += 86400
        with mock.patch.object(self.m.os, "replace", side_effect=OSError("disk full")):
            code, _, err = self.run_cli("sync", ok=False)
        self.assertEqual(code, 1)
        self.assertEqual(self.read(*NOTE), before)
        self.assertEqual(sorted(os.listdir(self.path(*NOTE[:-1]))), ["Aufgabe 1 - REST API.md", "TASK.md"])

    def test_mode_is_kept(self):
        self.run_cli("add", "1001")
        os.chmod(self.path(*NOTE), 0o640)
        self.fake.assigns[11][0]["duedate"] += 86400
        self.run_cli("sync")
        self.assertEqual(os.stat(self.path(*NOTE)).st_mode & 0o777, 0o640)

    def test_non_utf8_note_is_left_alone(self):
        os.makedirs(self.path("notes", "SEW"))
        with open(self.path("notes", "SEW", "REST API.md"), "wb") as f:
            f.write(b"---\ntype: assignment\nmoodle: 1001\n---\n\xff\xfe broken\n")
        _, out, err = self.run_cli("sync")
        self.assertIn("not UTF-8", err)
        with open(self.path("notes", "SEW", "REST API.md"), "rb") as f:
            self.assertIn(b"\xff\xfe broken", f.read())

    def test_crlf_text_is_kept(self):
        self.run_cli("add", "1001")
        with open(self.path(*NOTE), "rb") as f:
            raw = f.read()
        with open(self.path(*NOTE), "wb") as f:
            f.write(raw + b"line one\r\nline two\r\n")
        self.fake.assigns[11][0]["duedate"] += 86400
        self.run_cli("sync")
        with open(self.path(*NOTE), "rb") as f:
            self.assertIn(b"line one\r\nline two\r\n", f.read())


class FrontMatter(MoodleCase):
    def test_yaml_quoting_round_trip(self):
        for v in ["plain", "a: b", 'say "hi"', "- dash", "C:\\path", "#tag", "x #y"]:
            line = self.m.yaml_line("k", v)
            self.assertEqual(self.m.props_of("---\n%s\n---\n" % line)["k"], v, line)
        self.assertEqual(self.m.yaml_line("k", "#tag"), 'k: "#tag"')        # unquoted it's a YAML comment

    def test_set_prop_adds_and_replaces(self):
        t = self.m.set_prop("---\na: 1\n---\nbody\n", "b", "2")
        t = self.m.set_prop(t, "a", "3")
        self.assertEqual(t, "---\na: 3\nb: 2\n---\nbody\n")
        self.assertEqual(self.m.set_prop("body\n", "a", "1"), "---\na: 1\n---\nbody\n")

    def test_put_block_replaces_only_the_block(self):
        t = self.m.put_block("mine\n", "one")
        t = self.m.put_block(t + "\nafter\n", "two")
        self.assertEqual(t, "mine\n\n<!-- moodle -->\ntwo\n<!-- /moodle -->\n\nafter\n")


if __name__ == "__main__":
    unittest.main()


class Names(MoodleCase):
    def test_forbidden_characters(self):
        n = self.m.task_name
        self.assertEqual(n('Aufgabe 2: "Web" / API?'), "Aufgabe 2 - 'Web' - API")
        self.assertEqual(n("C# <Basics> | 1*"), "C Basics 1")
        self.assertEqual(n("tab\there\nnewline"), "tab here newline")

    def test_hidden_and_trailing_dots(self):
        self.assertEqual(self.m.task_name(".NET Projekt"), "NET Projekt")
        self.assertEqual(self.m.task_name("Teil 1..."), "Teil 1")
        self.assertEqual(self.m.task_name("..."), "Assignment")
        self.assertEqual(self.m.task_name(".bashrc", fallback="attachment", keep_ext=True), "bashrc")

    def test_long_names(self):
        self.assertEqual(len(self.m.task_name("x" * 300)), self.m.MAX_NAME)
        long_file = self.m.task_name("y" * 300 + ".pdf", keep_ext=True)
        self.assertTrue(long_file.endswith("y.pdf") and len(long_file) == self.m.MAX_NAME, long_file)

    def test_dot_name_is_found_again_by_sync(self):
        self.fake.assigns[11][0]["name"] = ".NET: Intro"
        self.run_cli("add", "1001")
        self.assertTrue(os.path.exists(self.path("notes", "SEW", "NET - Intro", "NET - Intro.md")))
        _, _, err = self.run_cli("sync")
        self.assertIn("0 updated, 1 unchanged", err)
