# Say vs. Spend: spoken pitch

Every number below comes from `frontend/runs/say_latest.json`, except the recount (0 mismatches, from `say/audit/RECOUNT.md`) and commit times (git history). Exact p-values marked * are stored in the run file (`fame_wiki.agreement.p_exact`, `repeat_run.agreement.*.p_exact`). Only the buying ranking vs. revenue was pre-registered; every other score is EXPLORATORY. Read numbers off the screen, not from memory. Say "AI crowd" or "AI shoppers," never "people." Say "revenue," never "website sales." Each number has its label in brackets; the label is shown on screen, you don't need to read it aloud unless asked.

---

## The 2-minute version (about 316 words)

> We tested an AI focus group against real money, using a rule we committed before computing any result. The result: the AI crowd's buying ranking matched real revenue at **0.03** [SYNTHETIC vs. MEASURED]. That's basically zero. So our tool says: **Ask real people.**
>
> A small online store wants to know what shoppers think. A real focus group costs thousands. An AI focus group is almost free. But nobody tells the owner whether to believe it.
>
> So we tested one where we already know the answer. Using Flashpoint, we built a crowd of **200** [SYNTHETIC] AI shoppers. They rated **6** public companies that sell mainly online. Then we checked the answer key: each company's real yearly revenue, from the SEC's data.
>
> At 11:47, before any result, we committed one test to GitHub: if the crowd's buying ranking matches revenue well, trust it. If not, ask real people. At 12:10, still before any statistic, we made it stricter: it must match well even at the unlucky end of its range.
>
> The miss holds up. A second panel of 200 different personas from the same persona model also missed: **-0.20** [SYNTHETIC vs. MEASURED, EXPLORATORY]. With two more brands added: **-0.14** [EXPLORATORY].
>
> The biggest miss: **ThredUp**. The crowd ranked it **number 1** [SYNTHETIC]. By revenue it's **number 5** [MEASURED].
>
> Two limits, said plainly: with only 6 brands, "Trust it" needs a near-perfect ranking, and revenue measures how big a business is, not how many people buy.
>
> Everything else we computed is exploratory. Fame alone, just "have you heard of it," scored **0.72** [SYNTHETIC vs. MEASURED, EXPLORATORY], and even that could be chance. So the crowd did not beat fame.
>
> Then the tool drafts one question for real shoppers. Claude wrote the words [AI-generated]; our code picked the brand and set the label. And it stops. "Stopped for a human. Nothing was bought."
>
> Cheap research is only fair if you know how far to trust it. Now you can check.

Trims if short on time, in order: cut the 8-brand -0.14, then "That's basically zero." Never cut the limits sentence. If a judge asks about checks: "A separate script recounted every number from the raw file: 0 mismatches."

---

## The 30-second version (about 70 words)

> Using a rule we committed before any results, we tested an AI focus group against real money. **200** [SYNTHETIC] AI shoppers ranked **6** online companies; we checked against real revenue from SEC data. Their buying ranking matched revenue at **0.03** [SYNTHETIC vs. MEASURED]. A second panel from the same persona model: **-0.20** [EXPLORATORY]. Label: **Ask real people.** Limits: only 6 brands, and revenue measures business size, not how many people buy.

---

## Numbers on one card (all from the run file)

| Say | Number | Label |
|---|---|---|
| AI shoppers, main crowd | 200 | SYNTHETIC |
| Brands | 6 | (12 checked, 6 passed) |
| Buying ranking vs. revenue (PRE-REGISTERED) | 0.03 (exact p = 1.00; range -0.94 to 0.64) | SYNTHETIC vs. MEASURED |
| Fame ("heard of it") vs. revenue | 0.72 (exact p = 0.11; range 0.00 to 1.00); could be chance | SYNTHETIC vs. MEASURED, EXPLORATORY |
| Wikipedia fame vs. revenue, 5 brands, added 12:24, BARK = BarkBox article | 0.90 (exact p = 0.08 *; range 0.25 to 1.00); could be chance | MEASURED vs. MEASURED, EXPLORATORY |
| Website score vs. revenue | 0.77 (exact p = 0.10; range 0.09 to 1.00); could be chance | SYNTHETIC vs. MEASURED, EXPLORATORY |
| Second panel (200 different personas, same persona model) agrees with first (buying ranks) | 0.89; no brand moved more than 1 place | SYNTHETIC vs. SYNTHETIC, EXPLORATORY |
| Second panel's buying vs. revenue | -0.20 (exact p = 0.71 *; range -0.80 to 0.82) | SYNTHETIC vs. MEASURED, EXPLORATORY |
| 8 brands (FIGS, CarParts.com added after results): buying vs. revenue | -0.14 (range -0.78 to 0.54); label unchanged | run file `extras.sensitivity`, EXPLORATORY |
| Biggest miss | ThredUp: crowd #1, revenue #5 | SYNTHETIC vs. MEASURED |
| Label | Ask real people | set by code |
| Draft question (about ThredUp, picked by code) | "When shopping online for clothing, shoes or accessories, how do you feel about buying used items instead of new ones?" | AI-generated (Claude, `claude-sonnet-5-5`; run file `trust_card.draft_question_source`) |
| Recount mismatches | 0 | from `say/audit/RECOUNT.md` |
| Model cost of the recorded run | about $0.04, 6 calls | ESTIMATE |

## Things not to say

- Don't say the website score "won." It was not the pre-registered test, its exact p is 0.10 (could be chance), its averages all sit between 6.0 and 6.5 [SYNTHETIC], and it fell to 0.54 in the second panel.
- Don't headline the website 0.77 or Wikipedia 0.90. Both are EXPLORATORY.
- Don't call the second panel "independent" or "separate." Say: "a second panel of 200 different personas from the same persona model."
- Don't imply any label is easy to reach. With 6 brands, "Trust it" needs a near-perfect ranking.
- Don't say the AI crowd wrote the draft question, or that a model picked the brand or the label. Claude wrote the words [AI-generated]; code picked the brand and set the label.
- Don't say the rule was never changed. Say: "We changed it once, at about 12:10, before any statistic. The change made 'Trust it' harder to get. The 13:30 perception rule in the store-owner tool came after results, so it's labeled exploratory and never applies to buying."
- Don't name stock tickers or say anything about investing.
- Don't say Flashpoint is bad. Say: "This crowd, on these 6 brands, today, did not earn trust."
