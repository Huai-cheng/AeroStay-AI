<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Mandatory scenario-dashboard parity

When editing scenario controls or behavior in this frontend, update the
Streamlit dashboard in `../prototype/app.py` in the same task. Also keep the
shared API, tests, both dashboard README files, and
`../UI_SCENARIO_PARITY.md` synchronized. Never add, remove, rename, re-range,
or reinterpret a scenario factor in only one dashboard. The canonical factor
list is `prototype.service.SCENARIO_CONTROL_KEYS`.
