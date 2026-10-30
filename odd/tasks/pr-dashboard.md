# Public PR dashboard
Standalone public repository: aiorellana502/pr-dashboard.
Status: Phase 1 (PR ledger) done and deployed. Phase 2 (issues + plain-language AI explanations) in progress.

## Specs
S1. "podemos crear un landing page se me ocurre para llevar control en que estatus esta cada uno de estos PR, y que se vaya actualizando a cada cierto momento ?"
S2. "si vamos con la 2 , me sirve para este fin" — option 2 was GitHub Actions scheduled updates and GitHub Pages hosting.
S3. "Repo nuevo: pr-dashboard (recomendado)" — selected repository: aiorellana502/pr-dashboard, public and separate from gentle-shell.
S4. "si adelante" — permission to create and work in C:\Proyectos2026\pr-dashboard.
S5. "avancemos con 1, considera tomar en cuenta los coleres de gentleman" — use Ledger structure with Gentleman colors.

## Tasks
T1 [S1,S3,S4,S5] done | route: delegated visual proposal | commit: pending | User selected Ledger, with Gentleman palette; alternatives remain illustrative.
T2 [S1,S2,S5] done | route: inline fallback after writer failure | commit: pending | app.mjs implemented (normalizeSnapshot/freshness/render, no innerHTML). node --test tests/view.test.mjs: 3/3 pass. python -m unittest tests/test_snapshot.py: 7/7 pass.
T3 [S2,S3] done | route: implementation and independent verification | commit: 93922af | Hourly cron workflow (.github/workflows/update.yml), permissions contents:read/pages:write/id-token:write. First dispatched run (40737504360) succeeded end to end (build+deploy). Verified: HTTP 200 on the public URL, site/data.json has real current PR data, no secrets/tokens in served HTML. Browser-level JS render check: installed Playwright+Chromium and ran it against the live public URL. 6/6 rows rendered, totals correct (6 total, 4 open, 2 draft), no console/page errors, first row link and state correct, freshness text "Up to date.", screenshot confirms Gentleman palette renders as designed.
T4 [S1-S4] done | route: parent delivery | commit: 93922af | Pushed to origin/main on the pre-created public remote; GitHub Pages enabled with build_type=workflow. Public URL: https://aiorellana502.github.io/pr-dashboard/ . Limits disclosed to user: schedules are best-effort, status data reflects only GitHub-reported signals.

## Specs (phase 2)
S6. "revisa si acá https://aiorellana502.github.io/pr-dashboard/ se muestra todo eso y me gustaría que tenga explicaciones de este tipo así sencillas y claras" — referring to the plain-language, grouped status summary given in chat (PRs AND issues, each with a short plain reason for its state).
S7. User chose "Sí, agregar Issues" — add a tracked-issues section alongside the existing PR ledger, same transparency/limits philosophy.
S8. User chose "Resumen con IA leyendo los comentarios reales" over a fixed template — the per-item explanation is written by an LLM reading the item's real comments, not a canned sentence per state. Provider: Gemini (user's choice). Secret name: GEMINI_API_KEY (default; confirm before first deploy). Must never block or partial-publish the core snapshot if the AI call fails (reuse existing "never publish a partial refresh" rule, extended: explanation is best-effort, core PR/issue data is not).

## Tasks (phase 2)
T5 [S7,S8] done | route: worker (backend) + parent-verified | commit: pending | scripts/update_snapshot.py: watchlist `type` field (pr/issue), collect_issue(), Gemini REST call (no SDK dependency) with caching (reuse previous explanation when the item's signal is unchanged) and graceful fallback on failure; tests/test_snapshot.py extended. Parent independently reviewed the full diff (key-leak paths, cache correctness) and reran tests: 13/13 pass.
T6 [S6,S7,S8] pending | route: worker (frontend) | commit: pending | site/app.mjs, index.html, styles.css: render an issues table, render the explanation text per row, simplify the legend copy; tests/view.test.mjs extended.
T7 [S6,S7] pending | route: parent | commit: pending | watchlist.json: add missing PRs (#2630, #2631, #2516, #2216) and new issues (#2629, #2096, #2420).
T8 [S8] pending | route: parent | commit: pending | Add GEMINI_API_KEY as a repo secret, wire it into .github/workflows/update.yml, dispatch and independently verify the live deploy.

## Log
L1 User: "podemos crear un landing page se me ocurre para llevar control en que estatus esta cada uno de estos PR, y que se vaya actualizando a cada cierto momento ?"
L2 User: "si vamos con la 2 , me sirve para este fin"
L3 User selected "Repo nuevo: pr-dashboard (recomendado)".
L4 User authorized local path: "si adelante".
L5 Initial six PRs: Gentleman-Programming/gentle-shell #2208, #2407, #2429, #2477, #2594, #2595. Hourly snapshots; schedules are best-effort. Public data only, no credentials in the browser.
L6 Repository initialized locally on feat/pr-dashboard. No remote, source or deployment exists yet.
L7 T1 visual proposal: design/pr-dashboard/{01-ledger,02-board,03-focus}.html and design.json; all three are alternatives, none selected. design/index.html links them. Worker structural checks passed: six unique PR links per artboard, no remote dependencies, manifest paths, textual status legends and focus rules. Browser rendering/accessibility not independently tested. Status data is explicitly illustrative.
L8 Local preview http://127.0.0.1:8767/ serves only design/; HTTP 200 observed. Gentle canvas tool cannot target this independent repository, so local preview used instead. Waiting for user's design selection before implementation.
L9 User: "avancemos con 1, considera tomar en cuenta los coleres de gentleman". Chosen artboard design/pr-dashboard/01-ledger.html; others are alternatives. Adapt visual design to Gentleman palette, not its original green/cream example colors.
L10 Palette reference read from gentle-shell assets/install-wizard/wizard.css: background #1a1218, surface #20161e/#241822, border #342230, text #f6eff3, muted #a78e9b, accent #f095c8/#ff76c3, success #b4e7c7, warning #e0c27a, error #ff718f, info #a9c7ee. Use readable contrast and text labels; no authentication or credentials in browser.
L11 Risk: item 5 (new Actions workflow, Pages deployment and token permissions) requires independent verification before delivery. API failures must not publish partial/misleading fresh data; retain previous deployed site by failing collection before deployment.
L12 Remote created: https://github.com/aiorellana502/pr-dashboard; gh repo create exit0. Empty repository, no push or deployment.
L13 Worker mvrh7e56-3-c30k failed before writing: child exit unconfirmed after 1000ms; capacity quarantined. No equivalent worker relaunched. Parent inline fallback wrote scripts/update_snapshot.py, tests/test_snapshot.py, watchlist.json, .gitignore. RED: Python unittest failed missing collector (exit1). GREEN: 7 unittest tests passed (exit0).
L14 Parent wrote site/index.html and site/styles.css using plum/pink Gentleman palette and tests/view.test.mjs. app.mjs not yet written. Node RED command not executed: twice rejected with 'Permission mode changed during tool admission. This action was not run; retry under the current mode.' Stopped without bypassing command admission. Workflow, independent verification, browser render and deployment remain unimplemented/unverified.
L15 Memory writes failed session registration; local feature document is current authority. Existing local preview port8767 still serves design proposals only, not the unfinished production site.
L16 New session resumed from this document. Command admission no longer blocked: node --test tests/view.test.mjs (3/3 pass) and python -m unittest discover tests (7/7 pass) both ran successfully. app.mjs implemented per view.test.mjs contract. T2 closed.
L17 Committed 93922af (681 lines, single initial-scaffold commit: collector+tests+site+workflow, no prior history to split against) and pushed to origin/main on the pre-created public remote https://github.com/aiorellana502/pr-dashboard. Enabled Pages with build_type=workflow (gh api POST .../pages) -> html_url https://aiorellana502.github.io/pr-dashboard/. Dispatched update.yml manually (run 40737504360); watching to completion before declaring T3/T4 done. Not yet independently verified.
