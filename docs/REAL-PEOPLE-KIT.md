# Real people check: one-page kit

Our tool's verdict on the AI crowd was **Ask real people**. This kit is how two students do that, by hand, at the venue,
for free. With 10 to 20 people this is a **demo of closing the loop, not a result.**

## 1. Print today's exact question (do this first)

The question comes from the run file, not from this page. Run:

```
python3 -m say.real_check --print-script --run frontend/runs/say_latest.json
```

It prints `trust_card.draft_question` word for word, plus the same yes/no item for every brand.
As of run `say-2026-11-14T12-17` it printed (re-run it; if it differs, the printout wins):

> When shopping online for clothing, shoes or accessories, how do you feel about buying used items instead of new ones?

AI-generated: Claude (`claude-sonnet-5-5`) wrote this question (run file `trust_card.draft_question_source`); our code picked the brand (ThredUp).
Heads-up: this question is open-ended, but the paper tally and the CSV below record only yes/no (`bought_12m`).
Decide how to record answers before you ask anyone.

## 2. Pick one mode before you start

| Mode | What you ask | Consent line (say it exactly) |
|---|---|---|
| **A. One question** (default) | Only the main question above | "It's for a student hackathon project, anonymous, one question, takes 10 seconds, OK?" |
| **B. All 6 brands** (if time allows) | Main question first, then the other 5 from the printout | "It's for a student hackathon project, anonymous, six quick yes/no questions, about 30 seconds, OK?" |

Mode B needs its own consent line. Saying "one question" and then asking six would be dishonest.
Mode A gives one share (ThredUp). Only Mode B can compare rankings with the AI crowd and with revenue.

## 3. How to ask

- Ask adults only. If someone says they are under 18, thank them and record nothing.
- Say the consent line. Anything other than a clear yes means stop, say thanks, record nothing.
- Read the question exactly as printed. Do not explain the brand or hint at an answer.
- Main question first, always (so the other brands do not change the answer).
- "Don't know", "skip" or a pause = leave that box blank. Never guess for them.
- Age band only if you ask and they agree: "under 25", "25-44" or "45+". Otherwise blank.
- Some brands are personal (Hims & Hers sells sexual-health and prescription products). Ask in a normal voice,
  not in front of a crowd, and accept "skip" without comment.

**Record NO names, NO contact info, NO photos, NO descriptions of the person.** Only a number (1, 2, 3 ...),
the yes/no answers, and the optional age band. The script refuses any file with a name, email or phone column.

## 4. Paper tally (one row per person)

| # | thredup (main) | hims | stitchfix | revolve | bark | petmeds | age band (optional) |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |
| 11 | | | | | | | |
| 12 | | | | | | | |
| 13 | | | | | | | |
| 14 | | | | | | | |
| 15 | | | | | | | |
| 16 | | | | | | | |
| 17 | | | | | | | |
| 18 | | | | | | | |
| 19 | | | | | | | |
| 20 | | | | | | | |

Write Y, N, or leave blank. Mode A: fill only the thredup column.

## 5. Type it in and score it

Make a CSV with exactly these columns, one line per person per answered brand (blank boxes: no line):

```
respondent_n,brand_id,bought_12m,age_band
1,thredup,no,under 25
1,hims,no,under 25
2,thredup,yes,
```

Then run:

```
python3 -m say.real_check --csv <your file> --run frontend/runs/say_latest.json --out <output json>
```

You get, per brand: the share who said yes, a 90% Wilson interval (the honest range for a small count),
and (Mode B only) how the real ranking matches the AI crowd's intent ranking and the revenue ranking
(Spearman, the same rank math as the main tool). Do not put the CSV of real answers in the public repo
unless both students agree; it has no personal data, but it is still other people's answers.

## 6. How to show it (and what not to claim)

Label every real number **"REAL (n=__, convenience sample)"**, with the n filled in.

Say this out loud: *"These are about 15 people who happened to be at a tech hackathon. They are not
representative of US shoppers. With this few people the ranges are wide and one answer can flip a ranking.
This shows the loop: our code flagged where the AI crowd was weak, Claude drafted the question, and real people answered it."*

Also true, and worth saying if asked: the AI crowd was asked about **intent** (likely to buy in the next
12 months, on a 1-10 scale). Real people here answer about **past purchases** (yes/no, last 12 months).
Those are related but not the same question.

Do not say "real people confirmed" or "real people disproved" anything. The tool's output says
`could_be_chance: true` when the range crosses zero; with ~15 people expect that.
