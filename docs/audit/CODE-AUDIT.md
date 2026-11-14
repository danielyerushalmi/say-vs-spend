# Code audit: Say vs. Spend math, importer, run pipeline, LLM client

Audited 2026-11-14, 12:31 to 12:45 ET, at HEAD `68938d0` (branch `jayden/say-vs-spend`).
This was a read-only audit. No code was changed. The probe scripts live outside the repo, in
`/private/tmp/claude-501/audit/` (p1_wiki.py, p2_parse.py, p3_llm.py, p4_e2e.py, p5_misc.py).

Files audited: say/compare.py, say/runfile.py, say/run.py, say/flashpoint_import.py, say/repeat.py,
say/fame/wiki.py, say/trust_text.py, say/detective.py, agent/llm.py.

Tests: `python3 -m unittest discover say/tests` ran 179 tests, all OK, at 12:36. One earlier run hit 1
failure while another agent was partway through editing runfile.py. Re-running gave OK.

## What checks out (verified, not assumed)

- The shown Spearman and exact p numbers match scipy for all three questions on the real panel. Say is
  0.7714, p 0.1028. Intent is 0.0286, p 1.0. Fame is 0.7247, p 0.1056.
- Rank ties: `ranks()` gives average ranks. Means are k/n of whole numbers, so two equal means are
  always the same float. Float noise cannot break a tie.
- Spearman with a constant input or n<3 returns None. Everything after that falls back to
  ask_real_people or n/a and does not crash.
- Bootstrap: brands are resampled with replacement, duplicate brands are re-ranked as ties, and
  zero-variance resamples are skipped. Percentiles use linear interpolation (numpy's default). The same
  seed gives the same answer. NaN values are filtered out by `_is_number` before ranking.
- trust_verdict applies the cutoffs to wobble_low, as decided at 12:10. The validator now checks
  `trust` against wobble_low.
- Importer on the real export: the BOM is removed (utf-8-sig), the repeated header row is detected and
  skipped, and the 2 admin `Quality: ... (0-100)` columns are ignored. The `ID` column is picked as the
  persona id (200 distinct values). AWARE uses 1 = Yes and 2 = No. `parse_bool("10")` returns
  unparseable, not True. Brand matching gives the same result whether 6 or 12 brands are loaded.
- Atomic writes use mkstemp in the same folder, then os.replace. They clean up the temp file on error.
- LLM 429 twice, 5xx, bad JSON twice, no key, and call-cap-hit all fall back to template text.

## Bugs found (confirmed with a probe unless marked)

### 1. DEMO CRASH: `NameError: MODELS` in run.py stage 5 when the model works
- **Where:** say/run.py:274 (added in commit 68938d0). `MODELS` is never imported. Line 28 imports only
  `LLM, NoKey`.
- **Trigger:** the verdict is `ask_real_people` (today's real verdict), and the model returns a draft
  question that differs from the fallback. That happens on every keyed run.
- **Observed:** p4_e2e.py with a working fake model gives `NameError: name 'MODELS' is not defined`.
  The traceback comes out uncaught. The page file stops at the stage-4 save, so it has no trust
  sentence, no repeat_run, no fame_wiki, no extras and no followup_loop.
- **Expected:** rc 0 and a full run file. With the import patched in, the same probe gives rc 0, an
  empty `validate_run` list, and repeat, wiki and extras all present.
- **Why the tests miss it:** `--no-llm` and the test transports return the fallback text, so the
  `else` branch never runs.
- **Severity:** demo crash.
- **Fix:**
```diff
-from agent.llm import LLM, NoKey
+from agent.llm import LLM, MODELS, NoKey
```

### 2. Wikipedia fame says "could_be_chance: false" under the old rule. The 12:45 rule says true.
- **Where:** say/fame/wiki.py:111-127, `wiki_fame_agreement`. This copy of `compare.agreement` was
  made before the exact-p red-team fix, so it never computes p_exact.
- **Input:** the real run plus `say/fame/wikipedia_pageviews.json` (5 brands, rho 0.9).
- **Observed:** `could_be_chance: False`, with no p_exact.
- **Expected:** the same data through `compare.agreement` gives `p_exact 0.0833` and
  `could_be_chance: True`. With n=5, rho=0.9 has 10 of 120 orderings at |rho| >= 0.9.
- **Severity:** affects shown numbers. The page tells judges the Wikipedia fame line is "not chance".
  The crowd lines use a stricter test that would call it chance.
- **Fix:** reuse the shared function.
```diff
 def wiki_fame_agreement(brands, views, n_boot=2000, seed=compare.DEFAULT_SEED):
-    usable = [{"revenue_usd": b.get("revenue_usd"), "views": views.get(b["id"])} for b in brands]
-    ... (own ranks / spearman / bootstrap) ...
+    rows = [{"revenue_usd": b.get("revenue_usd"), "aware_share": views.get(b["id"])} for b in brands]
+    rows = [r for r in rows if compare._is_number(r["aware_share"]) and compare._is_number(r["revenue_usd"])]
+    out = compare.agreement(rows, "fame", n_boot=n_boot, seed=seed)
+    out["n_brands"] = len(rows)
+    return out
```

### 3. `crowd_beat_wiki_fame` compares two different brand sets
- **Where:** say/fame/wiki.py:138-140.
- **What happens:** the intent rho comes from all 6 brands (0.0286). The wiki rho comes from the 5 brands
  that have an article (Revolve left out).
- **Observed:** intent rho on the same 5 brands is 0.1. Today the answer is False either way, so the
  shown boolean is right by luck. It becomes wrong whenever the dropped brand decides the result.
- **Severity:** affects shown numbers (latent).
- **Fix:**
```diff
-    intent = ((run.get("agreement") or {}).get("intent") or {}).get("spearman")
+    same = [b for b in brands if compare._is_number(views.get(b["id"]))]
+    intent = compare.agreement(same, "intent", n_boot=1)["spearman"]
```

### 4. LLM client: some network failures get past the fallback and stop or crash the run
- **Where:** agent/llm.py:88-98 (`_http_transport` catches only URLError, TimeoutError and OSError)
  and llm.py:156-163. The callers in trust_text.py:44 and detective.py:64/84 catch only NoKey,
  StopSwitch and LLMError.
- **Inputs (p3_llm.py, fake urlopen):**
  - A 200 response with an HTML body (proxy or captive portal) raises `JSONDecodeError`, which escapes.
    In run.py, `main` catches it as ValueError and prints "STOPPED" with rc 2, right after stage 3.
  - A dropped connection during `read()` raises `http.client.IncompleteRead`, which escapes as an
    uncaught traceback.
  - A 200 body that is not a dict raises `AttributeError`, which escapes.
- **Observed (p4_e2e.py):** the page keeps the stage-3 file, which is valid. It has no
  repeat_run, fame_wiki or extras, and no trust sentence.
- **Expected:** template text, and the run carries on to stage 7.
- **Severity:** demo crash on flaky venue Wi-Fi.
- **Fix:**
```diff
     try:
         with urllib.request.urlopen(req, timeout=timeout) as resp:
-            return resp.status, json.loads(resp.read().decode("utf-8"))
+            body = json.loads(resp.read().decode("utf-8"))
+            return resp.status, (body if isinstance(body, dict) else {})
     except urllib.error.HTTPError as e:
         ...
-    except (urllib.error.URLError, TimeoutError, OSError) as e:
+    except (urllib.error.URLError, TimeoutError, OSError, ValueError,
+            http.client.HTTPException) as e:
         raise LLMError(f"network error: {type(e).__name__}") from None
```
(This also needs `import http.client`.)

### 5. Verdict and shown wobble_low can disagree right at the 0.7 cutoff
- **Where:** compare.py:243-245 bands the unrounded wobble_low. runfile.py:105 shows it rounded to 4
  places, and runfile.py:118 shows 2 places.
- **Input:** `trust_verdict(0.9, 0.69996, 1.0)`.
- **Observed:** verdict `verify`. The file shows `wobble_low: 0.7`, and the reason text says "range
  (0.70 to 1.00), so it is Double-check it". The stated rule says "0.7 or higher = trust it".
- **Severity:** affects the shown verdict, but only in a narrow edge case. Today's wobble_low is
  -0.9355, so it does not apply now.
- **Fix:** band the same number that is shown.
```diff
-    verdict = _band(wobble_low)
+    verdict = _band(round(wobble_low, 4))
```
Also print 4 places in `_why_trust`, or say "just under 0.70".

### 6. Importer reads a repeated header in the middle of the file as a persona who answers "aware = yes"
- **Where:** flashpoint_import.py:83-85. The yes/no patterns have no word boundary after `aware`,
  `heard` or `familiar`. Also flashpoint_import.py:289-316: only the FIRST repeated header row is
  skipped.
- **Inputs:** `parse_bool("AWARE__figs")` gives `(True, None)`. `parse_bool("familiarity")` gives True.
  A CSV with the header row pasted again mid-file (two exports joined) gives n_personas 3 instead of
  2, plus a fake persona "ID" with aware=True for every brand.
- **Severity:** affects shown numbers only if exports are ever joined. The `--expect-n` guard would
  catch the count. The current exports are clean.
- **Fix:**
```diff
     for n, row in enumerate(data, start=1):
-        if not any(c.strip() for c in row):
+        if not any(c.strip() for c in row) or [c.strip() for c in row] == header:
             continue
```
and in parse_bool: `...|aware|familiar)(?![\w])` (no letter, digit or underscore may follow).

### 7. An admin column with " - " in its name blocks the whole run (likely, if Flashpoint adds one)
- **Where:** flashpoint_import.py:113 together with run.py:189-192.
- **Input:** header `Start Date - UTC`. `split_header` returns ('Start Date', 'UTC'), which lands in
  `unmatched_columns`. run.py then aborts with "column(s) could not be matched".
- **Severity:** demo crash, only if the export format changes. The current exports have no such column.
- **Fix:** in import_export, treat a split column as an admin column when its loop key matches no brand
  AND its question key is not a known label.
```diff
         bid, note = match_brand(loop_key)
         if bid is None:
+            if norm(qkey) not in {"say", "intent", "aware", "buy"} and not detect_kind(qkey):
+                ignored.append(h); continue
             unmatched.append({"column": h, "reason": note})
```

### 8. Smaller issues (cosmetic or latent)
- **runfile.py:199-201 with run.py:265:** gap dicts in the run file have no `places_off`, so
  `max(... places_off or 0)` always picks the first gap. It is right only because `top_gaps` is
  already sorted. Fix: use `run["top_gaps"][0]`, or keep `places_off` in the gap dict.
- **compare.py:221, top_gaps:** the tie at the cut-off is hidden. Today hims (|2|) and petmeds (|2|)
  tie for 3rd place. Only hims is shown, because "h" comes first alphabetically. The page could say
  "tied with petmeds".
- **runfile.py:245-348, validate_run:** it only checks `trust` against the rule. A run with
  `verdict: "verify"` and intent wobble_low -0.94 validates with no errors (probe c). Fix:
  `if tc["verdict"] != compare.trust_verdict(None, a_int["wobble_low"], None)["verdict"]: errs.append(...)`.
  Note that wobble_low is rounded, so pair this with fix 5.
- **repeat.py:32-34:** `_round_agreement` has a fixed key list, so `p_exact` is dropped from
  repeat_run.agreement. Its could_be_chance still uses p_exact, so the flag is right but the number is
  not shown.
- **trust_text.py:46 / detective.py:66:** if the model returns `{"sentence": ["a","b"]}`, the trust
  card reason reads `['a', 'b']`. Fix: accept only `isinstance(out.get(key), str)`.
- **run.py:252/275 trace:** steps are labeled model "llm" even when every call fell back to template
  text (no key, 401). `llm.calls` also counts failed attempts.
- **runfile.py:354, mkstemp:** the run files are created 0600 (owner-only). That is fine for a local
  same-user server or git. A server running as a different user could not read say_latest.json. Fix:
  `os.chmod(tmp, 0o644)` before `os.replace`.
- **flashpoint_import.py:59-74 parse_scale:** these misreads happen silently, but no real export
  produces such values. `"1-10"` reads as 1, `"-3"` as 3, `"1,5"` as 1, and `"1e1"` as 1. In parse_bool,
  `"No idea"` reads as False. `"1.0"` and `"2.0"` are reported as unparseable, which is safe.
- **Design note, not a bug:** with no key and no `--no-llm`, run.py exits 2 before writing anything
  (KEY_HELP). It does not fall back. Have the `--no-llm` command ready for the demo.

## Ranked top-5 fix list

1. **run.py:28:** import `MODELS`. The next keyed run crashes at stage 5 without it. One line.
2. **wiki.py:111:** route Wikipedia fame through `compare.agreement`, so p_exact and the 12:45
   could_be_chance rule apply. The shown flag is wrong today: False, should be True (p = 0.083).
3. **llm.py:88-98:** turn JSONDecodeError, HTTPException and non-dict bodies into LLMError, so
   flaky Wi-Fi falls back to template text instead of stopping the run.
4. **wiki.py:138:** compare intent and wiki rho on the same 5 brands for `crowd_beat_wiki_fame`.
5. **compare.py:245, plus a validate_run check:** band the rounded wobble_low that is shown, and make
   the validator re-derive the verdict for all three labels.
