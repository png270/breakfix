"""Local API. Live analysis gated until a real observability adapter is wired."""
import asyncio
import os
import time
from fastapi import FastAPI, HTTPException
from .agent import Agent
from .github import GitHubClient, GitHubError
from .llm import CompatibleLLM
from contextlib import asynccontextmanager
from .observability import ObserverFactory, emit, run_scope
from .sandbox import DockerSandbox
from .schemas import AnalyzeRequest, AnalysisResult


def create_app(observer=None, github_factory=None, llm_factory=None, sandbox_factory=None):
    telemetry = observer or ObserverFactory()

    @asynccontextmanager
    async def lifespan(app):
        yield
        if hasattr(telemetry, 'shutdown'):
            await asyncio.to_thread(telemetry.shutdown)

    app = FastAPI(title='Break My Fix', version='0.1.0', lifespan=lifespan)
    app.state.observer = telemetry
    active = asyncio.Lock()

    @app.get('/health')
    def health():
        return {'status': 'ok', 'live_analysis_enabled': app.state.observer.live_ready,
                'trace_id': app.state.observer.trace_id()}

    @app.post('/api/analyze', response_model=AnalysisResult)
    async def analyze(request: AnalyzeRequest):
        if not app.state.observer.live_ready:
            raise HTTPException(503, 'Live analysis disabled until neatlogs observability is integrated')
        if active.locked():
            raise HTTPException(429, 'One analysis at a time')
        async with active:
            run_observer = telemetry.new_run() if hasattr(telemetry, 'new_run') else telemetry
            with run_scope(run_observer):
                started = time.monotonic()
                github = github_factory() if github_factory else GitHubClient(token=os.getenv('BMF_GITHUB_TOKEN'))
                llm = None
                try:
                    emit(run_observer, 'github.start', {'pr_url': request.pr_url})
                    pr = await asyncio.wait_for(github.fetch(request.pr_url), 30)
                    emit(run_observer, 'github.end', {'commit': pr.head_sha})
                    endpoint, model = os.getenv('BMF_LLM_ENDPOINT'), os.getenv('BMF_LLM_MODEL')
                    if llm_factory:
                        llm = llm_factory()
                    elif not endpoint or not model:
                        raise HTTPException(503, 'Model endpoint and model name must be configured')
                    else:
                        llm = CompatibleLLM(endpoint, model, os.getenv('BMF_LLM_API_KEY'))
                    sandbox = sandbox_factory() if sandbox_factory else DockerSandbox(os.getenv('BMF_FIXTURE_APPROVALS'))
                    return await Agent(llm, sandbox, run_observer,
                                       overall_timeout=120 - (time.monotonic() - started)).run(pr)
                except (GitHubError, asyncio.TimeoutError, ValueError) as exc:
                    return AnalysisResult(pr_url=request.pr_url, verdict='INCONCLUSIVE',
                                          terminal_state='failed', summary='Ingestion/configuration failed',
                                          errors=[type(exc).__name__], limitations=['No live tests executed'],
                                          trace_id=run_observer.trace_id())
                finally:
                    await github.close()
                    if llm:
                        await llm.close()

    return app


app = create_app()
