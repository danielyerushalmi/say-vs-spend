> **SUPERSEDED 2026-11-14 11:20 ET by Jayden's decision: KEEP the weekday (Mon-Fri) question.** Reason: our own MTA pull (agent/mta.py, Oct 5-30, Oct 12 removed) shows Friday shares from 13.1% (Bedford Av) to 18.8% (St Lawrence Av), a 5.7-point gap between stations, not 0.3-0.6. Ideas still adopted: per-station noise bar (bootstrap), headline = predicted error band hit rate on exam stations, "spot-check a new intern" analogy, one label set (trust it / double-check it / ask real people). Note kept below unchanged for the record.

# CHANGE NOTE (Sat Nov 14, 2026, ~11:15 AM): the panel question changed. Read this before running or grading any panel.

For agents on both laptops (Jayden's and Daniel's). This note SUPERSEDES the old question wherever it appears (docs/CROWD-COACH.md "Mon-Fri which mornings", docs/FRONTEND.md `"question"` line, and any weekday-share grading in `agent/`). It does not edit those files; whoever owns them should update them.

Labels: REPORTED = a stress-test agent says it ran the check; the queries are in its own notes; NOT re-run by the sender. UNVERIFIED = not checked.

## CORRECTION (11:30 AM) - READ THIS FIRST: the weekday question is NOT dead
The first version of this note said weekday shares are "almost the same from station to station". That was only true for the 40 most morning-heavy stations. The sender re-ran the check on all stations (MTA `5wq4-mkjj`, subway, Oct 5 to 30 2026, hours 6 to 9, Mon to Fri, 417 stations with all 5 weekdays and at least 5,000 entries):
- ALL stations: Friday's share of the week runs from 13.1% to 21.6% (spread, 1 stdev = 1.6 points; range 8.5 points). Monday to Thursday spreads are smaller (stdev 0.5 to 0.8).
- TOP 40 morning-heavy stations only: Friday 17.7% to 19.4%, stdev 0.3 to 0.5. Flat.
So the jointly-agreed read is: weekday patterns DO vary, but only if the station set spans office-heavy and residential areas. This matches the 11:05 line in decisions.md ("Kept the Mon-Fri question ... Fri ~13% in hybrid-work areas vs ~19% in the Bronx").
**Current decision: keep the Mon-Fri weekday question as written in docs/FRONTEND.md** ("Which weekday mornings do you usually ride the subway?" - "usually", not "last week"). Do NOT switch to the hour question unless the pilot panel shows the weekday answers cannot be graded.
Conditions that still apply: (1) choose stations across the WIDE range of Friday shares, not only the most morning-heavy ones; (2) show the noise bar for every station (a small panel's own wobble is several points, so only differences larger than the wobble count); (3) the 12:30 go/no-go and every rule below still apply.
Caveat the sender cannot settle: where a station is mostly office workers, its entries are not the neighborhood's residents, so a panel of residents is the wrong crowd. Say this on screen. The hour-question numbers below are REPORTED by an agent and NOT re-run.

## What changed (superseded by the correction above; kept for the record and as the fallback question)
OLD (original question): "Which weekday mornings do you usually ride the subway?" / "which mornings last week..."
NEW (single choice): **"On a typical weekday, what time do you usually first enter the subway?"**
Options, exactly: Before 5 AM / 5:00-5:59 / 6:00-6:59 / 7:00-7:59 / 8:00-8:59 / 9:00-9:59 / 10 AM or later / I don't ride the subway on weekdays.

## Why (plain English)
1. "Last week" has no answer key. The newest MTA hour in dataset `5wq4-mkjj` is 2026-11-05 23:00 (verified by the sender with a `max(transit_timestamp)` query). Nov 9 to 13 is not in the data.
2. Weekday shares are almost the same from station to station (about 0.3 to 0.6 points apart, REPORTED), which is smaller than the random wobble of a small AI panel (several points, textbook math, assumes the personas act like a random sample, UNVERIFIED). A coach would learn noise.
3. Time-of-day shares differ more between stations (about 2 to 3.4 points per hour bucket, REPORTED), and the MTA rounds each swipe down to the hour, so the answer options line up exactly with the data.

## What the answer key becomes
Share of weekday entries by hour bucket for hours 5 through 9 (5:00 to 9:59), subway only, date window Oct 5 to Oct 30 2026, per station, from `https://data.ny.gov/resource/5wq4-mkjj.json` (grouped on the server, no key). Cache each query result and its URL to a file.
- Exclude `fare_class_category` = `OMNY - Students` and `Metrocard - Students` (student fares are a large share of 7 AM entries, REPORTED; the panel is adults).
- Remove holidays and low days by a GENERAL rule: federal holidays, plus any day under 75% of that weekday's middle value. Report only what it really removes. Do not stage a catch. (Mon Oct 12, 2026 was a holiday; whether it lowered entries is REPORTED as yes citywide, but let the rule find it.)
- Drop "I don't ride on weekdays" panel answers and show how many there were.
- Say on screen: entries are trips, not people; they include visitors and exclude fare evasion.

## Rules the code must follow
- Grade in plain code, not model calls. Only the Coach and the Skeptic call Claude (about 4 to 6 calls). Test each model id with `check_key.py` at 11:30 (it does not print the key).
- Coach rules are ONE fixed-format line: {trait, cutoff, hour bucket, shift in points}. Code applies them. The model never does arithmetic.
- Before ANY panel result exists, write to `decisions.md`, with the time: (a) the 3 traits the coach may use (for example median income, share aged 65+, share with a college degree), and (b) the label cutoffs (for example "error under [__] points = trust it").
- Exam split: fixed random seed; print a fingerprint (hash) of the split file before panels finish; pull the exam answer key only at the exam step.
- Noise bar per station: resample the panel 1,000 times in code and show the spread. Panel size 100 if the pilot allows, 50 is the floor.
- The dumb baseline is per hour bucket: shift each bucket by the average training error. A rule is kept only if it beats that in leave-one-out by more than the noise bar.
- Never use Flashpoint's `generate_test_data` for results (it makes random junk, per its docs). Check that answers come from the persona run.
- Label every number SYNTHETIC, MEASURED or ESTIMATE. A zip per station chosen by a stated method is an ESTIMATE; save each `demographics` answer as a receipt file.

## Panel plan (Daniel)
1. PILOT FIRST: one panel, one station, about 20 personas, the NEW question. Time it. Look at what comes back and in what format.
2. Then start all stations at once at one fixed size. Whatever has finished at 12:30 is the data set.
3. 12:30 go/no-go: 6 or more finished panels = Crowd Coach. 1 to 5 = Turnstile Truth (one station). 0 = labeled Claude stand-in personas.

## Build order
Build the whole thin path end to end on LABELED Claude stand-in personas first (target ~12:45), then swap in Flashpoint results. Trust card is the first screen: one question in, one label out (icon + word + one-line reason). Everything else sits under "Show the work". Words or icons on every status, never color alone. The map is a small inset or skipped.

## Pitch changes (Jayden presents; agents keep screens consistent with this)
- Analogy: "spot-check a new intern" replaces the thermometer. A passing thermometer implies it works on everything; the intern is honest that skill may not transfer.
- The trust label is the hero, not the coach. Headline number: "the agent predicted how wrong the crowd would be on the locked stations, and landed inside its range on [__] of [__]." This still works if coaching does not help.
- Say "for a new station", never "for any new question". Say "everyone who taps in", not "everyone".
- One label set everywhere: **trust it / double-check it / ask real people.**
- At most 3 numbers spoken. Blanks stay blank until our own run fills them.

## Not changed
The idea, the flow (planner, grader, auditor, coach, skeptic, locked exam, trust card), the fallback order (Turnstile Truth, then Hype Check), and every hard rule in CLAUDE.md. No secrets, keys or tokens in any file. Nothing here is a result.

## UNVERIFIED
How Flashpoint panel answers come back; whether personas really follow each station's census text; which fields `demographics` returns; panel speed and concurrency; event key models and spend cap; presentation length.
