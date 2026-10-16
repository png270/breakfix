"""Read-only GitHub ingestion; never checkout or execute fetched PR code."""
import base64
import re
import httpx
from .schemas import AnalyzeRequest, PRData

REPO = 'png270/breakfix'
# Positive allowlist: neither tests nor README/build-log text can reach the LLM.
SOURCE_PATHS = frozenset({
    'demo-app/app.py', 'demo-app/templates/base.html',
    'demo-app/templates/browse.html', 'demo-app/templates/book.html',
    'demo-app/templates/auth.html', 'demo-app/templates/profile.html',
    'demo-app/templates/edit_profile.html',
})


def source_path(path):
    return path in SOURCE_PATHS


def scrub_comments(text, path):
    # Remove fixture labels/comments, including prewritten demonstrations.
    if path.endswith('.py'):
        text = '\n'.join(line for line in text.splitlines() if not line.lstrip(' +-').startswith('#'))
    return re.sub(r'{#.*?#}|<!--.*?-->', '', text, flags=re.S)


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, client=None, token=None):
        self.client = client or httpx.AsyncClient(
            base_url='https://api.github.com', timeout=10, follow_redirects=False,
            trust_env=False, headers={'Accept': 'application/vnd.github+json',
                                      **({'Authorization': f'Bearer {token}'} if token else {})})

    async def close(self):
        await self.client.aclose()

    async def get(self, path):
        try:
            async with self.client.stream('GET', path) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 1_000_000:
                        raise GitHubError('GitHub response exceeds ingestion limit')
            import json
            return json.loads(content)
        except (httpx.HTTPError, ValueError) as exc:
            raise GitHubError('GitHub retrieval failed or returned invalid JSON') from exc

    async def fetch(self, url):
        AnalyzeRequest(pr_url=url)
        try:
            return await self._fetch(url)
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise GitHubError('Incomplete or invalid PR/source metadata') from exc

    async def _fetch(self, url):
        AnalyzeRequest(pr_url=url)
        number = url.rsplit('/', 1)[1]
        endpoint = f'/repos/{REPO}/pulls/{number}'
        metadata = await self.get(endpoint)
        if metadata.get('base', {}).get('repo', {}).get('full_name') != REPO:
            raise GitHubError('Repository mismatch')
        base_sha, head_sha = metadata['base']['sha'], metadata['head']['sha']
        if not all(re.fullmatch('[0-9a-f]{40}', sha) for sha in (base_sha, head_sha)):
            raise GitHubError('Invalid commit identifier')
        changed, patches, limits = [], [], []
        for page in range(1, 5):
            files = await self.get(endpoint + f'/files?per_page=100&page={page}')
            if not isinstance(files, list):
                raise GitHubError('Invalid file listing')
            for item in files:
                path = item['filename']
                if not source_path(path):
                    continue
                changed.append(path)
                patch = item.get('patch')
                if patch is None:
                    limits.append(f'Patch unavailable for {path}')
                else:
                    patches.append(f'FILE {path}\n{scrub_comments(patch[:16000], path)}')
                    if len(patch) > 16000:
                        limits.append(f'Patch excerpt truncated: {path}')
            if len(files) < 100:
                break
        else:
            limits.append('Changed file pagination limit reached')
        sources = {}
        for path in sorted(SOURCE_PATHS):
            result = await self.get(f'/repos/{REPO}/contents/{path}?ref={head_sha}')
            if result.get('type') != 'file' or result.get('encoding') != 'base64':
                raise GitHubError('Unsupported source response')
            raw = base64.b64decode(result['content'], validate=False).decode('utf-8')
            if len(raw) > 20000:
                limits.append(f'Source excerpt truncated: {path}')
            sources[path] = scrub_comments(raw[:20000], path)
        # Pull-file diffs are mutable API data: reject a head/base changed during ingestion.
        latest = await self.get(endpoint)
        if latest['head']['sha'] != head_sha or latest['base']['sha'] != base_sha:
            raise GitHubError('PR changed during ingestion; retry against a stable head')
        if not changed:
            limits.append('No allowlisted application files changed')
        return PRData(pr_url=url, base_sha=base_sha, head_sha=head_sha,
                      changed_files=changed, diff='\n'.join(patches), sources=sources,
                      limitations=limits)
