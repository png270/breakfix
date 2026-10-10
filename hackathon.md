# Break My Fix — neatHack build record

Project: **Break My Fix** — an autonomous security agent that independently verifies whether AI-generated security patches actually remediate vulnerabilities. It addresses patches that appear correct but leave exploitable behavior.

Team: **0day**
Repository: https://github.com/png270/breakfix
Event: October 10–12, 2026

## Project overview
BookShelf is the authorized, controlled local test environment. The Break My Fix agent and dashboard are planned after BookShelf is complete.

## Architecture
- BookShelf (planned): Python, Flask, SQLite via sqlite3, HTML/CSS, built-in Jinja2 templates.
- Break My Fix (planned): Python FastAPI; React + TypeScript + Vite; HTTPX; Playwright; pytest.
- `demo-app/`: BookShelf. `backend/` and `frontend/`: agent placeholders.

## Development milestones
- Completed: official skill downloaded, inspected and installed; no downloaded scripts executed.
- Planned: environment setup, BookShelf implementation, database seed, workflow/security tests, documentation.
- Later: controlled vulnerability branches and patch PRs, autonomous agent, dashboard, sponsor evidence and demo.

## Dated build log
### 2026-10-10 — phase 1
Read the official skill and event pages. Python 3.14.6 detected. Existing repository and Entire/Codex configuration preserved. No application code written in phase 1.

## Experiments and failures
Initial skill download failed with sandbox DNS resolution; approved network download succeeded. No application tests run yet.

## Sponsor integrations
- Entire: enabled with Codex CLI; checkpoint verification pending this session.
- neatlogs: account registered (builder reported); SDK integration pending.
- cfo.ai: business planning pending; pricing, costs, revenue and runway plan required.

## Demo evidence
Pending. Local reproduction commands and verified results will be recorded after implementation. Public demo and video not created.

## Submission checklist
Published requirements checked 2026-10-10: [official event](https://neatlogs.com/hackathon), [Luma](https://luma.com/s5blr882).
- [ ] Agent completes a substantial task autonomously with verification and failure recovery.
- [ ] Evidence for neatlogs, Entire and cfo.ai; before/after agent runs.
- [ ] cfo.ai business plan covering pricing, costs, revenue and runway.
- [ ] Public repository with hackathon-dated commits (no commits authorized this session).
- [ ] Demo video at most three minutes explicitly covering all three sponsors.
- [ ] Building-in-public evidence tagged #neatHack.
- [ ] Submit via public quote post of official neatlogs X submission post with team, name, project, repo and demo.
- [ ] Confirm final cutoff on Discord. Published window: October 12, 7:00–11:55 PM IST, planned close; official submission post pending.
- [ ] Confirm team registration/check-in. Luma page currently reports registration closed; no registration action taken.

## Known limitations
Application and agent not yet implemented. No public deployment, sponsor runtime integration, business plan or submission yet. Intentionally vulnerable scenarios are future isolated local work only.

### 2026-10-10 — BookShelf implementation and verification
Completed phases 2–8 for the BookShelf scope:
- Installed the inspected official skill at `.agents/skills/neathack/SKILL.md` after protected-directory approval. No scripts from remote content executed.
- Created `demo-app/` app, six page types, CSS, tests and requirements; `backend/` and `frontend/` contain only `.gitkeep` placeholders.
- Created virtual environment using Python 3.14.6. Installed Flask 3.1.3 and pytest 9.1.1 and verified imports. Direct dependencies pinned; SQLite uses the standard library.
- Implemented signup, login, POST logout, password hashing, display name/bio/favorite genre profiles, ownership enforcement, 12-book browse/search/details and persistent reviews with author/UTC timestamp.
- Initialized `demo-app/bookshelf.sqlite3` via Flask `init-db`. Seed operation is idempotent. Database, virtual environment, environment files and Python/test caches are Git-ignored.
- Implemented parameterized SQL, Jinja2 escaping, per-session CSRF tokens, HttpOnly/SameSite cookies and form length limits. Environment secret has a documented development-only fallback.
- Ran `demo-app/.venv/bin/python -m pytest demo-app/tests -q`: **9 passed in 0.72s**. Actual coverage: authentication/validation, profiles, ownership, catalog/seed/foreign keys, SQL attack inputs, unauthenticated review prevention, stored review escaping, author identity, timestamp and persistence across recreated app instances, CSRF.
- Started Flask at `127.0.0.1:5001`; curl fetched browse and book detail pages successfully (HTTP 200). Chrome rendered the catalog/landing page, visually inspected at desktop size and a 390×844 mobile viewport. No full device matrix tested.
- Wrote README with exact setup, initialization, run and test commands.
- Entire CLI confirms enabled on main and active Codex session `01a12769-0df5-7e02-9826-ebec42b9bdf1`. `entire session info ... --json` reports 1 turn and **0 checkpoints**; `entire checkpoint list` confirms **0 checkpoints**, including network-enabled recheck. No checkpoint capture claimed.
- No application-agent scaffolding, intentional vulnerabilities, branches, PRs, commits or pushes. Existing Entire settings and Codex hooks preserved.

Implementation decisions: one Flask app factory, request-scoped sqlite3 connection with foreign keys, Flask CLI for schema/seed, CSS covers instead of image dependencies, tests with temporary databases. Favorite genre is editable alongside required profile fields. Logout is POST-only to avoid state changes on GET.

Problems and solutions: sandbox blocked `.agents` writes, package DNS and localhost socket binding; approved escalation enabled skill install, dependencies and local server. Entire's first remote checkpoint lookup could not reach remote; network-enabled retry succeeded and still showed zero checkpoints. In-app browser was unavailable; Chrome provided the visual check. No application test failures encountered.

## Updated milestone status
- Completed: official skill, environment, secure BookShelf, SQLite initialization/seed, automated workflow/security tests, desktop browser/HTTP verification, setup docs and Entire status inspection.
- Planned next: review BookShelf baseline; authorize a commit when ready; implement Break My Fix after baseline approval, integrate neatlogs runtime traces and cfo.ai business planning, then add isolated reproducible SQL-injection/stored-XSS scenarios and patch PRs when explicitly requested.

## Updated demo evidence
Reproduce locally using README commands. Automated suite has nine passing tests; localhost catalog and book details returned HTTP 200. Desktop and 390px mobile Chrome previews inspected. No public URL, video, public evidence upload or submission created. Entire active session is confirmed; checkpoint evidence remains outstanding.

## Updated sponsor integrations and limitations
Entire enabled with Codex CLI, active session confirmed, zero checkpoints currently. neatlogs account registration is builder-reported; no SDK/runtime evidence yet. cfo.ai business planning remains pending. BookShelf is a local demo, not a hardened production service: no recovery, rate limiting or moderation. Agent/dashboard and execution-based Playwright tests remain future work. Submission items above remain unchecked until supporting evidence exists.

### 2026-10-10 — intentionally vulnerable BookShelf baseline

Completed verification before changes: main was clean, fetched origin, and HEAD matched origin/main at `e9fe1dbb608eae7af195fec7455a1c0ffc4746d4`. Secure BookShelf suite: **9 passed in 0.67s**. Created `demo/vulnerable-bookshelf` from that exact commit; main has not been modified.

This branch exists solely as the owned, isolated local baseline for later security-fix PR verification. Two deliberate changes:
- Search SQL uses direct interpolation of `q`. Searching `no-such-demo-book` finds nothing; `no-such-demo-book' OR 1=1 -- ` returns all 12 books through the normal endpoint.
- Book-detail reviews use Jinja2 `safe`, serving stored review text as trusted HTML. The harmless `<script>document.documentElement.dataset.bookshelfXss="demo-only";</script>` marker persists and is returned unescaped to subsequent visitors. Profile rendering stays escaped.

No other security controls were disabled: authentication, CSRF, password hashing, profile ownership, bound queries in other routes and foreign keys are preserved. No external targets or exfiltration payloads used.

Added four clearly named vulnerable baseline tests for normal search, injected search, normal review persistence and stored script HTML. Preserved both original secure regression tests as strict xfails because their protections are intentionally absent on this branch. All applicable tests ran: `demo-app/.venv/bin/python -m pytest demo-app/tests -q -rx` → **11 passed, 2 xfailed in 0.81s**. The seven unaffected original tests still verify normal authentication and other controls. No unexpected failures. SQLite files remain temporary/ignored. Browser JavaScript execution was not tested in this session; HTML-level stored-XSS evidence is confirmed. README records local reproduction steps.

Planned use: future isolated fix PRs will target this baseline, restore secure regression expectations and let Break My Fix verify a complete SQL-injection fix versus an incomplete stored-XSS fix. Agent, dashboard, fix branches and PRs remain unimplemented. neatlogs SDK and cfo.ai business planning remain pending. Entire commit association will be checked after the authorized commit; no evidence claimed in advance.

Issue encountered: sandbox blocks Git metadata writes; approved access used for fetch/branch operations. No implementation errors encountered. This branch must remain local-demo-only and must not be merged into main or publicly deployed.
