# Dependencies by execution environment

Each `requirements.txt` declares exact direct versions. The matching
`requirements.lock.txt` pins the complete transitive closure with SHA-256 hashes.
Install locks with `--require-hashes`; do not use the backend lock in worker images.
No package versions were upgraded during this split.

| Environment | Python | Input / hash lock | Packages |
| --- | --- | --- | --- |
| Backend orchestration | 3.13 | `requirements.txt` / `requirements.lock.txt` | 76 |
| Local backend development/tests | 3.13 | `requirements-dev.txt` / `requirements-dev.lock.txt` | 83 |
| BookShelf fixture and HTTP worker | 3.14 | `fixture/requirements.txt` / `fixture/requirements.lock.txt` | 18 |
| Browser worker | 3.12 | `browser/requirements.txt` / `browser/requirements.lock.txt` | 8 |

The backend needs FastAPI, Uvicorn, Pydantic, HTTPX and neatlogs 1.4.27. The SDK
requires Python below 3.14 and brings its own instrumentor dependencies even when
automatic instrumentation is disabled. Flask, Playwright and pytest are absent
from the backend runtime lock. The development lock adds pytest and Playwright
because unit tests inspect the browser executor with mocked browser operations.
No host browser binaries or provider calls are needed to run those tests.

The fixture needs Flask, HTTPX and Pydantic only. Its future-build recipe copies
only schemas, the fixture worker and HTTP tool, and installs no SDK, browser,
API server, test framework or Chromium system dependencies. The fixture dispatcher
refuses browser actions. The browser image installs Playwright/Pydantic and their
dependencies only, on the digest-pinned official Playwright base; its Python
package version matches the preinstalled browsers. Both Dockerfiles enforce hashes.

From the repository root:

```sh
# Deployment runtime
python3.13 -m venv backend/.venv
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements.lock.txt

# Local tests (runtime plus development dependencies)
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements-dev.lock.txt
cd backend
.venv/bin/python -m pytest -q
```

To regenerate a lock without deliberately upgrading its existing pins, run from
the repository root, using the corresponding Python version and target platform:

```sh
uv pip compile backend/requirements.txt --python-version 3.13 --generate-hashes --no-header --no-annotate --constraint backend/requirements.lock.txt --output-file backend/requirements.lock.txt
uv pip compile backend/requirements-dev.txt --python-version 3.13 --generate-hashes --no-header --no-annotate --constraint backend/requirements-dev.lock.txt --output-file backend/requirements-dev.lock.txt
uv pip compile backend/fixture/requirements.txt --python-version 3.14 --python-platform aarch64-unknown-linux-gnu --generate-hashes --no-header --no-annotate --constraint backend/fixture/requirements.lock.txt --output-file backend/fixture/requirements.lock.txt
uv pip compile backend/browser/requirements.txt --python-version 3.12 --python-platform aarch64-unknown-linux-gnu --generate-hashes --no-header --no-annotate --constraint backend/browser/requirements.lock.txt --output-file backend/browser/requirements.lock.txt
```

Worker target validation covers Docker Desktop Linux ARM64. Backend validation is
on macOS ARM64. Revalidate for other Python/platform targets before deployment.
Pinned image digests and package hashes make dependency inputs reproducible;
they do not guarantee identical image timestamps or vulnerability-free packages.

Existing approved BookShelf images and commit attestations are unchanged. The
fixture Dockerfile updates apply only to a future explicitly reviewed build;
neither existing approved fixture was rebuilt. Those historical images still
contain their original broader dependency set. Removing packages from them would
require new image approvals, and is intentionally outside this change.

The changed browser recipe/lock requires a new immutable browser-only approval.
Both inputs are included in `app.sandbox.browser_digest()`, so changing dependency
policy cannot silently reuse an old approval. The previous browser image remains
available; no mutable tag or automatic build is used by the runtime.

Validation: independent hash-locked Python 3.13 backend/development and Python 3.14
fixture environments installed successfully and passed dependency checks. The
runtime imported without Flask, Playwright or pytest. All fixture Linux ARM64
Python 3.14 wheels were resolved/downloaded with hash verification. The new browser
image installed its complete lock under Python 3.12 and passed `pip check`.
