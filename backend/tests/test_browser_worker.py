import asyncio
import json
from pathlib import Path
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from pydantic import TypeAdapter, ValidationError
from app.browser_worker import fixture_origin, run_tool
from app.sandbox import BACKEND, SandboxError
from app.schemas import ToolAction
from conftest import run


def action(name):
    return TypeAdapter(ToolAction).validate_python({'name': name, 'arguments': {}})


def test_browser_routes_to_separate_worker(pr, docker_setup):
    sandbox, calls, state = docker_setup
    async def scenario():
        await sandbox.start(pr)
        try:
            await sandbox.execute(action('browser_test'))
            args, kw = calls[-1]
            assert args[2] == sandbox.browser and 'app.browser_worker' in args
            assert json.loads(kw['input_data']) == action('browser_test').model_dump()
            await sandbox.execute(action('http_request'))
            assert calls[-1][0][2] == sandbox.container
        finally:
            await sandbox.stop()
    run(scenario())


@pytest.mark.parametrize('failure', ['network', 'app', 'browser', 'health'])
def test_partial_start_failure_removes_all_resources(pr, docker_setup, failure):
    sandbox, calls, state = docker_setup
    state['fail'] = lambda args: (
        (failure == 'network' and args[:2] == ('network', 'inspect')) or
        (failure == 'app' and args[0] == 'run' and args[args.index('--name') + 1].endswith('-app')) or
        (failure == 'browser' and args[0] == 'run' and args[args.index('--name') + 1].endswith('-browser')) or
        (failure == 'health' and args[0] == 'exec'))
    with pytest.raises(SandboxError):
        run(sandbox.start(pr))
    assert not state['containers'] and not state['networks']


@pytest.mark.parametrize('unsafe', ['gateway', 'internal'])
def test_unsafe_network_fails_closed(pr, docker_setup, unsafe):
    sandbox, calls, state = docker_setup
    state[unsafe] = '172.30.0.1' if unsafe == 'gateway' else False
    with pytest.raises(SandboxError):
        run(sandbox.start(pr))
    assert not state['containers'] and not state['networks']


def test_cleanup_failure_retains_names_for_retry(pr, docker_setup):
    sandbox, calls, state = docker_setup
    async def scenario():
        await sandbox.start(pr)
        state['fail'] = lambda args: args[0] == 'rm'
        with pytest.raises(SandboxError):
            await sandbox.stop()
        assert sandbox.container and sandbox.browser and sandbox.network
        state['fail'] = None
        await sandbox.stop()
        await sandbox.stop()
    run(scenario())
    assert not state['containers'] and not state['networks']


@pytest.mark.parametrize('exception', [asyncio.TimeoutError, asyncio.CancelledError])
def test_tool_timeout_and_cancellation_remove_workers(pr, docker_setup, exception):
    sandbox, calls, state = docker_setup
    original = sandbox.command
    async def command(*args, **kw):
        if args[:2] == ('exec', '-i'):
            raise exception()
        return await original(*args, **kw)
    async def scenario():
        await sandbox.start(pr)
        sandbox.command = command
        with pytest.raises(exception):
            await sandbox.execute(action('browser_test'))
    run(scenario())
    assert not state['containers'] and not state['networks']


@pytest.mark.parametrize('field', ['runner_sha256', 'seccomp_sha256'])
def test_stale_browser_approval_rejected_before_execution(pr, docker_setup, field):
    sandbox, calls, state = docker_setup
    data = json.loads(sandbox.browser_manifest.read_text())
    data[field] = '0' * 64
    sandbox.browser_manifest.write_text(json.dumps(data))
    with pytest.raises(SandboxError, match='approved'):
        run(sandbox.start(pr))
    assert not any(args[0] == 'run' for args, _ in calls)


def test_cancellation_after_container_creation_removes_partial_run(pr, docker_setup):
    sandbox, calls, state = docker_setup
    original = sandbox.command
    async def command(*args, **kw):
        result = await original(*args, **kw)
        if args[0] == 'run':
            raise asyncio.CancelledError()
        return result
    sandbox.command = command
    with pytest.raises(asyncio.CancelledError):
        run(sandbox.start(pr))
    assert not state['containers'] and not state['networks']


def test_seccomp_delta_is_only_browser_sandbox_calls():
    baseline = json.loads((BACKEND / 'browser/docker-default-seccomp.json').read_text())
    profile = json.loads((BACKEND / 'browser/chromium-seccomp.json').read_text())
    assert profile['defaultAction'] == 'SCMP_ACT_ERRNO'
    extra = profile['syscalls'][len(baseline['syscalls']):]
    assert {name for rule in extra for name in rule['names']} == {'clone', 'setns', 'unshare', 'chroot'}
    profile['syscalls'] = profile['syscalls'][:len(baseline['syscalls'])]
    assert profile == baseline


def test_worker_rejects_other_tools_and_model_code(monkeypatch):
    monkeypatch.setattr('app.browser_worker.require_browser', lambda: None)
    with pytest.raises(ValueError, match='browser_test only'):
        run(run_tool(action('http_request').model_dump_json()))
    with pytest.raises(ValidationError):
        run(run_tool(json.dumps({'name': 'browser_test', 'arguments': {'javascript': 'evil()'}})))


def test_browser_context_enforces_origin_download_worker_and_socket_boundaries(monkeypatch):
    from app.tools.browser import browser_test
    from app.schemas import BrowserArgs
    monkeypatch.setattr('app.browser_worker.fixture_origin', lambda: 'http://172.30.0.2:5000')
    page = SimpleNamespace(
        set_default_timeout=Mock(), goto=AsyncMock(return_value=SimpleNamespace(status=200)),
        wait_for_function=AsyncMock(), evaluate=AsyncMock(return_value=False),
        url='http://172.30.0.2:5000/',
        locator=Mock(return_value=SimpleNamespace(inner_text=AsyncMock(return_value='BookShelf'))))
    context = SimpleNamespace(route=AsyncMock(), route_web_socket=AsyncMock(),
                              new_page=AsyncMock(return_value=page), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    launch = AsyncMock(return_value=browser)
    class Playwright:
        async def __aenter__(self): return SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        async def __aexit__(self, *args): pass
    monkeypatch.setattr('app.tools.browser.async_playwright', Playwright)
    async def scenario():
        await browser_test(BrowserArgs())
        assert launch.call_args.kwargs == {'headless': True, 'chromium_sandbox': True, 'timeout': 5000}
        assert browser.new_context.call_args.kwargs == {'service_workers': 'block', 'accept_downloads': False}
        restrict = context.route.call_args.args[1]
        for url, allowed in [('http://172.30.0.2:5000/', True), ('https://example.com/', False),
                             ('http://172.30.0.2:5001/', False), ('http://169.254.169.254/', False),
                             ('file:///etc/passwd', False), ('http://host.docker.internal/', False),
                             ('http://evil@172.30.0.2:5000/', False)]:
            route = SimpleNamespace(request=SimpleNamespace(url=url), continue_=AsyncMock(), abort=AsyncMock())
            await restrict(route)
            assert route.continue_.await_count == int(allowed)
            assert route.abort.await_count == int(not allowed)
        socket = SimpleNamespace(close=AsyncMock())
        await context.route_web_socket.call_args.args[1](socket)
        socket.close.assert_awaited_once()
        context.close.assert_awaited_once()
        browser.close.assert_awaited_once()
    run(scenario())


@pytest.mark.parametrize('address', ['127.0.0.1', '169.254.169.254', '0.0.0.0', '8.8.8.8', 'host.docker.internal'])
def test_browser_target_cannot_be_host_metadata_or_public(monkeypatch, address):
    monkeypatch.setattr('app.browser_worker.require_browser', lambda: None)
    monkeypatch.setenv('BMF_FIXTURE_IP', address)
    with pytest.raises(ValueError):
        fixture_origin()
