# Data audit: frontend/runs/say_latest.json

Audited 2026-11-14, 12:31 to 12:40 ET, branch `jayden/say-vs-spend`, run `say-2026-11-14T12-17`.
Read-only audit. This file is the only file written. Nothing committed.

How: re-fetched sources with `curl`, User-Agent `HackTheUnreachable student research project (no-reply)`, requests
spaced 1.2 to 2 s apart. No www.sec.gov. Raw responses kept in the session scratchpad only (not in the repo).

## 1. Revenue (SEC XBRL, data.sec.gov companyconcept)

Source URL pattern: `https://data.sec.gov/api/xbrl/companyconcept/CIK<cik>/us-gaap/<concept>.json` (all returned HTTP 200).
companyconcept returns only facts with no segment breakdown, so each value is the consolidated company total.

| item | file value | source value | source | match? | note |
|---|---|---|---|---|---|
| Hims & Hers revenue | 2,347,637,000 (2025-01-01 to 2025-12-31) | 2,347,637,000, 364 days, 10-K, fy 2025 FY, accn 0001773751-26-000022, filed 2026-02-23 | companyconcept/CIK0001773751/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json | YES | Full year, calendar 2025 |
| Stitch Fix revenue | 1,348,119,000 (2025-08-03 to 2026-08-01) | 1,348,119,000, 363 days, 10-K, accn 0001628280-26-063365, filed 2026-09-24 | companyconcept/CIK0001576942/... same concept | YES | Full fiscal year (52 weeks) ending Aug 2026 |
| Revolve revenue | 1,225,682,000 (2025-01-01 to 2025-12-31) | 1,225,682,000, 364 days, 10-K, accn 0001193125-26-071307, filed 2026-02-25 | companyconcept/CIK0001746618/... | YES | Full year, calendar 2025 |
| BARK revenue | 394,843,000 (2025-04-01 to 2026-03-31) | 394,843,000, 364 days, 10-K, accn 0001628280-26-042242, filed 2026-06-10 | companyconcept/CIK0001819574/... | YES | Full fiscal year ending Mar 2026 |
| ThredUp revenue | 310,813,000 (2025-01-01 to 2025-12-31) | 310,813,000, 364 days, 10-K, accn 0001484778-26-000007, filed 2026-03-02 | companyconcept/CIK0001484778/... | YES | Full year, calendar 2025 |
| PetMed Express revenue | 179,021,000 (2025-04-01 to 2026-03-31) | 179,021,000, 364 days, 10-K, accn 0001040130-26-000019, filed 2026-06-02 | companyconcept/CIK0001040130/... | YES | Full fiscal year ending Mar 2026 |
| Filing URLs (all 6) | www.sec.gov/Archives/... | accession folder in each URL matches the recorded accession | brand files | YES | Not opened (www.sec.gov blocked earlier). Revolve's `rvlv-20251231.htm` name also confirmed by EDGAR full-text search hit id |

Concept check:
- All 6 use `RevenueFromContractWithCustomerExcludingAssessedTax`. The `Revenues` concept returned 404 for Hims, Revolve,
  BARK, ThredUp. For Stitch Fix and PetMeds, the latest `Revenues` fact is from FY2018 (filed 2018), so the companies
  switched concepts; they do not report a second, bigger total today. "Excluding assessed tax" means sales tax collected
  for governments is left out. That is standard and is not a hidden business line. No flag.
- Not a flag, but worth saying: the windows differ. Three brands are calendar 2025; BARK and PetMeds end March 2026;
  Stitch Fix ends August 2026. I checked whether this changes the revenue ranking: using each company's prior full year
  from the same 10-K instead (Hims 1.477B, Stitch Fix 1.267B, Revolve 1.130B, BARK 484M, ThredUp 260M, PetMeds 227M)
  gives the same order 1 to 6. The closest pair under mixed windows is Stitch Fix FY2025 1.267B vs Revolve 1.226B, still
  the same order. So the ranking is robust to the window choice.

## 2. Online-sales evidence

| brand | quote source | URL type | strength | check done | note |
|---|---|---|---|---|---|
| Hims & Hers | Company 10-Q PDF on IR CDN (q4cdn) | IR-hosted 10-Q | Strong, but partial period | Not re-fetched | 98.4% online is for the six months ended 2025-06-30, not FY2025. The note says so; the label does not |
| Stitch Fix | FY2026 earnings release, investors.stitchfix.com | IR page | Medium-strong | Not re-fetched | No percentage; says purchases are made in app or on website |
| Revolve | Q2 2026 earnings release, investors.revolve.com | IR page | Medium | EDGAR full-text search: "go-to online source for discovery and inspiration" found in Revolve 10-Ks, 7 hits, including FY2025 10-K accn 0001193125-26-071307 | Phrase confirmed in the 10-K. Still no online percentage; physical retail not sized |
| BARK | FY2026 earnings release, investors.bark.co | IR page | Medium-strong | Not re-fetched | 82.3% = DTC / revenue (324,927 / 394,843; arithmetic checks). Assumes DTC means own site/app; release does not say so |
| ThredUp | FY2025 earnings release, ir.thredup.com | IR page | Medium | Tried to re-read the page: HTTP 403 "Access Denied" (Akamai). Stopped there, no retry, no bypass | No percentage; Resale-as-a-Service share not sized |
| PetMed Express | FY2026 earnings release PDF on IR CDN (q4cdn) | IR-hosted PDF | WEAKEST | EDGAR full-text search: "national online pharmacy" in PetMeds 10-Ks = 0 hits | Phrase is press-release wording only, not in any 10-K. No online share; phone orders not ruled out |

Full-text search URL used: `https://efts.sec.gov/LATEST/search-index?q="<phrase>"&ciks=<cik>&forms=10-K` (both HTTP 200).

## 3. Wikipedia pageviews

| item | file value | source value | source URL | match? | note |
|---|---|---|---|---|---|
| Hims & Hers Health, 365 days | 107,995 | 107,995 (365 daily rows, 2025-11-14 to 2026-11-13) | wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Hims_%26_Hers_Health/daily/20251114/20261113 | YES | Article description: "American telehealth company". Right entity |
| BarkBox, 365 days | 11,137 | 11,137 (365 daily rows) | .../user/BarkBox/daily/20251114/20261113 | YES | See title check below |
| Stitch Fix, ThredUp, PetMed Express | 26,592 / 12,820 / 5,613 | not re-fetched (limit 2) | saved URLs | not checked | Titles exist; descriptions: "Online personal styling service (company)", "American company", "American online pet pharmacy". Right entities |
| Revolve | null | Revolve (company), Revolve Group, Revolve (online retailer) all missing on en.wikipedia | en.wikipedia.org/w/api.php?action=query&titles=... | YES (null is honest) | Revolve left out, so the wiki agreement uses 5 brands, not 6 |

Title checks (en.wikipedia API, `redirects`):
- **BARK -> "BarkBox"**: acceptable. "Bark (company)" and "BARK (company)" do not exist. The redirect "Bark & Co." (the
  company's former name) points to BarkBox, so Wikipedia treats BarkBox as the company article. Its short description is
  "Dog toy and treat subscription box", so the file's `uncertain_title` status is fair. Keep it, keep the note.
- Caveat for all brands: per-article pageviews do not count views that arrive through a redirect title
  (for example "Hims & Hers", "PetMeds", "Stitchfix", "Bark & Co."). Views are a floor, not a total. Same rule for every
  brand, so the ranking is less affected than the raw numbers. This caveat is not in the run file.
- ThredUp has a young page id (78045881, so the article itself may be recent). UNVERIFIED whether a full 365 days of
  the article existed; the API did return 365 daily rows for the saved file.

## 4. Flashpoint panel

| item | file value | source value | source | match? | note |
|---|---|---|---|---|---|
| Q4 export row count | n_personas 200 | 201 data rows = 200 COMPLETE + 1 repeated header row | say/panels/q4_export.csv | YES | All 200 have Panel = synthetic:01a1db0a, Calibration = uncalibrated, Quality Excluded blank |
| Persona ids | 200 in personas[] | all 200 equal the export `ID` column; 200 unique | q4_export.csv | YES | |
| Main panel id | 01a1db0a-5b35-7f4a-956d-79e1585ada17 | same string | ../decisions.md, 12:20 ET entry | YES | |
| say_mean / intent_mean, 6 brands | e.g. hims 6.275 / 3.635 | recomputed from CSV: identical for all 6 brands to 3 decimals | q4_export.csv | YES | |
| Repeat panel | panel_id 01a1dafd-97a0-7330-b505-be47f17f8705, n 200 | main_export.csv: 200 COMPLETE, Panel synthetic:01a1dafd | ../decisions.md lists run id 01a1dafd-97a9-7001-... and survey 46608e7a, not this panel id | PARTIAL | Prefix matches; the full panel id is not in decisions.md |
| Follow-up panel | panel 01a1db18-7a8c-..., run 01a1db18-7a9b-..., survey 540b434a-..., n 30 | followup_trace.json and followup_export.csv (30 COMPLETE) agree | ../decisions.md | NOT LOGGED | These ids appear nowhere in decisions.md |

## 5. Labels in say_latest.json

Labeled: brand revenue (MEASURED), brand say/intent/aware/buy numbers (SYNTHETIC, via `labels`), personas[] (SYNTHETIC),
repeat_run (SYNTHETIC), followup_loop (SYNTHETIC), cost (ESTIMATE), fame_wiki views and agreement (MEASURED; that
agreement is pageviews vs revenue, both measured, so the label fits).

Unlabeled numbers:
- `agreement.say/intent/fame.*` (spearman, wobble_low, wobble_high, avg_places_off, n_brands). These are the headline
  statistics. They compare a SYNTHETIC crowd with MEASURED revenue but carry no label.
- `agreement_buyers.*` (spearman, wobble, avg_places_off, n_brands, min_yes_respondents).
- `top_gaps[].crowd_rank`, `top_gaps[].revenue_rank`.
- `trust_card.metric` string "intent spearman = 0.03".
- `panel.n_personas` (a count from the export).
- `brands[].rank_*`: covered only implicitly (rank_fame maps to `aware` through `rank_fame_source`; rank_revenue to
  `revenue`). A reader of the JSON has to infer it.
- Numbers inside `brands[].online_note` text (98.4%, 82.3%): no label key, and Hims' 98.4% is a half-year figure.

Other inconsistencies a judge could spot in the run file:
- Main `trace` says "no follow-up question drafted (model off, no key, call cap hit, or no gaps)" and "0 of 3 gaps got a
  summary", while `followup_loop.trace` says WHY-questions were drafted at 12:24 and run on 30 personas. `top_gaps[].why_summary`
  and `raw_link` are null even though the raw answers exist in say/panels/followup.json.
- The follow-up WHY questions were drafted with `tool: none` and cost shows 0 model calls, so who wrote them is not stated.
  If a Claude session wrote them, they should say AI-generated.
- `trust_card.draft_question` comes from a code template (say/run.py line 270), not a model; the note "Drafted by the agent"
  is true only if "agent" means the code.

## Verdict

Every external number checked matches its source. All 6 revenues match SEC XBRL exactly: right value, full fiscal year,
10-K, consolidated total, no concept that hides revenue. The 2 re-fetched Wikipedia counts match exactly. The panel export
has 200 COMPLETE rows and the means recompute exactly. Weak spots are about evidence strength and labels, not wrong numbers.

## Top fixes (in order)

1. Label the headline statistics: add a label to `agreement`, `agreement_buyers`, `top_gaps` and `trust_card.metric`
   (for example "SYNTHETIC crowd vs MEASURED revenue").
2. Fix the contradictory `trace` lines about the follow-up question, fill `top_gaps[].raw_link` with
   `say/panels/followup.json`, and say who wrote the WHY questions (label AI-generated if a model did).
3. PetMeds is the weakest online-sales case: press-release wording only, not found in any 10-K. Mark it lower confidence
   on screen, or find 10-K wording about the online share.
4. Hims: say "98.4% online in H1 2025 (10-Q)" wherever that figure is shown, not FY2025.
5. Log the follow-up panel ids (survey 540b434a, panel 01a1db18-7a8c, run 01a1db18-7a9b) and the repeat panel id
   (01a1dafd-97a0-7330) in ../decisions.md.
6. Add one line to `fame_wiki.note`: views exclude redirects, so they are a floor; Revolve has no article, so n = 5.

## Not checked

- IR pages for Stitch Fix, BARK, PetMeds, Hims (not re-fetched). ThredUp's IR page returned 403 Access Denied; I stopped
  there, no bypass.
- www.sec.gov filing documents (not opened, by instruction).
- Stitch Fix, ThredUp and PetMeds pageviews (only 2 re-fetches allowed).
- say_latest.json was regenerated by another session during this audit (12:35 ET): it gained an `extras` block and an
  `agreement.*.p_exact` field. Neither was audited. Rechecked at 12:35: revenues, say/intent means, the intent agreement
  numbers and the wiki views are unchanged.
