# Development history (our original repo)

This public repo is a one-commit clean copy of our work. We built it in a separate development repo. We kept that repo private because its history held unrelated personal information.

Below is that repo's full commit list: short ID, time (US Eastern, Nov 14 2026), author, and commit message. Emails are left out. The README's timeline claims (rule committed 11:47, brand set 12:01, rule made stricter 12:09, first statistic 12:21) come from this list.

UNVERIFIED for outside readers: these IDs live in a private repo, so you can't check them on GitHub. Exported with `git log --reverse --format='%h|%ad|%an|%s'`.

| # | Commit | Time (ET) | Author | Message |
|---:|---|---|---|---|
| 1 | `91c1019` | 09:41:10 | Daniel Yerushalmi | Add team-relay MCP config and coordination protocol |
| 2 | `a9249bc` | 10:56:30 | Daniel Yerushalmi | Add Crowd Coach plan and frontend spec (docs only) |
| 3 | `1a30941` | 10:58:25 | Daniel Yerushalmi | Docs: Daniel owns Flashpoint panels + frontend |
| 4 | `23a5e41` | 11:03:05 | Jayden Ling | Add station list, locked exam split, and agent pipeline contract |
| 5 | `df17c95` | 11:11:15 | Jayden Ling | Add Crowd Coach pipeline: MTA answer key, auditor, grading, coach/skeptic, orchestrator, tests |
| 6 | `fb179d3` | 11:11:18 | Jayden Ling | Docs: panel question changed to time-of-day (see docs/QUESTION-CHANGE.md) |
| 7 | `f6aa020` | 11:13:05 | Jayden Ling | Mark question-change note superseded: keep weekday question (data in note) |
| 8 | `ba11c84` | 11:13:11 | Jayden Ling | Docs: correct QUESTION-CHANGE (weekday question stays; spread depends on station mix) |
| 9 | `b127b5b` | 11:14:16 | Jayden Ling | Add per-station noise bar (bootstrap) and exam band hit-rate; coach directions respected in fit |
| 10 | `adea053` | 11:15:48 | Jayden Ling | Pre-register rule features, trust cutoffs and split fingerprint before any panel result |
| 11 | `947f018` | 11:16:05 | Jayden Ling | Trust label from pre-registered cutoffs; only pre-registered traits reach the coach |
| 12 | `1da5ab1` | 11:21:16 | Jayden Ling | Add README and how-it-works explainer (results left blank until the recorded run) |
| 13 | `09b0e02` | 11:21:33 | Jayden Ling | Add pitch, demo click path and judge Q&A draft (results blank) |
| 14 | `37fe7f3` | 11:22:58 | Jayden Ling | Fix predict_bands crash and tier leak; code-set trust verdict passed to model; Census tract traits (key from env only); end-to-end tests |
| 15 | `b302794` | 11:23:21 | Jayden Ling | Add preflight: key/model check without printing keys, panel count, tests, next commands |
| 16 | `ed67868` | 11:25:30 | Jayden Ling | Trust card carries question, raw and corrected shares for the frontend card |
| 17 | `2d944b4` | 11:30:59 | Jayden Ling | Add 4 Flashpoint panel results (Astoria, Bay Ridge, Kings Hwy, Forest Hills; n=100 each) |
| 18 | `7736bf0` | 11:33:48 | Jayden Ling | Add 4 Flashpoint panel results (St Lawrence Av, 167 St, Jamaica-179 St, Flatbush Av; n=100 each) |
| 19 | `b3b2029` | 11:43:04 | Daniel Yerushalmi | Remove Crowd Coach docs (pivoting to a new idea) |
| 20 | `41796c0` | 11:43:53 | Jayden Ling | Say vs. Spend: plan, split and draft run-file contract (plan only) |
| 21 | `ff5b31a` | 11:47:19 | Jayden Ling | Contract: Daniel's fields, rename do->intent, pre-registered trust rule |
| 22 | `fff207f` | 11:47:27 | Jayden Ling | Contract: store field do_mean -> intent_mean |
| 23 | `06b3717` | 11:53:26 | Jayden Ling | Say vs Spend backend: comparer, run writer, Flashpoint importer (SAY/INTENT/AWARE, 1=Yes 2=No), detective, trust text, 6 brand revenue files, README/pitch drafts |
| 24 | `97cbea6` | 11:58:05 | Jayden Ling | Add one-command runner and try-your-store; question text matches the real survey; respondents not told the store is fictional |
| 25 | `1bdd084` | 12:01:08 | Jayden Ling | Brand verification: 12 brand files (revenue from SEC data API; online-share evidence from company IR pages); 6 pass |
| 26 | `8ebf44a` | 12:09:14 | Jayden Ling | Trust rule: cutoffs apply to the low end of the intent wobble range (amended 12:10, before any result computed) |
| 27 | `80da690` | 12:12:47 | Jayden Ling | Q4 BUY: importer reads BUY__id; buy_share, niche flag (<30%), buyers-only intent agreement (secondary, not the trust label); label-row skip; 106 tests |
| 28 | `78426e5` | 12:16:08 | Jayden Ling | Run file: personas[] (per-shopper answers only, labeled), for Daniel's persona wall; 107 tests |
| 29 | `6a6ee7f` | 12:21:26 | Jayden Ling | First real run (Q4 panel, 200 personas, 6 verified brands): run file + raw exports. Draft question from biggest gap when ask_real_people; importer skips repeated header row and ignores admin columns; 109 tests |
| 30 | `cd48fc4` | 12:25:17 | Jayden Ling | Repeat run (12:02 panel) side by side + stability; independent recount (no mismatches, own code); --expect-n 200 guard; cost note labeled ESTIMATE; 115 tests |
| 31 | `7c7f414` | 12:26:40 | Jayden Ling | Independent fame: Wikipedia 365-day pageviews (Wikimedia API, URLs saved) as fame_wiki line; brand recheck (FIGS, CarParts pass rule but stay out: set locked at first Q4 statistic); 129 tests |
| 32 | `e2374f3` | 12:30:23 | Jayden Ling | Agent loop: biggest gaps -> WHY question -> new 30-persona synthetic panel -> raw answers + timestamped trace (followup_loop in run file) |
| 33 | `80a8ab6` | 12:34:42 | Jayden Ling | Red-team fixes: exact permutation p-value per agreement (could_be_chance uses it); limits for revenue=size, EXPLORATORY lines, n=6; validator checks real rule; no absolute paths. Docs: README, methods card, pitch, judge Q&A, red-team report, license draft |
| 34 | `68938d0` | 12:37:12 | Jayden Ling | Exploratory extras (8-brand sensitivity, order effect, compression, crowd vs crowd); real-people kit (PII-refusing, Wilson intervals); audit fixes: labels on agreement/gaps/metric, wiki caveats, draft-question source, follow-up question source, evidence confidence; audits: idea, data, public repo (GO); 184 tests |
| 35 | `3284a4f` | 12:38:09 | Jayden Ling | Repro audit: fresh clone reproduces every number (tests, rebuild, recount: 0 mismatches) |
| 36 | `c38a9d6` | 12:39:16 | Jayden Ling | Offline evidence report (docs/report/index.html, no JS, inline SVG) + generator say/report.py + tests; honest wording: same-model panels, draft-question source |
| 37 | `318e9e5` | 12:42:51 | Daniel Yerushalmi | Add Say vs. Spend frontend: landing page + desk |
| 38 | `d822bb8` | 12:43:16 | Jayden Ling | Code-audit fixes: key-path crash (MODELS import) + regression test; wiki line via compare.agreement (exact p), same-brand comparison; LLM bad-body handling; honest draft note + same-model wording; 45 hardening tests (230 total); docs fix-pass (exact p, EXPLORATORY labels, repro command) |
| 39 | `40a5056` | 12:47:05 | Daniel Yerushalmi | Frontend: Wikipedia caveat (n brands, exploratory, could be chance) and trust_card.note on the desk |
| 40 | `97b0e2f` | 12:47:20 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (backend, Claude wrapper, latest run file) |
| 41 | `0c22195` | 12:57:48 | Jayden Ling | Model run (6 calls, ~$0.04 ESTIMATE, Sonnet/Haiku on event key): draft question + WHY summaries now AI-generated and labeled; stats unchanged (intent 0.03, verdict ask_real_people) |
| 42 | `200da66` | 13:04:50 | Jayden Ling | Docs fix-pass from numbers audit: 47 values matched; fixed 18 wording issues (test count 331, p-values now stored, rule timing 12:09/12:10, 12 rank scores, AI-generated draft question + cost ~$0.04 ESTIMATE, RED-TEAM status note); report verdict wording; narrower report regression test |
| 43 | `2253912` | 13:07:58 | Daniel Yerushalmi | Frontend polish: navy/ice-blue palette, centered icebergs, depth ruler, rise-in, focus fade |
| 44 | `1a1cdee` | 13:08:15 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (0c22195 model-written draft question + trace path fix, 200da66 docs fix-pass) |
| 45 | `cb9df1c` | 13:11:40 | Jayden Ling | Judge-review fixes (docs): README how to open page + offline report; bootstrap = resamples with replacement; JUDGE-QA Q16 (store owner with no SEC answer key) |
| 46 | `76c06ff` | 13:13:15 | Jayden Ling | Judge-review docs: tagline scoped to 'where the real answer is known'; 230 Say vs. Spend tests named apart from 101 prototype tests; JUDGE-QA: label holds on the point score, exact p = 1.00 explained, Q16 where the AI does work |
| 47 | `839597a` | 13:14:12 | Jayden Ling | Handoff: exact page fixes from judge review for Daniel (docs only; frontend/ untouched) |
| 48 | `dfc9e15` | 13:18:58 | Daniel Yerushalmi | Frontend: judge-review fixes (AI shoppers headline, 0.03 -> Ask real people result pill, Earned not Spent, no census claim, Q4 wording, same-model second crowd, chat sees repeat_run/fame_wiki/followup_loop/extras) |
| 49 | `ee494d9` | 13:19:06 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (docs: README open-the-page steps, JUDGE-QA, METHODS-CARD, PAGE-FIXES) |
| 50 | `de24c47` | 13:20:33 | Jayden Ling | Trust check: 'Should I trust my AI focus group?' for a store owner. Code picks the evidence line + level (same cutoffs, could-be-chance never trusts, untested kinds = ask real people); one Sonnet call sorts the question + drafts a real-people question (never sees numbers/revenue); works with no key. 10 tests (240 total) |
| 51 | `09e5589` | 13:21:12 | Jayden Ling | Handoff: tested server snippet + response fields + UI suggestion for the trust check |
| 52 | `dfdee9c` | 13:22:14 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (trust check engine say/trust_check.py + tests + handoff) |
| 53 | `2bce1ee` | 13:24:43 | Daniel Yerushalmi | Desk: 'Check my crowd' tab wired to /api/trust-check (rate-my-website example first), chat routes website/store questions there; berg name tags never sit on the headline |
| 54 | `8762fc4` | 13:31:10 | Daniel Yerushalmi | Landing: website report card (grades from the crowd's 1-10 website scores, rating spread, second-crowd check), revenue-match pill, verdict leads with where the Flashpoint crowd looked promising; fix verdict hide + note join |
| 55 | `bcce272` | 13:31:41 | Jayden Ling | Trust check: 'Trust it for perception (exploratory)' for like/aware questions when the crowd's score vs revenue AND a second AI crowd's agreement are both >= 0.7 (Jayden's decision 13:30). Labeled EXPLORATORY + could be chance in level_text/why/level_source; 'buy' unchanged (pre-registered rule, Ask real people). 11 tests (241 total) |
| 56 | `7673400` | 13:32:52 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (trust check: 'Trust it for perception (exploratory)' for like/aware kinds) |
| 57 | `19ec15f` | 13:34:36 | Jayden Ling | Predict the AI crowd's website/buy score for a new store (EXPLORATORY, ESTIMATE): 12-brand crowd averages by code; Sonnet few-shot prediction used only where leave-one-out shows it beats 'guess the average'; else the average. Baseline error: website 0.26, buy 0.60. 9 tests (250 total) |
| 58 | `e14d3ef` | 13:34:53 | Jayden Ling | Handoff: wiring for the AI-crowd score predictor |
| 59 | `c876e6c` | 13:35:35 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (say/predict.py: predicted AI-crowd website score, ESTIMATE) |
| 60 | `3410b93` | 13:36:32 | Daniel Yerushalmi | Desk: 'What would an AI crowd rate your website?' - /api/predict (say/predict.py) wired; predicted rating card with range gauge, labeled ESTIMATE, above the trust answer |
| 61 | `367da41` | 13:40:25 | Jayden Ling | Predictor validation (12 Sonnet calls, ~$0.03 ESTIMATE, leave-one-out on 12 brands): website score model 0.289 vs average 0.257 -> average used; buy score model 0.414 vs average 0.60 -> model used. EXPLORATORY |
| 62 | `dfe8941` | 13:41:25 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (predictor validation: website uses average, buy uses model) |
| 63 | `7f8c8d3` | 13:43:50 | Jayden Ling | Predictor: never say 'model used' when no model call ran (no key); says average is used instead. +1 test (251 total). Daniel's catch. |
| 64 | `a06b8e3` | 13:44:41 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (predict: honest no-key wording) |
| 65 | `39f3352` | 13:53:04 | Daniel Yerushalmi | Review fixes: game refuses tied guesses, pre-registered 0.03 first in pill, both crowds' revenue numbers, SYNTHETIC vs SYNTHETIC tag, 'AI-crowd average (no prediction ran)', ties share a grade, favicon |
| 66 | `15a0b6d` | 13:53:17 | Jayden Ling | README finished (no DRAFT, roles from git history, Check my crowd + predictor section, 253 tests). Trust check shows second crowd's own score vs revenue (0.54/0.83) + website-score band; honest docstring; cleaner template question. Predictor: tested-on-famous-brands caveat. +2 tests (253). |
| 67 | `6145b53` | 13:54:31 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (README finished, trust check + predictor wording) |
| 68 | `72a446d` | 13:55:03 | Jayden Ling | Rename perception answer to 'Promising for perception, not proven (exploratory)' (Jayden's decision; text only, same rule and numbers). 253 tests OK. |
| 69 | `e89b419` | 13:55:41 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (perception answer: 'Promising for perception, not proven') |
| 70 | `054435d` | 14:07:40 | Jayden Ling | Public-repo audit: replace the private-name search list with 'private client names' (Jayden). No history rewrite. |
| 71 | `94f8811` | 14:07:59 | Daniel Yerushalmi | Landing story: question-led hero ('Which AI focus-group answers can you bet on?'), strengths-first pill, say/do-gap verdict, impact + cost lines, 'Rate my website' CTA |
| 72 | `0d1a410` | 14:08:46 | Daniel Yerushalmi | Merge origin/main (Jayden's audit doc fix) into local main |
| 73 | `37c3fc7` | 14:14:49 | Daniel Yerushalmi | Verdict wording matches the rule's levels ('Promising, not proven' / 'Ask real people: the say/do gap'); unify asset version tags |
| 74 | `8d64fa2` | 14:18:59 | Daniel Yerushalmi | Grade my website: paste a link, the server loads the real page (public addresses only) and runs 10 code checks with fixes; Claude's read when a key is set; shown next to the Flashpoint crowd's range |
| 75 | `7a2513e` | 14:23:47 | Jayden Ling | Codex review: predictor says 'no usable model prediction was returned' (true with or without a key); README: Grade my website line, Known issues list (UNVERIFIED descriptions). |
| 76 | `1efd487` | 14:25:27 | Daniel Yerushalmi | Deploy on Vercel (api/index.py + vercel.json; key only from the ANTHROPIC_API_KEY env var). Review fixes: grader re-checks every redirect hop (blocks private targets), non-object JSON -> 400, 20s model timeout + 25s page fallback, wording |
| 77 | `f0c04a4` | 14:27:05 | Daniel Yerushalmi | Merge jayden/say-vs-spend into main (README Grade my website + Known issues, predict wording) |
