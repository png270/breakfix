# Break My Fix

Team **0day** · [GitHub](https://github.com/png270/breakfix) · neatHack, October 10–12, 2026

An autonomous security agent that independently verifies whether AI-generated security patches actually remediate vulnerabilities. **BookShelf and the backend investigation loop are implemented.** Live agent analysis is gated pending model validation and explicit review; the dashboard is future work.

## Repository architecture

```text
.agents/skills/neathack/SKILL.md  Official neatHack build-log skill
 demo-app/
   app.py                       Flask app factory, routes, SQLite schema and seed CLI
   templates/                   Jinja2 pages
   static/css/style.css         Responsive interface and illustrated book covers
   tests/test_bookshelf.py       Workflow and security tests
   requirements.txt             Flask and pytest
 backend/                       FastAPI agent, bounded tools, tests and Docker fixture recipe
 frontend/.gitkeep              Future React/TypeScript/Vite dashboard placeholder
 hackathon.md                   Evidence-based build log and submission checklist
```

## BookShelf

A small book-reviewing platform with signup/login/logout, editable reader profiles (display name, bio, favorite genre), a 12-book seeded catalog, title/author search, book details and persistent text reviews. Public profiles show each reader's reviews. Review authors and UTC timestamps appear on book pages.

The interface uses HTML/CSS and Flask's built-in Jinja2 templates. Optional Google Fonts enhance typography; local system and Georgia fallbacks work without network access. No React or frontend build step is required.

## Setup

Run from the repository root. Verified with **Python 3.14.6**, **Flask 3.1.3** and **pytest 9.1.1**.

```sh
python3 --version
python3 -m venv demo-app/.venv
demo-app/.venv/bin/python -m pip install -r demo-app/requirements.txt
demo-app/.venv/bin/python -c 'import flask, pytest; print("Flask and pytest imports OK")'
```

The initial install used `Flask>=3.1,<4` and `pytest>=8,<10`; requirements now pin the successfully installed direct dependencies. Werkzeug, Jinja2 and other supporting packages are Flask/pytest transitive dependencies. SQLite uses Python's built-in `sqlite3`; no server is needed.

## Initialize and run

```sh
demo-app/.venv/bin/python -m flask --app demo-app/app.py init-db
demo-app/.venv/bin/python -m flask --app demo-app/app.py run --host 127.0.0.1 --port 5001
```

Open **http://127.0.0.1:5001**. Stop with Ctrl+C. Initialization creates `demo-app/bookshelf.sqlite3` and seeds 12 books. Rerunning it preserves users/reviews and does not duplicate seeds. Generated databases are ignored by Git.

`BOOKSHELF_SECRET_KEY` supplies the session signing key. When unset, the app uses the explicitly development-only fallback `bookshelf-local-development-only`. For a private local key, use this before the run command (do not commit its value):

```sh
export BOOKSHELF_SECRET_KEY="$(demo-app/.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
```

Keep the same key across restarts to retain existing login sessions. The app is for local controlled use; the Flask development server and shared fallback key are not production settings. Cookies are HttpOnly and SameSite=Lax; `BOOKSHELF_COOKIE_SECURE=1` enables Secure cookies when serving over HTTPS. Leave that unset for localhost HTTP.

## Tests

```sh
demo-app/.venv/bin/python -m pytest demo-app/tests -q
```

Verified result on October 10: **9 passed in 0.72s**. Tests use isolated temporary SQLite files and verify signup, validation, login/logout, profile editing/ownership, browsing/search/details, review submission and persistence after app recreation. Security assertions cover password hashes, unauthenticated writes, bound SQL inputs, escaped profile/review HTML, and CSRF tokens. Seed idempotency and foreign-key enforcement are also checked.

## Security-testing plan

Current BookShelf uses parameterized queries, Werkzeug password hashing, Jinja2 HTML escaping and CSRF tokens on every POST. No intentional vulnerabilities have been introduced.

The controlled baseline exists on `demo/vulnerable-bookshelf`. Independent, unmerged SQLi and XSS patch candidates are [PR #1](https://github.com/png270/breakfix/pull/1) and [PR #2](https://github.com/png270/breakfix/pull/2). Main remains the secure BookShelf implementation. The backend loop is implemented, but independent live verification of these PRs has not run; neatlogs and approved Docker fixtures are prerequisites.

Break My Fix uses FastAPI, HTTPX, Playwright, Pydantic and pytest for its backend. A React + TypeScript + Vite dashboard remains planned. See [hackathon.md](hackathon.md) for sponsor status and next milestones.

## Current limits

No password recovery, email verification, rate limiting, moderation, review editing or production deployment. Search supports SQLite LIKE wildcards. Automated tests verify HTML escaping; execution-based Playwright adversarial testing belongs to the future agent. Desktop and 390px mobile landing layouts were visually checked in Chrome; a full device matrix has not been tested. Entire is enabled with Codex tracking. See the dated build log for session-specific checkpoint evidence; this backend session makes no new commits or pushes.


## Agent backend

See [backend/README.md](backend/README.md) for architecture, model configuration, tool permissions and Docker boundaries. No real LLM calls or live PR analyses have run. The API accepts only this repository's PRs and excludes test/build-log material from model context. It deliberately remains disabled for live analysis; neatlogs synthetic delivery is verified, and both approved fixtures pass HTTP and sandboxed-browser component checks; no host fallback is permitted.

```sh
python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements.lock.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Install `backend/requirements-dev.lock.txt` with `--require-hashes` before running backend tests from `backend/`: `.venv/bin/python -m pytest -q`. Keep them separate from BookShelf's test command to avoid the two `app` import roots colliding. Main BookShelf remains secure; controlled demo and independent fix branches/PRs remain separate and unmerged.

## October 15 recovery

Backend `.venv` now uses Python 3.13.15 with neatlogs 1.4.27 and a complete dependency lock. The old Python 3.14 environment is preserved in ignored `backend/.venv-python314-backup`. All 58 backend tests pass. SDK Doctor local and network probes pass; a fresh application synthetic trace is retrievable with 18 spans. Dashboard project-name confirmation remains pending. Live analysis stays disabled. Chromium validation was completed in the subsequent browser isolation update below; real model tool calling remains outstanding. See backend README for repeatable diagnostics.

## October 15 browser isolation update

The Chromium sandbox blocker is resolved using a separate approved browser worker and a default-derived seccomp profile. Both immutable BookShelf images remain unchanged. The two containers retain non-root execution, read-only filesystems, dropped capabilities, no-new-privileges and resource limits, and share a per-run internal bridge without a host gateway or external route. See [architecture, reproduction and limitations](backend/browser/README.md) and [component evidence](backend/browser/validation-report.json). Live analysis remains disabled pending separate model verification and review.

Backend, fixture and browser dependencies are separately pinned and hash-locked for their Python versions. See [dependency environments and validation](backend/DEPENDENCIES.md). Existing approved BookShelf images remain unchanged; fixture recipe changes affect only future reviewed builds.
