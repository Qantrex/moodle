"""The real script in a subprocess against a local HTTP server: real urllib, real exit codes, machine in UTC."""
import json
import os
import subprocess
import sys
import shutil
import tempfile
import unittest

from fakemoodle import NOW_ISO, PDF, SCRIPT, TOKEN, Server


class CLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="moodle-cli-")
        self.addCleanup(shutil.rmtree, self.root, True)
        conf = os.path.join(self.root, "config")
        os.makedirs(conf)
        with open(os.path.join(conf, "token"), "w") as f:
            f.write(TOKEN + "\n")
        os.chmod(os.path.join(conf, "token"), 0o600)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("MOODLE_") and "proxy" not in k.lower()}
        self.env.update(MOODLE_CONFIG=conf, MOODLE_URL=self.server.site, MOODLE_NOW=NOW_ISO, TZ="UTC",
                        MOODLE_NOTES=os.path.join(self.root, "notes"), MOODLE_FILES=os.path.join(self.root, "files"),
                        MOODLE_STATE=os.path.join(self.root, "state"), no_proxy="127.0.0.1,localhost")
        self.server.fake.token = TOKEN
        self.server.fake.downloads.clear()

    def moodle(self, *args, code=0):
        r = subprocess.run([sys.executable, SCRIPT, *args], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def test_due_json(self):
        d = json.loads(self.moodle("due", "--json").stdout)
        self.assertEqual(d["schema"], "moodle-due/1")
        self.assertEqual(d["items"][1]["due"], "2026-11-05T00:30:00+01:00")

    def test_list_show_courses_grades_doctor(self):
        self.assertIn("Datenbank Entwurf", self.moodle("list").stdout)
        self.assertIn("Build a **small** REST API.", self.moodle("show", "1001").stdout)
        self.assertIn("SEW", self.moodle("courses").stdout)
        self.assertIn("Projekt Abgabe", self.moodle("grades").stdout)
        self.assertIn("logged in as student", self.moodle("doctor").stdout)

    def test_add_and_sync_download_through_http(self):
        self.moodle("add", "1001")
        with open(os.path.join(self.root, "files", "SEW", "Aufgabe 1 - REST API", "spec.pdf"), "rb") as f:
            self.assertEqual(f.read(), PDF)
        r = self.moodle("sync")
        self.assertIn("0 updated, 1 unchanged", r.stderr)
        self.assertEqual(len(self.server.fake.downloads), 1)

    def test_refused_token_exit_code(self):
        self.server.fake.token = "0" * 32
        r = self.moodle("due", "--json", code=2)
        self.assertEqual(json.loads(r.stdout)["error"]["code"], "invalidtoken")

    def test_unreachable_site(self):
        self.env.update(MOODLE_URL="http://127.0.0.1:9", MOODLE_RETRY_DELAYS="0")
        r = self.moodle("courses", code=3)
        self.assertIn("can't reach", r.stderr)

    def test_help_lists_commands(self):
        out = self.moodle("--help").stdout
        for c in ("due", "grades", "doctor", "list", "show", "add", "sync", "courses", "token"):
            self.assertIn(c, out)


if __name__ == "__main__":
    unittest.main()
