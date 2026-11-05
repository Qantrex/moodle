"""Attachment downloads: only to Moodle, size limit, safe names, never clobber your edits or a git repo."""
import json
import os
import subprocess
import unittest
import urllib.parse

from base import MoodleCase
from fakemoodle import FILE_TM, PDF, SITE, pluginfile

WORK = ("files", "SEW", "Aufgabe 1 - REST API")


class Downloads(MoodleCase):
    def spec(self):
        return self.fake.assigns[11][0]["introattachments"][0]

    def add_file(self, name, data, path=None, tm=FILE_TM):
        path = path or "55/mod_assign/introattachment/0/" + name
        self.fake.files[path] = data
        f = {"filename": name, "filesize": len(data), "timemodified": tm, "fileurl": pluginfile(SITE, urllib.parse.quote(path))}
        self.fake.assigns[11][0]["introattachments"].append(f)
        return f

    def work(self, *name):
        return self.path(*WORK, *name)

    def read_bytes(self, *name):
        with open(self.work(*name), "rb") as f:
            return f.read()

    def replace_in_moodle(self, data, tm=FILE_TM + 86400):
        self.fake.files["55/mod_assign/introattachment/0/spec.pdf"] = data
        self.spec().update(filesize=len(data), timemodified=tm)

    def test_mtime_is_moodles(self):
        self.run_cli("add", "1001")
        self.assertEqual(int(os.path.getmtime(self.work("spec.pdf"))), FILE_TM)
        self.assertEqual(os.listdir(self.work()), ["spec.pdf"])          # no .part left over

    def test_token_only_goes_to_moodle(self):
        self.spec()["fileurl"] = "https://elsewhere.example.invalid/spec.pdf"
        _, _, err = self.run_cli("add", "1001")
        self.assertIn("the token only goes to Moodle", err)
        self.assertFalse(os.path.exists(self.work("spec.pdf")))

    def test_lookalike_host_is_not_moodle(self):
        self.spec()["fileurl"] = SITE + ".evil.invalid/webservice/pluginfile.php/55/spec.pdf"
        _, _, err = self.run_cli("add", "1001")
        self.assertIn("the token only goes to Moodle", err)

    def test_size_limit_from_metadata(self):
        self.m.MAX_DOWNLOAD = 10
        _, _, err = self.run_cli("add", "1001")
        self.assertIn("limit", err)
        self.assertEqual(self.fake.downloads, [])

    def test_size_limit_while_streaming(self):
        self.m.MAX_DOWNLOAD = 10
        self.spec().pop("filesize")
        _, _, err = self.run_cli("add", "1001")
        self.assertIn("limit", err)
        self.assertEqual(os.listdir(self.work()), [])

    def test_refused_download_leaves_nothing(self):
        self.fake.files["55/mod_assign/introattachment/0/spec.pdf"] = json.dumps(
            {"error": "Sorry, the requested file could not be found", "errorcode": "filenotfound"}).encode()
        self.spec()["filesize"] = None
        _, out, err = self.run_cli("add", "1001")
        self.assertIn("can't download spec.pdf: Sorry", err)
        self.assertEqual(os.listdir(self.work()), [])
        self.assertNotIn("spec.pdf", self.read("notes", "SEW", "Aufgabe 1 - REST API", "Aufgabe 1 - REST API.md"))

    def test_http_error(self):
        self.spec()["fileurl"] = pluginfile(SITE, "55/missing.pdf")
        _, _, err = self.run_cli("add", "1001")
        self.assertIn("can't download spec.pdf: HTTP 404", err)

    def test_name_with_space_in_url(self):
        f = self.add_file("Angabe Teil 2.pdf", b"two")
        f["fileurl"] = pluginfile(SITE, "55/mod_assign/introattachment/0/Angabe Teil 2.pdf")
        self.run_cli("add", "1001")
        self.assertEqual(self.read_bytes("Angabe Teil 2.pdf"), b"two")

    def test_unsafe_and_duplicate_names(self):
        self.add_file("a:b?.txt", b"x")
        self.add_file("spec.pdf", b"other spec", path="55/mod_assign/intro/0/spec.pdf")
        self.add_file("../../escape.txt", b"y", path="55/mod_assign/introattachment/0/escape.txt")
        self.run_cli("add", "1001")
        self.assertEqual(sorted(os.listdir(self.work())), ["a - b.txt", "escape.txt", "spec (2).pdf", "spec.pdf"])
        self.assertEqual(self.read_bytes("spec (2).pdf"), b"other spec")
        _, _, err = self.run_cli("sync")
        self.assertIn("1 unchanged", err)
        self.assertEqual(len(self.fake.downloads), 4)

    def test_same_file_under_two_urls_is_fetched_once(self):
        dup = dict(self.spec(), fileurl=pluginfile(SITE, "55/mod_assign/intro/0/spec.pdf"))
        self.fake.status[101]["assignmentdata"] = {"attachments": {"intro": [dup]}}
        self.run_cli("add", "1001")
        self.assertEqual(os.listdir(self.work()), ["spec.pdf"])

    def test_replaced_in_moodle_is_updated(self):
        self.run_cli("add", "1001")
        self.replace_in_moodle(b"%PDF new version")
        self.run_cli("sync")
        self.assertEqual(self.read_bytes("spec.pdf"), b"%PDF new version")

    def test_your_edit_is_kept_when_moodle_is_unchanged(self):
        self.run_cli("add", "1001")
        with open(self.work("spec.pdf"), "wb") as f:
            f.write(b"my annotated copy")
        self.run_cli("sync")
        self.assertEqual(self.read_bytes("spec.pdf"), b"my annotated copy")
        self.assertEqual(len(self.fake.downloads), 1)

    def test_your_edit_is_kept_when_moodle_changes(self):
        self.run_cli("add", "1001")
        with open(self.work("spec.pdf"), "wb") as f:
            f.write(b"my annotated copy")
        self.replace_in_moodle(b"%PDF new version")
        _, _, err = self.run_cli("sync")
        self.assertIn("keeping yours", err)
        self.assertEqual(self.read_bytes("spec.pdf"), b"my annotated copy")
        self.assertEqual(self.read_bytes("spec (Moodle 2026-10-21).pdf"), b"%PDF new version")
        _, _, err = self.run_cli("sync")
        self.assertIn("1 unchanged", err)

    def test_file_from_older_version_is_adopted(self):
        os.makedirs(self.work())
        with open(self.work("spec.pdf"), "wb") as f:
            f.write(PDF)
        os.utime(self.work("spec.pdf"), (FILE_TM, FILE_TM))
        self.run_cli("add", "1001")
        self.assertEqual(self.fake.downloads, [])

    def test_unknown_local_file_is_never_overwritten(self):
        os.makedirs(self.work())
        with open(self.work("spec.pdf"), "wb") as f:
            f.write(b"something else entirely")
        self.run_cli("add", "1001")
        self.assertEqual(self.read_bytes("spec.pdf"), b"something else entirely")
        self.assertTrue(os.path.exists(self.work("spec (Moodle 2026-10-20).pdf")))

    def test_git_repo_gets_no_downloads(self):
        os.makedirs(self.work())
        subprocess.run(["git", "init", "-q", self.work()], check=True)
        self.run_cli("add", "1001")
        self.assertEqual(sorted(os.listdir(self.work())), [".git"])
        self.assertIn("files: " + self.work(), self.read("notes", "SEW", "Aufgabe 1 - REST API", "Aufgabe 1 - REST API.md"))

    def test_files_path_with_tilde(self):
        self.run_cli("add", "--no-files", "1001")
        note = self.path("notes", "SEW", "Aufgabe 1 - REST API", "Aufgabe 1 - REST API.md")
        home = os.path.dirname(self.m.FILES)
        with open(note) as f:
            text = f.read().replace("files:", "files: ~/files/SEW/Mein Ordner\nold-files:")
        with open(note, "w") as f:
            f.write(text)
        self.m._env["HOME"] = home
        self.run_cli("sync")
        with open(self.path("files", "SEW", "Mein Ordner", "spec.pdf"), "rb") as f:
            self.assertEqual(f.read(), PDF)
        with open(note) as f:
            self.assertIn("files: ~/files/SEW/Mein Ordner", f.read())

    def test_dry_run_writes_no_state(self):
        self.run_cli("add", "--dry-run", "1001")
        self.assertFalse(os.path.exists(self.path("state")))


if __name__ == "__main__":
    unittest.main()
