"""list / show / courses / add / sync against the fake Moodle."""
import base64
import json
import os
import unittest

from base import MoodleCase
from fakemoodle import PDF, TOKEN

TASK = os.path.join("notes", "SEW", "Aufgabe 1 - REST API")
NOTE = os.path.join(TASK, "Aufgabe 1 - REST API.md")
WORK = os.path.join("files", "SEW", "Aufgabe 1 - REST API")


class Courses(MoodleCase):
    def test_current_courses_and_subjects(self):
        _, out, _ = self.run_cli("courses")
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any(line.startswith("SEW ") and "2026-27" in line for line in lines), out)
        self.assertTrue(any(line.startswith("? ") and "Schulinfo" in line for line in lines), out)
        self.assertNotIn("SYT", out)

    def test_all_years(self):
        _, out, _ = self.run_cli("courses", "--all")
        self.assertIn("SYT", out)
        self.assertIn("2025-26", out)


class List(MoodleCase):
    def test_open_assignments_only(self):
        _, out, _ = self.run_cli("list")
        self.assertIn("Aufgabe 1: REST API", out)
        self.assertIn("Datenbank Entwurf", out)
        self.assertNotIn("Note 1. Semester", out)      # grade slot
        self.assertNotIn("Projekt Abgabe", out)        # submitted
        self.assertNotIn("Altes Projekt", out)         # last year
        late = [line for line in out.splitlines() if "Datenbank" in line][0]
        self.assertIn("LATE", late)
        self.assertIn("view.php?id=1001", out)

    def test_json(self):
        _, out, _ = self.run_cli("list", "--json")
        items = json.loads(out)
        self.assertEqual({x["cmid"] for x in items}, {1001, 1004, 2001})

    def test_all_includes_finished(self):
        _, out, _ = self.run_cli("list", "--all")
        self.assertIn("Projekt Abgabe", out)
        self.assertIn("Note 1. Semester", out)

    def test_dated(self):
        self.fake.assigns[11][2]["name"] = "Undated thing"
        self.fake.status[103] = {"lastattempt": {"submission": {"status": "new"}}}
        _, out, _ = self.run_cli("list")
        self.assertIn("Undated thing", out)
        _, out, _ = self.run_cli("list", "--dated")
        self.assertNotIn("Undated thing", out)

    def test_status_calls_are_one_per_listed_assignment(self):
        self.run_cli("list")
        ids = sorted(int(p["assignid"]) for p in self.fake.calls_to("mod_assign_get_submission_status"))
        self.assertEqual(ids, [101, 103, 104, 201])


class Show(MoodleCase):
    def test_full_text(self):
        _, out, _ = self.run_cli("show", "https://moodle.example.invalid/mod/assign/view.php?id=1001")
        self.assertIn("Aufgabe 1: REST API", out)
        self.assertIn("Build a **small** REST API.", out)
        self.assertIn("- GET /items\n- POST /items", out)
        self.assertIn("Files: spec.pdf", out)

    def test_grade_and_feedback(self):
        _, out, _ = self.run_cli("show", "1003")
        self.assertIn("graded: 14,00 / 15,00", out)
        self.assertIn("Feedback: Well done.", out)

    def test_json(self):
        _, out, _ = self.run_cli("show", "1001", "--json")
        self.assertEqual(json.loads(out)["name"], "Aufgabe 1: REST API")

    def test_unknown(self):
        code, _, err = self.run_cli("show", "999", ok=False)
        self.assertNotEqual(code, 0)
        self.assertIn("999", err)


class Add(MoodleCase):
    def test_creates_note_task_and_work_folder(self):
        _, out, err = self.run_cli("add", "1001")
        note = self.read(NOTE)
        self.assertIn("moodle: 1001", note)
        self.assertIn("subject: SEW", note)
        self.assertIn("status: open", note)
        self.assertIn("due: 2026-11-", note)
        self.assertIn("> - [ ] Hand in by **", note)
        self.assertIn("<!-- moodle -->", note)
        task = self.read(TASK, "TASK.md")
        self.assertIn("Build a **small** REST API.", task)
        with open(self.path(WORK, "spec.pdf"), "rb") as f:
            self.assertEqual(f.read(), PDF)
        self.assertIn("1 new", err)

    def test_skips_finished_unless_forced(self):
        _, _, err = self.run_cli("add", "1003")
        self.assertIn("already finished", err)
        self.assertFalse(os.path.exists(self.path("notes", "SEW", "Projekt Abgabe")))
        self.run_cli("add", "--force", "1003")
        self.assertIn("status: done", self.read("notes", "SEW", "Projekt Abgabe", "Projekt Abgabe.md"))

    def test_dry_run_writes_nothing(self):
        self.run_cli("add", "--dry-run", "1001")
        self.assertFalse(os.path.exists(self.path("notes")))
        self.assertFalse(os.path.exists(self.path("files")))
        self.assertEqual(self.fake.downloads, [])

    def test_no_files(self):
        self.run_cli("add", "--no-files", "1001")
        self.assertTrue(os.path.exists(self.path(NOTE)))
        self.assertFalse(os.path.exists(self.path(WORK)))

    def test_unmapped_course_fails(self):
        self.fake.assigns[13] = [{"id": 301, "cmid": 3001, "name": "Info", "duedate": 0, "configs": [], "intro": ""}]
        code, _, err = self.run_cli("add", "3001", ok=False)
        self.assertNotEqual(code, 0)
        self.assertIn("subjects.json", err)


class Sync(MoodleCase):
    def test_unchanged_note_is_not_rewritten(self):
        self.run_cli("add", "1001")
        before = os.stat(self.path(NOTE)).st_mtime_ns
        _, out, err = self.run_cli("sync")
        self.assertEqual(out, "")
        self.assertIn("0 updated, 1 unchanged", err)
        self.assertEqual(os.stat(self.path(NOTE)).st_mtime_ns, before)
        self.assertEqual(len(self.fake.downloads), 1)        # the attachment wasn't fetched again

    def test_due_date_change_updates_note_but_keeps_own_text(self):
        self.run_cli("add", "1001")
        with open(self.path(NOTE), "a", encoding="utf-8") as f:
            f.write("\nMy own notes stay.\n")
        self.fake.assigns[11][0]["duedate"] += 7 * 86400
        _, out, err = self.run_cli("sync")
        self.assertIn("update", out)
        note = self.read(NOTE)
        self.assertIn("due: 2026-11-17", note)
        self.assertIn("My own notes stay.", note)
        self.assertIn("1 updated", err)

    def test_submission_marks_done(self):
        self.run_cli("add", "1001")
        self.fake.status[101]["lastattempt"]["submission"]["status"] = "submitted"
        self.run_cli("sync")
        note = self.read(NOTE)
        self.assertIn("status: done", note)
        self.assertIn("> - [x] Hand in by", note)

    def test_never_creates_notes(self):
        self.run_cli("sync")
        self.assertFalse(os.path.exists(self.path("notes")))

    def test_links_hand_made_note_by_name(self):
        os.makedirs(self.path("notes", "SEW"))
        with open(self.path("notes", "SEW", "REST API.md"), "w") as f:
            f.write("---\ntype: assignment\nsubject: SEW\n---\n# REST API\n\nmine\n")
        _, out, _ = self.run_cli("sync")
        self.assertIn("linked by name", out)
        note = self.read("notes", "SEW", "REST API.md")
        self.assertIn("moodle: 1001", note)
        self.assertIn("### Task", note)
        self.assertIn("mine", note)


class Token(MoodleCase):
    def test_refused_token(self):
        self.fake.token = "0" * 32
        code, _, err = self.run_cli("list", ok=False)
        self.assertNotEqual(code, 0)
        self.assertIn("refused the token", err)

    def test_parse_plain_and_link(self):
        self.assertEqual(self.m.parse_token(TOKEN, None), TOKEN)
        raw = base64.b64encode(("x:::%s:::private" % TOKEN).encode()).decode()
        self.assertEqual(self.m.parse_token("moodlemobile://token=" + raw, None), TOKEN)

    def test_parse_garbage(self):
        with self.assertRaises(SystemExit):
            self.m.parse_token("hello", None)


if __name__ == "__main__":
    unittest.main()
