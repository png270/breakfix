# Break My Fix backend

The backend implements a bounded, tool-using patch investigation loop. **No live PR analysis or real LLM call has been executed.** The default API deliberately blocks live analysis; neatlogs is integrated and synthetic delivery is verified. Docker Desktop is operational and both exact-commit fixtures remain immutable. A separate approved browser worker now launches sandboxed Chromium and passes component checks against both fixtures. Live analysis remains disabled; there is no host fallback. See [browser architecture and validation](browser/README.md).

## Setup and run

From the repository root:

```sh
python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements.lock.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

`GET /health` is operational. `POST /api/analyze` accepts `{"pr_url":"https://github.com/png270/breakfix/pull/<number>"}`. Invalid/noncanonical repository URLs return 422. With the live-analysis gate closed, a valid URL returns 503 without fetching GitHub, calling a model or starting a sandbox. Once enabled, errors produce structured INCONCLUSIVE results; one analysis runs at a time. Keep the API on loopback; it has no public-service authentication or distributed job queue.

Install test dependencies with `backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements-dev.lock.txt` from the repository root. Run tests separately from BookShelf because both packages use `app` as their import root:

```sh
cd backend
.venv/bin/python -m pytest -q
```

From the repository root, BookShelf tests remain:

```sh
demo-app/.venv/bin/python -m pytest demo-app/tests -q
```

Runtime dependencies are FastAPI, Uvicorn, Pydantic, HTTPX and neatlogs. Pytest and host Playwright imports belong to the separate development lock. See [dependency environments](DEPENDENCIES.md) for the fixture and browser locks. The OpenAI-compatible client is implemented with HTTPX; no paid-provider SDK/key is required. `requirements.lock.txt` records the orchestration runtime; `requirements-dev.lock.txt` adds test dependencies. Host Chromium was not installed: browser tests run in the dedicated restricted browser worker, never in a host fallback.

## Modules and execution flow

- `app/github.py`: validates only png270/breakfix PRs; reads metadata, changed-file patches and head-SHA-pinned application source. Rechecks base/head after ingestion to reject a moving PR.
- `app/schemas.py`: strict Pydantic request, hypothesis, tool-action, observation, evidence and verdict contracts; rejects extra fields.
- `app/state.py`: per-run hypotheses, action/observation history, errors, attempts, steps and wall-clock budget.
- `app/llm.py`: configurable `/chat/completions` function-calling adapter; requires exactly one `decide` tool call with a typed action or terminal decision.
- `app/agent.py`: OBSERVE → REASON → SELECT TOOL → EXECUTE → EVALUATE. Each next model request includes actual observations and comparisons. At most eight reasoning steps, one action per step, one retry per eligible call, 15 seconds per tool, 20 seconds per model call, 30 seconds for sandbox startup, and 120 seconds overall (including ingestion in the API). Cleanup can take an additional six seconds. Mutation/browser actions are not automatically retried.
- `app/tools/`: inspection, worker-only HTTP/browser implementations and a registry with deterministic comparisons and regression artifact generation.
- `app/sandbox.py`: coordinated application/browser container and isolated internal network lifecycle, immutable approvals and JSON worker protocol. No shell tool, subprocess argument from an LLM, source mount, remote checkout, automatic image build or automatic pull.
- `app/fixture_worker.py`: immutable-image fixture dispatcher/server with 150-second self-expiry; a fixed trusted launcher changes only its bind address for the private bridge.
- `app/browser_worker.py`: separate container-only, bounded stdin browser dispatcher, without application code or a listening control server.
- `app/replay.py`: generated regression reproduction with an approved image; no LLM needed.
- `app/observability.py`: request-scoped neatlogs workflow/child spans, strict field redaction and exporter masking, graceful telemetry failures and shutdown. `live_ready=False` deliberately keeps live analysis disabled.

## Model configuration

See `.env.example`; `.env` files are not loaded automatically. Export configuration explicitly before starting Uvicorn:

```sh
export BMF_LLM_ENDPOINT=http://127.0.0.1:1234/v1
export BMF_LLM_MODEL=your-tool-capable-local-model
```

Endpoint must implement OpenAI-compatible chat completions and function tool calls. HTTP is allowed only for localhost; remote endpoints require HTTPS. Optional `BMF_LLM_API_KEY` and `BMF_GITHUB_TOKEN` may be supplied through the environment. Never log/commit them. The server receives only filtered public application context, not secrets or host environment contents. Model response compatibility is mocked in tests; actual provider/model behavior must be verified after neatlogs integration.

## Tool permissions

| Tool | Allowed operations | Denied operations |
|---|---|---|
| `inspect_patch` | Source/diff excerpts from seven exact app/template paths | Tests, README, hackathon log, arbitrary disk reads |
| `http_request` | GET/POST to fixed container loopback target; allowlisted app routes and bounded fields; optional fresh account; automatic CSRF token | Arbitrary origins, custom headers/credentials, redirects, oversized responses, external network |
| `browser_test` | Fresh controlled signup/logout/login; book review submission; navigation; optional anonymous revisit; random `{{MARKER}}` substitution and observation of `document.documentElement.dataset.bmfMarker` | Model-supplied evaluate JS/selectors, arbitrary browser destinations, downloads, external network, host execution |
| `compare_behavior` | Successful observation references: browser marker absent/present, search count against an unmatched control and its SQL-predicate variant, response text check | Invented observations, failed HTTP status as bypass proof, normal differing searches as SQLi proof |
| `generate_regression_test` | Confirmed browser/search evidence → JSON actions plus constant pytest replay code in a temporary directory | Model-written executable Python, arbitrary output paths, auto-running generated tests |

Payload HTML supplied by the model can execute **only inside the isolated browser**, in the approved no-network fixture. Browser evaluator code is fixed by us. Browser observation checks a fresh marker over 1.2 seconds; absence is scoped to that test/window. HTTP uses a fresh session per call, with random test credentials kept internal. Browser uses a fresh context per action. Multiple GET calls can compare search results; persistent multi-call HTTP login sessions are not supported. Write-oriented tests should use a single browser flow.

`FIX_VERIFIED` requires execution-derived comparison evidence covering every declared hypothesis, with no bypass, errors or incomplete ingestion. It means no bypass reproduced within that scope. `BYPASS_CONFIRMED` requires an actual observed browser marker or a search-control violation. Response text alone cannot establish either security verdict. Missing evidence, setup/tool failure, unsupported model output or budget exhaustion yields `INCONCLUSIVE`. A failing or timed-out test is never reported as a verified fix. The LLM chooses hypotheses and scope, so coverage must still be reviewed by a human; no claim of exhaustive security is made.

## GitHub and evaluation boundaries

Only `demo-app/app.py` and the six named Jinja templates are admitted. Only these files' patches and head source reach the agent. README, hackathon.md, tests, prewritten exploit demonstrations and PR title/body/commit messages are excluded. Comments in application source are stripped to reduce fixture-label leakage. No verdict depends on a PR number. Source/diff and tool response text are untrusted data; prompts explicitly reject instructions found inside them, and strict tool validation enforces permissions regardless of model compliance.

Network ingestion and local execution are separate. Downloaded PR Python is **never imported, run, built, mounted or checked out on the Mac**. The execution target must be an operator-preapproved immutable Docker image matching the pinned head SHA. An image label is an operator attestation, not cryptographic proof of source provenance: before approving it, review the snapshot and verify it matches that commit. Source content not covered by that approval must not run. New PR heads require fresh approval; there is no automatic approval based on URL/branch name.

## Original Docker fixture preparation (historical single-container validation)

The following records the October 11 configuration. Current runtime topology and validation are documented in [browser/README.md](browser/README.md).

`fixture/Dockerfile` now pins the official Python base by digest and uses locked backend dependencies. The two reviewed BookShelf fixtures were built and their startup/HTTP execution tested on October 11. Manually create a clean, reviewed snapshot of BookShelf at the pinned head alongside this trusted backend runner. The recipe copies only app/templates/static, excludes evaluation tests and secrets through `.dockerignore`, and installs Flask plus the runner dependencies and Chromium. Build only after source/base review; never automatically build arbitrary PRs. Record the resulting local `sha256:<image ID>` and commit in a private operator manifest:

```json
{
  "<40-character reviewed head SHA>": "sha256:<64-character local image ID>"
}
```

Export `BMF_FIXTURE_APPROVALS` with that manifest's absolute path. Do not feed it to the LLM. `fixture/approvals.example.json` deliberately has no approved images. Live Docker flags use `--network=none`, `--read-only`, nonroot UID 10001, no capabilities, no-new-privileges, CPU/memory/PID limits and temporary writable `/tmp`. There are no host mounts, published ports, secrets or Docker socket mounts. App and browser share container loopback; Chromium keeps its own sandbox enabled. Chromium launch with `chromium_sandbox=True` failed under these restrictions with “No usable sandbox.” No `--no-sandbox`, unconfined seccomp, added capabilities or privileged mode was used. Resolve sandbox-compatible runtime support under a reviewed policy before browser validation. Containers self-expire and are removed on completion/error.

The backend process can access the Docker daemon for these fixed commands; do not expose the API publicly. Container isolation is defense in depth, not a VM security guarantee. Docker itself is operational. Fixture startup, resource/permission probes, bounded HTTP requests, timeout enforcement and teardown have been verified. Chromium execution and runtime PR analysis have not succeeded.

## What was verified

Current backend suite: **86 passed, 1 deprecation warning in 2.88s**. BookShelf: **9 passed in 0.67s**. Real Uvicorn smoke check: health HTTP 200; analysis gate HTTP 503, with no GitHub/model activity.

Unit and component tests mock GitHub, model responses, Docker commands and browser observations. They exercise ingestion, source exclusions, validation, adaptive multi-step state, evidence adjudication, regression artifacts, retry/timeout budgets, lifecycle/approval failures and API gates. The HTTP component uses MockTransport. A full API component test uses a synthetic PR and mocked execution; it is not a live PR analysis. Real BookShelf tests run independently against temporary SQLite files. Current two-container Docker component results are recorded in `browser/validation-report.json`; sandboxed Chromium passes. The original `fixture/validation-report.json` is retained as historical evidence. TestClient emits a Starlette HTTPX deprecation warning; HTTPX remains the requested network client.

## neatlogs integration and recovery (October 15)

Python 3.13.15 and neatlogs 1.4.27 are verified. The official SDK requires Python >=3.10,<3.14. The runtime lock includes the SDK and 76 packages; the separate development lock contains 83 packages. Install using Python 3.13. The previous Python 3.14 environment is preserved locally at `.venv-python314-backup`; `.venv-recovery` is the validated staging environment. Both are ignored.

Tracing is already implemented: request-scoped root/child correlation, GitHub and agent lifecycle events, model usage/timing, tool attempts/retries, sandbox lifecycle and verdict events. Freeform source, payloads, credentials and exception text are omitted. Automatic instrumentation and log capture are disabled. The live API gate remains closed independently of successful SDK initialization.

The backend does not load `.env` automatically. The synthetic script loads only `NEATLOGS_API_KEY` from its local `.env` as a convenience. Export `NEATLOGS_ENDPOINT` explicitly if overriding the default `https://ingest.neatlogs.com`; export uses `/v1/traces`. The configured API key determines the project; `workflow_name='break-my-fix'` names a workflow, not a project.

Run network-free SDK validation:

```sh
backend/.venv/bin/python -m neatlogs doctor --local --json
```

With `NEATLOGS_API_KEY` exported, `python -m neatlogs doctor --probe --json` exports generated diagnostic data and retrieves its exact persisted trace. For the application integration, use:

```sh
backend/.venv/bin/python backend/scripts/synthetic_trace.py --verify --project-id <expected-project-id>
```

This uses fake model/sandbox components, never calls a provider, GitHub or Docker, prints loss counters and verifies the exact trace via `/api/traces/v3/:traceId`. A nonzero exit indicates initialization, tracing, flush, loss-counter or readback failure. A flush success alone does not prove delivery. The exporter mask preserves SDK completion markers required by backend finalization.

October 15: all 58 backend tests and local/network SDK Doctor checks passed. An application synthetic trace was retrieved with 18 spans from the configured key's project (ID retained locally). API visibility is verified; the human-readable project name/dashboard selection has not been confirmed. Sandbox DNS blocked the first network probe; approved network access succeeded. This explains the observed sandbox failure, but does not establish the historical cause of earlier missing traces.

Remaining prerequisites for live work: verify a real tool-calling model separately and explicitly review enabling live analysis. Chromium sandbox support is now verified in the separate browser worker. No live PR or provider call was made during recovery.

## October 11 sandbox validation (historical)

Reviewed fixtures (remote branch heads confirmed unchanged):

- PR #1: `b0b635eba99f24a3641f729c1a95864a2ee36c9d` → `sha256:1f15e8c7ecc7ee8c8baa0b64f3b45156507811dc0a55845985d23a7d07b77d9a`.
- PR #2: `b855cb68e745767153506f7dab9abf368a11e403` → `sha256:81710a0aead1350872a1952e0ad872ff1016a4499567b6e9906ca882b56681d1`.

Temporary build contexts contained exact Git blobs for app/templates/static plus the trusted runner; no PR code was executed on host, and no existing PR branch was changed. SHA labels and immutable image IDs were registered in ignored `fixture/approvals.json`. Per-file source hashes and sanitized results are in [fixture/validation-report.json](fixture/validation-report.json).

For both fixtures, five component checks passed: startup, restrictions, HTTP connectivity, command timeout, teardown. Browser workflow failed on both because sandboxed Chromium could not launch. Runtime probes verified UID 10001, zero effective capabilities, read-only `/fixture`, external routing blocked, no Docker socket, CPU quota `100000/100000`, memory limit 805306368 bytes. Docker inspection verified no privileged mode, no binds/mounts/published ports, PID limit 128 and no-new-privileges. The worker's 150-second self-expiry was inspected in code; it was not waited out during the smoke test.

Re-run the deterministic smoke script after resolving runtime sandbox support:

```sh
backend/.venv/bin/python backend/scripts/validate_fixtures.py backend/fixture/approvals.json
```

It requires Docker socket permission, never calls a model or agent, and exits nonzero if any component fails. It uses ordinary reviews only. No exploit verification, live PR analysis, neatlogs installation, commit or push occurred. The ignored local approval manifest makes images selectable, but does not enable the API's observability gate. neatlogs integration can proceed while Chromium support is resolved; live browser-dependent analysis must wait.

## October 15: separate sandboxed browser

Chromium's namespace sandbox now works in a dedicated container with a default-derived seccomp policy. The app keeps default seccomp, while both containers retain non-root/read-only/cap-drop/no-new-privileges/resource limits. They share only an internal isolated bridge without a host gateway or external route; no ports or host mounts are published. Application image IDs, commit attestations and fixture source are unchanged.

See [browser/README.md](browser/README.md) for the architecture, reviewed syscall allowances, browser approval manifest, build process, reproduction command and remaining kernel/cleanup limitations. Current component evidence is [browser/validation-report.json](browser/validation-report.json); older fixture reports above remain historical. Backend tests cover image/policy approval, routing, navigation/socket restrictions, partial startup, timeout/cancellation cleanup and cleanup retries. Live analysis is still deliberately disabled, and no real model or autonomous PR analysis has run.

## Dependency compatibility resolution

[Dependency environments](DEPENDENCIES.md) now separate Python 3.13 orchestration, Python 3.14 fixture/HTTP work and Python 3.12 browser execution, using exact versions and hash-locked transitive dependencies. Neither existing BookShelf fixture image nor its commit attestation was changed or rebuilt. The updated fixture Dockerfile applies only to a future reviewed build. A new browser-only image was validated against the unchanged fixtures; live analysis remains disabled.
