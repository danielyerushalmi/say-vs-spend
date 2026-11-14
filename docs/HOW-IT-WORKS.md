# How Crowd Coach works

> SUPERSEDED: this is our earlier Crowd Coach prototype from the morning. For Say vs. Spend, see `README.md` and `docs/PITCH-SAY.md`.

Same idea as the README, with a bit more detail. Source of truth is the code; see `agent/CONTRACT.md`.

## The question

"In a typical week, which weekday mornings (6-10 AM) do you ride the subway from your home station? Select all: Mon, Tue, Wed, Thu, Fri, None." (`agent/config/stations.json`)

The panel's answers become **shares**: the fraction of Mon-Fri selections that fall on each day. The MTA data gives the same five shares from real entries. The **gap** is the average absolute difference over the five days, in percentage points.

## Stages (`agent/run.py`)

1. **Plan.** Load 12 stations and the locked train/exam split.
2. **Answer key.** Pull MTA entries (dataset `5wq4-mkjj`, 6-10 AM, Oct 5-30 2026). Cached.
3. **Auditor.** Code checks for holidays, missing days, unequal weekday counts, and days far below a station's usual. Only real catches are logged.
4. **Panels.** Read the saved Flashpoint panel for each station. Compute each panel's noise bar.
5. **Coach and skeptic.** The coach proposes a rule: a condition (for example, a demographic feature above a value) and a direction. Code fits the size of the adjustment. The skeptic (code) keeps a rule only if it matches at least 3 training stations, improves at least 3 in leave-one-out, and beats the dumb fix. A model then explains each verdict in one sentence, using numbers from code. Up to 2 rounds.
6. **Predict.** Before the exam, the agent writes an expected error band per exam station (ESTIMATE).
7. **Exam.** Kept rules are applied once to the 4 locked stations.
8. **Trust card.** Pre-registered cutoffs turn the exam error into a label. For "Ask real people" a draft question is written and the run stops for a human.

## Terms

- **Leave-one-out:** fit a rule on all training stations except one, test it on the one left out, repeat for each.
- **Dumb fix:** add the average (measured minus panel) error per day to every station. If a clever rule cannot beat it, the cleverness is not earning anything.
- **Pre-registration:** writing down the test and the cutoffs before seeing results, so we cannot adjust them afterward.
- **Noise bar:** how much a panel's shares would move by chance alone.

## Safety switches

A call limit stops model calls (default 60). With no API key, model steps fall back or are skipped. `--no-llm` runs code only. Nothing is purchased; Flashpoint payment tools are never called.

## Status

`docs/CROWD-COACH.md` is the original plan. `docs/QUESTION-CHANGE.md` is superseded: the weekday question stayed.
