"""Only fixed Docker lifecycle/worker commands, never arbitrary shell or PR code.

An operator must approve an immutable, locally built fixture image for a commit.
Fetched source is inspected as text and is never mounted or executed on host.
"""
import asyncio
import json
import hashlib
import ipaddress
import os
import re
import shutil
import uuid
from pathlib import Path


class SandboxError(RuntimeError):
    pass


async def docker_command(*arguments, input_data=None, timeout=10):
    executable = shutil.which('docker')
    if not executable:
        raise SandboxError('Docker CLI unavailable; host fallback is disabled')
    process = await asyncio.create_subprocess_exec(
        executable, *arguments, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def bounded_read(stream):
        chunks = bytearray()
        while chunk := await stream.read(4096):
            chunks.extend(chunk)
            if len(chunks) > 100000:
                raise SandboxError('Docker worker output exceeds limit')
        return bytes(chunks)

    async def communicate():
        process.stdin.write(input_data or b'')
        await process.stdin.drain()
        process.stdin.close()
        output, error = await asyncio.gather(bounded_read(process.stdout), bounded_read(process.stderr))
        await process.wait()
        if process.returncode:
            raise SandboxError('Docker command failed; check daemon and approved image locally')
        return output.decode()

    try:
        return await asyncio.wait_for(communicate(), timeout)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


# Fixed trusted launcher: immutable fixture's only changed runtime setting is bind address.
# Neither this code nor any Docker argument comes from model output or downloaded PR text.
FIXTURE_LAUNCH = """import runpy, sys
from flask import Flask
original = Flask.run
def private_run(self, *args, **kwargs):
    kwargs['host'] = '0.0.0.0'
    return original(self, *args, **kwargs)
Flask.run = private_run
sys.argv = ['fixture_worker', 'serve']
runpy.run_module('app.fixture_worker', run_name='__main__')
"""
BACKEND = Path(__file__).resolve().parents[1]
BROWSER_FILES = ('app/__init__.py', 'app/schemas.py', 'app/browser_worker.py',
                 'app/tools/__init__.py', 'app/tools/browser.py', 'browser/Dockerfile',
                 'browser/requirements.txt', 'browser/requirements.lock.txt')


def browser_digest():
    digest = hashlib.sha256()
    for name in BROWSER_FILES:
        digest.update(name.encode() + b'\0' + (BACKEND / name).read_bytes() + b'\0')
    return digest.hexdigest()


class DockerSandbox:
    def __init__(self, manifest=None, command=docker_command, browser_manifest=None):
        self.manifest = Path(manifest) if manifest else None
        self.browser_manifest = Path(browser_manifest or os.getenv('BMF_BROWSER_APPROVAL',
                                         str(BACKEND / 'browser/approval.json')))
        self.command = command
        self.container = self.browser = self.network = self.commit = None

    async def approved_images(self, pr):
        approvals = json.loads(self.manifest.read_text()) if self.manifest and self.manifest.is_file() else {}
        image = approvals.get(pr.head_sha)
        if not isinstance(image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
            raise SandboxError('Pinned head has no preapproved immutable fixture image')
        details = json.loads(await self.command('image', 'inspect', image, timeout=5))[0]
        if details.get('Id') != image or details.get('Config', {}).get('Labels', {}).get('bmf.commit') != pr.head_sha:
            raise SandboxError('Fixture image does not attest the pinned commit')
        approval = json.loads(self.browser_manifest.read_text()) if self.browser_manifest.is_file() else {}
        browser_image = approval.get('image')
        profile = BACKEND / 'browser/chromium-seccomp.json'
        if (not isinstance(browser_image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', browser_image)
                or approval.get('runner_sha256') != browser_digest()
                or approval.get('seccomp_sha256') != hashlib.sha256(profile.read_bytes()).hexdigest()):
            raise SandboxError('No matching approved immutable browser worker and seccomp policy')
        details = json.loads(await self.command('image', 'inspect', browser_image, timeout=5))[0]
        labels = details.get('Config', {}).get('Labels', {})
        if (details.get('Id') != browser_image or labels.get('bmf.browser-worker') != '1'
                or labels.get('bmf.runner.sha256') != browser_digest()
                or details.get('Config', {}).get('Volumes')):
            raise SandboxError('Browser image does not attest the trusted runner')
        return image, browser_image, profile

    async def start(self, pr):
        if self.container or self.browser or self.network:
            raise SandboxError('Sandbox already started or cleanup incomplete')
        await self.command('info', '--format', '{{.ServerVersion}}', timeout=5)
        image, browser_image, profile = await self.approved_images(pr)
        token = uuid.uuid4().hex
        self.network, self.container, self.browser = (f'bmf-{token}-{suffix}' for suffix in ('net', 'app', 'browser'))
        self.commit = pr.head_sha
        common = ('--pull=never', '--read-only', '--cap-drop=ALL',
                  '--security-opt=no-new-privileges', '--user=10001:10001',
                  '--cpus=1', '--memory=768m', '--pids-limit=128',
                  '--tmpfs=/tmp:rw,nosuid,size=128m,mode=1777', '--shm-size=128m',
                  '--init', '--log-driver=none', '--dns=127.0.0.1',
                  '--workdir=/runner', '--entrypoint=python')
        try:
            await self.command('network', 'create', '--driver=bridge', '--internal',
                               '--opt=com.docker.network.bridge.gateway_mode_ipv4=isolated',
                               '--opt=com.docker.network.bridge.enable_ip_masquerade=false',
                               '--label=bmf.managed=true', self.network, timeout=5)
            network = json.loads(await self.command('network', 'inspect', self.network, timeout=3))[0]
            if (not network.get('Internal') or network.get('EnableIPv6') or
                    network.get('Options', {}).get('com.docker.network.bridge.gateway_mode_ipv4') != 'isolated'):
                raise SandboxError('Docker cannot enforce the required isolated internal network')
            await self.command('run', '-d', '--name', self.container, '--network=' + self.network,
                               *common, image, '-c', FIXTURE_LAUNCH, timeout=8)
            details = json.loads(await self.command('inspect', self.container, timeout=3))[0]
            settings = details['NetworkSettings']['Networks'][self.network]
            address = ipaddress.IPv4Address(settings['IPAddress'])
            if settings.get('Gateway') or not address.is_private or address.is_loopback or address.is_link_local:
                raise SandboxError('Fixture network has an unsafe route or address')
            await self.command('run', '-d', '--name', self.browser, '--network=' + self.network,
                               *common, '--security-opt=seccomp=' + str(profile),
                               '--env=BMF_FIXTURE_IP=' + str(address), browser_image,
                               '-m', 'app.browser_worker', 'serve', timeout=8)
            for container, module in ((self.container, 'app.fixture_worker'), (self.browser, 'app.browser_worker')):
                for attempt in range(6):
                    try:
                        await self.command('exec', container, 'python', '-m', module, 'health', timeout=2)
                        break
                    except SandboxError:
                        if attempt == 5:
                            raise SandboxError('Worker did not become ready')
                        await asyncio.sleep(.2)
        except BaseException:
            # Cancellation during startup must also remove partial resources.
            await asyncio.shield(self.stop())
            raise

    async def execute(self, action):
        if not self.container or not self.browser:
            raise SandboxError('Sandbox not started')
        if action.name not in ('http_request', 'browser_test'):
            raise ValueError('Worker action not permitted')
        # Revalidate at the host boundary; the worker validates independently too.
        from pydantic import TypeAdapter
        from .schemas import ToolAction
        action = TypeAdapter(ToolAction).validate_json(action.model_dump_json())
        browser = action.name == 'browser_test'
        try:
            output = await self.command('exec', '-i', self.browser if browser else self.container,
                                        'python', '-m', 'app.browser_worker' if browser else 'app.fixture_worker',
                                        'tool', input_data=action.model_dump_json().encode(), timeout=14)
            result = json.loads(output)
            if not isinstance(result, dict):
                raise SandboxError('Invalid worker observation')
            return result
        except BaseException:
            # Killing a Docker exec client alone does not kill its container process.
            await asyncio.shield(self.stop())
            raise

    async def stop(self):
        # Query exact owned names before removal: partial startup may never have
        # created a resource. Retain references whenever the daemon cannot confirm.
        names = [name for name in (self.browser, self.container) if name]
        if names:
            present = set((await self.command('ps', '-a', '--format', '{{.Names}}',
                                             '--filter=name=^bmf-', timeout=1.5)).splitlines())
            owned = [name for name in names if name in present]
            if owned:
                await self.command('rm', '-f', *owned, timeout=1.5)
            self.browser = self.container = None
        if self.network:
            present = (await self.command('network', 'ls', '--format', '{{.Name}}',
                                          '--filter=name=^' + self.network + '$', timeout=1)).splitlines()
            if self.network in present:
                await self.command('network', 'rm', self.network, timeout=1.5)
            self.network = None
