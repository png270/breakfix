import asyncio
import json
import pytest
from app.schemas import PRData, Decision


@pytest.fixture
def pr():
    return PRData(pr_url='https://github.com/png270/breakfix/pull/17',
                  base_sha='a' * 40, head_sha='b' * 40,
                  changed_files=['demo-app/app.py'], diff='application-only diff',
                  sources={'demo-app/app.py': 'application-only source'})


class FakeLLM:
    def __init__(self, decisions):
        self.decisions = iter(decisions)
        self.contexts = []

    async def decide(self, context):
        self.contexts.append(context)
        item = next(self.decisions)
        if isinstance(item, Exception):
            raise item
        return Decision.model_validate(item)

    async def close(self):
        pass


class FakeSandbox:
    def __init__(self, results=(), fail=False):
        self.results = iter(results)
        self.fail = fail
        self.stopped = False
        self.actions = []

    async def start(self, pr):
        if self.fail:
            raise RuntimeError('daemon unavailable')

    async def execute(self, action):
        self.actions.append(action)
        item = next(self.results)
        if isinstance(item, Exception):
            raise item
        return item

    async def stop(self):
        self.stopped = True


def run(coroutine):
    return asyncio.run(coroutine)


def hypothesis():
    return {'id': 'h1', 'statement': 'Review content may execute',
            'security_property': 'Submitted review must not execute a browser marker'}


def browser_step():
    return {'hypotheses': [hypothesis()], 'action': {'name': 'browser_test',
            'arguments': {'review_text': '<svg onload="document.documentElement.dataset.bmfMarker=\'{{MARKER}}\'"></svg>'}}}


def compare_step():
    return {'action': {'name': 'compare_behavior', 'arguments': {
        'hypothesis_id': 'h1', 'property': 'no_browser_execution', 'observation_id': 'o1'}}}


@pytest.fixture
def docker_setup(pr, tmp_path):
    """Daemon model with separate resource state; never starts Docker."""
    import hashlib
    from app.sandbox import DockerSandbox, BACKEND, browser_digest, SandboxError
    app_image, browser_image = 'sha256:' + 'd' * 64, 'sha256:' + 'e' * 64
    manifest = tmp_path / 'fixtures.json'
    manifest.write_text(json.dumps({pr.head_sha: app_image}))
    approval = tmp_path / 'browser.json'
    approval.write_text(json.dumps({'image': browser_image, 'runner_sha256': browser_digest(),
        'seccomp_sha256': hashlib.sha256((BACKEND / 'browser/chromium-seccomp.json').read_bytes()).hexdigest()}))
    state = {'containers': set(), 'networks': set(), 'fail': None, 'gateway': '', 'internal': True}
    calls = []
    async def command(*args, **kwargs):
        calls.append((args, kwargs))
        if state['fail'] and state['fail'](args):
            raise SandboxError('injected daemon failure')
        if args[:2] == ('image', 'inspect'):
            labels = {'bmf.commit': pr.head_sha} if args[2] == app_image else {
                'bmf.browser-worker': '1', 'bmf.runner.sha256': browser_digest()}
            return json.dumps([{'Id': args[2], 'Config': {'Labels': labels}}])
        if args[:2] == ('network', 'create'):
            state['networks'].add(args[-1])
        elif args[:2] == ('network', 'inspect'):
            return json.dumps([{'Internal': state['internal'], 'EnableIPv6': False,
                'Options': {'com.docker.network.bridge.gateway_mode_ipv4': 'isolated'}}])
        elif args[0] == 'run':
            state['containers'].add(args[args.index('--name') + 1])
        elif args[0] == 'inspect':
            network = next(iter(state['networks']))
            return json.dumps([{'NetworkSettings': {'Networks': {network: {
                'IPAddress': '172.30.0.2', 'Gateway': state['gateway']}}}}])
        elif args[0] == 'ps':
            return '\n'.join(state['containers'])
        elif args[:2] == ('rm', '-f'):
            state['containers'].difference_update(args[2:])
        elif args[:2] == ('network', 'ls'):
            return '\n'.join(state['networks'])
        elif args[:2] == ('network', 'rm'):
            state['networks'].discard(args[2])
        elif args[:2] == ('exec', '-i'):
            return json.dumps({'status_code': 200, 'marker_executed': False})
        return 'ready'
    return DockerSandbox(manifest, command, approval), calls, state
