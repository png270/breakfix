# Manual operator-reviewed fixture build only. Never build remote PR code automatically.
# Official Python base pinned for reproducible fixture validation.
FROM python@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170
ARG FIXTURE_COMMIT
LABEL bmf.commit=$FIXTURE_COMMIT
ENV BMF_FIXTURE_WORKER=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /runner
COPY backend/fixture/requirements.lock.txt /runner/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY backend/app/__init__.py backend/app/schemas.py backend/app/fixture_worker.py /runner/app/
COPY backend/app/tools/__init__.py backend/app/tools/http.py /runner/app/tools/
# Source snapshot must be manually reviewed and verified against FIXTURE_COMMIT.
COPY demo-app/app.py /fixture/app.py
COPY demo-app/templates /fixture/templates
COPY demo-app/static /fixture/static
USER 10001:10001
ENTRYPOINT ["python", "-m", "app.fixture_worker", "serve"]
