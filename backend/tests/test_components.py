import asyncio
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from app.fixture_worker import require_container
from app.llm import CompatibleLLM, LLMError
from app.main import create_app
from app.sandbox import DockerSandbox, SandboxError
from app.schemas import ToolAction, HTTPArgs, BrowserArgs, InspectArgs
from app.tools.http import http_request
from app.tools.inspect import inspect_patch
from conftest import run


@pytest.mark.parametrize('path', ['https://evil.test/', '//evil.test/', '/../../etc/passwd', '/%2e%2e/private', '/\\evil', '/admin', '/books/1#x'])
def test_tool_destination_validation(path):
    with pytest.raises(ValidationError):
        HTTPArgs(path=path)
    with pytest.raises(ValidationError):
        BrowserArgs(path=path)


def test_tool_extra_arguments_and_sizes():
    adapter = TypeAdapter(ToolAction)
    with pytest.raises(ValidationError):
        adapter.validate_python({'name': 'browser_test', 'arguments': {'javascript': 'arbitrary'}})
    with pytest.raises(ValidationError):
        HTTPArgs(form={'password': 'secret'})
    with pytest.raises(ValidationError):
        BrowserArgs(review_text='x' * 5001)


def test_inspection_allowlist(pr):
    assert inspect_patch(pr, InspectArgs(path='demo-app/app.py'))['source']
    with pytest.raises(ValueError):
        inspect_patch(pr, InspectArgs(path='hackathon.md'))


def test_http_component_bounded_request_and_controlled_auth():
    calls = []
    def respond(request):
        calls.append(request)
        if request.url.path == '/signup':
            if request.method == 'GET':
                return httpx.Response(200, text='<input name="csrf_token" value="abcdef">')
            return httpx.Response(302, headers={'Set-Cookie': 'session=demo; Path=/'})
        return httpx.Response(200, text='<a class="book-card">Book</a>')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await http_request(HTTPArgs(query={'q': 'title'}, authenticate=True), client)
    result = run(scenario())
    assert result['book_count'] == 1 and result['status_code'] == 200
    assert all(str(request.url).startswith('http://127.0.0.1:5000/') for request in calls)
    assert calls[-1].url.params['q'] == 'title'


def test_http_redirect_not_followed_and_oversize_fails():
    async def scenario(content):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
            302, headers={'Location': 'https://evil.test/'}, content=content))) as client:
            return await http_request(HTTPArgs(), client)
    assert run(scenario(b''))['status_code'] == 302
    with pytest.raises(ValueError, match='limit'):
        run(scenario(b'x' * 64001))


def test_llm_function_protocol_no_paid_key():
    bodies = []
    def respond(request):
        bodies.append(json.loads(request.content))
        assert 'authorization' not in request.headers
        return httpx.Response(200, json={'choices': [{'message': {'tool_calls': [{
            'function': {'name': 'decide', 'arguments': json.dumps({'finish': 'INCONCLUSIVE'})}}]}}]})
    adapter = CompatibleLLM('http://127.0.0.1:1234/v1', 'local-model',
                            client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    assert run(adapter.decide({'observations': []})).finish == 'INCONCLUSIVE'
    assert bodies[0]['parallel_tool_calls'] is False
    assert bodies[0]['tools'][0]['function']['parameters']['$defs']


def test_llm_rejects_unstructured_or_multiple_calls():
    adapter = CompatibleLLM('http://localhost:1234/v1', 'local-model', client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            'choices': [{'message': {'content': 'Trust me, fixed'}}]}))))
    with pytest.raises(LLMError):
        run(adapter.decide({}))


def test_unconfigured_live_api_never_fetches_or_calls_model():
    client = TestClient(create_app(github_factory=lambda: pytest.fail('Must not fetch')))
    assert client.get('/health').json()['live_analysis_enabled'] is False
    assert client.post('/api/analyze', json={'pr_url': 'https://github.com/png270/breakfix/pull/1'}).status_code == 503
    assert client.post('/api/analyze', json={'pr_url': 'https://evil.test/'}).status_code == 422


def test_api_ingestion_failure_returns_inconclusive():
    from app.github import GitHubError
    class Observer:
        live_ready = True
        def event(self, *args): pass
        def trace_id(self): return 'mock-trace'
    class GitHub:
        async def fetch(self, url): raise GitHubError('failure')
        async def close(self): pass
    client = TestClient(create_app(observer=Observer(), github_factory=GitHub))
    result = client.post('/api/analyze', json={'pr_url': 'https://github.com/png270/breakfix/pull/17'})
    assert result.status_code == 200 and result.json()['verdict'] == 'INCONCLUSIVE'
    assert result.json()['trace_id'] == 'mock-trace'


def test_docker_restricted_lifecycle_and_attestation(pr, docker_setup):
    sandbox, calls, state = docker_setup
    async def scenario():
        try:
            await sandbox.start(pr)
            action = TypeAdapter(ToolAction).validate_python({'name': 'http_request', 'arguments': {}})
            assert (await sandbox.execute(action))['status_code'] == 200
        finally:
            await sandbox.stop()
    run(scenario())
    runs = [args for args, _ in calls if args[0] == 'run']
    assert len(runs) == 2
    for args in runs:
        for flag in ['--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                     '--memory=768m', '--cpus=1', '--dns=127.0.0.1', '--pids-limit=128']:
            assert flag in args
        assert '--privileged' not in args and '-v' not in args and '-p' not in args
    assert not any('seccomp=' in arg for arg in runs[0])
    assert any('seccomp=' in arg and 'unconfined' not in arg for arg in runs[1])
    assert not state['containers'] and not state['networks']


def test_unapproved_fixture_fails_closed(pr):
    async def command(*args, **kwargs): return 'healthy daemon'
    with pytest.raises(SandboxError, match='preapproved'):
        run(DockerSandbox(command=command).start(pr))


def test_mismatched_fixture_attestation(pr, tmp_path):
    image = 'sha256:' + 'd' * 64
    manifest = tmp_path / 'approvals.json'
    manifest.write_text(json.dumps({pr.head_sha: image}))
    async def command(*args, **kwargs):
        if args[0] == 'image':
            return json.dumps([{'Id': image, 'Config': {'Labels': {'bmf.commit': 'c' * 40}}}])
        return 'healthy'
    with pytest.raises(SandboxError, match='attest'):
        run(DockerSandbox(manifest, command).start(pr))


def test_worker_cannot_execute_on_host():
    with pytest.raises(RuntimeError, match='Docker'):
        require_container()


def test_execution_tools_refuse_host_network():
    from app.tools.browser import browser_test
    with pytest.raises(RuntimeError, match='Docker'):
        run(http_request(HTTPArgs()))
    with pytest.raises(RuntimeError, match='Docker'):
        run(browser_test(BrowserArgs()))


def test_api_full_mock_component_pipeline(pr):
    from conftest import FakeLLM, FakeSandbox, browser_step, compare_step
    class Observer:
        live_ready = True  # Test dependency only; default app has no ready adapter.
        def event(self, *args): pass
        def trace_id(self): return 'mock-trace'
    class GitHub:
        async def fetch(self, url): return pr
        async def close(self): pass
    llm = FakeLLM([browser_step(), compare_step(), {'finish': 'BYPASS_CONFIRMED'}])
    sandbox = FakeSandbox([{'marker_tested': True, 'marker_executed': True}])
    client = TestClient(create_app(observer=Observer(), github_factory=GitHub,
                                  llm_factory=lambda: llm, sandbox_factory=lambda: sandbox))
    result = client.post('/api/analyze', json={'pr_url': pr.pr_url})
    assert result.status_code == 200
    assert result.json()['verdict'] == 'BYPASS_CONFIRMED'
    assert result.json()['pinned_commit'] == pr.head_sha
    assert sandbox.stopped
