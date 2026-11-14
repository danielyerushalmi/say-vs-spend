# Red team: Say vs. Spend (judge's review, 2026-11-14 ~12:45 ET)

> **Status at 12:58 PM ET, Nov 14 (commit `0c22195`).** Everything below is the original review at commit 7c7f414; its numbers are as of then. Since then:
> - Finding 1 fixed: `compare.agreement` stores `p_exact` and `could_be_chance` uses it, so say, fame and Wikipedia now all read "could be chance" (run file `agreement`, `fame_wiki.agreement`).
> - Findings 2, 3, 4 fixed in text: the near-perfect-ranking limit, the revenue-measures-size limit and the PRE-REGISTERED / EXPLORATORY labels are in the run file `limits` and in `README.md`, `docs/METHODS-CARD.md`, `docs/PITCH-SAY.md`, `docs/JUDGE-QA.md`. The rule was not changed.
> - Finding 5: the run file's `extras.compression` gives a median SE of 0.148 for the say means (the reviewer's figure below says about 0.14).
> - Finding 6: the draft question is now written by a model (`trust_card.draft_question_source` = "model (claude-sonnet-5-5), AI-generated"), so "Drafted by the agent." is now accurate. The repeat-run note says "same persona model". `extras.sensitivity` (8 brands) exists. The Wikipedia comparison also has a same-5-brand intent score (`fame_wiki.agreement.intent_same_brands_spearman` = 0.10). Still open: `panel.source_link` is null.
> - Finding 9: the docs now give the amendment as 12:09 (commit stamp 12:09:14; rule text and log say 12:10).
> - Finding 10: the run file no longer holds a home-folder path (commit `0c22195`).
> - Tests now: 230 (`say/tests`) + 101 (`agent/tests`).

Reviewer role: the toughest judge in the room (statistician + startup investor).
Scope: branch `jayden/say-vs-spend` at commit 7c7f414, `frontend/runs/say_latest.json`, `say/*.py`, brand files, `../decisions.md`.
Checks I ran myself (no files changed except this one):
- `python3 -m unittest discover say/tests` -> `Ran 129 tests ... OK`.
- My own recount from `say/panels/q4_export.csv` (200 rows, all `COMPLETE`). Means, shares and Spearman match the run file.
- Exact permutation p-values (all 720 orderings of 6 brands), a bootstrap over personas, and a probe of the trust rule. Script is outside the repo. Numbers below.
- Greps of the working tree and all git history for secrets and personal info.

Bottom line: the main verdict ("Ask real people": the crowd's buying intent does not track revenue) is robust. It holds in every check I ran. The risk is in the side numbers and labels around it. Several of them say "not chance" or "measured" or "drafted by the agent" when the evidence is weaker than that. A statistician judge will find those in two minutes.

---

## Ranked findings

### 1. HIGH: "could_be_chance: false" overstates. The bootstrap is the wrong tool at n = 5-6.
**Judge says:** "Your 'say' line is 0.77 and you flag it as not chance. With 6 brands, the exact p-value is 0.10 (two-sided). Your own fame line has the same strength and you call that one chance."
**Evidence:**
- `say_latest.json` `agreement.say`: rho 0.7714, wobble 0.0909 to 1.0, `could_be_chance: false`. Exact permutation test: one-sided p = 0.051, two-sided p = 0.103.
- `agreement.fame`: rho 0.7247, wobble_low exactly 0.0, so `could_be_chance: true` (`compare.py:171` uses `low <= 0`). One-sided p = 0.053. That is the same strength of evidence with the opposite label. The flip is a boundary artifact.
- `fame_wiki.agreement`: rho 0.9, n = 5, `could_be_chance: false`. Exact two-sided p = 0.083.
- Why it happens: `compare.py:140-164` resamples brands with replacement. With 6 items, a resample repeats some brands. A repeated brand agrees with itself on both rankings, so the correlation is pushed up. A percentile interval from 6 points is not reliable.
**Severity:** high. It is the one place where a shown label is statistically wrong.
**Smallest fix:** in `compare.agreement`, add `p_exact` (two-sided, all n! orderings: 720 for n = 6, cheap) and set `could_be_chance = p_exact > 0.05`. Keep the wobble range for display only. About 20 lines plus 2 tests. The verdict does not change. The say line and the wiki line then flip to "could be chance", which is honest.

### 2. HIGH: With 6 brands, "Trust it" needs a perfect ranking. The traffic light is close to fixed in advance.
**Judge says:** "Your green light only turns on for a perfect order. Swap the top two brands and you get yellow. Is this a test or a foregone conclusion?"
**Evidence:** I probed `trust_verdict` with `bootstrap_wobble` on synthetic 6-brand orders against revenue ranks 1..6:

| crowd order vs revenue | point rho | wobble_low | verdict |
|---|---|---|---|
| perfect | 1.00 | 1.00 | trust |
| top two swapped | 0.94 | 0.61 | verify |
| last two swapped | 0.94 | 0.52 | verify |
| three adjacent pairs swapped | 0.83 | 0.46 | verify |
| top three rotated | 0.83 | 0.09 | ask_real_people |

The 12:10 amendment (cutoffs on the 5th percentile) made this stricter. It did not change today's result: under the 11:47 point-estimate rule, intent rho 0.03 < 0.4 is also "Ask real people". So the amendment is harmless here. But the committed `docs/PITCH-SAY.md` (line 25 at 7c7f414: "For a new store, you get one plain label") implies all three labels are reachable. Another session is rewriting that file now (uncommitted). Check that the new version does not imply this either.
**Severity:** high for the pitch, if a judge asks. None for the shown verdict.
**Smallest fix:** say it out loud, and add one line to `limits[]`: "With 6 brands, only a perfect ranking can earn Trust it. The rule is deliberately cautious. More brands are needed for a green light." Do not change the rule now. Changing it after results would be worse.

### 3. HIGH: Revenue is a weak answer key for "how likely are YOU to buy".
**Judge (investor) says:** "Revenue is customers x basket size x how often they buy x international sales. Hims ranks #1 because it sells costly prescription subscriptions, not because more people buy there. Your intent question measures reach. Your answer key measures company size."
**Evidence:** `limits[0]` admits worldwide and wholesale revenue. It does not admit the per-person vs. whole-company mismatch (README hole 3 in `docs/SAY-VS-SPEND.md` names it but the run file does not). Fiscal periods also differ: they end anywhere from 2025-12-31 to 2026-08-01 (`brands[].fiscal_year`).
**Severity:** high on the "impact/validity" score. It cannot be fixed in an hour.
**Smallest fix:** add one `limits[]` line: "Revenue measures business size (customers x spend per customer), not how many people buy. A crowd can be right about who shops and still miss revenue." Possible later work: active-customer counts from the same 10-Ks as a second answer key. Do not add that as a scored line today, because it would be another test chosen after results (see finding 4).

### 4. MEDIUM-HIGH: Forking paths. Ten Spearman numbers, one pre-registered.
**Judge says:** "How many correlations did you compute? Which one would you have shown if intent had come out at 0.8?"
**Evidence:** the run file holds say, intent, fame (aware), buyers-only intent, x 2 panels, plus the wiki fame line: 10 rank correlations on 5-6 brands. Only intent vs revenue (and "crowd beats fame") was pre-registered (decisions.md 11:47). The wiki line was added at 12:24, after the 12:21 result was seen. `decisions.md` says so honestly.
**Severity:** medium-high if the pitch headlines "say 0.77" or "Wikipedia fame 0.9". Low if it does not.
**Smallest fix:** in the pitch and on the page, mark the intent line "PRE-REGISTERED" and every other line "EXPLORATORY (not pre-registered)". Never headline say 0.77 or wiki 0.9.

### 5. MEDIUM: The wobble range ignores noise from the 200 personas. The "say" ranks are mostly noise.
**Judge says:** "Your say means run from 6.04 to 6.47. The standard error of each mean is about 0.14. Half of your say ranks are separated by 0.01-0.02 points."
**Evidence:** say_mean: thredup 6.035, petmeds 6.05, bark 6.06 (ranks 6, 5, 4 inside 0.025); hims 6.275 vs stitchfix 6.255. SD per brand is about 2.0-2.2 (n = 200, SE ≈ 0.14). Bootstrap over PERSONAS (brands fixed, 2000 draws): say rho 5th/50th/95th percentile = 0.03 / 0.60 / 0.83. Intent: -0.49 / -0.14 / 0.14. The repeat panel agrees: say fell to 0.54, intent was -0.20.
**Severity:** medium. It confirms that the intent verdict is robust and that the say number is not.
**Smallest fix:** show the repeat panel's number next to each main number (already in the run file). Add one sentence: "Say ranks change between two AI crowds; intent stays near zero in both."

### 6. MEDIUM: Labels that overstate (run file).
| field | says | reality | fix |
|---|---|---|---|
| `trust_card.note` (`run.py:35`, `DRAFT_NOTE`) | "Drafted by the agent." | The trace says "no follow-up question drafted (model off...)". The question is the code template `run.py:270` (`fallback`). | Use a different note when the fallback is used: "Template question (code). Stopped for a human." |
| `repeat_run.note` (`repeat.py:20`) | "Two independent AI crowds" | Same model (gpt-5.4-mini, uncalibrated), and the main panel had a 4th question. Stability 0.89 shows the model is consistent, not that it is right. Also, the "repeat" ran first (12:02) and the "main" second (12:17). | "Second AI crowd, same model, different 200 personas; main panel also asked a 4th question." |
| `trace` and two brand files (`figs.json:6`, `carparts.json:6`) | "Shown only in the labeled sensitivity view." | No sensitivity block exists in the run file (`grep -c sensitiv say_latest.json` finds only the trace text). | Add the block (see below) or change the text to "not shown". |
| `fame_wiki.crowd_beat_wiki_fame` (`wiki.py:140`) | compares intent rho (6 brands) with wiki rho | Wiki has 5 brands (Revolve null). Different brand sets. | Compute intent on the same 5 brands for that comparison, or drop the boolean. |
| `panel.source_link` | `null` | A judge cannot open the panel. | Point to `say/panels/q4_export.csv` (raw export in the repo) or the Flashpoint link if one exists. |
| `questions` (`runfile.py:35` comment) | wording of survey 46608e7a | Main data is survey 9afcaa05. UNVERIFIED that the wording is identical. | Check once in Flashpoint; fix the comment. |
| `docs/README-SAY-DRAFT.md:59` | describes the 11:47 point-estimate rule as the rule | The 12:10 amendment (low end of the wobble range) is what the code uses. | Copy `TRUST_RULE_TEXT` from `compare.py:29` into the README. |

Sensitivity numbers, computed by me (red team, ~12:40 ET) from the same Q4 export, adding FIGS and CarParts (8 brands): intent -0.14, say 0.54, fame (aware) 0.55. The verdict is unchanged. If you add the sensitivity view, label it "added after results were seen", as decisions.md 12:31 already says.

### 7. MEDIUM: The fame baseline is weak on both lines.
**Judge says:** "Your 'fame' is the same AI model saying whether it has heard of a brand. And your Wikipedia line is missing Revolve and uses BarkBox for BARK."
**Evidence:** `limits[2]`. `wiki.py:33` (Revolve: no article found; UNVERIFIED by me) and `wiki.py:38` (BarkBox, flagged `uncertain_title`). The wiki line is n = 5.
**Severity:** medium. The team already labels this.
**Smallest fix:** on the page, show wiki fame as "n = 5, exploratory". The crowd lost to fame on both fame lines (intent 0.03 vs 0.72 and 0.9), so the conclusion does not depend on which fame line you pick. Say that. It is a strength.

### 8. LOW-MEDIUM: Both counts share one assumption: the Yes/No code book.
**Evidence:** `flashpoint_import.py:82` treats "1" = Yes, "2" = No. `say/audit/recount.py` was written separately but uses the same assumption, so the recount does not test it. If the codes were reversed, every aware and buy share flips.
**Smallest fix:** one sentence in `RECOUNT.md` naming the source of the code book (a Flashpoint page or a screenshot of the survey builder). Plausibility check: Hims at 0.835 aware and BARK at 0.60 point the right way.

### 9. LOW: Timing details a picky judge could catch.
- Commit 8ebf44a (the rule amendment) is timestamped 12:09:14. decisions.md says 12:10. That is harmless, but say "about 12:10".
- `fame_guess` is `null` for every brand. The plan (`docs/SAY-VS-SPEND.md` timeline, "Jayden judges brand FAME before any revenue lookup") was not carried out. Figs revenue was seen before selection (logged 11:47). Either drop the field or say it was skipped.
- Brand selection: 6 of 12 pass. The online-first rule was tightened to a frozen rule at 12:24, after the 12:21 stats. The team correctly kept the two late passers out. The 8-brand sensitivity above shows this choice does not change the verdict.

### 10. Public-repo hygiene
| item | evidence | severity | fix |
|---|---|---|---|
| No `sk-ant`, `X-Amz-Security-Token`, `X-Amz-Signature`, `Amz-Credential`, or `@gmail` in any tracked file | `grep -rIn` on the tree, plus `git log --all -S<term>` for each: no hits | none | none |
| Only "token" use is `.mcp.json`: `Bearer ${TEAM_RELAY_TOKEN}` (read from env, not a secret). The relay URL becomes public. | `.mcp.json:7` | low | OK as is. Make sure the relay rejects calls without the token. |
| A teammate's personal Gmail address is the author email on 4 commits | `git log --all --format='%an <%ae>' \| sort \| uniq -c` | medium (personal info, and it is the teammate's call) | Ask him before the repo goes public. Removing it from past commits means rewriting shared history (hard to undo). The simpler option: he accepts it, and uses GitHub's private noreply address from now on. |
| Local home-folder path (`/Users/<macOS username>/Documents/...`) in the trace | `say_latest.json:8874`, the same line in `say_say-2026-11-14T12-17.json`, and untracked `say_progress.json` | low | Log a repo-relative path in the importer trace step (`run.py`) and regenerate. Do not commit `say_progress.json`, or regenerate it first. |
| Raw export columns `IP Hash`, `User Agent`, `City` | `q4_export.csv` header; all empty, synthetic personas | none | none |
| Brand evidence URLs (q4cdn PDFs, sec.gov) | `say/brands/*.json` | none | Not signed, public. |

---

## The 3 changes that would most raise the score in the next hour
1. **Exact p-value instead of the bootstrap "chance" flag** (finding 1). About 20 lines in `compare.agreement` plus 2 tests. Then rebuild the run file. This removes the only label a statistician can call wrong, and "we used an exact permutation test because n = 6" is a strong thing to say.
2. **Fix the overstating text in one pass** (finding 6 + README rule text). Change the draft-question note, the "independent" wording, the missing sensitivity view (add it, labeled "added after results were seen", or remove the claim), the absolute path, `source_link`, and README line 59. About 30 minutes, all small edits.
3. **Re-frame the pitch around the robust result and say the limits first** (findings 2, 3, 4). Lead with: "Pre-registered test: AI crowd buying intent vs real revenue = 0.03. Second crowd: -0.20. With 8 brands: -0.14. The AI crowd knows which brands are famous (0.72) but not where people spend." Then say: "With 6 brands only a perfect order can earn Trust it, and revenue measures business size, not shopper count." Tag every other line EXPLORATORY. This costs no code.

## 3 strengths to say out loud
1. **Pre-registration with an honest log.** The rule was written at 11:47, and every later change is timestamped, including the peeks ("statistics computed at 12:21 BEFORE this instruction"). The 12:10 amendment made the rule stricter and does not change the verdict. Brands that passed late (FIGS, CarParts) were kept out of the main result because the set locked when the first statistic was computed.
2. **Every number is computed by code and checked twice.** Raw per-persona export in the repo, 129 tests passing, and an independent recount with no mismatches. I recounted again from the CSV and got the same means, shares and Spearman values. LLMs never produce a shown number.
3. **The negative result is robust and reported plainly.** Intent vs revenue is near zero in the main panel (0.03), the second panel (-0.20), the 8-brand sensitivity (-0.14) and a bootstrap over personas (median -0.14). The tool says "Ask real people" and buys nothing. Investors want exactly this: a tool that tells you when not to trust cheap AI research.
