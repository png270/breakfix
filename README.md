# Break My Fix

Team **0day** · [GitHub](https://github.com/png270/breakfix) · neatHack, October 10–12, 2026

An autonomous security agent that independently verifies whether AI-generated security patches actually remediate vulnerabilities. **Only BookShelf is implemented so far.** The agent and dashboard are future work.

## Repository architecture

```text
.agents/skills/neathack/SKILL.md  Official neatHack build-log skill
 demo-app/
   app.py                       Flask app factory, routes, SQLite schema and seed CLI
   templates/                   Jinja2 pages
   static/css/style.css         Responsive interface and illustrated book covers
   tests/test_bookshelf.py       Workflow and security tests
   requirements.txt             Flask and pytest
 backend/.gitkeep               Future FastAPI agent placeholder
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

Later, in isolated local test branches, create a SQL-injection search baseline and a stored-XSS review baseline. The intended demonstrations are a correct SQL-injection patch and an incomplete stored-XSS patch verified by browser execution. No vulnerability branches, security-fix PRs or agent code exist yet.

Break My Fix is planned to use FastAPI, HTTPX, Playwright and pytest with a React + TypeScript + Vite dashboard. See [hackathon.md](hackathon.md) for sponsor status and next milestones.

## Current limits

No password recovery, email verification, rate limiting, moderation, review editing or production deployment. Search supports SQLite LIKE wildcards. Automated tests verify HTML escaping; execution-based Playwright adversarial testing belongs to the future agent. Desktop and 390px mobile landing layouts were visually checked in Chrome; a full device matrix has not been tested. Entire reports this Codex session active and zero checkpoints on main; no commits or pushes were made.
