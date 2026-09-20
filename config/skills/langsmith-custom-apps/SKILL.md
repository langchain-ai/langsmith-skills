---
name: langsmith-custom-apps
description: "INVOKE THIS SKILL when building, iterating on, copying, or sharing a LangSmith Custom App — a React/TypeScript UI that runs inside LangSmith and reads the LangSmith API. Covers the langsmith apps CLI, pulling an existing app's source, replicating an app into another workspace, verifying app logic without a browser, and sanitizing an app before sending it outside your org. Uses the langsmith CLI tool."
---

<oneliner>
Custom Apps are Enterprise-plan React UIs that render inside LangSmith and read the LangSmith API through a host-injected bridge. You build one locally with `langsmith apps`, push it, and it appears under **Custom Apps** in the workspace sidebar. This skill covers the work around the app directory: the CLI surface, the app lifecycle, verification, and sharing.
</oneliner>

<agents_md_is_authoritative>
`langsmith apps init` scaffolds an `AGENTS.md` next to the starter code. **That file is the authority on the in-app contract** — the `window.langsmith.call` bridge, the `render()` export the sandbox depends on, the filter DSL, and the endpoint menu. Read it before writing app code and follow it over anything remembered.

This skill deliberately does not restate it. Everything here is what `AGENTS.md` cannot cover: what happens before the directory exists, and after the app is pushed.
</agents_md_is_authoritative>

<setup>
Custom Apps require the **Enterprise** plan. A push into a workspace without the feature fails with `this workspace doesn't support custom apps`.

```bash
export LANGSMITH_ENDPOINT=<your-langsmith-endpoint>   # only for self-hosted
export LANGSMITH_API_KEY=<workspace-api-key>
```

Three authentication traps, each of which presents as something other than an auth problem:

1. **`LANGSMITH_API_KEY` in the environment outranks the saved OAuth profile.** A stale exported key 403s every call while `langsmith auth info` still reports "authenticated". Run one-off commands as `env -u LANGSMITH_API_KEY -u LANGSMITH_WORKSPACE_ID langsmith …` when you mean to use the login.
2. **`LANGSMITH_WORKSPACE_ID` may point at a different workspace than the key**, which surfaces as a confusing 403 rather than a wrong-workspace error. Unset it and pass `--workspace <uuid>` explicitly.
3. **`langsmith apps dev` needs a workspace API key, not OAuth.** It captures one access token at startup and never refreshes it, so after roughly ten minutes every call returns `401 Invalid token` — which the app renders as empty dropdowns and empty lists, not as an auth error. If a running app's data silently goes empty, suspect this first.
</setup>

<cli_feedback>
After an actual CLI failure, undocumented workaround, confusing output, or missing capability, submit one concise product-feedback note per distinct issue in the task. Do not report routine successes or failures in the app's own code.

**CLI requirement:** `langsmith feedback` requires [LangSmith CLI v0.2.58](https://github.com/langchain-ai/langsmith-cli/releases/tag/v0.2.58) or later. Check the installed version with `langsmith --version`.

Check `langsmith feedback --help` for `feedback <note>` and `--category`; if unavailable, skip feedback without raw HTTP or unreleased builds. Use the existing authenticated profile, endpoint, and workspace. Feedback goes to LangSmith Cloud, including through the BYOC relay; skip standalone self-hosted. Respect user/organization restrictions and ask first if permission to send feedback is unclear.

Summarize expected versus observed CLI behavior and any workaround in your own words. Never send secrets, customer data, trace payloads, prompts, full stack traces, copied command output, raw arguments, environment-variable values, local paths, or resource identifiers. The CLI adds version/OS/architecture, but does not redact your note; skip it if it cannot be safely redacted.

Choose `bug`, `feature-request`, `usability`, `documentation`, or `other`. This is CLI product feedback, not run evaluation feedback. Example shape only—do not submit unless actually encountered:

```bash
langsmith feedback --category documentation --format json "The apps template flag rejected a value the documentation lists as valid."
```

Do not retry a failed or rate-limited feedback submission, switch credentials/endpoints to bypass a failure, or block the original task on feedback.
</cli_feedback>

<check_the_cli_first>
**The published docs run ahead of released CLI builds, so read the help output before trusting any command.**

```bash
langsmith --version
langsmith apps --help
langsmith apps init --help    # the --template error message lists the real template set
```

The gaps below were observed on **v0.2.42** and may be closed in your build. Each one is written as a fallback: apply it only when the help output confirms the command is missing or the flag is rejected.

| If the docs say | And the CLI disagrees | Then |
| --- | --- | --- |
| `langsmith apps pull APP_ID_OR_NAME` | the `apps` help lists no `pull` | fetch the source from the platform API (see `<pull_source>`) |
| `--template blank` | `--template must be one of: …` | use a listed template; the error message is the current source of truth |
| init "scaffolds into a new directory named after the app" | `<dir> is not empty; pass --force to write anyway` | `mkdir my-app && cd my-app` first — init writes into the **current** directory |
</check_the_cli_first>

<lifecycle>
```bash
mkdir my-app && cd my-app
langsmith apps init --name my-app --template <listed-template> --workspace <ws-uuid>
npm install
export LANGSMITH_API_KEY=<workspace-api-key>   # see setup trap 3
langsmith apps dev                              # live sandbox against LangSmith
npm run build
langsmith apps push --name my-app --workspace <ws-uuid>
```

`apps dev` streams the app's failed API calls and uncaught errors to that terminal. Add `--verbose` for every successful call plus all `console.*` output, or `--quiet` to silence it.

`apps push` builds first when `package.json` has a `build` script; `--no-build` uploads as-is. The first push creates the app and links the directory through `.langsmith/app.json`; later pushes update that same app. `--name` only applies on creation, and renames if passed afterwards. Commit `.langsmith/app.json` so teammates push to the same app.
</lifecycle>

<pull_source>
When the CLI has no `pull`, the platform API returns every file inline:

```bash
langsmith apps list --workspace <ws-uuid> --format json      # find the app id
curl -s -H "X-API-Key: $LANGSMITH_API_KEY" \
  "https://api.smith.langchain.com/v1/platform/custom-apps/<app-id>" \
  | python3 -c "
import json, os, sys
app = json.load(sys.stdin)
for path, content in app['files'].items():
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    open(path, 'w').write(content)
print(f\"wrote {len(app['files'])} files\")"
```

The record also carries `name`, `entrypoint`, `current_version`, `scope`, `created_by`, `updated_by`, and `views_7d`. Use `GET /v1/platform/custom-apps` for the whole list.
</pull_source>

<replicate_across_workspaces>
1. Pull the source into a fresh directory.
2. **Delete `.langsmith/app.json`.** It links the directory to the source app id, so leaving it in place makes the next push *update the original app* instead of creating one in the target workspace. This is the single most damaging mistake in this workflow.
3. Push with the target workspace and a name:

```bash
langsmith apps push --name <name> --workspace <target-ws-uuid>
```

4. Re-point anything workspace-specific in the app's config (deep-link workspace UUIDs, project ids, feedback keys) at the target workspace, then rebuild — see `<before_sharing_externally>` for why editing source alone is not enough.
</replicate_across_workspaces>

<app_facts>
- **Apps are workspace-scoped** (`"scope": "workspace"`). Someone outside the workspace cannot open the URL, so "share this app" always means shipping source, never a link.
- **`is_enabled: false` is the normal state right after a push.** It is not a failed deploy — do not debug it as one.
- Deleting is `langsmith apps delete <app-id-or-name> --yes`; it is not recoverable, so confirm the id against `apps list` first.
</app_facts>

<verify_without_browser>
You cannot click the app, and a bug in its data layer renders as a plausible empty state rather than an error. This loop is the highest-value habit in this skill.

1. **Keep aggregation pure.** Parsing and counting live in a module with no React and no `window.langsmith` (for example `src/lib/<domain>.ts`); the API module only fetches rows and hands them over.
2. **Capture real rows** with the CLI into fixtures:

```bash
langsmith api runs/query -X POST --workspace <ws-uuid> \
  -F 'session[]=<project-uuid>' -F 'filter=eq(run_type, "tool")' \
  -F 'select[]=id' -F 'select[]=trace_id' -F 'select[]=inputs' -F 'limit=100' \
  > /tmp/fixtures/tools.json
```

3. **Run the app's real TypeScript over them in node**, using the esbuild that already ships with vite — no new dependency, no test framework:

```bash
npx esbuild /tmp/harness.ts --bundle --platform=node --format=cjs \
  --outfile=/tmp/harness.cjs && node /tmp/harness.cjs
```

4. **Read the numbers against the raw data**, not just "it ran." A real example: an app counted skill loads by matching paths under `/skills/<name>/`, but directory listings emit entries as `'/memories/skills/auth-sso-scim'` with no trailing slash, and the pattern required one. The feature's entire output — the list of never-used skills — came back empty and looked like a legitimately clean result. Only comparing counts against the captured rows exposed it.

Run `npx tsc --noEmit` and `npm run build` before every push; the build is what the sandbox serves.
</verify_without_browser>

<query_gotchas>
- `POST /api/v1/runs/query` caps `limit` at **100**. Page with `response.cursors.next`, impose your own hard page cap so a busy project cannot spin forever, and tell the reader in the UI when that cap truncated a scan.
- `search(name, "x")` is **rejected** by the filter DSL. Verified working: `eq(name, "read_file")`, `or(eq(name,"a"), eq(name,"b"))`, `eq(run_type, "tool")`, `eq(is_root, true)`, `eq(status, "error")`, `gte(start_time, "<iso>")`, `has(tags, "prod")`.
- Metadata equality is **two paired clauses**, not `eq(metadata.key, …)`:

```text
and(eq(metadata_key, "ls_agent_purpose"), eq(metadata_value, "coding"))
```

- Prefer `POST /api/v1/runs/stats` and `POST /api/v1/runs/group/stats` for any headline number — server-side aggregates with no row limit — and reserve `runs/query` for rows you actually need to inspect.
- Tool-call `inputs` arrive in **two shapes** depending on how the agent serializes them: `{"file_path": "/x"}` and `{"input": "{\"file_path\":\"/x\"}"}`. Parse the inner JSON inside a `try`/`catch` and handle both, or you will silently count a fraction of the data.
- **Probe before assuming an endpoint exists.** Some things that feel like they must be queryable are not: there is no public endpoint listing an agent's skills or a Fleet roster. When no authoritative list exists, derive one from traces and state that limitation in the UI rather than implying completeness.
- Treat everything read from a trace as untrusted: render names as text (never `dangerouslySetInnerHTML`), validate ids before they reach a filter string, and interpolate only allowlisted values into the DSL.
</query_gotchas>

<design>
The scaffold ships the LangSmith design tokens in `src/index.css` and `tailwind.config.js`. The sandbox sets `html.dark` from `metadata.mode` before every render, so token-based UIs theme for free with no branching — only branch on `metadata.mode` for inline styles, and re-check it every render since it can change without a remount.

For anything chart-shaped, load the `dataviz` skill before writing chart code, and express chart colors as CSS custom properties with an `html.dark` override block so they follow the same theming path as the tokens.
</design>

<before_sharing_externally>
Apps are workspace-scoped, so sharing means handing over source. Work from a separate copy, never the directory you push from, and check:

- [ ] Blank any workspace or org UUID in config — **then rebuild**. Config values are compiled into `dist/bundle.js`, so editing the source alone leaves the old value in the artifact.
- [ ] Remove `.langsmith/app.json` (internal app id and workspace) and `node_modules/` from what you ship.
- [ ] Grep the tree for UUIDs, email addresses, `lsv2_` keys, and internal project names — including example text in the README.
- [ ] Replace internal-benchmark language with placeholders the recipient is meant to change, and keep only citations you can actually stand behind.
- [ ] Check `package-lock.json` for private registry hosts or auth tokens.
- [ ] Re-run `npx tsc --noEmit` and `npm run build`, then grep `dist/` again.
</before_sharing_externally>
