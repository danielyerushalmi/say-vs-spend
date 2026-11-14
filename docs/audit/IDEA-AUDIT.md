# Idea and story audit: Say vs. Spend (judge's view, 2026-11-14 ~12:45 ET)

Scope: the IDEA and the STORY, not the code. Stats problems are in `docs/RED-TEAM.md`; this file does not repeat them except where they change the story.
Numbers come from `frontend/runs/say_latest.json` and `say/panels/followup.json` unless marked. Keyword counts in the WHY answers are mine (simple substring count over the 30 answers per brand, run at 12:32 ET); they are rough and EXPLORATORY.

Judging context (from `../JUDGES-AND-CRITERIA-FROM-SLIDES.md`, photos of the slides): 8 criteria, **Storytelling & Presentation highlighted as core**. Panel is mostly engineers (eBay, Zillow, Meta), a Fordham program director, a UN innovation head, and a co-founder whose company is UNVERIFIED. Event goal (Eventbrite): "build AI agents that uncover what people really think" with Flashpoint + Anthropic.

---

## 1. The one sentence a judge will remember

**Recommended:** "Two AI crowds agreed with each other at 0.89, and with real revenue at 0.03. Consistent is not correct."

Why this beats the current headline:
- The current headline is a question: "Did the AI crowd understand shoppers, or just pick the famous brands?" Questions are not remembered; answers are.
- Worse, the honest answer to that question is "neither, mostly." The crowd's *buying* ranking did not follow its own *fame* ranking either (my quick calc: intent rank vs crowd fame rank ≈ 0.52 on 6 brands, EXPLORATORY). So the "or just pick famous brands" half sets up a story the data does not tell. A sharp judge will ask "so did it pick the famous ones?" and you'll have to say "not really."
- The 0.89 vs 0.03 contrast is the real surprise, and it carries the key insight: the miss **repeats**. It is bias, not noise. Running more AI shoppers will not fix it.

Three headline options, each only on real numbers:
1. **"Consistent is not correct."** Two AI crowds of 200: 0.89 agreement with each other; 0.03 and -0.20 with real revenue. (Best. Use as the slide title and the last line.)
2. **"The AI shoppers' favorite was ThredUp. By revenue it's 5th of 6."** (Most concrete. Use as the reveal moment, not the headline.)
3. **"Before you spend on what an AI focus group says, check it against the money. Ours failed, and our tool said so."** (Best for the user/impact angle. Use in README subtitle.)

Keep the title "Say vs. Spend." It is good. The ThredUp WHY answers make it even better (see section 4, minute 2): the AI shoppers sound like what survey people *say* (saving money, sustainability), not what they spend.

## 2. Who the user is, and theme fit

**User, one line:** "Anyone about to spend money because a synthetic panel said so: a small online brand, a startup founder, or the panel company itself."

Name the store owner in the pitch, but know the strongest user for THIS room is the synthetic-panel maker and its buyers. Say it as: "a fact-check you run on an AI focus group before you trust it." Flashpoint's own metadata labels these personas "gpt-5.4-mini, uncalibrated" (run file `panel.persona_model_note`). That is your bridge: "A calibrated panel might pass. This is the test that would show it."

**The hole a judge will find in the user story:** a small store has no public revenue for *its own* brand, so it cannot run this test on itself. Your answer must be ready: "You don't test it on your brand. You test the crowd on public brands in your category, where the answer is known, like checking a thermometer in ice water before you use it. We did that for online retail. For buying intent, it failed." Say this unprompted in the pitch; it turns the weakness into the method.

**Theme fit ("Hack the Unreachable"):** not obvious from the current pitch. Never say the word "unreachable" now. One line:
> "AI shoppers are a shortcut to people you can't afford to reach. We built the check that tells you when the shortcut actually reaches them, and when it's just an echo. When it fails, it tells you to go ask the real ones."

## 3. The 5 weakest points a judge will poke, and the best honest answer

**1. "Six brands is an anecdote."**
Answer: "Yes. Six is all that passed our 'sells mainly online' rule in time, and we locked the set before seeing results. With 6 brands our rule can only say 'Trust it' for a perfect ranking, so it's deliberately cautious. But the miss was not close: 0.03 in one crowd, -0.20 in a second crowd. The tool is the product; this is its first run."
Do NOT claim the result generalizes to AI panels. Say "this crowd, this question, these 6 brands."

**2. "Revenue isn't 'likely to buy'. Hims makes more per customer."**
Answer: "Right. Revenue is how many people buy times how much they spend. Our question measures the first part. We say that limit on screen. And the follow-up panel hints at why: when the AI shoppers explained Revolve, 20 of 30 mentioned price. Revolve's real revenue comes from fewer, bigger spenders. The AI crowd answers like an average, price-careful shopper." (Count: mine, EXPLORATORY; the answers are AI-generated.)

**3. "Where is the AI agent? This is a correlation in a spreadsheet."**
Answer: show the loop, with its own timestamps from `followup_loop.trace`: 12:24:30 the agent found the 3 biggest gaps and drafted a WHY question; 12:26:17 Flashpoint built 30 new personas; 12:26:38 they answered; 12:29:11 raw answers saved. Then it drafted the one question for real people and stopped. "The agent's job is to know when not to trust itself."
Prep: if the agent loop is not visible on the page, this answer is weak. See addition A.

**4. "Isn't 'LLM survey answers are biased' already known? What's new?"**
Answer: "What's new is that it's a guardrail, not a paper. The rule was written before results and committed at 11:47. Code sets the label, not a model. The tool checks the crowd against public money, explains the miss with a follow-up panel, drafts one question for humans, and stops." Don't cite studies you haven't read; none are in the repo.

**5. "Flashpoint is a sponsor. Are you saying their product doesn't work?"**
Answer: "No. This crowd, on this question, on 6 brands, did not earn trust today. The awareness answers lined up with revenue better (0.72, exploratory). Flashpoint is what made the test possible: two 200-person crowds and a follow-up panel in minutes. Every panel maker needs a test like this, and a calibrated panel might pass it."

## 4. The 3-minute demo, minute by minute

Rule: one number per beat. Every other number waits for Q&A.

| Time | Show | Say (short) |
|---|---|---|
| 0:00-0:20 | Title: "Say vs. Spend" + "Consistent is not correct." | "AI focus groups are cheap. Nobody tells you whether to believe one. We built the check." |
| 0:20-0:50 | Page: the 6 brands, the persona wall (200 AI shoppers), the answer key column (SEC revenue). | "200 AI shoppers from Flashpoint rated 6 online companies. The answer key is real yearly revenue from SEC filings. We wrote our pass/fail rule before any result: committed 11:47." |
| 0:50-1:25 | The rank table: ThredUp crowd #1 vs revenue #5. Then the big number 0.03 and the label **Ask real people** (word + icon, not color only). | "The AI shoppers' favorite was ThredUp. By revenue it's 5th of 6. Their buying ranking matched revenue at 0.03. Basically none." |
| 1:25-1:55 | Repeat run side by side. | "Fluke? We ran a second crowd of 200. The two agreed at 0.89. No brand moved more than one place. Against revenue: -0.20. Consistent is not correct. More AI shoppers won't fix it." |
| 1:55-2:30 | Agent loop timeline (trace times) + 2 WHY quotes. | "So the agent asked why. It built 30 new AI shoppers and asked about the biggest misses. On ThredUp they talk about saving money and sustainability. On Revolve, 20 of 30 talk about price. They sound like what people *say* in surveys, not where people spend." |
| 2:30-3:00 | The trust card: draft question + "Stopped for a human." | "Then it does the one thing it should: drafts one question for real shoppers and stops. Who's it for: anyone about to spend money because an AI panel said so. Test the crowd where the answer is public, before you trust it where it isn't." |

**Cut from the 3 minutes** (keep for Q&A): website score 0.77 (not pre-registered, fragile: 0.54 in crowd 2); Wikipedia 0.90 (added after results, 5 brands); buyers-only view; cost line; 129 tests; recount; the FIGS/CarParts sensitivity view; "try your store." The 12:10 rule change: do not mention unless asked, then answer exactly as `PITCH-SAY.md` says.

If Q&A asks "what WOULD have predicted revenue?": "Free public fame data. Wikipedia page views tracked revenue at 0.90 on 5 brands. We added that after results, so it's exploratory. But it says a free signal beat the AI crowd here."

## 5. Three additions that would most raise the score (45 minutes, by agents)

Freeze for new features is 2:15 PM (decisions.md 12:24). All three fit before that.

**A. Agent-loop timeline + "Why did it miss?" on the page (highest value: Innovation, Theme, Storytelling).** ~35 min, Daniel's frontend agent.
- Read `followup_loop.trace` from the run file; show 5 steps as a vertical timeline with the real timestamps and the Flashpoint survey/panel ids.
- Under each of the 3 gap brands, show 2 verbatim answers from `say/panels/followup.json`, labeled "SYNTHETIC, AI-generated".
- Add one code-computed line per brand: a theme count from the 30 answers. My rough counts (EXPLORATORY, substring match): ThredUp "return" 19/30, "sustainab" 10/30, "cautious" 11/30; Revolve "price" 20/30, "return" 18/30; Hims "prescription" 11/30, "privacy" 8/30. Have a small script compute these and write them to the run file so the page doesn't hard-code them. Label "keyword count, not a theme model."
- Why: it makes the "AI agent" visible and directly serves "uncover what people really think." Today the follow-up panel exists only in a JSON field.

**B. Tag every number PRE-REGISTERED or EXPLORATORY, and swap the bootstrap "could be chance" flag for an exact test.** ~25 min, Jayden's session. This is RED-TEAM.md fixes 1 and 4. Engineers on the panel will respect "with 6 brands we used an exact permutation test" and the tags pre-empt the "how many numbers did you try?" attack. Verdict does not change.

**C. A "Should I trust an AI panel for this?" card for the user (Impact, Feasibility, UX).** ~15 min, copy + a small page block, any agent.
- Three rows, word + icon: "Which brand will sell more? → Don't trust it (failed, 2 crowds)." "Have shoppers heard of us? → Double-check (lined up better, exploratory)." "Why might shoppers hesitate? → Use as ideas to test, not as answers."
- Plus one line on feasibility: "One run = one Flashpoint panel + SEC data (free) + plain Python. Re-run on any category with public companies."
- Why: right now the page answers "did it match?" but not "what should I do?" That is the Potential Impact criterion.

Not recommended: active-customer counts as a second answer key (another test picked after results; definitions differ by company), and a live poll of people in the room (asks strangers about Hims; tiny skewed sample; Jayden would have to approve collecting it).

## 6. Overclaims and wording that could read as dishonest: exact fixes

| Where | Now | Problem | Change to |
|---|---|---|---|
| `PITCH-SAY.md` line 9, `README.md` line 17 | "A real focus group costs thousands." / "can't pay thousands" | No source in the repo. UNVERIFIED number in front of judges. | "Real research with real people costs real money and time." |
| `PITCH-SAY.md` line 9, `README.md` line 5 | "An AI focus group is almost free." | Flashpoint charge is UNVERIFIED (run file `cost.flashpoint_note`). | "An AI focus group is fast and cheap." |
| Run file `trust_card.note`, `README.md` line 41 and 69, pitch line 27 | "Drafted by the agent." / "The agent drafts one question" | In the recorded run it is a code template (0 model calls). Judges hear "agent" as an AI model. | "Drafted by our code from the biggest miss." |
| Same places | "Nothing was bought." | In a shopping demo this reads as "no shopper bought anything." Confusing. | "Stopped for a human. No real people were surveyed or paid." |
| Pitch line 23, README | "a second, separate crowd" | Both crowds come from the same tool and the same underlying model, so "separate" suggests more independence than there is. The 0.89 shows the bias repeats; it does not show two independent sources agree. | "a second panel of 200 new AI shoppers from the same tool." |
| Pitch line 29 | "A separate script recounted every number from the raw file: 0 mismatches." | Both counts share one Yes/No code book (RED-TEAM finding 8). | "A second script, written separately, recounted every number from the raw file: 0 mismatches." (Keep for Q&A only.) |
| Run file `headline` | "Did the AI crowd understand shoppers, or just pick the famous brands?" | Sets up an answer the data doesn't give (see section 1). | "Two AI crowds agreed with each other. Neither agreed with the money." |
| Pitch line 15 | "Where the money actually goes." | Revenue is worldwide, includes wholesale, and fiscal years differ. | "each company's total yearly revenue." |
| Any slide | "AI crowds don't understand shoppers" (if anyone says it) | Generalizes from 6 brands and one model. | "This AI crowd, on buying intent, on 6 brands, did not earn trust." |
| Pitch, if asked about the rule | "We never changed the rule." | False. | Keep `PITCH-SAY.md`'s line: "We changed it once, at 12:09, before any statistic. It made 'Trust it' harder to get." |

One more honesty point to say out loud if asked: the brand-set inclusion rule was frozen at 12:24, three minutes AFTER the first statistic (12:21). `decisions.md` logs this. The set did not change after (FIGS and CarParts kept out). Say it before a judge finds it.

## What I'm unsure about
- Whether the page currently shows the repeat run, the persona wall, or the trace: I did not open Daniel's frontend.
- My keyword counts are substring matches on AI-generated text; good enough for a talking point, not a finding.
- Judge affiliations beyond the slide photo are UNVERIFIED.
