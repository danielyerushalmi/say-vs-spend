# Crowd Check, Study 2: pre-registration

Written 2026-11-17 by Claude, directed by Jayden Ling. Locked before any AI-crowd answer exists.
The SHA-256 fingerprint of this file is logged in `RESUME.md` (outside the repo) with the time it was locked. Any later change gets a dated "Amendment" section below. The text above it is never edited.

What existed when this was written: a list of 3,210 Wikidata companies with an SEC ID and an English Wikipedia page, and a running lookup of their SEC industry codes. Not yet looked at: any revenue figure, any page-view count, any crowd answer.

## Question
Does an AI-simulated crowd of shoppers know anything about where consumer money goes that plain fame does not already explain?

## Brand rule (applied by code, in this order; every drop is logged with its reason)
1. Pool: Wikidata items with an SEC CIK (P5531) and an English Wikipedia article (query run 2026-11-17).
2. SEC industry code (SIC, from data.sec.gov) between 5200 and 5999 (retail trade).
3. Filed a 10-K with filing date between 2025-07-01 and 2026-11-17 (still an active US filer).
4. Annual revenue on data.sec.gov company facts, in USD, for a period of 330 to 400 days ending between 2025-01-01 and 2026-10-31. Take the latest such period. Concepts tried in this order: RevenueFromContractWithCustomerExcludingAssessedTax, Revenues, SalesRevenueNet, RevenueFromContractWithCustomerIncludingAssessedTax.
5. Revenue at least $50 million (removes shells and near-dead filers).
6. English Wikipedia page views (all-access, user agents) summed over 2025-11-01 to 2026-10-31 are available and above 0, using the article from step 1 (redirects followed once).
7. One entry per CIK. If two CIKs share one Wikipedia article, keep the larger revenue.
8. If more than 80 brands remain: random sample of 80 with Python `random.Random(20261117).sample` on the CIK-sorted list. If fewer than 30 remain: stop and report. Do not loosen the rule without a dated amendment.

Subgroup (EXPLORATORY): SIC 5961 (catalog and mail-order, mostly online sellers), reported separately, whatever its size.

## The AI crowd
- 200 personas built by code from a fixed grid: age band, household income band, US region, online-shopping frequency. Weights are rough US shares (stated in the code). Persona list fixed with seed 20261117 before any call.
- Each persona gets one neutral line per brand: its name and SEC industry label. Same text for every brand. Brand order shuffled per persona.
- Questions, same as Study 1:
  - Heard of it: 1 to 10 ("1 = never heard of it, 10 = know it very well").
  - Likely to buy in the next 12 months: 1 to 10.
- Answers returned as JSON. Brands may be split into batches of up to 40 per call; batch split fixed by seed.
- Main run plus one repeat run (same personas, new shuffle seed 20261118).
- Model: filled in by Jayden before the first paid call. Recorded in the amendment section with the time. Pilot (5 personas, 3 brands) is for checking the prompt and parser only and never enters the results.

## Scores
Spearman rank agreement (1 = same order, 0 = no link). 90% range = 5th to 95th percentile of 2,000 bootstrap draws over brands, seed 20261117 (code: `say/compare.py`).
- Intent = mean "likely to buy" per brand. Revenue = step 4. Fame = Wikipedia views (step 6).

## Hypotheses and pass/fail
- **H1, fame tracking.** PASS if Spearman(intent, fame) minus Spearman(intent, revenue) is at least 0.20 AND the 5th percentile of the bootstrap of that difference is above 0. Otherwise FAIL: "fame effect not confirmed at this n."
- **H2, no extra signal.** Partial Spearman of intent vs revenue holding fame fixed (rank all three, then partial correlation of the ranks). PASS ("crowd adds nothing") if the partial is below 0.30 OR its 90% range includes 0. FAIL ("crowd adds something") if it is 0.30 or more AND the range stays above 0.
- **H3, calibration.** Leave-one-out over brands. Correction A: ordinary least squares, log revenue ~ intent + log(fame views). Comparison: fame-only fit, log revenue ~ log(fame views). Score = Spearman(predicted, actual) over all held-out predictions. PASS if Correction A beats raw Spearman(intent, revenue) by at least 0.15. Fame-only is always reported next to it. If fame-only scores within 0.05 of Correction A, the write-up says "the correction works by adding fame back in."
- Everything else (crowd "heard of it" vs revenue, the SIC 5961 subgroup, repeat-run agreement) is EXPLORATORY.

## Known limits (said now, before results)
- Revenue measures company size, not the share of people who buy.
- The model may remember company sizes from training data. That is a memory effect, not shopper sense.
- The brands are public US retailers with Wikipedia pages, not small brands.
- n near 80 detects a medium link (about 0.3 to 0.4); it cannot settle very weak ones.
- This crowd is a do-it-yourself LLM crowd, not Flashpoint's product.

## Amendments
(none yet)

### Amendment 1 (2026-11-17, ~18:45 ET): code fix, rule unchanged
Before any AI-crowd answer existed, the first brand build let in Vipshop, whose annual report is a 20-F, because the code read "last annual filing" as any of 10-K, 20-F or 40-F. Step 3 says 10-K. The code now also requires the revenue figure to come from a 10-K. The brand list was rebuilt with the same seed. Also noted: Wikimedia rate-limited the first two attempts; the build now waits 2 seconds per request and identifies itself with the public repo URL, as Wikimedia's User-Agent policy asks. Revenue and page-view numbers had been fetched but no statistic was computed.

### Amendment 2 (2026-11-17, ~18:47 ET): prompt wording, before any model call
- Brand names shown to the crowd are the English Wikipedia article title with a trailing "(...)" removed (e.g. "Amazon", "Lowe's"), not SEC legal names ("AMAZON COM INC"). Reason: shoppers know everyday names. Known quirk: Village Super Market shows as "ShopRite", the banner it operates; its revenue is Village's only.
- Persona text grammar fixed ("You shop online every week").
- Note on the brand set: the rule has no "sells mostly to consumers" filter, so some business-to-business sellers are in (Fastenal, CDW, Builders FirstSource, Insight Enterprises, Aramark, Copart). This was fixed by the rule before any crowd answer; they stay in.
- Final brand list: 80 brands sampled from 97 eligible (seed 20261117), 9 in SIC 5961. File: study2/data/brands.json.

### Amendment 3 (2026-11-17 18:50 EST): model chosen, before any model call
Model for the pilot, main and repeat runs: claude-haiku-5-5, default settings (thinking on, default effort). Jayden approved the spend on 2026-11-17. Cap: 450 calls per run.
