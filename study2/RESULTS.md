# Crowd Check, Study 2: results (2026-11-17)

Rules: `study2/PREREG.md`, locked before any crowd answer (fingerprints in the hackathon RESUME.md). Labels: MEASURED (SEC revenue, Wikipedia views), SYNTHETIC (AI crowd), EXPLORATORY (not one of the three pre-registered tests).

## Setup
- 80 US retail companies, picked by a fixed rule and a seeded random draw from 97 that qualified (SEC filers with a Wikipedia page, retail-trade industry code, 10-K revenue of at least $50M).
- AI crowd: 200 personas (age, income, region, online-shopping habit) played by Claude Haiku 5.5. Each rated every company: "heard of it" and "likely to buy in the next 12 months", 1 to 10. Main run plus a repeat run with a new shuffle. 32,000 answers, 0 failed calls, total cost $0.47.

## Pre-registered results (main run; repeat run gives the same verdicts)
Spearman rank agreement, 1 = same order, 0 = no link.

| Score | Value | 90% range |
|---|---|---|
| Crowd buy-intent vs real revenue | 0.55 | |
| Crowd buy-intent vs Wikipedia fame | 0.78 | |
| Wikipedia fame vs real revenue (MEASURED vs MEASURED) | 0.57 | |

- **H1, the crowd tracks fame more than spending: PASS.** Fame minus revenue = 0.23 (range 0.11 to 0.37, above 0).
- **H2, nothing left once fame is held fixed: PASS by the rule.** The leftover link is 0.21, under the 0.30 bar. Honest note: its range is 0.002 to 0.42, which sits just above 0, so a small extra signal beyond fame cannot be ruled out. It is not a strong one.
- **H3, a calibration fix beats the raw crowd by 0.15: FAIL.** Correction A (crowd + fame) = 0.57, fame alone = 0.55, raw crowd = 0.55. The fix works only as well as fame alone: "calibrating just adds fame back in."

## Exploratory
- The two crowd runs agree at 0.999. The 200 personas barely differ: the average spread of one company's buy score across personas is 0.76 points on a 10-point scale. 200 "different" shoppers acted almost like one.
- Crowd "heard of it" vs revenue: 0.53.
- Mostly-online subgroup (SIC 5961, 9 companies): intent vs revenue 0.38. Too few to mean much.
- Crowd top 5 by buy intent: Walmart, Amazon, McDonald's, Costco, Home Depot. Revenue top 5: Amazon, Walmart, CVS Health, Costco, Home Depot.

## Checks
- Independent recount with different code (scipy/numpy, `study2/recount.py`): every number above matches to 4 decimals (`data/recount_main.json`).
- 14 unit tests for the Study 2 code, including fake crowds built to follow fame or follow revenue; Study 1's 262 tests still pass.

## What changed from Study 1, and limits
- Study 1 (6 online brands, Flashpoint panel) found 0.03 vs revenue. Here, on 80 large, mostly famous retailers, the crowd's order matches revenue at 0.55. But fame alone matches revenue just as well (0.57), and the crowd follows fame more closely (0.78). So the crowd looks right about money mainly because famous companies are big.
- The model may remember company sizes from its training data. That is memory, not shopper sense.
- Revenue measures company size, not what share of people buy.
- This is a do-it-yourself crowd on one model (Haiku 5.5), not Flashpoint's product. One model, one prompt style.
- The brand rule let in some business-to-business sellers (Fastenal, CDW, Builders FirstSource). Fixed before results.

## One line for an AI engineer
"On 80 retailers, with the rules written down before the run, an AI shopper crowd ranked companies by fame (0.78) more than by real revenue (0.55); once fame was held fixed only a weak link was left (0.21), and a calibration fix did no better than fame alone. Also, 200 personas answered almost identically (0.999 between runs)."
