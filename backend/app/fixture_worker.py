"""Trusted runner shipped in the reviewed image; never invoked on the Mac."""
import asyncio
import importlib.util
import json
import os
import sys
from pydantic import TypeAdapter
from .schemas import ToolAction


def require_container():
    if not os.path.exists('/.dockerenv') or os.environ.get('BMF_FIXTURE_WORKER') != '1':
        raise RuntimeError('Fixture worker requires the approved Docker image')


async def run_tool(data):
    require_container()
    action = TypeAdapter(ToolAction).validate_json(data)
    if action.name == 'http_request':
        from .tools.http import http_request
        return await http_request(action.arguments)
    raise ValueError('Unsupported worker tool')


def main():
    require_container()
    if sys.argv[1:] == ['serve']:
        import signal
        signal.alarm(150)  # Container self-expires even if the API process disappears.
        spec = importlib.util.spec_from_file_location('bookshelf_fixture', '/fixture/app.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        app = module.create_app({'DATABASE': '/tmp/bookshelf.sqlite3',
                                 'SECRET_KEY': 'isolated-fixture-only',
                                 'SESSION_COOKIE_SECURE': False})
        # Factory's root_path comes from /fixture/app.py, so templates stay there.
        result = app.test_cli_runner().invoke(args=['init-db'])
        if result.exit_code:
            raise RuntimeError('Fixture initialization failed')
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    elif sys.argv[1:] == ['health']:
        import httpx
        response = httpx.get('http://127.0.0.1:5000/', timeout=2, trust_env=False)
        response.raise_for_status()
        print('ready')
    elif sys.argv[1:] == ['tool']:
        print(json.dumps(asyncio.run(run_tool(sys.stdin.buffer.read(20000)))))
    else:
        raise ValueError('Unsupported worker operation')


if __name__ == '__main__':
    main()
