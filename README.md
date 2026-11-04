# moodle

My TGM Moodle assignments in the terminal and in my vault. It uses Moodle's own web-service API, the one the Moodle app uses, with a personal token. Only Python's standard library (3.11+).

```
moodle token                     # once: get a token through TGM single sign-on (no password involved)
moodle due [--days N] [--json]   # what still needs doing, by deadline (the app's timeline), overdue first
moodle list [--dated] [--json]   # open assignments (dated + undated), no grade slots, no finished ones (--all: everything)
moodle show <link or id> [--json]  # one assignment in full: task text, attachments, submission, grade, feedback
moodle grades [--days N] [--json]  # recent grades and teacher feedback (default: last 30 days, --all: every grade)
moodle add <link or id> [...]    # set up a task: vault folder + TASK.md + <files> folder (--dry-run, --no-files, --force)
moodle sync [--dry-run]          # refresh existing tracker notes only (idempotent, never creates folders)
moodle courses [--all]           # which subject each course maps to
moodle doctor                    # check config, token and site (never prints the token)
```

It's read-only towards Moodle: it never submits, uploads or changes anything there. It's meant both for me in the terminal and for Claude/Gemini or a homelab agent to read deadlines and task texts.

## Getting the token

`moodle token` prints a link. Log in to Moodle in Chrome as usual, then open that link. Moodle answers with a `moodlemobile://token=…` link that the browser can't open. Cancel the dialog, open DevTools (F12 → Network), pick the **last** `launch.php` request (ending in `&confirmed`, status 302) and copy its `location` response header. Paste it when the command asks, and nowhere else: it works like a password. Run `moodle token` in a normal terminal, since the input is hidden.

The token is saved in `~/.config/moodle/token` (mode 600). To keep it in Bitwarden instead, set `MOODLE_TOKEN_CMD='rbw get "TGM Moodle token"'`; on a server, `MOODLE_TOKEN` in the environment works too. If Moodle ever refuses the token, run `moodle token` again. `moodle doctor` checks it without showing it.

## What add does

`moodle add` sets up only the assignments you name — nothing is bulk-created, so there are no empty folders for upload boxes you'll never fill. Already submitted or graded assignments are skipped unless `--force`.

- **Assignment folder in vault:** `<notes>/<subject>/<Exact Task Name>/` containing `<Exact Task Name>.md` (tracker note with `type` `assignment` or `test`, `subject`, `year`, `status`, `due`, `files` and `moodle: <id>`) and `TASK.md` (the exact Markdown-formatted Moodle task description and instructions). Only characters forbidden in paths or by LiveSync are replaced (`:` → ` - `); leading and trailing dots go (a leading dot would hide the folder), and very long names are cut at 120 characters.
- **Working folder:** `<files>/<subject>/<Exact Task Name>/` is always created (unless `--no-files`), and Moodle intro/activity attachments are downloaded into it and linked via `files`.

## What sync does

`moodle sync` refreshes only tracker notes that already exist in `<notes>/`: `due`, `status: done` once submitted/graded, the auto to-do checkboxes, grade, teacher feedback, `TASK.md` and attachments. Unchanged notes are left untouched so LiveSync isn't spammed, and notes are written atomically (temp file + rename).

- **Linking:** a note with `moodle: <id>` is updated directly. An unlinked hand-made tracker in the same subject is linked when it shares the task's key words or Classroom50 repo slug ("linked by name" in the output), keeping inline `### Task` on flat notes. Existing `files` paths are reused (`~` works); git repos and paths outside `<files>` are never written to.
- Moodle "assignments" that are only grade slots or admin pages (Note, Zeugnis, Schulnachricht, Zwischennote, Organisation, …) are always ignored.

Courses map to subjects by the code in the short name, then by the subject's name, then by an upper-case code in the full name (ITP, INSY, "Softwareentwicklung" → SEW, "Wirtschaft und Recht" → WIRE, …; words like "am" or "E-Learning" don't count). For a course that doesn't map, add it to `~/.config/moodle/subjects.json`, e.g. `{"Schulinfo": "ITP"}` (`""` ignores a course). Unmapped courses are skipped and named in the output.

## Attachments

- The token is only ever sent to the Moodle site itself, and never printed: a file link to another host is skipped.
- Files over 100 MB are skipped (`MOODLE_MAX_MB`). Names are made safe like task names, and two files with the same name become `name.pdf` and `name (2).pdf`.
- Unchanged files aren't fetched again. `~/.local/state/moodle/downloads.json` remembers what was downloaded: if a teacher replaces a file you haven't touched, it's updated; if you edited your copy, it's kept and the new version is saved next to it as `name (Moodle <date>).pdf`. A file that was already there and differs is never overwritten.

## For scripts and agents

`moodle due --json` and `moodle grades --json` print one JSON object with a versioned schema. Fields are only ever added within a version; times are ISO 8601 in Europe/Vienna, plus Unix seconds.

```json
{"schema": "moodle-due/1", "site": "https://elearning.tgm.ac.at", "generated": "2026-11-04T12:00:00+01:00",
 "timezone": "Europe/Vienna", "from": "…", "to": "…",
 "items": [{"id": 1, "cmid": 2001, "module": "assign", "course": "INSY4", "subject": "INSY", "name": "…",
            "due": "2026-11-01T23:59:00+01:00", "due_ts": 1793573940, "overdue": true,
            "action": "Add submission", "url": "https://…/mod/assign/view.php?id=2001"}]}
```

`moodle-grades/1` items have `course`, `subject`, `name`, `module`, `cmid`, `grade`, `range`, `percentage`, `graded` (ISO), `graded_ts`, `feedback` (Markdown) and `url`.

Exit codes: `0` ok, `1` error, `2` token missing or refused, `3` Moodle unreachable. With `--json`, an error is also printed as `{"schema": …, "error": {"code": "invalidtoken", "message": "…"}}` on stdout. Example for a server: `MOODLE_TOKEN=… MOODLE_RETRY_DELAYS=2 moodle due --days 3 --json`.

## Private data

The school's details (site URL, subjects, name patterns) belong in this repo. Nothing about you does: the token, `subjects.json` and your folders stay in `~/.config/moodle/`, which is outside the repo.

```toml
# ~/.config/moodle/config.toml
notes = "~/path/to/school-notes"
files = "~/path/to/school-files"
# timezone = "Europe/Vienna"
# max_download_mb = 100
```

## Settings

| Env | Default |
|---|---|
| `MOODLE_URL` | `https://elearning.tgm.ac.at` |
| `MOODLE_CONFIG` | `~/.config/moodle` |
| `MOODLE_NOTES` | `notes` in the config, else `~/.local/share/moodle/notes` |
| `MOODLE_FILES` | `files` in the config, else `~/.local/share/moodle/files` |
| `MOODLE_STATE` | `~/.local/state/moodle` (`downloads.json`) |
| `MOODLE_TOKEN` / `MOODLE_TOKEN_CMD` | (unset; else the token file) |
| `MOODLE_TZ` | `timezone` in the config, else `Europe/Vienna` |
| `MOODLE_MAX_MB` | `max_download_mb` in the config, else `100` |
| `MOODLE_TIMEOUT` / `MOODLE_RETRY_DELAYS` | `30` seconds / `2,5` (busy servers and network errors are retried, other HTTP errors aren't) |
| `MOODLE_NOW` | (unset; an ISO time pins the clock, for tests) |
| `MOODLE_DEBUG` | (unset; `1` prints a redacted traceback on unexpected errors) |

## Tests

```
python3 -m unittest discover -s tests
```

Offline: `tests/fakemoodle.py` answers the web-service calls with made-up data, through a patched `urlopen` or a local HTTP server. GitHub Actions runs them on every push.
