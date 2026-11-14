# Say vs. Spend: the 17 hardest judge questions

> Commit IDs in this file are from our development repo, which is private. This public repo is a one-commit clean copy; the full commit list with times is in `docs/DEV-HISTORY.md`.

Short, honest answers. Every number is from `frontend/runs/say_latest.json` unless another file is named. Exact p-values marked * are stored in the run file (`fame_wiki.agreement.p_exact`, `repeat_run.agreement.*.p_exact`). Only intent vs. revenue was pre-registered; every other score is EXPLORATORY. If you don't know, say "I don't know, here's how we'd find out."

---

**1. "Isn't 6 brands too few?" (statistician)**
Yes, for proving anything general. That's why we show a range and an exact p-value, not just a score. The buying score is 0.03 (exact p = 1.00), and its range runs from -0.94 to 0.64 [SYNTHETIC vs. MEASURED]. Our rule uses the low end, so with 6 brands "Trust it" needs a near-perfect ranking: a red-team probe found that swapping just the top two brands drops the label to "double-check it" (`docs/RED-TEAM.md`). That is cautious on purpose, and we did not change the rule after results. The label doesn't hang on the range either: the score itself, 0.03, is already under the 0.4 cutoff. And "exact p = 1.00" isn't a bug: with 6 brands no ordering can score closer to 0 than about ±0.03, so every possible ordering matches revenue at least as strongly as ours did. Our claim is narrow: this crowd did not earn trust on these 6 brands. We checked 12; only 6 passed our "sells mainly online" rule.

**2. "You changed the trust rule."**
Once, and it's in git. The rule was committed at 11:47 (commit `ff5b31a`). At 12:09 (commit `8ebf44a`, stamped 12:09:14; the rule text and log say 12:10) we switched the cutoffs from the single score to the low end of its range. One panel had finished, but we had only checked its row count. The first statistic appears at 12:21 (commit `6a6ee7f`). The change made "Trust it" harder to get, not easier. And the label is the same either way: the single score, 0.03, is also under 0.4. Separately, at 13:30 (after the results were known) we added one EXPLORATORY rule for the store-owner tool: website and fame questions get "Promising for perception, not proven" when the score vs. revenue and the agreement between two AI crowds are both at least 0.7. It never applies to buying, and the main result did not change.

**3. "You saw results before locking the brands."**
The 6 brands were committed at 12:01 (commit `1bdd084`), before any result existed. After the 12:21 results, a recheck found two more brands that pass (FIGS and CarParts.com). We kept them out on purpose, because adding brands after seeing results is exactly the cheat you're worried about. One more disclosure: we saw FIGS's revenue during an SEC data test before picking brands. FIGS is not in the main result.

**4. "Why trust SEC revenue as ground truth?"**
It's the best free, public, audited-by-law number for what customers actually paid a company. It comes straight from the SEC's data API, and each brand file links the filing. But it's not perfect: it's total revenue, not website-only sales, and business models differ (subscriptions, resale). Revenue also measures business size (customers x spend per customer), not how many people buy, so a crowd can be right about who shops and still miss revenue. So it's an answer key for ranking, not a perfect measure of shopper spending. We say that on the page.

**5. "Isn't this just a fancy correlation?"**
The math is a rank correlation (Spearman), yes. On purpose: simple math a judge can check. What's new is the wrapper: a rule written before results, a fame baseline the crowd must beat, a range and an exact p-value instead of one number, a second panel from the same persona model, an independent recount, and a label a store owner can act on. The product is the trust label, not the correlation.

**6. "Doesn't the AI just remember famous brands?"**
That's the question we tested. The pre-registered part: did the buying score beat fame? No. Fame alone ("heard of it") matched revenue at 0.72 (exact p = 0.11) [SYNTHETIC vs. MEASURED, EXPLORATORY]. The crowd's buying answer matched at 0.03. Outside fame, from Wikipedia page views, matched at 0.90 (exact p = 0.08 *) [MEASURED vs. MEASURED, EXPLORATORY]: 5 brands, added at 12:24 after the main result was seen, with BARK measured by the BarkBox article. Both fame lines beat the buying answer (on the same 5 brands, buying = 0.10 [SYNTHETIC vs. MEASURED, EXPLORATORY]; run file `fame_wiki.agreement.intent_same_brands_spearman`), so the conclusion does not depend on which fame line you pick. But with 6 brands, neither fame score clears p = 0.05, so they could be chance too.

**7. "Your website score hit 0.77. Why not lead with that?"**
Because it wasn't our pre-registered test, and picking the best-looking number after the fact is cherry-picking. Only intent vs. revenue was pre-registered; the run file holds 12 rank scores against revenue (counting the repeat panel and the 8-brand sensitivity), and the rest are EXPLORATORY. Its exact p is 0.10, so it could be chance. It's also fragile: all six website averages sit between 6.0 and 6.5 out of 10 [SYNTHETIC], so tiny differences decide the order. In the second panel it dropped to 0.54 (exact p = 0.30 *) [SYNTHETIC vs. MEASURED, EXPLORATORY].

**8. "Your two crowds agree at 0.89. Doesn't that prove the AI crowd works?"**
It proves it's consistent, not that it's right. The second panel is 200 different personas from the same persona model (gpt-5.4-mini), so the two panels can share the same blind spot. Both put ThredUp first for buying [SYNTHETIC], and both missed revenue: 0.03 and -0.20 (exact p = 0.71 *) [SYNTHETIC vs. MEASURED; the second panel is EXPLORATORY]. Consistent and wrong is the warning we want a store owner to see.

**9. "With a range that wide, did you learn anything?"**
Yes: we learned we can't trust this crowd for this job yet. That's the label's whole point. A wide range that includes 0 is an honest "we don't know," and our rule turns "we don't know" into "ask real people" instead of a false "trust it."

**10. "Your personas are uncalibrated and run on another company's model."**
Correct. Flashpoint's own metadata says "gpt-5.4-mini, uncalibrated." We report that. Our result is about this crowd on this day. It's not a verdict on Flashpoint or on all AI crowds. If a calibrated crowd scored better, our same test would show it.

**11. "Why 0.7 and 0.4? Why the 5th percentile?" (statistician)**
They are our judgment calls, written before any data, not tuned to it. We read 0.7 as "strong" agreement and 0.4 as a "moderate" floor; we did not take them from a cited standard. The 5th percentile is the low end of a 90% range. The label doesn't hinge on the exact cutoff: the low end is -0.94. The flip side: with 6 brands, "Trust it" needs a near-perfect ranking (see question 1). We kept the rule anyway, because changing it after results would be worse.

**12. "Commit times can be faked."**
True for a local clock. Two things help. Each commit was pushed to GitHub within about a second of being made (our local push log; UNVERIFIED: local log, not in repo), and GitHub keeps its own record of pushes in our development repo, which is private (we can show it on request). We haven't confirmed that record is visible on the public page (UNVERIFIED). And the rule change made our job harder, which is the opposite of what someone faking it would do.

**13. "Who would pay for this?" (VC)**
Our guess, not tested: small online stores, nonprofits and community groups that already try AI focus groups, and the companies that sell AI panels, as a quality check. We haven't talked to customers or measured demand. Today it's a method demo. The recorded run cost about $0.04 in model calls (ESTIMATE, 6 calls); Flashpoint showed no charge (UNVERIFIED). Revenue data is free.

**14. "Marketers already know people say one thing and do another. What's new?" (marketer)**
Agreed, the say-do gap isn't new. What's new is measuring it for an AI crowd, against a hard answer key, with a fame baseline, before anyone acts on it. AI crowds are fast and cheap, so the risk is that people skip the check. We built the check.

**15. "How much did AI build? What did you two actually do?"**
Claude Code wrote most of the code under Jayden's direction. Jayden chose the idea, the trust rule and the brand rules, and approved each decision. Daniel built the web page (landing page, desk, Grade my website tab with the site grader), set up the team relay, and merged each piece into main. Flashpoint made the AI shoppers. Plain code does all the math and picks the label. One detail: the question for real shoppers ("When shopping online for clothing, shoes or accessories, how do you feel about buying used items instead of new ones?") was written by Claude (`claude-sonnet-5-5`) in the recorded run, so it is AI-generated and labeled that way. Code picked the brand (ThredUp, the biggest miss) and the label.

**16. "Where is the AI actually doing work? The stats are plain Python." (AI judge)**
The AI crowd is the thing under test, so it does the core work: 200 AI shoppers (Flashpoint, SYNTHETIC) produced every rating we grade. Claude (`claude-sonnet-5-5`) turns the biggest miss into one question for real people and summarizes the crowd's WHY answers from a 30-shopper follow-up panel (AI-generated, labeled). We keep the model away from the numbers and the label on purpose: a model grading its own kind is the failure we're testing for. Honest limit: the follow-up panel was launched from a signed-in Claude Code session, not by the product code (`README.md`).

**17. "A small store owner has no SEC answer key. How does this help them?" (VC / store owner)**
It's a calibration check you run before you trust the crowd on your own store. Pick a few public companies in your own category, where revenue is public, and ask the same AI crowd about them first. If the crowd can't rank companies whose answer is known, don't trust it on the one whose answer isn't. Today that check said "Ask real people" for online shopping brands. We haven't tested other categories (UNVERIFIED that the result carries over).

---

Backup facts (if asked):
- Biggest miss: ThredUp, crowd #1 for buying, revenue #5 of 6. Next: Revolve, crowd #6, revenue #3.
- ThredUp had the highest "this is a kind of product I buy" share: 0.565 [SYNTHETIC]. One guess, not tested: secondhand clothes feel like an everyday buy to the AI shoppers.
- Buyers-only check (only AI shoppers who said they buy that kind of product): 0.14 (exact p = 0.80), range -0.82 to 0.82 [SYNTHETIC vs. MEASURED, EXPLORATORY]. Secondary view, not the label.
- 8 brands (FIGS and CarParts.com added after results; run file `extras.sensitivity`, display only): buying vs. revenue -0.14, range -0.78 to 0.54, same label [EXPLORATORY].
- Red-team check (`docs/RED-TEAM.md`, script outside this repo; UNVERIFIED: not reproducible from here): bootstrap over the 200 personas, buying score median -0.14, 5th to 95th percentile -0.49 to 0.14 [EXPLORATORY].
- Independent recount: 0 mismatches across 4,800 answers (`say/audit/RECOUNT.md`).
