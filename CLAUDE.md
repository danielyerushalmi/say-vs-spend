# CLAUDE.md

## Team relay protocol

Several Claude Code agents are working in this repo at once, each on its own laptop and git branch. The `team-relay` MCP server is how you coordinate with them. Follow this protocol in every session.

**Your name.** Your agent name is the value of the `AGENT_NAME` environment variable (your human's first name). Read it once with `echo $AGENT_NAME` and pass it as `agent` / `from` in every relay call. If it is empty, ask your human for it before doing anything else.

**At session start**
1. `set_status` with your branch and what you are about to do.
2. `read_messages` and act on anything addressed to you. Keep the returned `newest_id` and pass it as `since_id` on later calls.

**Before editing any file outside the folder you were assigned**
- Call `claim_files` for the paths first. End a path with `/` to claim a whole directory.
- If it returns conflicts, do not edit those files. Post a `question` message to the holder saying what you need and why, then work on something else until they answer or release.

**After every commit + push**
- Post a `done` message to `all`, 1–2 lines: what changed, which files, which branch.
- `release_files` for every claim you no longer need.
- `set_status` if your task has changed.

**If a teammate's work is blocking you**
- Post a `blocker` message to that teammate (or `all` if you don't know who), saying exactly what you need.

**When to check messages**
- Call `read_messages` only at task boundaries: session start, before starting a new task, and after a commit + push.
- Never poll it in a loop and never wait on it. If you are blocked, tell your human and switch tasks.

**Keep it short.** Messages are capped at 500 characters. Claims expire after 45 minutes unless you re-claim them, so re-claim if you are still editing.
