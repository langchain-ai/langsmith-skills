---
name: improve-agent
description: "INVOKE when the user runs /improve-agent, or wants to close the feedback loop / self-improve / continuously improve an agent. The Improve phase of the ADLC — works standalone or as a step of /productionalize-agent. Wires failing traces + 👎 feedback back into the dataset; links LangSmith Engine."
version: 1.0.0
allowed-tools: [Read, Write, Edit, Bash, AskUserQuestion, WebFetch]
triggers: ["improve my agent", "close the loop", "self-improve", "auto-improve my agent"]
---

<oneliner>
Close the loop so the agent gets better over time: failing traces + thumbs-down feedback → annotation queue → dataset → CI.
</oneliner>

<entry>
Standalone drop-in. On entry:
1. Load `.adlc.json`; if absent, bootstrap by inspecting the agent + traces; mark earlier phases done.
2. **Prereq: tracing + evals + monitoring** (the loop connects existing pieces). Missing one → point to `/test-agent` (evals) or `/monitor-agent` (online evals) first.
3. Follow the SHARED conventions in `../productionalize-agent/SKILL.md`. Teaching: `../productionalize-agent/scripts/teach.py --print improve`.
</entry>

<prereqs>
A traced agent with an eval suite and (ideally) online monitoring.
</prereqs>

<flow>
**Iron Law — only improve against evals you trust.** Optimizing toward an unaligned metric makes the agent worse, confidently.

- **self_improve?** yes/no. Requires tracing + evals + monitoring (gate here). If yes, wire the loop: online-eval failures → failing traces → dataset → re-eval (CI guards it).
- **Auto-route negative feedback?** Offer a `/runs/rules` automation that adds any **thumbs-down**-feedback trace to the annotation queue (filter on the thumbs-down feedback key → add-to-annotation-queue action). Closes the human-feedback side: 👎 → triage queue → dataset → CI. Wire now / skip / defer → `pending_reminders`. (Confirm the app's thumbs-down feedback key.)
- **LangSmith Engine** auto-proposes assertions/examples from recurring production issues (and prompt/model fixes). **Can't be enabled via API — link the user to it in the LangSmith UI**; defer → `pending_reminders` if "later".
- Optional, evals-adjudicated, user-driven: harness tuning / model selection to raise scores. (Improving the agent's IQ is the user's call; this skill wires the loop.)
- **success_criteria?** open text (feedback signals + online evals).
</flow>
