# Public-repo audit

Repo: `danielyerushalmi/hackathon-project`. Audited 2026-11-14, 12:31 to 12:40 PM ET, read-only.
Scope: all 33 commits (through `80a8ab6`, pushed at about 12:34) on every local and remote branch (`main`, `jayden/agent-pipeline`, `jayden/say-vs-spend`, and their `origin/` copies), no tags, no stashes. Also the working tree as of 12:35, including untracked files that are not committed yet. GitHub: no pull requests, no issues. The repo is private right now (checked with `gh api`).

Anything committed after `80a8ab6` is NOT covered. Re-run the check at the bottom right before going public.

## Verdict

**GO, after the steps below (about 10 minutes, plus Daniel's decision).** No secrets anywhere in history. No real-person survey data. No private client names. Nothing needs a history rewrite unless Daniel wants his Gmail address removed.

## Findings

| # | Finding | Severity | Exact location | Minimal fix |
|---|---|---|---|---|
| 1 | API keys and tokens. Searched every commit for `sk-ant`, `sk-...`, `ANTHROPIC_API_KEY=` with a value, `X-Amz-Security-Token`, `X-Amz-Signature`, `Signature=`, `Bearer `, Firecrawl `fc-`, Brave `BSA`, GitHub `ghp_`/`github_pat_`, AWS `AKIA`, Slack `xox`, Google `AIza`, Hugging Face `hf_`, JWT `eyJ`, `password`, `secret`. No real secret found. | ok | The only hits are safe: `.mcp.json:7` is `Bearer ${TEAM_RELAY_TOKEN}`, a placeholder read from the environment. `README.md:85` is `export ANTHROPIC_API_KEY=...`, an instruction. `say/tests/test_run.py:206` is the fake test value `sk-tes...`. | None. |
| 2 | `.env` files, `__pycache__`, `.pyc`, `.DS_Store`, `.claude/`. None of them was ever committed in any of the 107 paths in history. | ok | `.gitignore` covers `__pycache__/`, `*.pyc`, `.env`, `.DS_Store`. | None. |
| 3 | `.claude/` is not in the repo's `.gitignore`. It is ignored on Jayden's Mac only (by a personal setting). A teammate could commit `.claude/settings.local.json` by accident. | should-fix | `.gitignore` | Add the lines `.claude/settings.local.json` and `.claude/*.lock` to `.gitignore`. |
| 4 | Daniel's personal Gmail address is the author and committer email on 4 commits on `main`. It becomes public with the repo. (Jayden's commits use a GitHub no-reply address, so they are fine.) | should-fix (Daniel decides) | Commits `91c1019`, `a9249bc`, `1a30941`, `b3b2029`, author `Daniel Yerushalmi <yerud...>` | Option A, recommended: Daniel says it is OK, and turns on GitHub's "Keep my email addresses private" setting for future commits. Option B: rewrite `main` history to swap the email (for example `git filter-repo` with a mailmap), then force-push. That is hard to undo, and every teammate must re-clone. Only Daniel can choose. |
| 5 | Full surnames of both students in the README credits line. Usual for a hackathon, but it is personal detail beyond first names. Daniel's surname is already public in the repo owner's username. | should-fix (both agree) | `docs/README-SAY-DRAFT.md:4`: "Team: Jayden ... and Daniel ...". (At `80a8ab6`, `README.md` no longer has this line, but older commits of `README.md` do, for example `1da5ab1`.) | Both say yes to full names, or change the line to first names only. |
| 6 | Local home-folder path `/Users/<mac-username>/...` in a run log line. It shows the Mac username. | should-fix | ALREADY FIXED at the branch tip: commit `80a8ab6` changed `say/run.py:162` to `os.path.relpath`, and the current files have no `/Users/` text (`say_progress.json` too). The path stays in OLD commits `6a6ee7f` to `e2374f3` (branch `jayden/say-vs-spend`): `frontend/runs/say_latest.json` and `frontend/runs/say_say-2026-11-14T12-17.json`, lines 8738 and 8874. | No history rewrite: the username is just Jayden's name. If the branch gets squash-merged into `main`, deleting the remote branch `jayden/say-vs-spend` afterwards also hides those old commits from casual browsing. |
| 7 | Flashpoint CSV exports. Checked every historical version of `say/panels/main_export.csv` (200 rows), `say/panels/q4_export.csv` (200 rows), `say/panels/followup_export.csv` (30 rows). `Panel Respondent ID`, `User Agent`, `IP Hash`, `Country`, `Region`, `City`, `Device`, `Timezone`, `Sample Source`, `Segment` are blank in every data row. The one non-blank row is a repeated header row. `Source` = `synthetic` and `Calibration` = `uncalibrated` in every row. | ok | `say/panels/*.csv` | None. |
| 8 | Other panel files. `data/panels/*.json` (branch `jayden/agent-pipeline`) hold only totals per station, plus Flashpoint job, panel and survey IDs. `say/panels/*.json` hold persona answers and panel IDs. No names, emails, IPs or locations. The `say/fixtures/FAKE_TEST_DATA_*` files are labeled as invented. | ok | `data/panels/*.json`, `say/panels/*.json`, `say/fixtures/` | None. UNVERIFIED: that Flashpoint IDs give no access without a login. That is very likely, because they are ID numbers, not keys. |
| 9 | Permission to publish Flashpoint exports. The raw exports come from a paid or sponsor tool. I did not read Flashpoint's terms. | should-fix (UNVERIFIED) | `say/panels/*_export.csv`, `data/panels/*.json` | Ask the Flashpoint sponsor or the organizers if raw synthetic exports may go in a public repo. If they say no, keep the summary JSON and remove the CSVs before going public. |
| 10 | Emails, phone numbers, street addresses, school names, student IDs in file contents. None in any commit or in the working tree. Place names are public subway stations. The only email-shaped text is `noreply@anthropic.com` in commit message trailers. | ok | all files | None. |
| 11 | Private client names. Zero hits in any commit, in commit messages, or in the working tree. | ok | none | None. |
| 12 | Large or binary files. No file over 5 MB. The largest is `say/panels/main_run.json` at 426 KB. No images, PDFs, archives or databases. The whole repo is 1.4 MB. | ok | none | None. |
| 13 | Copied third-party code. All imports are Python standard library. No copyright headers, "adapted from" or Stack Overflow notes. Data sources are public: SEC `sec.gov`, NY Open Data `data.ny.gov`, Census, Wikimedia pageviews, company investor pages (links and short excerpts, longest text 599 characters). | ok | none | None. |
| 14 | No LICENSE file. A public repo without one is "all rights reserved" by default. `LICENSE-DRAFT.md` (MIT, copyright holder left blank) was committed in `80a8ab6`. | should-fix | repo root | Daniel picks the holder, saves the text as `LICENSE`, and deletes `LICENSE-DRAFT.md`. |
| 15 | Team-relay URL becomes public. The token itself is not in the repo. | should-fix (low) | `.mcp.json:5`: `https://team-relay.vercel.app/api/mcp` | Make sure the relay rejects calls without the token, or shut it down after the event. |
| 16 | Future real-people answers. `docs/REAL-PEOPLE-KIT.md:89` already says not to commit the real-answers CSV. Nothing in `.gitignore` enforces it. | should-fix (low) | `.gitignore` | Agree on one folder for real answers (for example `say/real/`) and add it to `.gitignore`. |
| 17 | New untracked folder `.playwright-mcp/` (2.1 MB: 3 page screenshots, a page snapshot, a console log from a local test server). It is not in `.gitignore`, so a `git add` of the whole folder would publish it. No secrets or paths found in it. | should-fix | `.playwright-mcp/` | Add `.playwright-mcp/` to `.gitignore`. Never stage it. |

## Steps before making the repo public (in order)

1. **Daniel decides on his Gmail address in the 4 old commits (finding 4).** Recommended: accept it and turn on GitHub's private-email setting. A history rewrite is the only way to remove it.
2. **Both students OK full names** in `docs/README-SAY-DRAFT.md:4` (and in old `README.md` commits), or change that line to first names only (finding 5).
3. **Home-folder path (finding 6):** already fixed in `80a8ab6`. Nothing to do, unless you also want to delete the old branch after merging.
4. **Add `LICENSE`** from `LICENSE-DRAFT.md` (finding 14). Add `.claude/settings.local.json`, `.claude/*.lock` and `.playwright-mcp/` to `.gitignore` (findings 3 and 17).
5. Should-do, if there is time: ask the organizers or the Flashpoint sponsor if raw exports may be public (finding 9), and check that the relay needs its token (finding 15).
6. Right before flipping to public, run the check below on the newest commits. Teammates may push after `80a8ab6`.

```bash
git fetch --all
git grep -I -n -E -i 'sk-ant|X-Amz-(Security-Token|Signature)|Bearer [A-Za-z0-9]|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}|/Users/' $(git rev-list --all) | sed 's/^[0-9a-f]*://' | sort -u
# Also searched: private client names (kept out of this public file).
git log --all --format='%an <%ae>' | sort | uniq -c
```

The only expected output: the `.mcp.json` placeholder (`Bearer ${TEAM_...`), the fake test key in `say/tests/test_run.py`, the `noreply` addresses, the search lines inside this audit file itself, and the 4 old Daniel commits (unless they were rewritten). Anything new: stop and look before going public.
