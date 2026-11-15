# Crowd Check

**A tool that tests whether an AI focus group can be trusted, by checking it first against an answer that is already known.**

Every small business wants to know what customers will actually buy. AI shoppers can answer in minutes, for almost nothing. Crowd Check tells you if you can bet your money on those answers.

**Study 1: Say vs. Spend.** Did 200 AI shoppers rank 6 online brands the way real money ranks them?

<p align="center">
  <img alt="Built at Hack the Unreachable 2026" src="https://img.shields.io/badge/built%20at-Hack%20the%20Unreachable%202026-0b2a3c">
  <img alt="Python 3, standard library only" src="https://img.shields.io/badge/python-3%20%C2%B7%20standard%20library%20only-1f4e5f">
  <img alt="253 tests passing on Nov 14, 2026" src="https://img.shields.io/badge/tests%20(Nov%2014)-253%20passing-2e7d5b">
  <img alt="Data: SEC EDGAR and Flashpoint" src="https://img.shields.io/badge/data-SEC%20EDGAR%20%2B%20Flashpoint-e8735a">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-555555">
</p>

Built in one day by Jayden Ling and Daniel Yerushalmi at the Hack the Unreachable AI Hackathon, Fordham University, November 14, 2026. It did not place. We are continuing it.

## The result

**The AI crowd is consistent, but not calibrated.**

- **Buying intent vs. real revenue: 0.03** (range -0.94 to 0.64, exact p = 1.00). A rule written before any result turns that into one label: **Ask real people.**
- **Fame did better: 0.72.** The crowd's "have you heard of it?" ranking matched revenue more closely than its "would you buy?" ranking (EXPLORATORY, could be chance).
- **A second AI panel agreed with the first at 0.89**, but its own buying score vs. revenue was **-0.20** (EXPLORATORY). Consistent is not the same as right.
- **Biggest miss: ThredUp.** The crowd ranked it #1 for buying. By revenue it is #5 of 6.

<p align="center">
  <img src="docs/images/scores.png" width="900" alt="Chart of five match scores against real revenue, each with its luck range. AI crowd 1 would-buy: 0.03, range -0.94 to 0.64 (the pre-registered test). AI crowd 2 would-buy: -0.20. Fame from the AI crowd: 0.72. Website score: 0.77. Wikipedia page views: 0.90. Dashed lines mark the 0.4 and 0.7 label cutoffs. A bar at the bottom says two AI crowds agree with each other at 0.89, but neither matches the money.">
</p>

The score is Spearman rank agreement: 1 = same order as revenue, 0 = no link, -1 = reversed. With only 6 brands, our finding is "this crowd did not earn trust here," not "AI crowds never work." Full table, every p-value and the timeline: [docs/METHODS-CARD.md](docs/METHODS-CARD.md).

## Live demo

**https://project-dy517.vercel.app**

The live page may lag behind this repo, and may still use the old "Say vs. Spend" name.

## How it works

<p align="center">
  <img src="docs/images/how-it-works.png" width="900" alt="Three steps. 1, The crowd says: 200 Flashpoint AI shoppers rate each brand (SYNTHETIC). 2, The money says: each company's SEC filing gives its real yearly revenue (MEASURED). 3, Code decides the trust: a rule written before any result turns the match into one label (COMPUTED).">
</p>

1. **The crowd says.** One Flashpoint synthetic panel of 200 AI shoppers rated each brand: heard of it, website quality, how likely to buy. Brand order was shuffled for each shopper.
2. **The money says.** Each company's yearly revenue comes from its SEC filing (the SEC's free data API). That is the answer key.
3. **Code decides the trust.** Plain Python ranks the brands, computes the scores, and picks the label from a rule written before any result. A model may write an explaining sentence. It never sets a number or the label.

Every number carries one of these labels:

- **MEASURED**: real public data (SEC revenue, Wikipedia page views).
- **SYNTHETIC**: from the AI crowd.
- **AI-generated**: text written by a model.
- **ESTIMATE**: our own rough number (for example, cost).
- **EXPLORATORY**: computed, but not part of the pre-registered test.

More detail: [docs/METHODS-CARD.md](docs/METHODS-CARD.md) and the original plan, [docs/SAY-VS-SPEND.md](docs/SAY-VS-SPEND.md).

## How to run it

You need Python 3 (we used 3.14). No installs: standard library only.

**Open the page.** From the repo root:

```bash
python3 frontend/server.py
```

Then open http://127.0.0.1:3001. It works with no key. To make the chat work, set `ANTHROPIC_API_KEY` in your terminal first (for example `read -s ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY`). Never put a key in a file. The chat is capped at 20 calls (`SAY_CHAT_MAX_CALLS`).

**Run the tests** (no key, no internet):

```bash
python3 -m unittest discover -s say/tests -t .
```

**Rebuild the results from the saved survey files**, with no model calls. Both `--run-dir` and `--panel-out` point at a scratch folder, so the saved run in the repo is not overwritten:

```bash
mkdir -p /tmp/say-check
python3 -m say.run --export say/panels/q4_export.csv --panel-id 01a1db0a-5b35-7f4a-956d-79e1585ada17 --recorded-at 2026-11-14T12:17:00-05:00 --expect-n 200 --extras --repeat-export say/panels/main_export.csv --repeat-panel-id 01a1dafd-97a0-7330-b505-be47f17f8705 --repeat-recorded-at 2026-11-14T12:02:10-05:00 --wiki-fame say/fame/wikipedia_pageviews.json --followup say/panels/followup.json --followup-trace say/panels/followup_trace.json --persona-model-note "Flashpoint metadata: answers generated by gpt-5.4-mini, uncalibrated" --no-llm --run-dir /tmp/say-check --panel-out /tmp/say-check/main_run.json
```

Then recount every number with the separate recount script: `python3 -I say/audit/recount.py`. A `--no-llm` rebuild gives the same numbers and label; the AI-generated text is replaced by code templates or left empty. Reproducibility check: [docs/audit/REPRO-AUDIT.md](docs/audit/REPRO-AUDIT.md).

No server? Open `docs/report/index.html` in a browser: an offline page with every number, its label and its source.

## Limits

- **Only 6 brands.** That is why the ranges are so wide. Even fame's range reaches 0.
- **One pre-registered test.** Only buying vs. revenue (and "did it beat fame?") was written down before results. Everything else is EXPLORATORY.
- **The AI shoppers are synthetic and uncalibrated.** Flashpoint's own metadata says the answers were generated by "gpt-5.4-mini" and marked "uncalibrated." Both panels come from that same persona model.
- **One category.** Public companies that sell mainly online. Not a random sample.
- **Revenue measures business size, not how many people buy.** It is total revenue (wholesale and worldwide included), not website-only sales.
- **Saying isn't buying.** The crowd's answers are stated opinions. Only revenue is real spending.
- **Fiscal years differ** between companies (FY2025 and FY2026).

Full list: [docs/METHODS-CARD.md](docs/METHODS-CARD.md) and [docs/RED-TEAM.md](docs/RED-TEAM.md).

**Not investment advice.** This tests a survey method. It says nothing about whether any company is a good investment.

## What's next

- **More brands**, picked by a rule before any survey.
- **Real-people checks** on the same questions ([docs/REAL-PEOPLE-KIT.md](docs/REAL-PEOPLE-KIT.md)). If real people also miss revenue, the problem is the answer key, not the AI crowd.
- **New pre-registered tests** as new studies. The Nov 14 result is frozen: we add new tests, we never edit that one.

## How AI tools were used, and what we did

- **Claude Code** (Anthropic) wrote most of the code under Jayden's direction, including the tests and the recount script. Jayden reviewed its work and the team ran the checks.
- **Jayden** chose the idea, set the trust rule and the brand rules, and made each decision in the decisions log. He directed Claude Code to build the analysis engine in `say/`.
- **Daniel** built the web page (landing page, desk, "Grade my website" tab, website report card), set up the team relay between our two Claude Code sessions, and merged each piece into main.
- **Flashpoint.AI** provided the synthetic personas (the AI crowd) and their answers.
- **Claude** (`claude-sonnet-5-5`) writes some explaining sentences inside the product. In the recorded run it wrote the reason sentence, the draft question for real people and three WHY summaries (6 calls, about $0.04 ESTIMATE). It never sets a number or the label.
- **Plain code** does all counting, ranking and statistics, and picks the label.

Commit-by-commit history: [docs/DEV-HISTORY.md](docs/DEV-HISTORY.md).

## Credits

Flashpoint.AI for the AI shopper panel. Anthropic for Claude and Claude Code. The organizers of Hack the Unreachable at Fordham. SEC EDGAR and Wikimedia for free public data.

## License

MIT. See [LICENSE](LICENSE).
