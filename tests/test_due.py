"""moodle due: the timeline, as text and as stable JSON (schema moodle-due/1)."""
import json
import unittest

from base import MoodleCase
from fakemoodle import DAY, NOW, SITE, event

KEYS = ["id", "cmid", "module", "course", "subject", "name", "due", "due_ts", "overdue", "action", "url"]


class Due(MoodleCase):
    def due_json(self, *args):
        _, out, _ = self.run_cli("due", "--json", *args)
        return json.loads(out)

    def test_text(self):
        _, out, _ = self.run_cli("due")
        lines = out.splitlines()
        self.assertEqual(lines[0], "2 due in the next 14 days, 1 overdue:")
        self.assertTrue(lines[1].startswith("OVERDUE  Sun 01.11. 23:59  INSY  Datenbank Entwurf  (Add submission)"), lines[1])
        self.assertIn("Thu 05.11. 00:30  SEW   Test Kapitel 3  (Attempt quiz now)", lines[2])
        self.assertIn("Aufgabe 1: REST API", lines[3])
        self.assertNotIn("Note 1. Semester", out)
        self.assertNotIn("Reflexion", out)                  # 30 days out

    def test_json_schema(self):
        d = self.due_json()
        self.assertEqual(d["schema"], "moodle-due/1")
        self.assertEqual(d["site"], SITE)
        self.assertEqual(d["timezone"], "Europe/Vienna")
        self.assertEqual(d["generated"], "2026-11-04T12:00:00+01:00")
        self.assertEqual(d["to"], "2026-11-18T12:00:00+01:00")
        self.assertEqual([list(x) for x in d["items"]], [KEYS] * 3)
        first = d["items"][0]
        self.assertEqual(first, {
            "id": 1, "cmid": 2001, "module": "assign", "course": "INSY4", "subject": "INSY",
            "name": "Datenbank Entwurf", "due": "2026-11-01T23:59:00+01:00", "due_ts": 1793573940, "overdue": True,
            "action": "Add submission", "url": SITE + "/mod/assign/view.php?id=2001"})

    def test_days_and_past(self):
        d = self.due_json("--days", "40", "--past", "1")
        self.assertEqual([x["cmid"] for x in d["items"]], [1004, 1001, 1005])
        self.assertEqual(d["items"][-1]["name"], "Reflexion & Feedback")
        self.assertIsNone(d["items"][-1]["action"])
        calls = self.fake.calls_to("core_calendar_get_action_events_by_timesort")
        self.assertEqual(int(calls[-1]["timesortfrom"]), NOW - DAY)
        self.assertEqual(int(calls[-1]["timesortto"]), NOW + 40 * DAY)

    def test_all_keeps_grade_slots(self):
        self.assertIn(1002, [x["cmid"] for x in self.due_json("--all")["items"]])

    def test_past_due_counts_as_overdue(self):
        self.fake.events[0]["overdue"] = False
        self.assertTrue(self.due_json()["items"][0]["overdue"])

    def test_pages_past_50(self):
        sew = self.fake.events[1]["course"]
        self.fake.events = [event(100 + i, 6000 + i, "Item %03d" % i, NOW + 3600 * i, sew) for i in range(120)]
        d = self.due_json("--days", "10")
        self.assertEqual(len(d["items"]), 120)
        self.assertEqual(len(self.fake.calls_to("core_calendar_get_action_events_by_timesort")), 3)
        self.assertEqual(len({x["id"] for x in d["items"]}), 120)

    def test_nothing(self):
        self.fake.events = []
        _, out, _ = self.run_cli("due", "--days", "3")
        self.assertEqual(out, "Nothing due in the next 3 days.\n")
        self.assertEqual(self.due_json()["items"], [])

    def test_errors_as_json(self):
        self.fake.token = "0" * 32
        code, out, err = self.run_cli("due", "--json", ok=False)
        self.assertEqual(code, 2)
        d = json.loads(out)
        self.assertEqual(d["schema"], "moodle-due/1")
        self.assertEqual(d["error"]["code"], "invalidtoken")
        self.assertIn("refused the token", err)

    def test_network_error_as_json(self):
        self.fake.http_errors = [503] * 3
        code, out, _ = self.run_cli("due", "--json", ok=False)
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out)["error"]["code"], "network")

    def test_one_api_call(self):
        self.run_cli("due")
        self.assertEqual([f for f, _ in self.fake.calls], ["core_calendar_get_action_events_by_timesort"])


if __name__ == "__main__":
    unittest.main()
