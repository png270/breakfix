"""Real Docker component checks only: no model, ingestion, or PR analysis."""
import asyncio
import json
import sys
from pathlib import Path
from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.sandbox import DockerSandbox, docker_command
from app.schemas import PRData, ToolAction

PROBE = r'''import json, os, socket
status = dict(line.split(':', 1) for line in open('/proc/self/status') if ':' in line)
blocked = {}
for address, port in [('1.1.1.1',443), ('169.254.169.254',80),
                      ('192.168.65.254',2375), ('192.168.65.2',80)]:
    with socket.socket() as sock:
        sock.settimeout(.3)
        blocked[address] = sock.connect_ex((address,port)) != 0
socket.setdefaulttimeout(.3)
try:
    socket.getaddrinfo('example.com',443); dns_blocked=False
except OSError:
    dns_blocked=True
try:
    open('/runner/write-probe','w').close(); read_only=False
except OSError:
    read_only=True
routes = open('/proc/net/route').read().splitlines()[1:]
print(json.dumps({'uid':os.getuid(), 'read_only':read_only,
    'cap_eff':status['CapEff'].strip(), 'seccomp':status['Seccomp'].strip(),
    'no_new_privs':status['NoNewPrivs'].strip(),
    'external_connections_blocked':blocked, 'dns_blocked':dns_blocked,
    'no_default_route':all(line.split()[1] != '00000000' for line in routes),
    'docker_socket_absent':not os.path.exists('/var/run/docker.sock'),
    'cpu_max':open('/sys/fs/cgroup/cpu.max').read().strip(),
    'memory_max':open('/sys/fs/cgroup/memory.max').read().strip(),
    'pids_max':open('/sys/fs/cgroup/pids.max').read().strip()}))'''

STARTUP = '''from playwright.sync_api import sync_playwright
from app.browser_worker import fixture_origin
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,timeout=5000)
    page=browser.new_page(service_workers='block',accept_downloads=False)
    response=page.goto(fixture_origin(),timeout=4000)
    assert response.status==200
    for forbidden in ('http://1.1.1.1/', 'http://169.254.169.254/'):
        try:
            page.goto(forbidden,timeout=1000)
        except Exception:
            continue
        raise AssertionError('Chromium reached a forbidden destination')
    print('sandboxed Chromium launched; fixture returned 200')
    browser.close()
'''


async def validate(sha, manifest):
    sandbox = DockerSandbox(manifest)
    result = {'commit': sha, 'checks': {}, 'restrictions': {}, 'runtime': {}}
    names = []
    network = None
    try:
        pr = PRData(pr_url='component-only', head_sha=sha, base_sha=sha,
                    changed_files=[], diff='', sources={})
        await asyncio.wait_for(sandbox.start(pr), 30)
        names, network = [sandbox.container, sandbox.browser], sandbox.network
        result['checks']['startup'] = True
        net = json.loads(await docker_command('network', 'inspect', network))[0]
        assert net['Internal'] and not net['EnableIPv6'] and len(net['Containers']) == 2
        assert net['Options']['com.docker.network.bridge.gateway_mode_ipv4'] == 'isolated'
        result['checks']['isolated_internal_network'] = True
        for role, name in zip(('app', 'browser'), names):
            details = json.loads(await docker_command('inspect', name))[0]
            host, config = details['HostConfig'], details['Config']
            assert not host['Privileged'] and not host['Binds'] and not host['PortBindings']
            assert not details['Mounts']  # tmpfs is in HostConfig.Tmpfs, no bind/volume mounts
            assert host['ReadonlyRootfs'] and config['User'] == '10001:10001'
            assert host['NanoCpus'] == 1_000_000_000 and host['Memory'] == 768 * 1024 * 1024
            assert host['PidsLimit'] == 128 and 'ALL' in host['CapDrop']
            assert 'no-new-privileges' in host['SecurityOpt']
            assert len(details['NetworkSettings']['Networks']) == 1
            assert not details['NetworkSettings']['Networks'][network]['Gateway']
            custom = [value for value in host['SecurityOpt'] if value.startswith('seccomp=')]
            assert bool(custom) == (role == 'browser')
            assert not any('unconfined' in value for value in host['SecurityOpt'])
            result['restrictions'][role] = {
                'image': details['Image'], 'user': config['User'], 'read_only': True,
                'privileged': False, 'mounts': [], 'published_ports': {},
                'cap_drop': host['CapDrop'], 'no_new_privileges': True,
                'seccomp': 'custom-default-derived' if custom else 'docker-default',
                'cpus': 1, 'memory_bytes': host['Memory'], 'pids_limit': host['PidsLimit']}
            probe = json.loads(await docker_command('exec', name, 'python', '-c', PROBE, timeout=8))
            assert probe['uid'] == 10001 and probe['read_only'] and probe['docker_socket_absent']
            assert int(probe['cap_eff'],16) == 0 and probe['seccomp'] == '2' and probe['no_new_privs'] == '1'
            assert all(probe['external_connections_blocked'].values()) and probe['dns_blocked']
            assert probe['no_default_route'] and probe['cpu_max'] == '100000 100000'
            assert probe['memory_max'] == str(768 * 1024 * 1024) and probe['pids_max'] == '128'
            result['runtime'][role] = probe
        result['checks']['runtime_isolation'] = True
        await docker_command('exec', sandbox.browser, 'python', '-c', STARTUP, timeout=12)
        result['checks']['sandboxed_chromium_and_fixture_navigation'] = True
        action = TypeAdapter(ToolAction).validate_python({'name': 'browser_test', 'arguments': {
            'authenticate': True, 'review_text': 'Component check {{MARKER}}', 'book_id': 1}})
        observation = await sandbox.execute(action)
        assert observation['marker_tested'] and not observation['marker_executed']
        assert observation['anonymous_revisit'] and observation['path'] == '/books/1'
        result['checks']['bounded_browser_workflow'] = True
        action = TypeAdapter(ToolAction).validate_python({'name': 'http_request', 'arguments': {'query': {'q': 'Hobbit'}}})
        response = await sandbox.execute(action)
        assert response['status_code'] == 200 and response['book_count'] == 1
        result['checks']['http_worker_preserved'] = True
        original = sandbox.command
        async def short_tool(*args, **kwargs):
            if args[:2] == ('exec', '-i'):
                kwargs['timeout'] = .05
            return await original(*args, **kwargs)
        sandbox.command = short_tool
        try:
            await sandbox.execute(TypeAdapter(ToolAction).validate_python({
                'name': 'browser_test', 'arguments': {}}))
            raise AssertionError('Expected the shortened tool deadline to expire')
        except asyncio.TimeoutError:
            assert sandbox.container is None and sandbox.browser is None and sandbox.network is None
        result['checks']['tool_timeout_cleanup'] = True
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    finally:
        await sandbox.stop()
        containers = (await docker_command('ps', '-a', '--format', '{{.Names}}')).splitlines()
        networks = (await docker_command('network', 'ls', '--format', '{{.Name}}')).splitlines()
        result['checks']['cleanup'] = not any(name in containers for name in names) and network not in networks
    return result


async def main():
    manifest = Path(sys.argv[1])
    results = [await validate(sha, manifest) for sha in json.loads(manifest.read_text())]
    report = Path(__file__).resolve().parents[1] / 'browser/validation-report.json'
    report.write_text(json.dumps({'synthetic_components_only': True, 'fixtures': results}, indent=2) + '\n')
    print(report.read_text())
    if any(result.get('error_type') or not all(result['checks'].values()) for result in results):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
