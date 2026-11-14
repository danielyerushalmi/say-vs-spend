# Say vs. Spend frontend

Two pages plus a tiny standard-library server. No packages to install.

- `index.html`: the landing page that explains the study (3D iceberg hero, how it works, the depth game, the verdict).
- `desk.html`: where people use it (the chat, with Evidence / Crowd / Verdict tabs).

```bash
python3 frontend/server.py     # open http://localhost:3001
```

- The page loads `runs/say_latest.json` (written by the pipeline), falling back to `runs/sample.json`. Show a specific file with `?run=runs/<file>.json`. With `"mode": "live"` it re-reads the file every 4 seconds.
- `runs/sample.json` is **placeholder data**; the page shows a "SAMPLE DATA, NOT A RESULT" banner whenever it is loaded.
- **The desk (chat):** always answers from the run file in the browser. If `server.py` runs with the team's `agent/llm.py` on the path and `ANTHROPIC_API_KEY` set in that terminal, free-text questions go to Claude (`claude-sonnet-5-5`), grounded only in the run file, capped by `SAY_CHAT_MAX_CALLS` (default 20). The server only checks whether the key is set; it never prints, logs or stores it.
- Scripts: `common.js` (shared helpers + run-file loading), `landing.js` (picker, card, depth game, verdict), `sea.js` (three.js icebergs: tip height = crowd's would-buy score, depth below water = revenue, both to scale), `desk.js` (chat, evidence, crowd bubbles, verdict tab).
- Libraries from jsDelivr at pinned versions: GSAP 3.13.0 and Lenis 1.1.14 (with integrity hashes), three.js 0.170.0 (via the import map). Fonts: Sora, Inter, Spline Sans Mono (Google Fonts). Everything works without them.
