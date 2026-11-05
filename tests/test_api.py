"""API errors, retries, exit codes and token secrecy."""
import http.client
import os
import unittest
from unittest import mock

from base import MoodleCase
from fakemoodle import TOKEN, FakeMoodle, run


class Retries(MoodleCase):
    def test_busy_server_is_retried(self):
        self.fake.http_errors = [503, 502]
        _, out, _ = self.run_cli("courses")
        self.assertIn("SEW", out)

    def test_gives_up_after_three_tries(self):
        self.fake.http_errors = [503] * 5
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 3)
        self.assertIn("can't reach", err)
        self.assertEqual(len(self.fake.http_errors), 2)

    def test_client_errors_are_not_retried(self):
        self.fake.http_errors = [403, 403, 403]
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 3)
        self.assertIn("HTTP 403", err)
        self.assertEqual(len(self.fake.http_errors), 2)

    def test_maintenance_page_is_retried(self):
        answers = iter(["<html>maintenance</html>"])
        real = self.fake.handle

        def handle(url, body):
            nxt = next(answers, None)
            return (200, "text/html", nxt.encode()) if nxt else real(url, body)
        self.fake.handle = handle
        self.run_cli("courses")

    def test_timeout_and_cut_off_answers(self):
        for exc in (TimeoutError("timed out"), http.client.IncompleteRead(b"{")):
            with self.subTest(exc=type(exc).__name__), mock.patch.object(self.fake, "urlopen", side_effect=exc):
                code, _, err = run(self.m, self.fake, "courses")
                self.assertEqual(code, 3)
                self.assertIn(type(exc).__name__, err)


class Errors(MoodleCase):
    def test_refused_token_exits_2(self):
        self.fake.token = "0" * 32
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("refused the token (invalidtoken)", err)

    def test_refused_token_during_status_is_not_swallowed(self):
        self.fake.overrides["mod_assign_get_submission_status"] = {
            "exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Invalid token"}
        code, _, err = self.run_cli("list", ok=False)
        self.assertEqual(code, 2)

    def test_other_moodle_error(self):
        self.fake.overrides["mod_assign_get_assignments"] = {
            "exception": "required_capability_exception", "errorcode": "nopermissions", "message": "Sorry"}
        code, _, err = self.run_cli("list", ok=False)
        self.assertEqual(code, 1)
        self.assertIn("mod_assign_get_assignments: Sorry", err)

    def test_error_without_exception_key(self):
        self.fake.overrides["core_enrol_get_users_courses"] = {"error": "Nope", "errorcode": "servicenotavailable"}
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 1)
        self.assertIn("Nope", err)

    def test_token_in_error_message_is_redacted(self):
        self.fake.overrides["core_enrol_get_users_courses"] = {
            "exception": "x", "errorcode": "x", "message": "bad request wstoken=%s&x=1 (%s)" % (TOKEN, TOKEN)}
        _, _, err = self.run_cli("courses", ok=False)
        self.assertIn("wstoken=***", err)

    def test_unexpected_error_is_redacted(self):
        with mock.patch.object(self.m, "cmd_courses", side_effect=KeyError("token=" + TOKEN)):
            code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 1)
        self.assertIn("unexpected KeyError", err)

    def test_no_token(self):
        os.remove(self.path("config", "token"))
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("moodle token", err)


class TokenSources(MoodleCase):
    def test_env_token(self):
        os.remove(self.path("config", "token"))
        self.m._env["MOODLE_TOKEN"] = TOKEN
        self.run_cli("courses")

    def test_token_cmd(self):
        os.remove(self.path("config", "token"))
        self.m._env["MOODLE_TOKEN_CMD"] = "echo %s" % TOKEN
        self.run_cli("courses")

    def test_failing_token_cmd(self):
        self.m._env["MOODLE_TOKEN_CMD"] = "exit 4"
        code, _, err = self.run_cli("courses", ok=False)
        self.assertEqual(code, 2)
        self.assertIn("MOODLE_TOKEN_CMD failed", err)

    def test_damaged_link(self):
        with self.assertRaises(SystemExit):
            self.m.parse_token("moodlemobile://token=%%%", None)
        with self.assertRaises(SystemExit):
            self.m.parse_token("moodlemobile://token=/w==", None)


if __name__ == "__main__":
    unittest.main()
