"""An offline stand-in for Moodle's web-service API, for the tests.

All data here is made up (no real courses, people or assignment texts). FakeMoodle answers
/webservice/rest/server.php calls and /webservice/pluginfile.php downloads, either through a patched
urllib.request.urlopen (in-process tests) or through a local http.server (CLI tests in a subprocess).
"""
import contextlib
import copy
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "moodle")
SITE = "https://moodle.example.invalid"
TOKEN = "c0ffee00" * 4                     # a fake 32-hex token; tests check it never shows up in any output
NOW = 1793790000                           # 2026-11-04 11:00 UTC = 12:00 in Vienna
NOW_ISO = "2026-11-04T12:00:00+01:00"
DAY = 86400

PDF = b"%PDF-1.4 fake spec\n"
FILE_TM = 1792483200                       # 2026-10-20 08:00 UTC


def pluginfile(site, path):
    return "%s/webservice/pluginfile.php/%s" % (site, path)


def assignment_data(site=SITE):
    """mod_assign_get_assignments, core_enrol_get_users_courses, … for a small fake school year."""
    courses = [
        {"id": 11, "shortname": "SEW 4XHIT 26/27", "fullname": "Softwareentwicklung 4XHIT 26/27",
         "startdate": 1788220800, "enddate": 0},
        {"id": 12, "shortname": "INSY4", "fullname": "Informationssysteme am Nachmittag",
         "startdate": 1788220800, "enddate": 0},
        {"id": 13, "shortname": "Schulinfo", "fullname": "Schulinformation", "startdate": 1788220800, "enddate": 0},
        {"id": 14, "shortname": "SYT 3XHIT 25/26", "fullname": "Systemtechnik 3XHIT 25/26",
         "startdate": 1756684800, "enddate": 1782864000},
    ]
    spec = {"filename": "spec.pdf", "filepath": "/", "filesize": len(PDF), "timemodified": FILE_TM,
            "mimetype": "application/pdf",
            "fileurl": pluginfile(site, "55/mod_assign/introattachment/0/spec.pdf")}
    assigns = {
        11: [
            {"id": 101, "cmid": 1001, "name": "Aufgabe 1: REST API", "duedate": 1794348000, "cutoffdate": 0,
             "allowsubmissionsfromdate": 0, "configs": [],
             "intro": "<p>Build a <b>small</b> REST API.</p><ul><li>GET /items</li><li>POST /items</li></ul>",
             "introattachments": [spec]},
            {"id": 102, "cmid": 1002, "name": "Note 1. Semester", "duedate": 0, "configs": [], "intro": ""},
            {"id": 103, "cmid": 1003, "name": "Projekt Abgabe", "duedate": 0, "configs": [], "intro": "<p>Repo link.</p>"},
            {"id": 104, "cmid": 1004, "name": "Test Kapitel 3", "duedate": 1793835000, "configs": [
                {"plugin": "file", "subtype": "assignsubmission", "name": "enabled", "value": "0"}], "intro": ""},
        ],
        12: [
            {"id": 201, "cmid": 2001, "name": "Datenbank Entwurf", "duedate": 1793573940, "configs": [],
             "intro": "<p>ER diagram</p>"},
        ],
        14: [{"id": 401, "cmid": 4001, "name": "Altes Projekt", "duedate": 1767225600, "configs": [], "intro": ""}],
    }
    status = {
        101: {"lastattempt": {"submissionsenabled": True, "submission": {"status": "new"}, "gradingstatus": "notgraded"}},
        102: {"lastattempt": {"submission": {"status": "new"}, "gradingstatus": "graded"},
              "feedback": {"gradefordisplay": "12,00 / 15,00"}},
        103: {"lastattempt": {"submission": {"status": "submitted"}, "gradingstatus": "graded"},
              "feedback": {"gradefordisplay": "14,00 / 15,00", "plugins": [
                  {"type": "comments", "editorfields": [{"text": "<p>Well done.</p>"}]}]}},
        104: {"lastattempt": {"submissionsenabled": False, "gradingstatus": "notgraded"}},
        201: {"lastattempt": {"submission": {"status": "new"}, "gradingstatus": "notgraded"}},
    }
    return courses, assigns, status


def event(eid, cmid, name, ts, course, module="assign", action="Add submission", overdue=False, site=SITE):
    return {"id": eid, "name": "%s is due" % name, "activityname": name, "modulename": module, "instance": cmid - 900,
            "eventtype": "due", "timesort": ts, "overdue": overdue, "course": course,
            "action": {"name": action, "url": "%s/mod/%s/view.php?id=%d&action=editsubmission" % (site, module, cmid),
                       "actionable": True} if action else None,
            "url": "%s/mod/%s/view.php?id=%d" % (site, module, cmid)}


def default_events(site=SITE):
    sew = {"id": 11, "shortname": "SEW 4XHIT 26/27", "fullname": "Softwareentwicklung 4XHIT 26/27"}
    insy = {"id": 12, "shortname": "INSY4", "fullname": "Informationssysteme am Nachmittag"}
    return [
        event(1, 2001, "Datenbank Entwurf", 1793573940, insy, overdue=True, site=site),
        event(2, 1004, "Test Kapitel 3", 1793835000, sew, module="quiz", action="Attempt quiz now", site=site),
        event(3, 1001, "Aufgabe 1: REST API", 1794348000, sew, site=site),
        event(4, 1002, "Note 1. Semester", 1794348000, sew, site=site),
        event(5, 1005, "Reflexion &amp; Feedback", NOW + 30 * DAY, sew, action=None, site=site),
    ]


def grade(name, raw, shown, ts, cmid=None, module="assign", feedback="", rng="0,00–15,00", pct="-", itemtype="mod"):
    return {"id": cmid or 0, "itemname": name, "itemtype": itemtype, "itemmodule": module if itemtype == "mod" else None,
            "cmid": cmid, "graderaw": raw, "gradeformatted": shown, "rangeformatted": rng, "percentageformatted": pct,
            "gradedategraded": ts, "gradedatesubmitted": ts and ts - DAY, "feedback": feedback, "feedbackformat": 1,
            "gradeishidden": False}


def default_grades():
    return {
        11: [
            grade("Projekt Abgabe", 14.0, "14,00", NOW - 2 * DAY, cmid=1003, feedback="<p>Well done.</p><p>More tests.</p>",
                  pct="93,33 %"),
            grade("Test Kapitel 2", 9.0, "9,00", NOW - 40 * DAY, cmid=1000, module="quiz"),
            grade("Aufgabe 1: REST API", None, "-", None, cmid=1001),
            grade("Kurs gesamt", 23.0, "23,00", NOW, itemtype="course"),
        ],
        12: [grade("ER Modell", 5.0, "5,00 / 10,00", NOW - 1 * DAY, cmid=2000, rng="0–10")],
    }


class FakeMoodle:
    def __init__(self, site=SITE, token=TOKEN):
        self.site = site
        self.token = token
        self.courses, self.assigns, self.status = assignment_data(site)
        self.files = {"55/mod_assign/introattachment/0/spec.pdf": PDF}
        self.events = default_events(site)
        self.grade_items = default_grades()
        self.overview = []
        self.functions = None                    # site_info "functions": None = all known ones
        self.overrides = {}                      # fn -> answer (dict) or callable(params)
        self.http_errors = []                    # queue of HTTP status codes to answer before the real answer
        self.calls = []                          # (fn, params) for every API call
        self.downloads = []                      # file paths that were downloaded
        self.lock = threading.Lock()

    # -- the API ----------------------------------------------------------------------------------------------

    def answer(self, fn, p):
        if fn in self.overrides:
            o = self.overrides[fn]
            return o(p) if callable(o) else copy.deepcopy(o)
        if p.get("wstoken") != self.token:
            return {"exception": "moodle_exception", "errorcode": "invalidtoken",
                    "message": "Invalid token - token not found"}
        if fn == "core_webservice_get_site_info":
            fns = self.functions or ["core_webservice_get_site_info", "core_enrol_get_users_courses",
                                     "mod_assign_get_assignments", "mod_assign_get_submission_status",
                                     "core_calendar_get_action_events_by_timesort", "gradereport_user_get_grade_items",
                                     "gradereport_overview_get_course_grades"]
            return {"sitename": "Example School", "username": "student", "fullname": "Test Student", "userid": 7,
                    "release": "4.5.1 (Build: 20241007)", "functions": [{"name": f, "version": "1"} for f in fns]}
        if fn == "core_enrol_get_users_courses":
            return copy.deepcopy(self.courses)
        if fn == "mod_assign_get_assignments":
            ids = [int(v) for k, v in p.items() if k.startswith("courseids[")]
            return {"courses": [{"id": c, "assignments": copy.deepcopy(self.assigns[c])}
                                for c in ids if c in self.assigns], "warnings": []}
        if fn == "mod_assign_get_submission_status":
            aid = int(p["assignid"])
            if aid not in self.status:
                return {"exception": "required_capability_exception", "errorcode": "nopermission", "message": "No"}
            return copy.deepcopy(self.status[aid])
        if fn == "core_calendar_get_action_events_by_timesort":
            lo, hi = int(p.get("timesortfrom", 0)), int(p.get("timesortto", 1 << 40))
            after, limit = int(p.get("aftereventid", 0)), int(p.get("limitnum", 20))
            evs = [e for e in sorted(self.events, key=lambda e: (e["timesort"], e["id"])) if lo <= e["timesort"] <= hi]
            if after:
                ids = [e["id"] for e in evs]
                evs = evs[ids.index(after) + 1:] if after in ids else []
            page = evs[:limit]
            return {"events": copy.deepcopy(page), "firstid": page[0]["id"] if page else 0,
                    "lastid": page[-1]["id"] if page else 0}
        if fn == "gradereport_user_get_grade_items":
            cid = int(p["courseid"])
            return {"usergrades": [{"courseid": cid, "userid": 7, "gradeitems": copy.deepcopy(self.grade_items.get(cid, []))}],
                    "warnings": []}
        if fn == "gradereport_overview_get_course_grades":
            return {"grades": copy.deepcopy(self.overview), "warnings": []}
        return {"exception": "dml_missing_record_exception", "errorcode": "invalidrecord",
                "message": "Can't find data record in database table external_functions."}

    def handle(self, url, body):
        """(status, content_type, bytes) for one request."""
        u = urllib.parse.urlsplit(url)
        with self.lock:
            if self.http_errors:
                return self.http_errors.pop(0), "text/html", b"<html>busy</html>"
        if u.path.endswith("/webservice/rest/server.php"):
            p = dict(urllib.parse.parse_qsl(body.decode()))
            with self.lock:
                self.calls.append((p.get("wsfunction"), p))
            return 200, "application/json", json.dumps(self.answer(p.get("wsfunction"), p)).encode()
        if "/webservice/pluginfile.php/" in u.path:
            q = dict(urllib.parse.parse_qsl(u.query))
            path = urllib.parse.unquote(u.path.split("/webservice/pluginfile.php/", 1)[1])
            if q.get("token") != self.token:
                return 200, "application/json", json.dumps(
                    {"error": "Invalid token", "errorcode": "invalidtoken"}).encode()
            if path not in self.files:
                return 404, "text/html", b"not found"
            with self.lock:
                self.downloads.append(path)
            return 200, "application/octet-stream", self.files[path]
        return 404, "text/html", b"not found"

    def calls_to(self, fn):
        return [p for f, p in self.calls if f == fn]

    # -- in-process transport ---------------------------------------------------------------------------------

    def urlopen(self, req, timeout=None, **kw):
        url = req.full_url if hasattr(req, "full_url") else req
        if not url.startswith(self.site + "/"):
            raise urllib.error.URLError("fake network: no route to %s" % urllib.parse.urlsplit(url).netloc)
        status, ctype, body = self.handle(url, getattr(req, "data", None) or b"")
        hdrs = {"Content-Type": ctype, "Content-Length": str(len(body))}
        if status != 200:
            raise urllib.error.HTTPError(url, status, "error", hdrs, io.BytesIO(body))
        return FakeResponse(body, hdrs)


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(body)
        self.headers = headers
        self.status = 200

    def getheader(self, k, default=None):
        return self.headers.get(k, default)


# -- loading the script -----------------------------------------------------------------------------------------

def load(config="", token=TOKEN, **env):
    """A fresh copy of the moodle script with its own config dir, notes/files/state folders and environment.
    Returns the module; m._tmp is the temp root (removed by cleanup(m))."""
    root = tempfile.mkdtemp(prefix="moodle-test-")
    conf = os.path.join(root, "config")
    os.makedirs(conf)
    if config:
        with open(os.path.join(conf, "config.toml"), "w") as f:
            f.write(config)
    if token:
        with open(os.path.join(conf, "token"), "w") as f:
            f.write(token + "\n")
        os.chmod(os.path.join(conf, "token"), 0o600)
    clean = {k: v for k, v in os.environ.items() if not k.startswith("MOODLE_")}
    base = dict(MOODLE_CONFIG=conf, MOODLE_URL=SITE, MOODLE_NOW=NOW_ISO,
                MOODLE_NOTES=os.path.join(root, "notes"), MOODLE_FILES=os.path.join(root, "files"),
                MOODLE_STATE=os.path.join(root, "state"))
    base.update(env)
    base = {k: v for k, v in base.items() if v is not None}
    with mock.patch.dict(os.environ, dict(clean, **base), clear=True):
        loader = importlib.machinery.SourceFileLoader("moodle_cli", SCRIPT)
        spec = importlib.util.spec_from_loader("moodle_cli", loader)
        m = importlib.util.module_from_spec(spec)
        loader.exec_module(m)
    m._tmp = root
    m._env = dict(clean, **base)
    return m


def cleanup(m):
    shutil.rmtree(m._tmp, ignore_errors=True)


@contextlib.contextmanager
def online(m, fake):
    """Route the module's HTTP through `fake` and freeze the clock at NOW."""
    with mock.patch("urllib.request.urlopen", fake.urlopen), mock.patch("time.sleep"), \
            mock.patch("time.time", return_value=float(NOW)), mock.patch.dict(os.environ, m._env, clear=True):
        yield


def run(m, fake, *argv, stdin=None):
    """Run `moodle <argv>` in-process. Returns (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with online(m, fake), mock.patch.object(sys, "argv", ["moodle", *argv]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            m.main()
        except SystemExit as e:
            if isinstance(e.code, str):
                err.write(e.code + "\n")
                code = 1
            else:
                code = e.code or 0
    return code, out.getvalue(), err.getvalue()


# -- a real local HTTP server, for subprocess tests -------------------------------------------------------------

class Server:
    def __init__(self, fake_factory=FakeMoodle):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.site = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.fake = fake_factory(site=self.site)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _handler(server):
        class H(BaseHTTPRequestHandler):
            def _do(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                status, ctype, data = server.fake.handle(server.site + self.path, body)
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _do

            def log_message(self, *a):
                pass
        return H

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
