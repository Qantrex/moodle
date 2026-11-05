"""Course -> subject mapping and school years."""
import json
import os
import unittest

from base import MoodleCase


class Subjects(MoodleCase):
    def subject(self, short, full, overrides=None):
        return self.m.subject_of({"shortname": short, "fullname": full}, overrides or {})

    def test_code_or_name(self):
        self.assertEqual(self.subject("SEW 4XHIT 26/27", "x"), "SEW")
        self.assertEqual(self.subject("4XHIT", "Softwareentwicklung"), "SEW")
        self.assertEqual(self.subject("4XHIT", "Wirtschaft und Recht"), "WIRE")
        self.assertEqual(self.subject("x", "IT-Sicherheit 4. Jg"), "ITSI")
        self.assertEqual(self.subject("x", "Kurs SYT"), "SYT")
        self.assertEqual(self.subject("Schulinfo", "Schulinformation"), None)

    def test_german_words_are_not_codes(self):
        self.assertEqual(self.subject("INSY4", "Informationssysteme am Nachmittag"), "INSY")
        self.assertEqual(self.subject("4XHIT", "Projekt am TGM INSY"), "INSY")
        self.assertEqual(self.subject("x", "Softwareentwicklung E-Learning"), "SEW")
        self.assertEqual(self.subject("x", "Treffpunkt am Montag"), None)

    def test_code_in_short_name_wins(self):
        self.assertEqual(self.subject("INSY 4XHIT", "Datenbanken und Recht"), "INSY")
        self.assertEqual(self.subject("E 4XHIT", "x"), "E")
        self.assertEqual(self.subject("D_4XHIT", "x"), "D")

    def test_overrides(self):
        self.assertEqual(self.subject("Schulinfo", "x", {"Schulinfo": "ITP"}), "ITP")
        self.assertEqual(self.subject("schulinfo", "x", {"Schulinfo": "ITP"}), "ITP")
        self.assertEqual(self.subject("SEW 4XHIT", "x", {"SEW 4XHIT": ""}), None)

    def test_overrides_file(self):
        with open(self.path("config", "subjects.json"), "w") as f:
            json.dump({"Schulinfo": "ITP"}, f)
        _, out, _ = self.run_cli("courses")
        self.assertIn("ITP", out)

    def test_broken_overrides_file_is_named(self):
        with open(self.path("config", "subjects.json"), "w") as f:
            f.write("{broken")
        _, out, err = self.run_cli("courses")
        self.assertIn("ignoring", err)
        self.assertIn("subjects.json", err)

    def test_sync_names_unmapped_courses(self):
        self.fake.assigns[13] = [{"id": 301, "cmid": 3001, "name": "Info", "duedate": 0, "configs": [], "intro": ""}]
        _, _, err = self.run_cli("sync")
        self.assertIn("no subject for Schulinfo", err)

    def test_insy_course_assignments(self):
        _, out, _ = self.run_cli("list")
        line = [x for x in out.splitlines() if "Datenbank Entwurf" in x][0]
        self.assertIn(" INSY ", line)


class Years(MoodleCase):
    def year(self, full, start=1788220800):
        return self.m.school_year({"fullname": full, "shortname": "", "startdate": start})

    def test_from_name(self):
        self.assertEqual(self.year("SEW 26/27"), "2026-27")
        self.assertEqual(self.year("SEW 26 / 27"), "2026-27")

    def test_from_start_date(self):
        self.assertEqual(self.year("SEW"), "2026-27")                    # starts 2026-09-01
        self.assertEqual(self.year("SEW", start=1782864000), "2026-27")   # set up in July: the new year
        self.assertEqual(self.year("SEW", start=1780000000), "2025-26")   # May 2026

    def test_date_like_numbers_are_not_years(self):
        self.assertEqual(self.year("Abgabe 10/12 SEW"), "2026-27")


if __name__ == "__main__":
    unittest.main()
