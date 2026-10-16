"""Worker-only HTTP executor. Target fixed to the container's loopback app."""
import re
import secrets
import httpx
from ..schemas import HTTPArgs, local_path

TARGET = 'http://127.0.0.1:5000'
BODY_LIMIT = 64000


async def request_bounded(client, method, path, **kwargs):
    local_path(path)
    async with client.stream(method, TARGET + path, **kwargs) as response:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > BODY_LIMIT:
                raise ValueError('Response exceeds tool limit')
        return response.status_code, body.decode('utf-8', errors='replace')


async def csrf(client):
    status, body = await request_bounded(client, 'GET', '/signup')
    if status != 200:
        raise ValueError('CSRF form unavailable')
    match = re.search(r'name="csrf_token" value="([a-f0-9]+)"', body)
    if not match:
        raise ValueError('CSRF token unavailable')
    return match[1]


async def signup(client):
    name = 'bmf_' + secrets.token_hex(5)
    token = await csrf(client)
    status, _ = await request_bounded(client, 'POST', '/signup', data={
        'username': name, 'password': secrets.token_hex(12), 'csrf_token': token})
    if status != 302:
        raise ValueError('Controlled account creation failed')
    return name


async def http_request(args: HTTPArgs, client=None):
    if client is None:
        from ..fixture_worker import require_container
        require_container()
        async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as owned:
            return await http_request(args, owned)
    if args.authenticate:
        await signup(client)
    form = dict(args.form)
    if args.method == 'POST':
        form['csrf_token'] = await csrf(client)
    status, body = await request_bounded(client, args.method, args.path,
                                        params=args.query, data=form if args.method == 'POST' else None)
    return {'status_code': status, 'body': body[:16000],
            'body_excerpt_truncated': len(body) > 16000,
            'book_count': body.count('class="book-card"'),
            'path': args.path, 'method': args.method}
