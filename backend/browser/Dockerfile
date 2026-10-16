# Trusted browser runner only: no fixture application, credentials or PR source.
FROM mcr.microsoft.com/playwright/python@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0
ARG BROWSER_WORKER_SHA256
LABEL bmf.browser-worker="1" bmf.runner.sha256=$BROWSER_WORKER_SHA256
COPY backend/browser/requirements.lock.txt /runner/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /runner/requirements.txt
ENV BMF_BROWSER_WORKER=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /runner
COPY backend/app/__init__.py backend/app/schemas.py backend/app/browser_worker.py /runner/app/
COPY backend/app/tools/__init__.py backend/app/tools/browser.py /runner/app/tools/
USER 10001:10001
ENTRYPOINT ["python", "-m", "app.browser_worker", "serve"]
