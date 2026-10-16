"""Reproduce generated security regressions inside an approved Docker fixture."""
import json
import os
from pydantic import TypeAdapter
from .schemas import PRData, ToolAction
from .sandbox import DockerSandbox


async def replay_artifact(path):
    data = json.loads(path.read_text())
    pr = PRData(pr_url='replay', head_sha=data['commit'], base_sha=data['commit'],
                changed_files=[], diff='', sources={})
    sandbox = DockerSandbox(os.environ.get('BMF_FIXTURE_APPROVALS'))
    try:
        await sandbox.start(pr)
        results = []
        for raw in data['actions']:
            action = TypeAdapter(ToolAction).validate_python(raw)
            if action.name not in ('http_request', 'browser_test'):
                raise ValueError('Replay accepts execution actions only')
            results.append(await sandbox.execute(action))
        if data['property'] == 'no_browser_execution':
            assert results[0]['marker_tested'] is True
            assert results[0]['marker_executed'] is False, 'Stored browser execution reproduced'
        elif data['property'] == 'same_book_count':
            assert all(result['status_code'] == 200 for result in results)
            assert results[0]['book_count'] == results[1]['book_count'], 'Search differs from stated control'
        else:
            raise ValueError('Unsupported replay property')
    finally:
        await sandbox.stop()
