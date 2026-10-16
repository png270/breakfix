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

### 2026-10-10 — bounded verification backend (no live analysis)
Applied the neatHack build-log skill. Initial checkout was clean on `fix/xss`; switched to existing main without modifying any branch commits. Main matched its local origin tracking branch and secure BookShelf tests passed (**9 passed in 0.69s** before implementation). Entire remained enabled, with configuration/hooks unchanged. CLI reports tracking divergence after branch switching; no repair/configuration changes made.

Implemented the FastAPI backend and explicit schemas for pinned PR data, hypotheses, validated tool actions, observations, evidence and verdicts. Added GitHub ingestion with exact app/template allowlist and source comments removed; tests, README, hackathon log, PR descriptions/commit labels and prewritten demonstrations do not reach model context. Base/head are rechecked after ingestion. No conclusions are based on PR numbers.

Added configurable OpenAI-compatible HTTPX function-calling adapter, per-run bounded state and adaptive OBSERVE → REASON → SELECT → EXECUTE → EVALUATE loop. Limits: eight steps, one bounded retry for model/read-only tools, no automatic mutation retries, per-tool and overall timeouts. Verdicts require actual structured execution evidence; source inspection alone cannot verify a fix. Deterministic comparison and temporary JSON-backed replay tests are implemented. Generated tests are not automatically executed.

Security tools: allowlisted inspection; bounded fixed-target HTTP with controlled account/CSRF; Playwright controlled signup/logout/login, review submission, anonymous revisit and harmless fresh marker observation. Docker worker runs tools inside a preapproved SHA-attested immutable image, with network disabled, no host mounts/secrets/socket, nonroot/read-only execution, resource limits, cleanup and self-expiry. No arbitrary shell/Python execution tool or host fallback. Model-requested HTML execution is confined to the isolated browser. Image approval is an operator trust boundary and not automatic source provenance proof.

Created `backend/.venv` with Python 3.14.6; installed FastAPI 0.143.0, Uvicorn 0.54.0, Pydantic 2.14.0, HTTPX 0.28.1, pytest 9.1.1 and Playwright 1.63.0. All imports verified; `pip check` reports no broken requirements. Recorded full installed versions in `backend/requirements.lock.txt`. No neatlogs SDK, paid API key, real model call, host browser test, or full live PR analysis used.

Verification: backend unit/component suite **50 passed, 1 warning in 0.14s**. GitHub/model/Docker/browser observations are mocked; HTTP component uses MockTransport; full API component uses synthetic PR data and mocked tools. Coverage includes URL restrictions, ingestion failures/races/size limits, evaluation exclusions, action validation, adaptive observations, evidence requirements, retries, write retry prevention, tool/overall timeouts, budget exhaustion, sandbox failure, approval/attestation and observability gates. Real secure BookShelf suite remains **9 passed in 0.67s**. Uvicorn localhost smoke test: `/health` HTTP 200 with live analysis false; `/api/analyze` HTTP 503 before GitHub/model activity. TestClient emits Starlette's HTTPX deprecation warning; no unexpected test failures remain.

Problems/fixes: initial package install failed with sandbox DNS; approved install succeeded. Sandbox blocked loopback listener; approved Uvicorn start succeeded. A context-exclusion test incorrectly used Python-comment syntax in HTML; corrected its fixture to valid Jinja comments. Docker CLI exists but daemon socket is absent, so **Docker isolation is not operational** and no container/Chromium success is claimed. A reviewed Docker recipe and empty example approval manifest are provided; no images were built. Chromium sandbox/seccomp compatibility remains unverified.

Added backend README/config example and root README architecture/setup notes. Environment files, virtual environments, generated tests and private approval manifests are ignored; the nonsensitive `.env.example` is permitted. Frontend remains a placeholder. No commits or pushes authorized or performed in this backend session. Existing demo/fix branches and Entire/Codex configuration preserved.

Next prerequisites before the first live PR analysis: integrate neatlogs at the observer interface, GitHub/run/model/tool/retry/verdict events plus provider usage and sandbox lifecycle spans; initialize a request-scoped trace and redact secrets; wire a ready observer into FastAPI. Then configure a tool-capable local/sponsor model, start Docker, review/build/approve commit-matched fixtures and verify browser/runtime isolation. API live analysis remains disabled until the real observer is wired. cfo.ai business planning remains pending; no evidence for those sponsor integrations fabricated.

### 2026-10-11 — Docker fixture validation, Chromium blocked
Docker Desktop daemon is operational, version 29.0.1 on Linux ARM64. Initial Docker socket access was denied by the workspace sandbox; approved daemon access succeeded. Inspected sandbox, worker, replay, Docker recipe/configuration and backend documentation. Existing backend work remained uncommitted on main; no PR branch changes made.

Built two reviewed fixtures using an official immutable Python base (`python@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170`) and the locked runner dependencies. Temporary build contexts contained only exact BookShelf Git blobs plus the trusted runner; no PR code was executed on host. Remote heads confirmed:
- PR #1 / fix/sqli: `b0b635eba99f24a3641f729c1a95864a2ee36c9d`, image `sha256:1f15e8c7ecc7ee8c8baa0b64f3b45156507811dc0a55845985d23a7d07b77d9a`.
- PR #2 / fix/xss: `b855cb68e745767153506f7dab9abf368a11e403`, image `sha256:81710a0aead1350872a1952e0ad872ff1016a4499567b6e9906ca882b56681d1`.

SHA labels verified and exact image IDs registered in ignored `backend/fixture/approvals.json`. Sanitized per-file snapshot hashes and runtime results saved in `backend/fixture/validation-report.json`. Added a deterministic component smoke script; no agent/model invocation, exploit payloads or inferred security verdicts.

Both fixtures passed startup, restriction probes, bounded HTTP search connectivity, command timeout enforcement and teardown (**10 component checks passed across two fixtures; 2 browser checks blocked**). Inspected runtime settings: privileged false; network none; no host binds, mounts or published ports; read-only root; UID 10001; cap-drop ALL; no-new-privileges; CPU quota 1; memory 768 MiB; PID limit 128. Runtime probes confirmed effective capabilities zero, read-only fixture files, no Docker socket, no external route/connectivity and actual cgroup CPU/memory limits. Container environment contained only the image's six declared runtime/base keys, no injected host secrets. Worker container gate/no-host-fallback and 150-second self-expiry inspected in code; full self-expiry interval was not waited out. All validation containers removed.

Playwright/Chromium is installed in both images, but launching with `chromium_sandbox=True` failed with **“No usable sandbox.”** Browser tool workflow did not execute. Retained all security restrictions: no privileged mode, extra capabilities, unconfined seccomp or `--no-sandbox` workaround. Compatible Chromium sandbox/runtime support remains the blocker to browser-dependent live execution.

Existing backend suite rerun: **50 passed, 1 Starlette/HTTPX deprecation warning in 0.19s**. Docker fixture execution is now verified for HTTP/lifecycle, while browser execution is explicitly unverified/blocked. Updated backend docs to distinguish this state from the earlier unavailable daemon. No complete agent, live PR analysis, LLM API call, neatlogs installation, commit or push. neatlogs interface integration can proceed independently; first live browser-dependent analysis must await a reviewed sandbox-compatible runtime and model configuration.

### 2026-10-15 — recovery, Python environment and neatlogs delivery

Read repository/build/backend documentation and the neathack skill; inspected configuration, modules, observability/agent/LLM code and tests. Preserved existing dirty main checkout, PR branches, credentials, Entire settings and Codex hooks. Existing implementation already included request-scoped tracing, root/child correlation, structured lifecycle and model-usage events, strict redaction/export masking, graceful shutdown and eight observability tests; earlier README statements were stale. The LLM adapter uses HTTPX OpenAI-compatible tool calls, not LiteLLM. No real provider compatibility is established.

Official PyPI metadata still requires Python >=3.10,<3.14. Existing `.venv` had Python 3.14.6 and unsupported legacy neatlogs 1.1.8. Created and validated a Python 3.13.15 staging environment with neatlogs 1.4.27 before preserving the old environment at ignored `backend/.venv-python314-backup` and creating the replacement `.venv`. Refreshed the lockfile with all 83 installed packages, including previously omitted neatlogs. Dependency check passes; final-path backend suite: **58 passed, one existing Starlette/HTTPX deprecation warning in 0.65s**. Environment backups are excluded from Git and Docker build context.

SDK Doctor local validation passes. Initial sandboxed probe failed DNS/export and readback with `BACKEND_CONNECTION_FAILED`; approved network execution passed exact-trace visibility, finalization, four-span hierarchy, attributes, I/O, metadata and typed-token checks. Generated fresh application synthetic traces using fake model/sandbox components only. Readback returned HTTP 200, status success, workflow break-my-fix, 18 spans in the configured key's project (ID retained locally); export failures and queue/mask drops were zero. Added repeatable synthetic `--verify --project-id` readback and loss-counter reporting, with nonzero exit on failure. No credentials or raw trace payloads recorded here.

Default exporter endpoint is https://ingest.neatlogs.com/v1/traces; authenticated exact-trace retrieval uses /api/traces/v3/:traceId. Key selects project; workflow name does not select project. `.env` is not loaded by the backend; synthetic helper explicitly loads only its neatlogs key. Sandbox DNS is a confirmed failure cause in this session; earlier missing-trace causes remain unproven. API visibility in the configured key's project is confirmed; intended project name/dashboard selection awaits builder confirmation because Chrome presents a profile chooser.

Updated setup/diagnostic documentation. Live-analysis gate remains closed. No full live agent, PR analysis, real LLM call, Docker build/restriction changes, commits or pushes. Chromium sandbox compatibility and actual model tool-calling remain blockers; recommended next work is resolve Chromium under the existing isolation policy, then separately authorize provider compatibility testing before enabling live analysis. Applied `.agents/skills/neathack/SKILL.md`; event/Luma pages were read as required, with no submission or eligibility claim.

### 2026-10-15 — separate Chromium worker and verified isolation

Inspected Docker lifecycle, immutable fixture worker, browser tool, approvals and tests before changes. Followed official Playwright non-root/seccomp guidance and Docker internal/isolated bridge documentation. Reproduced sandboxed Chromium initialization with current Moby default-derived policy: namespace allowances exposed a second chroot denial under cap-drop ALL; adding chroot for the browser alone allowed launch without capabilities or sandbox-disable flags. Playwright's older bundled profile failed Docker 29.0.1 initialization; vendored the current official default with provenance/license and an automated exact-delta check.

Implemented a dedicated browser-only image/worker and a per-run internal bridge in isolated gateway mode. The application retains default seccomp and both existing immutable image IDs/commit labels. A fixed trusted launcher changes only Flask's bind address; application source and intended vulnerabilities are unchanged. Browser code has a separate immutable approval tied to its runner-content and seccomp hashes. Instructions remain bounded validated JSON over docker-exec stdin; no listening control server or arbitrary model execution interface. Preserved non-root, read-only filesystems, zero capabilities, no-new-privileges, one CPU, 768 MiB RAM, 128 PIDs, no host mounts/socket/secrets/published ports and 150-second expiry. Blocked external DNS, non-fixture routes and all WebSockets. Cleanup covers partial startup, exceptions, tool deadlines and cancellation, retaining resource references on removal failures.

Built only trusted local runner files in a minimal context on the digest-pinned official Playwright v1.63.0 base. Reviewed image metadata and recorded its immutable local browser approval; existing fixture approvals were unchanged. Browser image: `sha256:761990d1f254b20595f88e0a97ecfd8168ac74c3efea7c16765c805d08162e9e`.

Verification: **79 backend tests passed**, one existing Starlette/HTTPX warning, in 1.36s. **16 real Docker component checks passed across both approved fixtures**: startup, isolated network, runtime restrictions, sandboxed Chromium/fixture navigation, controlled signup/login/review/anonymous-revisit flow, HTTP worker preservation, forced tool-timeout cleanup and teardown. Probes confirmed seccomp mode 2, no-new-privileges, zero capabilities, read-only filesystems, cgroup limits, no default route, DNS blocking and failed connections to external/metadata/Docker-host addresses. Chromium itself could not navigate to external/metadata endpoints. Docker inspections confirmed no privileged mode, host/volume mounts, socket or published ports. No test containers or temporary networks remained. Sanitized current evidence: [browser validation report](backend/browser/validation-report.json); original fixture report retained as historical.

Limits: shared Linux kernel, browser namespace syscall attack surface, Docker daemon trusted, address probes are samples; abrupt backend death can leave stopped containers/network objects despite worker self-expiry. Current source/approval matching prevents silently using stale workers. Live API gate stays closed pending real provider compatibility and review. No live LLM, GitHub PR analysis/modification, .env edits, commits or pushes. Existing dirty main work and PR branches preserved.

### 2026-10-15 — dependency compatibility and pre-commit audit

Split exact runtime inputs and SHA-256 hash locks by execution environment: Python 3.13 backend orchestration (76 packages), Python 3.13 development/tests (83), Python 3.14 fixture/HTTP worker (18), Python 3.12 browser worker (8). Retained all existing pinned versions. Updated Dockerfiles to install only each worker's hash lock; future fixture builds no longer install neatlogs, FastAPI, pytest, Playwright or Chromium, and copy only the trusted HTTP worker/schema files. Browser dependency inputs are now covered by its content approval digest.

Validated hash-locked backend runtime/development and fixture environments independently with dependency checks. Backend imports without Flask/Playwright/pytest. Downloaded all Linux ARM64 Python 3.14 fixture wheels with hash checks, then installed/imported the 18 packages and trusted worker offline in an isolated disposable Linux Python 3.14.8 container without loading BookShelf source. Initial validation used noexec temporary storage, which prevented loading a native extension; repeating this dependency-only check with executable temporary storage passed. Production app/browser sandbox policies were unchanged.

Built a new browser-only image with the hash-locked eight-package closure and verified pip check under Python 3.12. Image: `sha256:7f7dc0f4d024566c7894a403906209b82c93dc6b45166671d96f75ea1f62e837`. Previous browser image retained. Both approved BookShelf images and commit attestations were unchanged, with the private fixture manifest byte-for-byte preserved; neither fixture image was rebuilt. New browser-only approval remains local/ignored. Future fixture recipe changes require separate operator review/build/approval.

Backend tests in the clean development environment: **86 passed**, one existing Starlette/HTTPX deprecation warning. All **16 Docker component checks passed** with the new browser image against both original fixtures, including sandboxed launch, network denial, HTTP/browser workflows and timeout cleanup. Added dependency-separation, hash-policy and approval-digest regression tests. Live analysis remains disabled; no real provider or autonomous PR workflow ran.

Reviewed an initially empty index (no partial staging survived the interrupted audit). Expanded Git/Docker ignore rules for credentials, environments, private approvals, caches, generated browser output and macOS metadata; sanitized validation evidence remains intended documentation. Removed unnecessary neatlogs tenant identifiers from new documentation. Credentials, .env and both GitHub PRs were untouched; no commit or push. See [dependency environments](backend/DEPENDENCIES.md) for reproduction and platform limits.
