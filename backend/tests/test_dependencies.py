"""Keep worker images independent of host orchestration and test packages."""
import re
from pathlib import Path
import pytest
from app.sandbox import BACKEND, BROWSER_FILES, browser_digest
from app.fixture_worker import run_tool
from conftest import run


def pins(path):
    return dict(re.findall(r'^([a-zA-Z0-9_.-]+)==([^\s]+)', path.read_text(), re.MULTILINE))


@pytest.mark.parametrize('relative,required,forbidden', [
    ('requirements.lock.txt', {'fastapi', 'uvicorn', 'httpx', 'pydantic', 'neatlogs'},
     {'pytest', 'playwright', 'flask'}),
    ('fixture/requirements.lock.txt', {'flask', 'httpx', 'pydantic'},
     {'pytest', 'playwright', 'neatlogs', 'fastapi', 'uvicorn'}),
    ('browser/requirements.lock.txt', {'playwright', 'pydantic'},
     {'pytest', 'neatlogs', 'flask', 'httpx', 'fastapi', 'uvicorn'}),
])
def test_environment_locks_are_separate_and_hashed(relative, required, forbidden):
    path = BACKEND / relative
    packages = pins(path)
    assert required <= packages.keys()
    assert not forbidden & packages.keys()
    for block in path.read_text().splitlines():
        if block and not block.startswith((' ', '#')):
            assert re.fullmatch(r'[a-zA-Z0-9_.-]+==[^\s]+ \\', block)
    assert path.read_text().count('--hash=sha256:') >= len(packages)


def test_development_lock_keeps_runtime_versions():
    runtime = pins(BACKEND / 'requirements.lock.txt')
    development = pins(BACKEND / 'requirements-dev.lock.txt')
    assert runtime.items() <= development.items()
    assert development['pytest'] == '9.1.1' and development['playwright'] == '1.63.0'
    assert runtime['neatlogs'] == '1.4.27'


def test_dockerfiles_use_worker_locks_and_hash_verification():
    for worker in ('fixture', 'browser'):
        recipe = (BACKEND / worker / 'Dockerfile').read_text()
        assert f'COPY backend/{worker}/requirements.lock.txt ' in recipe
        assert '--require-hashes' in recipe
        assert 'COPY backend/requirements.lock.txt' not in recipe
    fixture = (BACKEND / 'fixture/Dockerfile').read_text()
    assert 'playwright install' not in fixture
    assert 'COPY backend/app /runner/app' not in fixture


def test_future_fixture_worker_refuses_browser_actions(monkeypatch):
    monkeypatch.setattr('app.fixture_worker.require_container', lambda: None)
    with pytest.raises(ValueError, match='Unsupported'):
        run(run_tool('{"name":"browser_test","arguments":{}}'))


def test_browser_approval_digest_covers_dependency_lock(tmp_path, monkeypatch):
    original = browser_digest()
    for name in BROWSER_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BACKEND / name).read_bytes())
    monkeypatch.setattr('app.sandbox.BACKEND', tmp_path)
    assert browser_digest() == original
    with (tmp_path / 'browser/requirements.lock.txt').open('a') as stream:
        stream.write('\n# Changed dependency policy\n')
    assert browser_digest() != original
