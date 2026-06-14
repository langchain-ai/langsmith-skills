---
name: build-agent
description: "INVOKE when the user runs /build-agent, or wants to scaffold a new agent or get an existing/in-prod agent traced into LangSmith. The Scope+Build phase of the ADLC — works standalone or as a step of /productionalize-agent. Shares .adlc.json + conventions with productionalize-agent. Exit gate: traces flowing to LangSmith."
version: 1.0.0
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion, WebFetch, Skill]
triggers: ["build an agent", "scaffold an agent", "add tracing to my agent", "instrument my agent"]
---

<oneliner>
Scope + Build: turn an idea into a running, traced agent — or instrument an agent you already have. Exit gate = traces flowing to LangSmith.
</oneliner>

<entry>
Standalone drop-in: runs on its own OR as the first step of `/productionalize-agent`. On entry:
1. Load `.adlc.json` at repo root. If absent, create it (see the `<manifest>` in `../productionalize-agent/SKILL.md`).
2. **Cold entry on an existing/in-prod agent:** bootstrap the manifest by INSPECTING — read the code, `langgraph.json`/framework, and any LangSmith traces; produce the build-spec table to confirm; mark Scope as done where inferable. Don't re-scaffold what exists.
3. Follow the SHARED conventions (breadcrumb, teach-as-you-go, surface links, manifest contract, defaults, tagging, wrap-up) in `../productionalize-agent/SKILL.md`. Teaching: `../productionalize-agent/scripts/teach.py --print build`.
</entry>

<prereqs>
A project to work in (or willingness to scaffold one) and `LANGSMITH_API_KEY` (region-correct `LANGSMITH_ENDPOINT` — see setup in `../productionalize-agent/SKILL.md`).
</prereqs>

<flow>
**Iron Law — Build isn't done until you can see it traced in LangSmith.** A chattable agent that emits no traces is not a built agent.

**Scope** (write each answer to `.adlc.json`; ask only what's null):
- **starting_point?** build_new · existing. (existing → inspect & bootstrap, see `<entry>`.)
- **Describe it** (open NL) — seeds domain, persona, likely knowledge source, capabilities; pre-fill the manifest, ask only what you can't infer.
- **goal?** demo · deploy. demo → lightweight (just enough to show); deploy → full downstream rigor.
- **audience? — the BRANCH POINT, ask early.** Who is this for?
  - **Myself** → `target=fleet`. **Exit early:** build it and deploy to **fleet** (managed runtime + share via the fleet UI), then stop. The full Test/Deploy/Monitor/Improve production cycle is overkill here — note they can still run those phase skills later if they want.
  - **My team / company** → `target=fleet`. Same early-exit path.
  - **Our customers / external users** → `target=langsmith-deployments`. **Continue** the full ADLC — production rigor applies.
- **learning_level?** low · medium · high — teach-as-you-go verbosity: low = teasers only, medium = teaser + Learn-more/Read-later card, high = full explainers + Read-more links. **Persisted per-user in `user-state.toml` as `teaching_mode`** — read it from there if set (don't re-ask); otherwise ask once and write it back. See the teach-as-you-go convention in `../productionalize-agent/SKILL.md`.
- Apply audience-derived defaults; confirm in one batch.

**Build:**
- **Defer framework specifics to the official building skills (don't hardcode — they stay current as the frameworks evolve; this skill owns the *lifecycle*, they own the *how-to-build*).** Invoke **`ecosystem-primer` FIRST** (LangChain vs LangGraph vs Deep Agents vs hybrid selection, install, env setup, which skill next), then the matching builders: **`deep-agents-core`** (+ **`deep-agents-memory`** for backends, **`deep-agents-orchestration`** for subagents/HITL) for an Agent; **`langgraph-fundamentals`** / **`langgraph-cli`** for a Workflow; **`langchain-fundamentals`** for a Prompt/simple agent; and **`langchain-dependencies`** for packages/versions. Map their guidance onto the manifest decisions below.
- **build_type? (only if build_new) → derives `framework`:**
  - **Agent** — an AI loop that calls tools → **deepagents**
  - **Workflow** — a fixed series of steps → **langgraph**
  - **Prompt** — a single request/reply → `init_chat_model().with_structured_output().invoke()`
- **framework** — derived from `build_type` (Agent→deepagents · Workflow→langgraph · Prompt→single `init_chat_model` call); for BYO/existing, inferred from inspection. **model?** choose-for-me (deferred — a sweep in Test picks the cheapest passing model; record `{mode:"choose-for-me", resolved:false}`) · i-choose · chat.
- **Demo seeding (ONLY if `goal=demo` AND `build_new`) — scaffold it with a few realistic weaknesses ON PURPOSE.** A demo where every test passes proves nothing, and a flawless first build makes the Test phase look like ceremony. Leave 2–4 *subtle, plausible* bugs the way real first drafts have them — e.g. a prompt that doesn't enforce grounding (so it can hallucinate balances/figures), a weak out-of-scope refusal, a tool that silently swallows an error, a missing confirmation before a destructive action. Keep them realistic, not cartoonish sabotage, and don't pre-harden. Record them in `.adlc.json` under `demo_seeds: [{id, where, expect}]` so the loop can confirm Test catches them — but do NOT feed the seeds to `/test-agent`; let its red-team discover them independently, then cross-check. For `goal=deploy`, build it right the first time — **no seeding.**
- **capabilities?** MULTISELECT over deepagents OOTB pieces, two groups:
  - *Already on (defaults, read-only):* TodoList, Filesystem, SubAgent, Summarization, PatchToolCalls, Anthropic prompt-caching — show for transparency, don't offer to "enable".
  - *Opt-in:* human-approval (`interrupt_on`), long-term memory (StoreBackend), subagents, skills, **computer use**, code-exec (sandbox backend), rubric. Tag each `(recommended)` from the manifest.
  - **If human-approval is on, specify WHICH tool calls are gated** — don't blanket-pause everything. Ask which tools need approval (the risky/irreversible ones: money movement, deletes, external writes) and set `interrupt_on={"<tool>": True, ...}`. Record the gated list in the manifest under `hitl` (e.g. `["transfer_funds","delete_account"]`); read-only tools should run without interruption.
- **tools?** the agent's domain tools. Offer **MCP integrations** (wire an MCP server's tools in) alongside hand-written Python tools and the knowledge-source retriever. Record under `tools`.
- **knowledge_source?** docs path · url · generate · none.  **interaction?** conversational · headless (agents only).
- **Tracing is ON by default** — the substrate; state it, don't ask.
- **Instrument a BYO/existing agent (do this FIRST — tracing is the substrate):** deepagents/LangChain/LangGraph → native (set `LANGSMITH_*` env) · Claude/OpenAI SDK → `from langsmith.wrappers import wrap_anthropic`/`wrap_openai` · home-grown → `@traceable`.
- **First-trace moment:** after the FIRST successful invocation, confirm the trace reached LangSmith and give the link to that exact run (`https://<host>/o/<org>/projects/p/<project_id>?...&trace_id=<run_id>`).
- **Local run (`make run`) — figure out + TEST how this agent runs locally before exiting Build.** Emit a `Makefile` whose `run` target spawns the **backend** (however the agent is served — e.g. `langgraph dev`) and, if a frontend is in play, the **frontend** together (the exact commands depend on the framework/FE — work them out for THIS agent). Actually run it once to confirm both come up; set **`local_run_ready: true`** in `.adlc.json` only after `make run` works (else `false` + note the gap in `pending_reminders`). This is part of the exit gate.
- **Let them interact (zero-install options):** auto-open **LangGraph Studio** chat mode (`https://<host>/o/<org>/studio/connect?mode=chat`, or `?baseUrl=<tunnel>` locally), AND share the hosted **agent-chat-ui** — a prebuilt drop-in chat app, no install: `https://agentchat.vercel.app/?apiUrl=<local-or-tunnel-url>&assistantId=<graphId>`. Do NOT ask which production frontend here — that's `/deploy-agent`.
- **EXIT GATE = traces confirmed in LangSmith + `make run` verified (`local_run_ready`)** — NOT a polished agent.
- **Build-spec sign-off (REQUIRED):** render the table (tools · middleware [defaults+opt-ins] · knowledge/docs · backend · code-exec · interrupt/HITL · integrations · how-to-run · deploy target), mark who chose each + flag gaps, get `AskUserQuestion` sign-off. For existing agents, inspect the code and produce the SAME table.
Hand back to `/productionalize-agent` (or suggest `/test-agent`) once traces are flowing.
</flow>
