"""Trusted, stdin-only browser dispatcher. No server or general execution API."""
import asyncio
import ipaddress
import json
import os
import signal
import sys
from pydantic import TypeAdapter
from .schemas import ToolAction


def require_browser():
    if not os.path.exists('/.dockerenv') or os.getenv('BMF_BROWSER_WORKER') != '1':
        raise RuntimeError('Browser worker requires the approved Docker image')


def fixture_origin():
    require_browser()
    address = ipaddress.IPv4Address(os.environ['BMF_FIXTURE_IP'])
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified:
        raise ValueError('Invalid fixture address')
    return f'http://{address}:5000'


async def run_tool(data):
    require_browser()
    action = TypeAdapter(ToolAction).validate_json(data)
    if action.name != 'browser_test':
        raise ValueError('Browser worker accepts browser_test only')
    from .tools.browser import browser_test
    async with asyncio.timeout(13):
        return await browser_test(action.arguments)


def main():
    require_browser()
    signal.alarm(150 if sys.argv[1:] == ['serve'] else 14)
    if sys.argv[1:] == ['serve']:
        signal.pause()  # PID 1 exits on expiry; Docker --init reaps children.
    elif sys.argv[1:] == ['health']:
        fixture_origin()
        print('ready')
    elif sys.argv[1:] == ['tool']:
        data = sys.stdin.buffer.read(20001)
        if len(data) > 20000:
            raise ValueError('Worker input exceeds limit')
        print(json.dumps(asyncio.run(run_tool(data))))
    else:
        raise ValueError('Unsupported browser operation')


if __name__ == '__main__':
    main()
