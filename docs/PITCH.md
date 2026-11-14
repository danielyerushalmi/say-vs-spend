# Crowd Coach: pitch, demo script, judge Q&A (DRAFT for Jayden)

> SUPERSEDED: this is our earlier Crowd Coach prototype from the morning. For Say vs. Spend, see `README.md` and `docs/PITCH-SAY.md`.

Written ~11:25 AM ET, Sat Nov 14, 2026. Presentations 3:30 PM. Jayden presents. Nothing here is a result.

Rules for filling this in:
- `[__]` stays blank until our own saved run fills it. Read each number off the screen, not from memory.
- Every number said aloud must exist on the screen with a label (SYNTHETIC, MEASURED or ESTIMATE).
- Verified facts used below (sources): MTA turnstile data, data.ny.gov dataset 5wq4-mkjj, Oct 5-30 2026, 6-10 AM entries. Friday share of the week's morning entries: 13.1% at Bedford Av (hybrid-work), 18.8% at St Lawrence Av (Bronx). Auditor caught Columbus Day (Oct 12 entries about 55% of a normal Monday at 7 of 12 stations) and removed it. Rules and cutoffs written down before any panel result (`agent/config/preregistration.json`, 11:16 AM). 12 stations, 4 locked as exam by seeded draw. Cutoffs: under 1.5 points trust it, 1.5 to 3 double-check it, over 3 ask real people.
- Do not quote "55%" aloud unless you want a fourth number. Say "about half of a normal Monday."

---

## 1. The 75-second pitch (about 190 words, say it slowly)

Spoken numbers: only three. (1) 13 vs 19 percent, (2) `[__]` of 4, (3) `[$__]` cost.

> **[Open with a person]**
> Picture a tenant group in the Bronx. They want to know what their neighbors think.
> A real survey is slow and costs real money. An AI survey is fast and cheap.
> But nobody tells them how far to trust it.
>
> **[Analogy]**
> It is like spot-checking a new intern. You don't ask, "Are they smart?" You ask, "On this kind of task, how often are they right?"
> That is Crowd Coach.
>
> **[The test]**
> We asked an AI crowd, built on Flashpoint, which weekday mornings people ride the subway. Then we graded it against MTA turnstile counts. Those count everyone who taps in.
> The real patterns differ. At a hybrid-work station, 13 percent of the week's morning rides are on Friday. At a Bronx station, 19.
> Our auditor checked the answer key and caught Columbus Day. Entries were about half of a normal Monday. It removed the day.
>
> **[Headline]**
> We locked four stations as a final exam. We wrote our rules and our trust cutoffs down before any result.
> Then the agent predicted how wrong the crowd would be on each locked station.
> It landed inside its own range on **[__] of 4**.
>
> **[Trust label is the hero]**
> So for a new station, you get one plain label: trust it, double-check it, or ask real people.
> If it says ask real people, it writes the question and stops. A human decides. It buys nothing.
>
> **[Honest-miss line. Say it only if it is true; pick one]**
> - If coaching did NOT help: "Our coaching rules did not beat a simple average fix. We are showing that, because the trust label still works. Knowing when not to trust the crowd is the product."
> - If coaching helped: "Coaching cut the exam error from [__] to [__] points. A simple average fix got [__]." (Replace one of the three numbers; drop the cost line.)
>
> **[Cost + sponsors, close]**
> One full run cost about **[$__]**, an estimate from our own call counter.
> Flashpoint builds and runs the AI crowd. Claude writes the coach's rules, predicts the crowd's error and drafts the trust card. Plain code does every calculation and the skeptic's test. Cheap research is only fair if you know how far to trust it.

Time trims: cut the cost sentence first, then the Columbus Day sentence (keep it for the demo).

Word choices (from the adopted pitch changes): say "for a new station", never "for any question". Say "everyone who taps in", never "everyone". Same three labels everywhere. Say "AI crowd" or "synthetic", never "real people", for the panel.

If asked for a single sponsor line each (use in the close or Q&A):
- Flashpoint: "Flashpoint grounds each crowd in census data for that station, and runs it."
- Anthropic: "Claude in named roles: coach (Opus), predictor and trust card (Sonnet), skeptic explanations. The planner, auditor, skeptic test and all arithmetic are plain code."
- Pioneering Minds: "Cheap research that is fair: small groups get it, and it tells them when not to trust it."

---

## 2. Two-minute live demo click path

Before you start: page open on the recorded run, badge visible. Say the badge out loud: "This is our recorded run from [time]" (or "live" only if it is truly live).
A replay is never called live.

| Time | Click / screen | Say |
|---|---|---|
| 0:00-0:20 | **Trust card** (first thing on the page). Point at the label, the icon + word, the one-line reason. | "This is the answer a tenant group or corner shop gets. One station, one label: [trust it / double-check it / ask real people]. Reason: [read the line]." |
| 0:20-0:35 | Same card: if verdict is "ask real people", point at the drafted question and "Stopped for a human. Nothing was bought." | "It wrote the question and stopped. A person decides." (If the verdict is another label, say: "When it says ask real people, it stops here.") |
| 0:35-0:45 | Click **Show the work**. Point at the closing number: predicted-range hit count. | "Four locked stations. The agent predicted its own error band first. It landed inside on [__] of 4." |
| 0:45-1:10 | **Rules**: kept cards, then thrown-out cards struck through. | "The coach wrote [__] rules. The skeptic kept [__] and threw out [__]. A rule stays only if it holds at three stations and beats the simple average fix." |
| 1:10-1:30 | **Auditor findings**: Columbus Day, "re-pulled / removed". | "The auditor caught Columbus Day in the answer key. About half a normal Monday. It removed it. We did not stage this. A general rule found it." |
| 1:30-1:50 | **Exam table**: predicted band vs real error, per station; point at SYNTHETIC / MEASURED badges. | "Each row: predicted range, real error, hit or miss. [Name one miss if there is one.] Every number says synthetic or measured." |
| 1:50-2:00 | **Trace** (expand, scroll briefly) and **cost line**. Limits footer. | "Every agent step is logged. Cost [$__], estimate. Limit: turnstiles count entries, not residents." |

Fallback lines (pick one, say it calmly, keep going on the recorded run):
- Live step fails: "That live step didn't come back. This is our recorded run from [time]. Same code, same screen."
- Page won't load: "The page isn't loading, so here is the backup video of the same run from [time]." (Phone video recorded 2:30-3:15; have it ready.)
- Never say a replay is live.

---

## 3. The 8 judging criteria: where each one is hit

Weights are not shown on the slides (UNVERIFIED). Storytelling is called a core criterion.

| Criterion | Sentence to say | Screen |
|---|---|---|
| Innovation | "The agent predicts how wrong the crowd will be on stations it has never seen, then gets graded." | Exam table (predicted band vs real error) |
| Theme alignment | "People say one thing and do another. Turnstiles count what everyone who taps in actually does." | Top of pitch; Friday 13 vs 19 contrast; exam table |
| Technical execution | "Planner, parallel workers, auditor, coach, skeptic. All arithmetic in code. Rules written down before any result." | Trace log; rules cards; preregistration file in repo |
| Functionality & completeness | "One working path from question to label, with a recorded backup." | Trust card -> Show the work, end to end |
| User experience & accessibility | "Every status is a word plus an icon, never color alone. Plain labels." | Trust card; badges; status words |
| Potential impact | "A tenant group or corner shop that cannot hire researchers gets a label and a drafted question." | Trust card; "ask real people" draft |
| Feasibility & sustainability | "One run costs about [$__], from our call counter. Public repo, free MTA data, one command." | Cost line; README |
| Storytelling & presentation | "Open with the tenant group. Intern analogy. One honest line about what did not work." | Pitch opening and honest-miss line |

---

## 4. Top 10 hard judge questions (honest 1-2 sentence answers)

1. **"Twelve stations is curve-fitting."**
   "Agreed, it is a small sample, so we call it a method demo, not a finished calibration. That is why four stations were locked as an exam, rules had to hold at three or more stations, and we show a simple average fix beside ours."

2. **"Turnstile entries are not residents."**
   "True. Entries include visitors and miss fare evasion. We chose morning hours and mostly residential stations, and the limit is printed on the screen. The question we grade is 'who taps in here', not 'who lives here'."

3. **"Isn't a synthetic panel just AI stereotypes?"**
   "Possibly, and that is exactly what we measure. The grade shows where the crowd matches the turnstiles and where it does not."

4. **"Why survey something you can measure?"**
   "Because turnstiles are the answer key. Where we have a key, we learn how far to trust the crowd, and the label carries over to a new station where there is no key. We do not claim it carries to any question."

5. **"Demographics are county-level, but neighborhoods differ."**
   "Right, a coarse description of the area can blur a station's neighborhood. [Fill in what level Flashpoint's demographics tool actually returned for our stations; UNVERIFIED until checked.] Our station-to-area match is an estimate, labeled that way, and the receipts are saved."

6. **"What if the coaching didn't help?"**
   "Then the screen says so, and the project still works. The trust label and the predicted error band do not depend on coaching helping. Knowing the crowd is off by too much is the useful answer."

7. **"What does a run cost?"**
   "About [$__] for the full run, an estimate from our own call counter. Cheap models do the bulk work, the larger model only the hard step."

8. **"How does it keep running after today?"**
   "The repo is public, the MTA data is free, and it runs from one command with an API key from the environment. Flashpoint access and costs after today are UNVERIFIED; we would check before promising anything."

9. **"You downloaded the exam data with the rest. How do we know you didn't peek?"**
   "The exam answer file existed on disk, but the code only reads it at the exam step, once, with no retakes. We wrote the rules and cutoffs at 11:16 AM and printed a fingerprint of the exam split (starts 685b897c9c4f6b9a) before panels finished. The repo is public, so you can check the order. We cannot prove more than that."

10. **"Is this financial advice?"**
    "No. It grades how far to trust an AI survey crowd about subway mornings. It does not predict markets or tell anyone what to buy."

Bonus, if asked "Did you write this yourself?": "I directed it, used Claude Code, and checked the results. The README says exactly how AI tools were used and what I did myself."

---

## 5. LinkedIn / X post, 3 lines (DRAFT ONLY, Jayden posts it himself)

> We asked an AI crowd which weekday mornings New Yorkers ride the subway, then graded it against MTA turnstile counts. Before the final exam, our agent predicted how wrong the crowd would be on 4 locked stations, and landed inside its range on [__] of 4.
> The result is a plain label for a new station: trust it, double-check it, or ask real people. Built at Hack the Unreachable with Flashpoint.AI and Anthropic's Claude.
> Repo: [link, after Jayden makes it public] #HackTheUnreachable

Check before posting: the blank is filled from the run, the repo is public by Jayden's click, tags and sponsor names are what Jayden wants.

---

## 6. Fill-in checklist (read from the saved run, about 3:00 PM)

- [ ] Hit count: `[__]` of 4 (the headline).
- [ ] Coaching helped or not (pick the matching honest-miss line).
- [ ] Rules kept / thrown out counts (demo only).
- [ ] Cost `[$__]` and its label ESTIMATE.
- [ ] Which trust label the card shows, and the run time for the "recorded at" line.
- [ ] What level of demographics Flashpoint returned (Q5).
- [ ] Backup video recorded; rehearsed three times with a timer.
