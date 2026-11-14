# Page fixes from the judge review (for Daniel's agent), 1:15 PM ET, Nov 14

Exact text on `origin/main` (1a1cdee) and a suggested replacement. These are Daniel's files; Jayden's side
does not edit `frontend/`. Every number in the suggestions comes from `frontend/runs/say_latest.json`.
Why each matters: these are the lines a skeptical judge flagged as wrong or overclaimed.

## 1. Hero shows no result, and says "people" (they are AI shoppers): `frontend/index.html:41-42`

Now:
```html
<h1 id="hero-h">People say one thing.<br>Their wallets go <em>deeper</em>.</h1>
<p class="lede" id="hero-lede">AI shoppers rated online brands. Above the water is what they <b>said</b>. Below it is what the companies actually <b>earned</b>. Tap a brand.</p>
```
Suggested:
```html
<h1 id="hero-h">AI shoppers say one thing.<br>The money goes <em>deeper</em>.</h1>
<p class="lede" id="hero-lede">200 AI shoppers ranked 6 online brands. Their buying ranking matched real revenue at <b>0.03</b> <span class="tag">SYNTHETIC vs MEASURED</span>, so the rule we committed before any result says: <b>Ask real people.</b> Tap a brand.</p>
```
Better: fill 0.03 and the verdict from `RUN.agreement.intent.spearman` and `RUN.trust_card.verdict` in
`landing.js`, so the hero can never disagree with the run file.

## 2. "WHAT PEOPLE SPENT": `frontend/index.html:45`

Revenue includes wholesale and non-US sales, so it is not "what people spent".
Now: `↓ WHAT PEOPLE SPENT · YEARLY REVENUE · MEASURED`
Suggested: `↓ WHAT THE COMPANIES EARNED · YEARLY REVENUE · MEASURED`
(`landing.js:24` "Spent" -> "Earned", same reason.)

## 3. "built from US census mixes": no source in the repo, so it is UNVERIFIED
- `frontend/index.html:61`: drop ", built from US census mixes".
- `frontend/desk.js:116`: drop ", built from US census mixes".

## 4. Wrong question text: `frontend/desk.js:44` and `:116`
The real Q4 was "Is this a kind of product you buy?" (run file `questions.buy.text`).
- `:44` `` ` · ${pct(b.buy_share)} said yes` `` -> `` ` · ${pct(b.buy_share)} buy this kind of product` ``
- `:116` "whether they would buy (yes or no)" -> "whether it is a kind of product they buy (yes or no)"

## 5. "second, separate crowd": `frontend/desk.js:92`
Both panels come from the same persona model (gpt-5.4-mini), so "separate" overclaims.
"We ran a second, separate crowd of" -> "We ran a second crowd of ... different AI personas from the same persona model"

## 6. "Each bubble is one person": `frontend/desk.js:112`
-> "Each bubble is one AI shopper"

## 7. "what people spent": `frontend/desk.js:117`
"The answer key is what people spent:" -> "The answer key is company revenue:"

## 8. Chat can't see half the evidence: `frontend/server.py` `compact_run`
`compact_run` leaves out `repeat_run`, `fame_wiki`, `followup_loop`, `extras`, so with a key the desk chat
will likely say "no data" to "What about a second crowd?". Suggested, inside the returned dict:
```python
        "repeat_run": {k: v for k, v in (run.get("repeat_run") or {}).items() if k != "personas"},
        "fame_wiki": {k: v for k, v in (run.get("fame_wiki") or {}).items() if k != "urls"},
        "followup_loop": {k: v for k, v in (run.get("followup_loop") or {}).items() if k != "raw_answers"},
        "extras": run.get("extras"),
```
Check the prompt size after this (the per-shopper rows are the big part; they stay out).
