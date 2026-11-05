# CLAUDE.md

`moodle` is a one-file Python CLI for the owner's TGM school Moodle (elearning.tgm.ac.at): deadlines, task texts,
grades, and tracker notes in an Obsidian vault. It talks to Moodle's web-service API (the app's API) with a personal
token. Public repo. README.md is the user documentation; keep it accurate when behaviour changes.

## Commands

```bash
python3 -m unittest discover -s tests       # all tests, offline (no network, no token)
./moodle doctor                              # config/token/site check on a machine that has a token
./moodle due --json                          # stable output for scripts (schema moodle-due/1)
```

Tests use `tests/fakemoodle.py`: made-up web-service answers through a patched `urlopen` (`run()`/`online()`) or a
local `http.server` (`Server`, used by `test_cli.py`). `tests/base.py` `MoodleCase.run_cli()` fails a test if the fake
token shows up in any output. Add a test with every fix. CI (`.github/workflows/test.yml`) runs them on push.

## Hard rules

- **Read-only towards Moodle.** Only call web-service functions that read (`core_*_get_*`, `mod_assign_get_*`,
  `gradereport_*_get_*`, `core_calendar_get_*`). Never submit, upload, save or change anything there.
- **The token is a password.** Never print or log it, never put it in an exception message, a note, a test fixture
  or a commit. `redact()` is the last line of defence; downloads send it only to `SITE`.
- **Standard library only**, Python 3.11+ (`tomllib`, `zoneinfo`). No pip packages.
- **No personal data in the repo**: not the owner's name, notes, real course or assignment contents. Personal settings
  live in `~/.config/moodle/` (`config.toml`, `subjects.json`, `token`); school-wide details (site, subject codes,
  name patterns) may stay in the code. Fixtures are invented.
- Never overwrite the owner's files: no downloads into git repos, edited attachments are kept (`downloads.json`),
  notes change only inside the `<!-- moodle -->` block and the known front-matter keys, written atomically.
- `--json` schemas (`moodle-due/1`, `moodle-grades/1`) are a contract for the homelab agent: only add fields;
  a breaking change needs a new schema version.

## Style

Short plain-English messages, small logical commits (`FIX:`, `FEAT:`, `TEST:`, `PERF:`, `DOCS:` prefixes).
AI attribution (Co-Authored-By) only on major reworks, not on small fixes.
