"""moodle grades: recent grades and feedback (schema moodle-grades/1)."""
import json
import unittest

from base import MoodleCase
from fakemoodle import NOW, SITE


class Grades(MoodleCase):
    def test_text(self):
        _, out, _ = self.run_cli("grades")
        lines = out.splitlines()
        self.assertEqual(len(lines), 2, out)
        self.assertTrue(lines[0].startswith("03.11. INSY  ER Modell"), lines[0])
        self.assertIn("5,00 / 10,00", lines[0])
        self.assertIn("14,00 / 15,00 (93,33 %)  Well done.", lines[1])
        self.assertNotIn("More tests", out)                   # first line of the feedback only
        self.assertNotIn("Kurs gesamt", out)
        self.assertNotIn("REST API", out)                      # not graded yet

    def test_json(self):
        _, out, _ = self.run_cli("grades", "--json")
        d = json.loads(out)
        self.assertEqual(d["schema"], "moodle-grades/1")
        self.assertEqual(d["days"], 30)
        x = d["items"][1]
        self.assertEqual(x["name"], "Projekt Abgabe")
        self.assertEqual(x["subject"], "SEW")
        self.assertEqual(x["feedback"], "Well done.\n\nMore tests.")
        self.assertEqual(x["graded_ts"], NOW - 2 * 86400)
        self.assertEqual(x["url"], SITE + "/mod/assign/view.php?id=1003")

    def test_days_and_all(self):
        _, out, _ = self.run_cli("grades", "--days", "50")
        self.assertIn("Test Kapitel 2", out)
        _, out, _ = self.run_cli("grades", "--all", "--json")
        self.assertEqual(len(json.loads(out)["items"]), 3)

    def test_one_call_per_mapped_course(self):
        self.run_cli("grades")
        ids = sorted(int(p["courseid"]) for p in self.fake.calls_to("gradereport_user_get_grade_items"))
        self.assertEqual(ids, [11, 12])                       # not the unmapped or last year's course

    def test_course_without_grade_report(self):
        real = self.fake.answer

        def answer(fn, p):
            if fn == "gradereport_user_get_grade_items" and p["courseid"] == "12":
                return {"exception": "moodle_exception", "errorcode": "nopermissiontoviewgrades", "message": "Hidden"}
            return real(fn, p)
        self.fake.answer = answer
        _, out, err = self.run_cli("grades")
        self.assertIn("no grades for INSY4", err)
        self.assertIn("Projekt Abgabe", out)

    def test_moodle_format_feedback_is_html_too(self):
        self.fake.grade_items[11][0]["feedbackformat"] = 0
        _, out, _ = self.run_cli("grades", "--json")
        self.assertEqual(json.loads(out)["items"][1]["feedback"], "Well done.\n\nMore tests.")

    def test_nothing_new(self):
        self.fake.grade_items = {}
        _, out, _ = self.run_cli("grades")
        self.assertEqual(out, "No new grades in the last 30 days.\n")


if __name__ == "__main__":
    unittest.main()
