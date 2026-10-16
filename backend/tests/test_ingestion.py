import base64
import json
import httpx
import pytest
from pydantic import ValidationError
from app.github import GitHubClient, GitHubError, SOURCE_PATHS
from app.schemas import AnalyzeRequest
from conftest import run


@pytest.mark.parametrize('url', [
    'http://github.com/png270/breakfix/pull/1',
    'https://github.com/other/repo/pull/1',
    'https://github.com/png270/breakfix/pull/1?x=2',
    'https://github.com@evil.test/png270/breakfix/pull/1',
    'https://github.com/png270/breakfix/pull/0',
    'https://github.com/png270/breakfix/pull/../1',
])
def test_url_rejection(url):
    with pytest.raises(ValidationError):
        AnalyzeRequest(pr_url=url)


def test_url_accepts_repository_pr():
    assert AnalyzeRequest(pr_url='https://github.com/png270/breakfix/pull/999').pr_url.endswith('/999')


def mocked_github(mode='ok'):
    calls = []
    count = 0

    def respond(request):
        nonlocal count
        calls.append(str(request.url))
        if mode == 'failure':
            return httpx.Response(403, json={'message': 'rate limited'})
        if '/contents/' in request.url.path:
            content = ('# known bypass demo-marker\nsource = "safe context"\n' if request.url.path.endswith('.py')
                       else '{# known bypass demo-marker #}<p>safe context</p>')
            return httpx.Response(200, json={'type': 'file', 'encoding': 'base64',
                                  'content': base64.b64encode(content.encode()).decode()})
        if request.url.path.endswith('/files'):
            return httpx.Response(200, json=[
                {'filename': 'hackathon.md', 'patch': 'EVALUATION SECRET'},
                {'filename': 'README.md', 'patch': 'EXPECTED VERDICT'},
                {'filename': 'demo-app/tests/test_bypass.py', 'patch': 'KNOWN PAYLOAD'},
                {'filename': 'demo-app/app.py', 'patch': '+# KNOWN PAYLOAD\n+source = "safe context"'},
            ])
        count += 1
        return httpx.Response(200, json={'title': 'EXPECTED VERDICT', 'body': 'KNOWN PAYLOAD',
            'base': {'sha': 'a' * 40, 'repo': {'full_name': 'png270/breakfix'}},
            'head': {'sha': ('c' if mode == 'race' and count > 1 else 'b') * 40}})
    return GitHubClient(httpx.AsyncClient(base_url='https://api.github.com',
                                        transport=httpx.MockTransport(respond))), calls


def test_context_exclusions_and_pinned_source_reads():
    client, calls = mocked_github()
    pr = run(client.fetch('https://github.com/png270/breakfix/pull/17'))
    context = pr.model_dump_json()
    assert 'EXPECTED VERDICT' not in context and 'KNOWN PAYLOAD' not in context
    assert 'demo-marker' not in context
    assert pr.changed_files == ['demo-app/app.py']
    assert set(pr.sources) == SOURCE_PATHS
    assert all('ref=' + 'b' * 40 in url for url in calls if '/contents/' in url)


@pytest.mark.parametrize('mode', ['failure', 'race'])
def test_ingestion_failure_and_mutating_pr(mode):
    client, _ = mocked_github(mode)
    with pytest.raises(GitHubError):
        run(client.fetch('https://github.com/png270/breakfix/pull/17'))


def test_large_response_rejected():
    client = GitHubClient(httpx.AsyncClient(base_url='https://api.github.com',
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 1_000_001))))
    with pytest.raises(GitHubError, match='limit'):
        run(client.get('/test'))


def test_malformed_metadata_is_ingestion_failure():
    client = GitHubClient(httpx.AsyncClient(base_url='https://api.github.com',
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'head': None}))))
    with pytest.raises(GitHubError):
        run(client.fetch('https://github.com/png270/breakfix/pull/17'))
