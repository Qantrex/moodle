# moodle

My TGM Moodle assignments in the terminal and in my vault. It uses Moodle's own web-service API, the one the Moodle app uses, with a personal token. Only Python's standard library.

```
moodle token                 # once: get a token through TGM single sign-on (no password involved)
moodle list                  # open assignments: due date, subject, submission status
moodle show <link or id>     # one assignment in full: task text, attachments, submission, grade
moodle sync --dry-run        # see what sync would do
moodle sync                  # tracker notes + attachments
moodle courses               # which subject each course maps to
```

It's read-only towards Moodle: it never submits, uploads or changes anything there.

## Getting the token

`moodle token` prints a link. Log in to Moodle in Chrome as usual, then open that link. Moodle answers with a `moodlemobile://token=…` link that the browser can't open. Cancel the dialog, open DevTools (F12 → Network), pick the **last** `launch.php` request (ending in `&confirmed`, status 302) and copy its `location` response header. Paste it when the command asks, and nowhere else: it works like a password. Run `moodle token` in a normal terminal, since the input is hidden.

The token is saved in `~/.config/moodle/token` (mode 600). To keep it in Bitwarden instead, set `MOODLE_TOKEN_CMD='rbw get "TGM Moodle token"'`. If Moodle ever refuses the token, run `moodle token` again.

## What sync does

For each assignment in this year's courses that has a due date in the last 30 days or later (`--all`: older ones too, `--undated`: also ones without a due date). Moodle "assignments" that are only grade slots or info pages (Note, Zeugnis, Schulnachricht, Zwischennote, Organisation) are always left out.

- **Note:** `~/Notes/School/<subject>/<Name>.md` with `type: assignment`, `subject`, `year`, `status`, `due`, `files` and `moodle: <id>`. The `due:` puts it in `School.base` and in the morning briefing.
- **Existing note:** if a note already has `moodle: <id>`, or an unlinked tracker in the same subject has the same key words in its title, sync updates that note instead ("linked by name" in the output). It only sets `due`, `moodle`, `updated` and `status: done` once submitted, and it rewrites the `<!-- moodle -->` block. Everything else in the note stays mine.
- **Attachments:** go to `~/Documents/Schule/<subject>/<Name>/`. Existing files aren't downloaded again.

Courses map to subjects by code or name (ITP, INSY, "Softwareentwicklung" → SEW, "Wirtschaft und Recht" → WIRE, …). For a course that doesn't map, add it to `~/.config/moodle/subjects.json`, e.g. `{"Schulinfo": "ITP"}`. Unmapped courses are skipped and named in the output.

## Settings

| Env | Default |
|---|---|
| `MOODLE_URL` | `https://elearning.tgm.ac.at` |
| `MOODLE_CONFIG` | `~/.config/moodle` |
| `MOODLE_NOTES` | `~/Notes/School` |
| `MOODLE_FILES` | `~/Documents/Schule` |
| `MOODLE_TOKEN_CMD` | (unset) |
