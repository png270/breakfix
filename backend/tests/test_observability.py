import json
from contextlib import contextmanager
from types import SimpleNamespace
from app.observability import NeatlogsObserver, ObserverFactory, sanitize
from app.agent import Agent
from conftest import FakeLLM, FakeSandbox, run, browser_step, compare_step


class SDK:
    def __init__(self): self.spans = []; self.fail = False
    @contextmanager
    def trace(self, name, kind=None):
        if self.fail: raise RuntimeError('export failure')
        attrs = {}
        self.spans.append((name, kind, attrs))
        yield SimpleNamespace(set_attribute=lambda k, v: attrs.update({k: v}),
                              get_span_context=lambda: SimpleNamespace(trace_id=123))
    def flush(self): raise RuntimeError('export failure')
    def shutdown(self): pass


def test_trace_creation_and_correlation():
    sdk = SDK(); observer = NeatlogsObserver(sdk)
    with observer.scope():
        observer.event('run.start', {'commit': 'a' * 40})
        observer.event('run.end', {'success': True})
    assert observer.trace_id() == format(123, '032x')
    assert len(sdk.spans) == 3
    assert {a['bmf.run_id'] for _, _, a in sdk.spans} == {observer.run_id}
    assert NeatlogsObserver(sdk).run_id != observer.run_id


def test_sensitive_data_redaction():
    dirty = {'password': 'hidden-password', 'Authorization': 'Bearer hidden-token',
             'cookie': 'hidden-cookie', 'env': {'KEY': 'hidden-key'},
             'action': {'name': 'http_request', 'arguments': {
                 'form': {'password': 'hidden-password'}, 'query': {'q': 'hidden-query'},
                 'path': '/login?token=hidden-path', 'method': 'POST'}},
             'observation': {'data': {'body': 'hidden-body', 'headers': {'x': 'hidden-header'}}},
             'hypotheses': [{'statement': 'hidden-prompt'}]}
    result = json.dumps(sanitize(dirty))
    assert 'hidden-' not in result
    assert 'http_request' in result and 'POST' in result


def test_missing_key(monkeypatch):
    monkeypatch.delenv('NEATLOGS_API_KEY', raising=False)
    factory = ObserverFactory()
    assert factory.status == 'missing_key'
    assert not factory.live_ready and factory.new_run().trace_id() is None


def test_export_failures_do_not_change_agent(pr):
    sdk = SDK(); sdk.fail = True
    observer = NeatlogsObserver(sdk)
    result = run(Agent(FakeLLM([{'finish': 'INCONCLUSIVE'}]), FakeSandbox(), observer).run(pr))
    assert result.terminal_state == 'finished' and observer.failed
    factory = ObserverFactory(SDK()); factory.shutdown()
    assert factory.status == 'export_failed' and not factory.live_ready


def test_agent_lifecycle(pr):
    sdk = SDK(); observer = NeatlogsObserver(sdk)
    result = run(Agent(FakeLLM([browser_step(), compare_step(), {'finish': 'BYPASS_CONFIRMED'}]),
                       FakeSandbox([{'marker_executed': True, 'marker_tested': True}]), observer).run(pr))
    names = [name for name, _, _ in sdk.spans]
    assert names[0:2] == ['break-my-fix.run', 'run.start']
    assert names[-2:] == ['verdict', 'run.end']
    assert 'agent.decision' in names and 'tool.attempt' in names and 'llm.call' in names
    assert result.verdict == 'BYPASS_CONFIRMED' and result.trace_id == observer.trace_id()
    assert all(a['bmf.run_id'] == observer.run_id for _, _, a in sdk.spans)


def test_broken_custom_observer_is_nonfatal(pr):
    class Broken:
        def event(self, *args): raise RuntimeError('broken observer')
        def trace_id(self): return None
    result = run(Agent(FakeLLM([{'finish': 'INCONCLUSIVE'}]), FakeSandbox(), Broken()).run(pr))
    assert result.terminal_state == 'finished'


def test_mask_preserves_completion_and_removes_resource_secrets():
    from app.observability import export_mask
    snapshot = {'attributes': {'neatlogs.trace.complete': True, 'neatlogs.internal': True,
                 'neatlogs.span.kind': 'Neatlogs.INTERNAL', 'input.value': 'hidden-input'},
                'resource': {'attributes': {'service.name': 'neatlogs',
                    'neatlogs.workflow_name': 'break-my-fix', 'process.env': 'hidden-env'}},
                'events': [{'attributes': {'exception.message': 'hidden-password'}}],
                'status': {'code': 'ERROR', 'description': 'hidden-description'}}
    masked = export_mask(snapshot)
    assert masked['attributes']['neatlogs.trace.complete'] is True
    assert masked['resource']['attributes']['neatlogs.workflow_name'] == 'break-my-fix'
    assert 'hidden-' not in json.dumps(masked)


def test_real_sdk_parent_and_trace_correlation(monkeypatch):
    import pytest
    from importlib.metadata import version
    if tuple(map(int, version('neatlogs').split('.')[:2])) < (1, 2):
        pytest.skip('Current SDK requires Python 3.10–3.13')
    monkeypatch.delenv('NEATLOGS_API_KEY', raising=False)
    import neatlogs
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    neatlogs.init(api_key='', instrumentations=[], capture_logs=False,
                  workflow_name='local-test', tracer_provider=provider,
                  register_shutdown_handlers=False)
    try:
        observer = NeatlogsObserver(neatlogs)
        with observer.scope():
            observer.event('run.start', {'commit': 'a' * 40})
            observer.event('verdict', {'verdict': 'INCONCLUSIVE'})
        spans = [s for s in exporter.get_finished_spans() if s.name != 'neatlogs.trace.complete']
        root = next(s for s in spans if s.name == 'break-my-fix.run')
        assert len(spans) == 3
        assert root.parent is None
        assert {s.context.trace_id for s in spans} == {root.context.trace_id}
        assert all(s.parent.span_id == root.context.span_id for s in spans if s is not root)
        assert observer.trace_id() == format(root.context.trace_id, '032x')
    finally:
        neatlogs.shutdown()
        provider.shutdown()
