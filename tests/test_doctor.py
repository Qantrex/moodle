"""moodle doctor: config, token and site checks, never the token itself."""
import os
import unittest

from base import MoodleCase


class Doctor(MoodleCase):
    def test_all_good(self):
        os.makedirs(self.m.NOTES)
        os.makedirs(self.m.FILES)
        with open(self.path("config", "config.toml"), "w") as f:
            f.write('notes = "x"\n')
        code, out, _ = self.run_cli("doctor", ok=False)
        self.assertEqual(code, 0, out)
        self.assertIn("ok   token from %s" % self.path("config", "token"), out)
        self.assertIn("Example School, Moodle 4.5.1, logged in as student", out)
        self.assertIn("time zone Europe/Vienna", out)
        self.assertIn("warn 3 current courses; no subject for: Schulinfo", out)
        self.assertNotIn("FAIL", out)

    def test_missing_folders_and_config_are_warnings(self):
        _, out, _ = self.run_cli("doctor")
        self.assertIn("warn notes folder", out)
        self.assertIn("warn no ", out)

    def test_unknown_config_key(self):
        with open(self.path("config", "config.toml"), "w") as f:
            f.write('notse = "x"\n')
        self.m.CONFIG = {"notse": "x"}
        _, out, _ = self.run_cli("doctor")
        self.assertIn("unknown keys: notse", out)

    def test_token_readable_by_others(self):
        os.chmod(self.path("config", "token"), 0o644)
        _, out, _ = self.run_cli("doctor")
        self.assertIn("readable by others: chmod 600", out)

    def test_no_token(self):
        os.remove(self.path("config", "token"))
        code, out, _ = self.run_cli("doctor", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("FAIL token from", out)
        self.assertEqual(self.fake.calls, [])

    def test_refused_token(self):
        self.fake.token = "0" * 32
        code, out, _ = self.run_cli("doctor", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("FAIL", out)
        self.assertIn("refused the token", out)

    def test_site_down(self):
        self.fake.http_errors = [503] * 3
        code, out, _ = self.run_cli("doctor", ok=False)
        self.assertEqual(code, 3)
        self.assertIn("can't reach", out)

    def test_missing_function(self):
        self.fake.functions = ["core_webservice_get_site_info", "core_enrol_get_users_courses"]
        _, out, _ = self.run_cli("doctor")
        self.assertIn("doesn't offer gradereport_user_get_grade_items (needed for grades)", out)

    def test_odd_token_shape(self):
        self.fake.token = "not-hex-token-value"
        with open(self.path("config", "token"), "w") as f:
            f.write("not-hex-token-value\n")
        os.chmod(self.path("config", "token"), 0o600)
        _, out, err = self.run_cli("doctor")
        self.assertIn("doesn't look like", out)
        self.assertNotIn("not-hex-token-value", out + err)


if __name__ == "__main__":
    unittest.main()
