# moodle

My TGM Moodle assignments in the terminal and in my vault. It uses Moodle's own web-service API, the one the Moodle app uses, with a personal token. Only Python's standard library.

```
moodle token                 # once: get a token through TGM single sign-on (no password involved)
moodle list [--dated] [--json]   # open assignments (dated + undated), no grade slots, no finished ones (--all: everything)
moodle show <link or id> [--json]  # one assignment in full: task text, attachments, submission, grade, feedback
moodle add <link or id> [...]  # set up a task: vault folder + TASK.md + <files> folder (--dry-run, --no-files, --force)
moodle sync [--dry-run]      # refresh existing tracker notes only (idempotent, never creates folders)
moodle courses [--all]       # which subject each course maps to
```

It's read-only towards Moodle: it never submits, uploads or changes anything there. It's meant both for me in the terminal and for Claude/Gemini to read deadlines and task texts.

## Getting the token

`moodle token` prints a link. Log in to Moodle in Chrome as usual, then open that link. Moodle answers with a `moodlemobile://token=…` link that the browser can't open. Cancel the dialog, open DevTools (F12 → Network), pick the **last** `launch.php` request (ending in `&confirmed`, status 302) and copy its `location` response header. Paste it when the command asks, and nowhere else: it works like a password. Run `moodle token` in a normal terminal, since the input is hidden.

The token is saved in `~/.config/moodle/token` (mode 600). To keep it in Bitwarden instead, set `MOODLE_TOKEN_CMD='rbw get "TGM Moodle token"'`. If Moodle ever refuses the token, run `moodle token` again.

## What add does

`moodle add` sets up only the assignments you name — nothing is bulk-created, so there are no empty folders for upload boxes you'll never fill. Already submitted or graded assignments are skipped unless `--force`.

- **Assignment folder in vault:** `<notes>/<subject>/<Exact Task Name>/` containing `<Exact Task Name>.md` (tracker note with `type` `assignment` or `test`, `subject`, `year`, `status`, `due`, `files` and `moodle: <id>`) and `TASK.md` (the exact Markdown-formatted Moodle task description and instructions). Only characters forbidden in paths or by LiveSync are replaced (`:` → ` - `).
- **Working folder:** `<files>/<subject>/<Exact Task Name>/` is always created (unless `--no-files`), and Moodle intro/activity attachments are downloaded into it and linked via `files`.

## What sync does

`moodle sync` refreshes only tracker notes that already exist in `<notes>/`: `due`, `status: done` once submitted/graded, the auto to-do checkboxes, grade, teacher feedback, `TASK.md` and attachments (re-downloaded if a teacher replaces a file). Unchanged notes are left untouched so LiveSync isn't spammed.

- **Linking:** a note with `moodle: <id>` is updated directly. An unlinked hand-made tracker in the same subject is linked when it shares the task's key words or Classroom50 repo slug ("linked by name" in the output), keeping inline `### Task` on flat notes. Existing `files` paths are reused; git repos and paths outside `<files>` are never overwritten.
- Moodle "assignments" that are only grade slots or admin pages (Note, Zeugnis, Schulnachricht, Zwischennote, Organisation, …) are always ignored.

Courses map to subjects by code or name (ITP, INSY, "Softwareentwicklung" → SEW, "Wirtschaft und Recht" → WIRE, …). For a course that doesn't map, add it to `~/.config/moodle/subjects.json`, e.g. `{"Schulinfo": "ITP"}`. Unmapped courses are skipped and named in the output.

## Private data

The school's details (site URL, subjects, name patterns) belong in this repo. Nothing about you does: the token, `subjects.json` and your folders stay in `~/.config/moodle/`, which is outside the repo.

```toml
# ~/.config/moodle/config.toml
notes = "~/path/to/school-notes"
files = "~/path/to/school-files"
```

## Settings

| Env | Default |
|---|---|
| `MOODLE_URL` | `https://elearning.tgm.ac.at` |
| `MOODLE_CONFIG` | `~/.config/moodle` |
| `MOODLE_NOTES` | `notes` in the config, else `~/.local/share/moodle/notes` |
| `MOODLE_FILES` | `files` in the config, else `~/.local/share/moodle/files` |
| `MOODLE_TOKEN_CMD` | (unset) |
