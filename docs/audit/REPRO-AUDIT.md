# Reproducibility audit: can a judge rerun the README?

> Note: this audit ran on our development repo, which is now private. This public repo is a one-commit clean copy of it, so commit IDs here are from the development repo (list with times: `docs/DEV-HISTORY.md`).

Date: Sat Nov 14 2026, 12:34 to 12:38 PM ET. Auditor: Claude (sub-agent). Nothing in the original repo was changed except this file. No commits, no pushes.

**Scope warning:** this audit tested commit `80a8ab6`, which was the public branch tip at 12:34. While I worked, someone else made local commit `68938d0` (184 tests) and edited `README.md` (uncommitted). Neither was in my clone. After those are pushed, rerun steps 1 to 3 below once before judging.

## Bottom line

**Yes. A judge can clone the public repo and reproduce every headline number with the system Python 3 and no installs.** All commands exit 0. The tests pass (129). The rebuilt run file matches the committed `frontend/runs/say_latest.json` on every number you asked about. The independent recount finds 0 mismatches, against both the committed file and the rebuilt one.

Two real gaps, both easy to fix (details below):
1. The README rebuild command leaves out 3 flags, so the rebuilt file is missing the `followup_loop` block and the `panel.persona_model_note` text. Numbers are unaffected.
2. The README promises a page ("Open the page") but no page code is on GitHub in any branch.

## Setup

- Clone: `git clone --branch jayden/say-vs-spend https://github.com/danielyerushalmi/hackathon-project` into a new empty folder `<scratch>/`. **No sign-in was needed, so the repo is already publicly readable.** Clone HEAD = `80a8ab6`, the same commit as the local branch.
- Python: `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3`, Python 3.14.4. Nothing installed.
- The clone does not contain the local untracked files (`say/extras.py`, `say/real_check.py`, `say/report.py`, their tests, `docs/report/`, `docs/REAL-PEOPLE-KIT.md`). This audit tests what a judge actually gets.
- `git status` in the clone stayed clean after every command (the README rebuild command writes only to `/tmp/say-check`).

## Commands run

### 1. Tests (README, exactly as written)

```
python3 -m unittest discover -s say/tests -t .
```
Exit code: **0**. Last lines:
```
Ran 129 tests in 28.384s
OK
```
Matches the "129 automated checks" claim in README and METHODS-CARD. Noise only: one `ResourceWarning: unclosed file` in `say/tests/test_flashpoint_import.py:148`, and expected test prints from fake fixtures (`FAKE-004 'Q1__figs' = '11': out of range`). Not a failure.

Extra (not in README): `python3 -m unittest discover -s agent/tests -t .` exit 0, `Ran 101 tests`, `OK`.

### 2. Rebuild (README, exactly as written)

```
mkdir -p /tmp/say-check
python3 -m say.run --export say/panels/q4_export.csv --panel-id 01a1db0a-5b35-7f4a-956d-79e1585ada17 --recorded-at 2026-11-14T12:17:00-05:00 --expect-n 200 --repeat-export say/panels/main_export.csv --repeat-panel-id 01a1dafd-97a0-7330-b505-be47f17f8705 --repeat-recorded-at 2026-11-14T12:02:10-05:00 --wiki-fame say/fame/wikipedia_pageviews.json --no-llm --run-dir /tmp/say-check --panel-out /tmp/say-check/panel.json
```
`/tmp/say-check` did not exist before. Exit code: **0**. Last lines:
```
Run say-2026-11-14T12-17 (recorded), 6 brands, panel '01a1db0a-5b35-7f4a-956d-79e1585ada17'
  say    spearman +0.77  wobble +0.09 to +1.00  could_be_chance=True  avg places off 1.00
  intent spearman +0.03  wobble -0.94 to +0.64  could_be_chance=True  avg places off 2.00
  fame   spearman +0.72  wobble +0.00 to +1.00  could_be_chance=True  avg places off 1.17
  crowd_beat_fame: False
  trust card: Ask real people (intent spearman = 0.03)
  gap: thredup crowd rank 1 vs revenue rank 5
Wrote /tmp/say-check/say_say-2026-11-14T12-17.json and /tmp/say-check/say_latest.json
```
Ran it a second time into the same folder: exit 0 again, so a judge who runs it twice is fine.

### 3. Independent recount

```
python3 -I say/audit/recount.py
```
Exit code: **0**. Last lines:
```
| persona answers mismatching CSV (of 4800) | 0 | 0 | YES |
| intent | -0.9355 to 0.6364 | -1.0000 to 0.7419 | 2000 |
MISMATCHES: none
```
73 checks, all YES. Note: this script always reads the committed `frontend/runs/say_latest.json` (path is fixed on line 6). So I also ran a temporary copy, outside the repo, pointed at the rebuilt `/tmp/say-check/say_latest.json`: exit 0, 73 YES, `MISMATCHES: none`.

## Rebuilt vs. committed run file

Full field-by-field comparison of `/tmp/say-check/say_latest.json` vs. the clone's `frontend/runs/say_latest.json`, ignoring trace times.

**Every number you asked about is identical:**

| Field | Committed | Rebuilt | Match |
|---|---|---|:---:|
| agreement.say spearman / p_exact / wobble | 0.7714 / 0.1028 / 0.0909 to 1.0 | same | YES |
| agreement.intent spearman / p_exact / wobble | 0.0286 / 1.0 / -0.9355 to 0.6364 | same | YES |
| agreement.fame spearman / p_exact / wobble | 0.7247 / 0.1056 / 0.0 to 1.0 | same | YES |
| brands: say_mean, intent_mean, all ranks (6 brands) | e.g. thredup intent_mean 4.255, rank_intent 1, rank_revenue 5 | same | YES |
| trust_card.verdict | ask_real_people | ask_real_people | YES |
| repeat_run.stability | intent 0.8857, say 0.7714, fame 0.9276, max move 1 | same | YES |
| fame_wiki.agreement | 0.9, 0.25 to 1.0, 5 brands | same | YES |
| agreement_buyers, top_gaps, crowd_beat_fame, cost, headline, limits | | same | YES |

**Differences found (not numbers):**

| Path | Committed | Rebuilt | Cause |
|---|---|---|---|
| `followup_loop` | present | missing | README command has no `--followup` / `--followup-trace` |
| `panel.persona_model_note` | "Flashpoint metadata: answers generated by gpt-5.4-mini, uncalibrated" | `null` | README command has no `--persona-model-note` |
| `trace` | 16 steps | 14 steps | the 2 follow-up steps are missing (same cause) |
| `trace[7].detail` | "...saved say/panels/main_run.json" | "...saved /tmp/say-check/panel.json" | expected: README sends the panel to the scratch folder |

**Fix tested:** adding these 3 flags to the README command makes the rebuilt file identical to the committed one except trace times and the expected `trace[7].detail` path (I ran it; exit 0):

```
  --followup say/panels/followup.json \
  --followup-trace say/panels/followup_trace.json \
  --persona-model-note "Flashpoint metadata: answers generated by gpt-5.4-mini, uncalibrated" \
```
Insert them before the `--no-llm` line. Then the README sentence can say "the whole run file matched, except timestamps and the scratch panel path." If you prefer not to change the command, change the sentence instead: "...matched the saved run file exactly. The command leaves out the follow-up loop and the persona-model note, which do not change any number."

## Paths and commands in the docs

Checked every file path, command and commit id in `README.md`, `docs/METHODS-CARD.md`, `docs/JUDGE-QA.md` against the clone.

**Exist and work:** `agent/`, `agent/llm.py`, `docs/`, `docs/METHODS-CARD.md`, `frontend/runs/say_latest.json`, `LICENSE-DRAFT.md`, `say/`, `say/audit/`, `say/audit/RECOUNT.md`, `say/audit/recount.py`, `say/brands/`, `say/brands/VERIFICATION-NOTES.md`, `say/compare.py`, `say/fame/`, `say/fame/wikipedia_pageviews.json`, `say/panels/` (q4_export.csv, main_export.csv, followup.json, followup_trace.json, main_run.json), `say/repeat.py`, `say/run.py`, `say/tests/`, `say/fixtures/FAKE_TEST_DATA_*` (3 files). Flags `--no-llm` and `--max-calls` (default 30) exist in `say/run.py`. `claude-sonnet-5-5` is in `agent/llm.py`.

**Commit ids all exist on GitHub with the stated times:** `ff5b31a` 11:47:19, `1bdd084` 12:01:08, `8ebf44a` 12:09:14, `6a6ee7f` 12:21:26, `cd48fc4` 12:25:17, `7c7f414` 12:26:40.

**Numbers in the docs spot-checked against the run file, all match:** repeat intent -0.20 (-0.80 to 0.82), repeat website 0.54, buyers-only 0.14 (-0.82 to 0.82), ThredUp buy share 0.565, website averages 6.035 to 6.465, Wikipedia ranks, `trust_card.rule` text (word for word), cost 0 calls / $0.00, recount bootstrap -1.00 to 0.74.

**Broken or missing:**

| Where | What | Fix |
|---|---|---|
| README "Open the page: [confirm...]" | No page code on GitHub. `frontend/` holds only `runs/`. Branches `main` and `jayden/agent-pipeline` have no page files either. A judge cannot open the page. | Daniel pushes the page (or a link to the hosted page), then replace the line with the exact open command or URL. |
| README "See LICENSE" | `LICENSE` does not exist (README admits this). | Daniel picks a license and adds `LICENSE`, or reword to "No license yet; see LICENSE-DRAFT.md." |
| README HTML comment | `docs/screenshot.png` does not exist. Hidden comment, so a judge only sees it in the raw file. | Add the screenshot or delete the comment. |

## Not code problems, but a judge will see them

- **The repo is already public** (cloned with no sign-in). The README still opens with `<!-- DRAFT ... Delete this comment before going public. -->` and has 4 `[confirm]` markers (page, AI-use roles x2, LICENSE). Jayden and Daniel should resolve these now. (Claude does not edit them: that is Jayden's call.)
- `.mcp.json` and `CLAUDE.md` (team-relay setup) are in the public repo. I found no secret in them: the token is read from `${TEAM_RELAY_TOKEN}`, not written in. A tree-wide grep for `sk-ant` and home-folder paths found nothing outside `docs/RED-TEAM.md`'s own description of that check.

## What I am unsure about

- I ran on Python 3.14.4 only. Older Python 3 versions are UNVERIFIED (README says "we used 3.14").
- "Each commit was pushed within about a second" (README, METHODS-CARD) cannot be checked from a clone. Remains UNVERIFIED as JUDGE-QA already says.
