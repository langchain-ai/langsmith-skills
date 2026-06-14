---
name: test-agent
description: "INVOKE when the user runs /test-agent, or wants to evaluate / add evals / test / harden the quality of an agent. The Test phase of the ADLC — works standalone or as a step of /productionalize-agent. Builds an eval suite you TRUST, then red→greens the agent. Uses langsmith-dataset + langsmith-evaluator."
version: 1.0.0
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion, Agent, WebFetch]
triggers: ["test my agent", "add evals", "evaluate my agent", "red-team my agent"]
---

<oneliner>
Build a dataset + evaluators you trust (align them to your judgment), then red→green the agent against them. TDD for agents.
</oneliner>

<entry>
Standalone drop-in — great for hardening an existing/in-prod agent. On entry:
1. Load `.adlc.json`. If absent, bootstrap by inspecting the agent + traces (build-spec table) and mark Build done.
2. **Prereq: a traced agent.** If no traces exist, instrument it first (point to `/build-agent`) — you can't test what you can't observe.
3. Follow the SHARED conventions in `../productionalize-agent/SKILL.md`. Teaching: `../productionalize-agent/scripts/teach.py --print test`. Print the Test sub-stepper on each sub-step; update `test_substep`; pace one beat at a time.
</entry>

<prereqs>
A traced agent (runs landing in a LangSmith project) and `LANGSMITH_API_KEY`/`LANGSMITH_ENDPOINT`.
</prereqs>

<flow>
**Iron Law — trust the evaluators before you trust the scores.** An unaligned eval is worse than no eval; align to human judgment first.

Build an eval suite **you trust**, then use it to red→green. Paced sub-steps:

**1. Find issues → build the dataset** (`find-issues`). The dataset is your suite of test cases.
- **Dataset?** synthetic · **production traffic** · I test — pick by what's available:
  - **I test (provided).** They hand you examples, or drive the agent themselves and tell you what's good/bad → build cases from that.
  - **Production traffic (existing / in-prod agent) → PREFER this.** Mine actual production traces for real failures instead of inventing them: **fan out N *cheap* subagents (a Workflow) that PARTITION the trace set** — each scans its slice, flags the traces with issues and names the issue — then build the dataset from those flagged real traces (each → a case + assertion). Real failures beat synthetic ones.
  - **New agent / little traffic → synthetic.** Use the **coverage-first generation** procedure below (positives + breakers), then harden with the red-team loop.
  - **Demo seeds present?** If `.adlc.json` has `demo_seeds` (planted by `/build-agent` for `goal=demo`), run the red-team **blind** first, THEN cross-check that each seed was surfaced — call out any the red-team missed, and flag any *extra* real issues it found (those are the win).
  - A dataset where everything passes proves nothing.
- **Knowledge-grounded seeds (reverse-RAG) — PREFER when the agent has a `knowledge_source` / retriever / RAG.** Don't invent queries in a vacuum; seed them from the agent's *actual* corpus so cases are grounded **and** diverse: **①** partition the KB and fan out cheap subagents over the chunks/docs; **②** each extracts key facts from its slice; **③** for each fact, generate realistic user queries (persona-driven) that the fact answers — "running RAG backwards"; **④** keep the source chunk as the case's **expected grounding / citation** — a free oracle for the groundedness evaluator in `write-tests`. Grounded, diverse seeds → a grounded, diverse dataset. **Combine with the coverage design below for even more diversity:** cross each grounded seed with the other factors (persona × difficulty × `tool` × adversarial…) via the covering array — the KB topic/doc becomes a `topic` factor, so cases are grounded **and** combinatorially diverse. (Self-Instruct "seed collection"; Ragas-style KB testset generation.)
- **Coverage-first synthetic generation — one design, grounded in experimental design** (run when `synthetic`, or to top up sparse cells on any path):
  - **Ask (open-ended):** *"Describe the kinds of scenarios your agent is expected to handle — the more the better."* Combine with what's known (`description`, `persona`, `capabilities`, `tools`).
  - **① Factors & levels.** Induce a taxonomy of **~10 scenario categories** (intents / use-cases) → that's your first, multi-level factor (`category`). Then add the other dimensions that drive behavior as factors: persona, difficulty, in-/out-of-scope, **`tool` — one level per tool the agent actually has (work *backwards from the manifest's `tools`/`capabilities`* to write realistic queries that would invoke each tool), plus `none` and `multi`**, turns, ambiguity, locale, length, adversarial. (Categories aren't a separate method — they're just one factor in the design.)
  - **② Covering array.** Generate a **t-wise covering array** over those factors with **`../productionalize-agent/scripts/covering_array.py`** (deterministic greedy IPOG/AETG; constraint-aware; self-verifies; t=2 pairwise default, t=3 for higher assurance) — a compact balanced table (e.g. 7 factors → ~13 rows vs 384 full) where every category appears AND every category×persona, category×difficulty… pair is covered. **Lite path:** run with *only* the `category` factor and it degenerates to ~N diverse prompts per category (the simple taxonomy fan-out).
  - **③ Generate + tag (a Workflow).** One subagent writes **one concrete prompt per row** instantiating those exact levels, given the agent's purpose / capabilities / tools (seed → expand for diversity, à la Self-Instruct / Evol-Instruct). **Store the row's factor-vector in each example's `metadata`** so failures map back to factor cells after the experiment (which levels actually break the agent). *(Subagents expose no temperature/"creativity" knob — drive diversity via the per-row factor vector + an explicit "maximize diversity, avoid overlap with already-generated cases" instruction, not sampling temp. For true temperature control, generate via a direct model API call in a script.)*
  - **④ Dedup + coverage check.** Semantic-dedupe near-duplicates (LLMs **mode-collapse**), confirm every cell is filled, balance happy-path vs breakers.
  - **Why:** stratified / quota sampling (categories = strata) + combinatorial coverage over dimensions — a covering array is the test-design cousin of fractional-factorial / orthogonal arrays, but tuned for *coverage* (every level & pair appears), not unbiased effect estimation, so it fits here better than a Resolution-III design. Dedup fights mode collapse; the adversarial factor probes the tails. **Optimize for representative coverage, not raw count.**
  - **Per-category guarantee:** pairwise only guarantees each category *appears* (≈ once per the largest other factor). If you need ≥k prompts per category, raise the strength, hold `category` to full coverage while pairwise-ing the rest, or generate the array per-category.
- **Red-team loop (hardening):** parallel adversarial subagents, each looping until it confirms a *real* break — adds confirmed failures the coverage pass may have missed.
- Open the dataset URL, show the cases, STOP — let them see the cases before any eval.

**2. What matters → build the evaluators** (`write-tests`).
- Ask **"what matters to you about this agent?"** — offer dimensions (groundedness, scope, safety, tone…) AND an escape: *"show me some outputs and I'll tell you what's good/bad,"* then derive dimensions from reactions.
- **Assertions** pattern: each example's `outputs` = `{assertions:[{key,comment}]}`; evaluator returns **one feedback score per assertion key** (LLM-judge). Each key = one Python test, 1-to-1.
- **Data model (get this right):** the dataset example holds `inputs` (the user query) + **`outputs` = the reference/target** (expected outcome — the `assertions`, plus any expected grounding/citation from reverse-RAG). The agent's **actual** response is **not** written into the dataset — it's produced per-run when you run the experiment (step 3) as the run's output, and the evaluator scores **run-output vs. the example's reference outputs**. (So: target → example reference outputs; actual → experiment run output.)

**3. Score → run the experiment** (`score`). Apply evaluators → per-sample, per-key scores. Surface the experiment URL.

**4. Align the evaluators — "are they any good?"** (`align`) — the TRUST step, gate for everything after.
- Open the **annotation queue** (user grades the same samples) + **align-evals view** (human vs evaluator → **alignment %**). Iterate until trusted: accept@k · auto-iterate · edit eval prompts (Prompt Hub) · later. **Train/test split** so you don't overfit the judges.

**5. Fix → red→green** (`fix-green`). With trusted evals, **adjust the harness to fix any issues uncovered** at the root; re-run; confirm red→green, nothing regressed. Keep the dataset as a permanent **regression suite**.
- Opt-in (evals adjudicate, user drives): prompt / tool / harness tuning to raise scores.
- **3-strike rule:** if 3 fix attempts don't flip a failing key green, STOP — it's likely the wrong layer (architecture, or the eval itself), not the fix. Reconsider or escalate via AskUserQuestion.

**6. Optimize → swap models** (`optimize`). Now that the suite is trusted and green, sweep models to find the **cheapest / best-performing** that still passes.
- **Resolve `model: choose-for-me` HERE — REQUIRED.** Score candidate models on the eval suite → pick the cheapest passing (or highest-scoring); record `model.name` + `model.resolved:true`. Never silently ship the scaffold default.

**7. Harden the evals** (`harden`).
- **Cost:** report last experiment cost; offer to reduce it (cheaper judge, fewer/auto-selected cases) — Yes/No/Later.
- **CI:** recommend a PR-triggered CI gate that runs the suite. If a GitHub repo, offer a PR to verify e2e. Yes/No/Later.
</flow>
