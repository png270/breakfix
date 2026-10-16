"""Exactly one synthetic workflow; no GitHub, Docker or provider calls."""
import argparse
import uuid
import asyncio
import json
import os
import sys
import time
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import Agent
from app.observability import ObserverFactory
from app.schemas import Decision, PRData


class SyntheticLLM:
    model = 'synthetic-no-provider'
    usage = {}
    def __init__(self): self.calls = 0
    async def decide(self, context):
        self.calls += 1
        if self.calls == 1:
            return Decision.model_validate({'hypotheses': [{'id': 'h1',
                'statement': 'Synthetic lifecycle check', 'security_property': 'synthetic_only'}],
                'action': {'name': 'inspect_patch', 'arguments': {}}})
        return Decision(finish='INCONCLUSIVE')


class SyntheticSandbox:
    async def start(self, pr): pass
    async def stop(self): pass


def verify_trace(trace_id, project_id=None):
    """Read only this generated trace; never print response bodies or credentials."""
    endpoint = os.getenv('NEATLOGS_ENDPOINT', 'https://ingest.neatlogs.com').rstrip('/')
    deadline = time.monotonic() + 20
    try:
        with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
            while time.monotonic() < deadline:
                response = client.get(f'{endpoint}/api/traces/v3/{trace_id}',
                                      headers={'x-api-key': os.environ['NEATLOGS_API_KEY']})
                if response.status_code == 200:
                    data = response.json()
                    spans = data.get('spans', [])
                    names = {s.get('node_name') for s in spans}
                    actual_project = data.get('projectId')
                    visible = (data.get('status') == 'success' and bool(spans)
                               and all(s.get('traceId') == trace_id for s in spans)
                               and {'break-my-fix.run', 'run.start', 'run.end', 'verdict'} <= names
                               and (project_id is None or project_id == actual_project))
                    return {'verified': visible, 'project_id': actual_project,
                            'span_count': len(spans), 'status': data.get('status'),
                            'workflow_name': data.get('workflowName')}
                if response.status_code not in (202, 404):
                    return {'verified': False, 'http_status': response.status_code}
                time.sleep(1)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {'verified': False, 'reason': 'readback_failed'}
    return {'verified': False, 'reason': 'readback_timeout'}


def main():
    env = Path(__file__).resolve().parents[1] / '.env'
    if not os.getenv('NEATLOGS_API_KEY') and env.is_file():
        for line in env.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() == 'NEATLOGS_API_KEY':
                os.environ['NEATLOGS_API_KEY'] = value.strip().strip('\"\'')
                break
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume-trace')
    parser.add_argument('--run-id')
    parser.add_argument('--verify', action='store_true', help='Read the exact trace back from neatlogs')
    parser.add_argument('--project-id', help='Require this project ID during readback')
    args = parser.parse_args()
    if args.resume_trace:
        # Retry only the existing synthetic trace, using a public OTel ID generator.
        import neatlogs
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.id_generator import IdGenerator
        from app.observability import export_mask
        trace_number = int(args.resume_trace, 16)
        if len(args.resume_trace) != 32 or not 0 < trace_number < 2 ** 128:
            raise ValueError('Invalid trace ID')
        class FixedTraceId(IdGenerator):
            def generate_trace_id(self): return trace_number
            def generate_span_id(self): return uuid.uuid4().int & (2 ** 64 - 1)
        neatlogs.init(api_key=os.environ['NEATLOGS_API_KEY'], workflow_name='break-my-fix',
                      instrumentations=[], capture_logs=False, mask=export_mask,
                      register_shutdown_handlers=False,
                      tracer_provider=TracerProvider(id_generator=FixedTraceId()))
        factory = ObserverFactory(neatlogs)
    else:
        factory = ObserverFactory()
    if factory.status != 'ready':
        print(json.dumps({'status': factory.status, 'trace_sent': False}))
        return 1
    observer = factory.new_run()
    if args.run_id:
        observer.run_id = uuid.UUID(args.run_id).hex
    pr = PRData(pr_url='https://github.com/png270/breakfix/pull/999999',
                base_sha='0' * 40, head_sha='0' * 40, changed_files=[], diff='', sources={})
    result = asyncio.run(Agent(SyntheticLLM(), SyntheticSandbox(), observer).run(pr))
    factory.shutdown()
    diagnostics = factory.sdk.get_delivery_diagnostics()
    readback = verify_trace(result.trace_id, args.project_id) if args.verify else None
    # Flushing is not dashboard verification. Read back this ID through the CLI.
    print(json.dumps({'trace_id': result.trace_id, 'run_id': observer.run_id,
                      'status': factory.status, 'delivery_diagnostics': diagnostics,
                      'readback': readback,
                      'synthetic': True, 'live_analysis_enabled': False}))
    losses = any(diagnostics.get(key, 0) for key in
                 ('span_queue_drops', 'span_export_failures', 'masked_span_drops'))
    return 0 if (result.trace_id and not observer.failed and factory.status == 'ready'
                 and not losses and (not args.verify or readback['verified'])) else 1


if __name__ == '__main__':
    raise SystemExit(main())
