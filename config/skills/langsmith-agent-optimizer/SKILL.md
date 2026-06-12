---
name: langsmith-agent-optimizer
description: "INVOKE THIS SKILL when improving a production agent from its traced sessions in LangSmith — 'make my agent better', 'why is my agent failing', 'improve agent quality', 'agent quality audit', 'why are users frustrated with the bot'. Mines recent sessions + user-flagged runs for concrete harness fixes: system-prompt changes, tool-description corrections, stale references to delete, and missing capabilities to build. Prescribes specific changes with trace evidence; you (or your agent) apply them."
---

<oneliner>
Turn production sessions into agent harness improvements: **(1) Pull** recent agent runs + every user-flagged (thumbs-down) run; **(2) Extract** conversations into a reviewable form; **(3) Analyze** across three vectors — response error modes, tool-call errors (target: zero), and user frustrations that are really feature requests; **(4) Prescribe** one concrete fix per recurring issue (system prompt, tool description, missing capability), each with trace IDs as evidence; **(5) Verify** by replaying the failing sessions from an append-only regression dataset — not by waiting for the next review.
</oneliner>

<setup>
Environment Variables

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here          # REQUIRED
LANGSMITH_PROJECT=your-agent-project                  # The project your agent traces to
```

CLI Tool
```bash
curl -sSL https://raw.githubusercontent.com/langchain-ai/langsmith-cli/main/scripts/install.sh | sh
```

You also need to know:
- **The root run name** of your agent (e.g. `my_agent` — the top-level run per session)
- **Your human-feedback key** if the app has thumbs up/down (e.g. `user-feedback`,
  with score 0 = bad, 1 = good)

**Gotchas that make commands silently return nothing:**
- Always pass `--format json` when piping to a parser (default output is pretty-printed).
- Filter by run name with `--filter 'eq(name, "my_agent")'` for exact match.
- Mind trace retention — sessions older than your plan's retention window are gone, so
  audit on a cadence shorter than retention.
</setup>

<pull_sessions>
## Step 1: Pull recent agent sessions

Fetch the last N days of root runs with io included, then compute health stats:

```bash
langsmith --format json run list \
  --project "$LANGSMITH_PROJECT" \
  --filter 'eq(name, "my_agent")' \
  --last-n-minutes 10080 \
  --limit 100 \
  --full --api-key $LANGSMITH_API_KEY > /tmp/agent_runs.json

python3 - << 'EOF'
import json
from datetime import datetime

d = json.load(open('/tmp/agent_runs.json'))
runs = d if isinstance(d, list) else d.get('runs', [])
for r in runs:
    r.setdefault('id', r.get('run_id'))
json.dump(runs, open('/tmp/agent_runs.json', 'w'))

print(f'Total runs: {len(runs)}')
errors = [r for r in runs if r.get('status') == 'error']
print(f'Errors: {len(errors)}')
for r in errors:
    print(f"  {r['id'][:12]} | {str(r.get('start_time',''))[:19]} | {(r.get('error') or '')[:100]}")

durs = []
for r in runs:
    if r.get('start_time') and r.get('end_time'):
        s = datetime.fromisoformat(r['start_time'].replace('Z','+00:00'))
        e = datetime.fromisoformat(r['end_time'].replace('Z','+00:00'))
        durs.append((e - s).total_seconds())
if durs:
    durs.sort()
    print(f'P50: {durs[len(durs)//2]:.1f}s  P90: {durs[int(len(durs)*0.9)]:.1f}s  Max: {max(durs):.1f}s')
EOF
```
</pull_sessions>

<pull_flagged>
## Step 2: Pull user-flagged runs (highest-signal — never skip)

Runs a real user thumbed-down are worth more than any random sample. Use the CLI's raw
REST wrapper to hit the feedback endpoint, **filtering by your human-feedback key
server-side** — projects with auto-evaluators are flooded with machine feedback that
would crowd out the rare human flags. Note the endpoint caps `limit` at 100.

```bash
# session=<project UUID>; find it with: langsmith project list
langsmith --format json api \
  "/api/v1/feedback?session=YOUR_PROJECT_UUID&key=YOUR_FEEDBACK_KEY&limit=100" \
  --api-key $LANGSMITH_API_KEY \
  | python3 - << 'EOF'
import sys, json
from datetime import datetime, timedelta, timezone

raw = json.load(sys.stdin)
fb = raw if isinstance(raw, list) else raw.get('feedback', raw.get('data', []))
since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
flagged = [f for f in fb if f.get('score') == 0.0 and (f.get('created_at') or '') >= since]
run_ids = list({f['run_id'] for f in flagged if f.get('run_id')})
print(f'Flagged runs (last 7 days): {len(run_ids)}')
json.dump(run_ids, open('/tmp/flagged_run_ids.json', 'w'))
EOF
```

If 0 flagged runs come back, that's usually genuine — users rarely click thumbs-down.
Sanity-check by dropping the date filter: if there are entries at all, the query works;
there just weren't any bad ones this window.
</pull_flagged>

<extract>
## Step 3: Extract conversations

Sample 20-30 sessions (or all, if fewer) **plus ALL flagged runs** — flagged runs are
mandatory, not part of the sample cap. Fetch any flagged run missing from Step 1's file
with `langsmith run get <id> --project "$LANGSMITH_PROJECT" --full`, then extract:

```bash
python3 - << 'EOF'
import json

runs = json.load(open('/tmp/agent_runs.json'))
flagged = set(json.load(open('/tmp/flagged_run_ids.json')))
by_id = {(r.get('id') or r.get('run_id')): r for r in runs}

sample = list(by_id)[:30]
sample += [f for f in flagged if f in by_id and f not in sample]

convos = []
for rid in sample:
    r = by_id[rid]
    convo = {'id': rid, 'flagged': rid in flagged, 'status': r.get('status'),
             'error': r.get('error'), 'user_messages': [], 'ai_messages': [],
             'tool_calls': [], 'tool_errors': []}
    msgs = ((r.get('inputs') or {}).get('messages') or []) + \
           ((r.get('outputs') or {}).get('messages') or [])
    for m in msgs:
        t = m.get('type')
        if t == 'human':
            convo['user_messages'].append((m.get('content') or '')[:500])
        elif t == 'ai':
            convo['ai_messages'].append((m.get('content') or '')[:500])
            convo['tool_calls'] += [tc.get('name','') for tc in (m.get('tool_calls') or [])]
        elif t == 'tool':
            c = m.get('content') or ''
            if 'error' in c.lower():
                convo['tool_errors'].append(c[:300])
    convos.append(convo)

json.dump(convos, open('/tmp/agent_conversations.json', 'w'), indent=2)
print(f"{len(convos)} conversations ({sum(c['flagged'] for c in convos)} flagged)")
EOF
```

**NOTE:** message shape varies by framework — inspect one run's `inputs`/`outputs`
before trusting the extraction (see the Golden Rule in **langsmith-evaluator**).
</extract>

<analyze>
## Step 4: Analyze across three vectors

Read every sampled conversation. For each vector, track count + example session IDs.

### Vector 1: Response errors — check EVERY ai message for these six modes

- **1a. Garbage output** — mostly emoji, random characters, or nonsense instead of an answer.
- **1b. Going silent** — the agent stops responding mid-conversation. Detect via user
  follow-ups: "Hello?", "continue", "???", "are you there?", repeated short nudges.
- **1c. Getting stuck** — calling the same tool repeatedly, repeating the same response,
  or retrying without changing approach; also unreasonably long sessions for simple asks.
- **1d. Continuing the user's sentence** — completing what the user was typing instead
  of answering it.
- **1e. Claiming success after failure** — the agent says "Done!" when the tool call
  actually errored. **The worst mode — it destroys user trust.** Cross-check every
  success claim against the adjacent tool results.
- **1f. Hallucinating tools/fields that don't exist.** This is never random — it almost
  always means dead code, a stale system-prompt reference, or an outdated tool
  description left behind by a refactor. For each hallucination, **trace the source**:
  search the system prompt and tool descriptions for the reference leading the agent
  astray, and note exactly what to delete or update.

### Vector 2: Tool-call errors — the target is ZERO

The agent has (or should have) everything it needs to call tools correctly. Every
tool-call error therefore means something is missing or wrong in the system prompt, the
tool description, or the schema docs. Group errors by tool; for each distinct error
record: the tool, the error, the count, the root cause (why the agent called it wrong),
and the fix (what to change in prompt/description/schema). Full error text for the first
occurrence; repeats just get counted.

### Vector 3: User frustrations and product signal

- **3a. Frustrations** — the user repeats themselves, corrects the agent, over-explains,
  or vents. Each pattern maps to a fix: a system-prompt update, a better tool
  description, or a missing capability.
- **3b. Recurring requests** — group what users ask for by theme. **3+ independent users
  asking for the same thing = a feature/skill candidate**, not noise. Note whether
  anything existing partially covers it.

### Flagged sessions get a dedicated write-up each

```markdown
### Flagged session: {run_id[:12]}
- **User wanted:** ...
- **Agent did:** ...
- **Why the user flagged it:** ...
- **Root cause:** (prompt issue / tool bug / missing capability / model variance)
- **Fix:** ...
```
</analyze>

<findings>
## Step 5: Findings format

One finding per **recurring** issue (skip one-offs and "the agent is fine here"). Each
finding is one concrete action:

- **Title** = the action, not the symptom: "Stop the agent claiming success after a
  failed save (4 sessions)", not "agent sometimes wrong".
- **Evidence** = the LangSmith run IDs of the affected sessions, plus one quoted exchange.
- **Root cause** = where the behavior comes from (prompt section, tool description,
  missing tool, model variance).
- **Fix** = the specific change, with a definition of done.
- **Severity** — triage by user impact: trust-destroying modes (1e, 1f) and agent-down
  patterns first; recurring frictions second; cosmetic last. When in doubt, rate it the
  worse level — under-calling lets real issues slip.

Recurring findings that survive a "fix" mean the root cause was misdiagnosed.
</findings>

<closing_the_loop>
## Step 6: Close the loop — verify fixes, don't just ship them

"Re-check on the next audit" is slow, passive verification. Do this instead:

### Build a regression dataset from the failing sessions

Every diagnosed failure session becomes an example in an **append-only** regression
dataset — the permanent record of scenarios the agent must handle correctly. Name it
so it's always discoverable from the project:

```
optimizer:<project-name>:evals
```

For each failure session, add an example: inputs = the user messages that triggered the
failure, reference outputs = what correct behavior looks like (or the failure mode to
assert against). Add examples — never replace them (see **langsmith-dataset** for
mechanics).

### Verify by replay, not by waiting

After applying a harness fix, re-run the agent against the regression dataset and check
the failure mode is gone — minutes, not next-audit-window. Run it once BEFORE the fix
too: a fix that can't move a before/after experiment on the very sessions that exposed
it isn't a fix.

### Version-stamp the system prompt

Harness fixes edit the system prompt; treat it like any versioned artifact — a version
string + one-line changelog per change, stamped into run metadata at session time.
Without the stamp you can never attribute "did the error rate drop?" to a specific
fix: deploys and prompt changes blur together and before/after analysis becomes
impossible.

### Graduate recurring error modes into online evaluators

Once an error mode has been diagnosed twice (e.g. claiming success after a failed tool
call), detection shouldn't wait for the next periodic review — encode it as an online
evaluator on the production project (see **langsmith-evaluator**). The periodic review
finds NEW failure classes; online evaluators watch the KNOWN ones. Caveat: if the
evaluator is an LLM judge, align it against hand labels first (Cohen's κ ≥ 0.6 before
trusting it on a dashboard, ≥ 0.8 before letting it gate anything automatically) — an
unaligned judge measures nothing.
</closing_the_loop>

<tips>
- **Audit on a cadence shorter than your trace retention**, or the evidence disappears.
- **Always include all flagged runs** — a random sample alone systematically misses the
  worst sessions, because bad sessions are rare and users who hit them often just leave.
- **Track session health stats over time** (error rate, P50/P90 duration) — a duration
  regression is often the first visible sign of a stuck-loop bug.
- **Test fixes against the original failing conversation** — replay the user's message
  locally and confirm the new behavior before shipping.
</tips>

<resources>
- [LangSmith Feedback / Annotations](https://docs.langchain.com/langsmith/annotate-traces-inline)
- [Filtering runs](https://docs.langchain.com/langsmith/filter-traces-in-application)
- **langsmith-trace** skill — querying and exporting the underlying traces
</resources>
