---
name: deploy-agent
description: "INVOKE when the user runs /deploy-agent, or wants to ship / put an agent into production / give it a frontend. The Deploy phase of the ADLC — works standalone or as a step of /productionalize-agent. Picks a deployment-client frontend, auth, and ships to LangSmith Deployment or your own infra."
version: 1.0.0
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion, WebFetch, Skill]
triggers: ["deploy my agent", "ship my agent", "put my agent in production", "add a frontend"]
---

<oneliner>
Put the agent where its users are: a thin deployment-client frontend + auth, shipped to LangSmith Deployment (or your infra).
</oneliner>

<entry>
Standalone drop-in. On entry:
1. Load `.adlc.json`; if absent, bootstrap by inspecting the agent + traces and mark earlier phases done.
2. **Prereq:** a working, traced agent. Recommend (don't require) trusted evals + a CI gate first — if absent, offer a quick `/test-agent`, or proceed and add CI later.
3. Follow the SHARED conventions in `../productionalize-agent/SKILL.md`. Teaching: `../productionalize-agent/scripts/teach.py --print deploy`.
</entry>

<prereqs>
A working, traced agent. For an external/production audience: confirm auth.
</prereqs>

<flow>
**Iron Law — the frontend is a client of the deployment, never the agent itself.** The agent runs ON the deployment; the UI only streams.

SKIP the public-facing questions if `host=local-only`.
- **host?** langsmith-deployments (recommended) · own-infra · local-only / skip-for-now (defer the actual ship → `pending_reminders`; the agent is deploy-ready, cloud is a connect step).
- **auth?** (only if hosted externally) oauth · api-key · sso · none.
- **frontend?** Tiered choice, ranked by involvement vs production-readiness. All except "own" and "none" are thin **deployment CLIENTS** (point at the deployment URL; agent runs ON the deployment, UI only streams; same code repoints local→cloud by changing one URL):
  1. **I have my own** — wire it to the deployment URL via `langgraph_sdk` / REST.
  2. **CopilotKit** — most involved, most production-ready. Needs **Node** + `CopilotKitMiddleware()` in the agent graph (two-sided). Uses `agents: { name: new LangGraphAgent({ deploymentUrl, graphId }) }` (`langGraphPlatformEndpoint` deprecated in runtime 1.6x).
  3. **assistant-ui** — medium; a headless React **component library** you build into your own app (wire `useStream` + render `<Thread/>`). First-class LangGraph support, deep customization.
  4. **agent-chat-ui** — low effort; a **prebuilt drop-in chat app** (Next.js) for any LangGraph agent. Clone + `pnpm dev` pointed at the deployment URL + graph id, or use the hosted `agentchat.vercel.app`. Great for fast/standard chat; for prod use its API-passthrough/auth path.
  5. **Streamlit client** — Python, **no Node**; a thin `langgraph_sdk.get_client(url=...)` client. (NOT in-process — that bypasses the deployment.)
  6. **No frontend** — LangGraph/LangSmith Studio against the deployment. Demo only.
- **hardening?** evals+ci · smoke · none. (evals+ci → emit `.github/workflows/` that runs the eval suite on PRs.)
- **Ship the backend:** LangSmith Deployment (UI connect / `langgraph deploy`) · own infra (`langgraph build` → container) · skip. Surface every URL; record to `resources[]`.
- **Defer deploy mechanics to the official skills (current commands/flows):** invoke **`managed-deep-agents`** for LangSmith-managed Deep Agents (deepagents-cli, Python/TS SDKs, React `useStream`, MCP tools, interrupts) and **`langgraph-cli`** for `langgraph build` / `deploy` / `langgraph.json`. This skill owns the deploy *decisions* (host, auth, frontend, CI); they own the exact commands.
</flow>
