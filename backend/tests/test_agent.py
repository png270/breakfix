import asyncio
import json
from app.agent import Agent
from conftest import FakeLLM, FakeSandbox, run, browser_step, compare_step, hypothesis


def marker(executed):
    return {'marker_executed': executed, 'marker_tested': True}


def test_adaptive_bypass_and_generated_regression(pr):
    llm = FakeLLM([browser_step(), compare_step(),
        {'action': {'name': 'generate_regression_test', 'arguments': {'evidence_id': 'e1'}}},
        {'finish': 'BYPASS_CONFIRMED', 'summary': 'Execution marker confirmed'}])
    sandbox = FakeSandbox([marker(True)])
    agent = Agent(llm, sandbox)
    result = run(agent.run(pr))
    assert result.verdict == 'BYPASS_CONFIRMED'
    assert result.terminal_state == agent.state.phase == 'finished'
    assert sandbox.stopped
    assert llm.contexts[1]['observations'][0]['data']['marker_executed'] is True
    assert llm.contexts[2]['evidence'][0]['outcome'] == 'violated'
    assert len(result.generated_regression_tests) == 2
    from pathlib import Path
    artifact = json.loads(Path(result.generated_regression_tests[0]).read_text())
    assert artifact['commit'] == pr.head_sha
    assert artifact['actions'][0]['name'] == 'browser_test'
    assert '{{MARKER}}' in artifact['actions'][0]['arguments']['review_text']
    assert 'eval(' not in Path(result.generated_regression_tests[1]).read_text()


def test_scoped_verified_fix(pr):
    agent = Agent(FakeLLM([browser_step(), compare_step(), {'finish': 'FIX_VERIFIED'}]), FakeSandbox([marker(False)]))
    result = run(agent.run(pr))
    assert result.verdict == 'FIX_VERIFIED'
    assert 'executed' in result.limitations[0]


def test_verdict_requires_real_execution_evidence(pr):
    for requested in ['FIX_VERIFIED', 'BYPASS_CONFIRMED']:
        result = run(Agent(FakeLLM([{'finish': requested}]), FakeSandbox()).run(pr))
        assert result.verdict == 'INCONCLUSIVE'


def test_errors_and_missing_marker_cannot_verify(pr):
    result = run(Agent(FakeLLM([browser_step(), compare_step(), {'finish': 'FIX_VERIFIED'}]),
                       FakeSandbox([{'marker_tested': False, 'marker_executed': False}])).run(pr))
    assert result.verdict == 'INCONCLUSIVE' and result.errors


def test_source_limits_prevent_verified_fix(pr):
    pr.limitations.append('Source truncated')
    result = run(Agent(FakeLLM([browser_step(), compare_step(), {'finish': 'FIX_VERIFIED'}]),
                       FakeSandbox([marker(False)])).run(pr))
    assert result.verdict == 'INCONCLUSIVE'


def test_budget_exhaustion(pr):
    decisions = [{'action': {'name': 'inspect_patch', 'arguments': {}}}] * 8
    result = run(Agent(FakeLLM(decisions), FakeSandbox()).run(pr))
    assert result.verdict == 'INCONCLUSIVE'
    assert result.terminal_state == 'budget_exhausted' and len(result.actions) == 8


def test_bounded_llm_retry(pr):
    llm = FakeLLM([RuntimeError('temporary'), {'finish': 'INCONCLUSIVE'}])
    agent = Agent(llm, FakeSandbox())
    result = run(agent.run(pr))
    assert len(llm.contexts) == 2 and len(result.errors) == 1


def test_read_only_tool_retry(pr):
    step = {'action': {'name': 'http_request', 'arguments': {}}}
    result = run(Agent(FakeLLM([step, {'finish': 'INCONCLUSIVE'}]),
                       FakeSandbox([RuntimeError('temporary'), {'status_code': 200}])).run(pr))
    assert result.observations[0].attempts == 2 and result.observations[0].status == 'ok'


def test_writes_are_not_retried(pr):
    sandbox = FakeSandbox([RuntimeError('write interrupted')])
    result = run(Agent(FakeLLM([browser_step(), {'finish': 'INCONCLUSIVE'}]), sandbox).run(pr))
    assert len(sandbox.actions) == 1 and result.observations[0].attempts == 1


def test_tool_timeout(pr):
    class SlowSandbox(FakeSandbox):
        async def execute(self, action):
            await asyncio.sleep(.1)
    result = run(Agent(FakeLLM([browser_step(), {'finish': 'INCONCLUSIVE'}]),
                       SlowSandbox(), tool_timeout=.01).run(pr))
    assert result.observations[0].status == 'error'
    assert 'TimeoutError' in result.errors[0]


def test_overall_timeout_and_cleanup(pr):
    class SlowSandbox(FakeSandbox):
        async def start(self, pr):
            await asyncio.sleep(.1)
    sandbox = SlowSandbox()
    result = run(Agent(FakeLLM([]), sandbox, overall_timeout=.01).run(pr))
    assert result.terminal_state == 'timeout' and sandbox.stopped


def test_sandbox_failure_never_calls_llm(pr):
    llm, sandbox = FakeLLM([]), FakeSandbox(fail=True)
    result = run(Agent(llm, sandbox).run(pr))
    assert not llm.contexts and sandbox.stopped
    assert result.verdict == 'INCONCLUSIVE' and result.terminal_state == 'failed'


def test_invalid_action_validated_before_execution(pr):
    llm = FakeLLM([{'action': {'name': 'shell', 'arguments': {'command': 'anything'}}},
                   {'finish': 'INCONCLUSIVE'}])
    sandbox = FakeSandbox()
    result = run(Agent(llm, sandbox).run(pr))
    assert not sandbox.actions and result.errors


def test_stated_search_property_and_control(pr):
    common = {'status_code': 200, 'path': '/', 'method': 'GET'}
    decisions = [
        {'hypotheses': [hypothesis()], 'action': {'name': 'http_request', 'arguments': {'query': {'q': 'no-such-probe'}}}},
        {'action': {'name': 'http_request', 'arguments': {'query': {'q': "no-such-probe' OR 1=1 --"}}}},
        {'action': {'name': 'compare_behavior', 'arguments': {'hypothesis_id': 'h1', 'property': 'same_book_count', 'observation_id': 'o2', 'control_id': 'o1'}}},
        {'finish': 'BYPASS_CONFIRMED'}]
    result = run(Agent(FakeLLM(decisions), FakeSandbox([{**common, 'book_count': 0}, {**common, 'book_count': 12}])).run(pr))
    assert result.verdict == 'BYPASS_CONFIRMED'


def test_comparing_normal_queries_cannot_claim_sqli(pr):
    decisions = [
        {'hypotheses': [hypothesis()], 'action': {'name': 'http_request', 'arguments': {'query': {'q': 'nothing'}}}},
        {'action': {'name': 'http_request', 'arguments': {'query': {'q': 'Hobbit'}}}},
        {'action': {'name': 'compare_behavior', 'arguments': {'hypothesis_id': 'h1', 'property': 'same_book_count', 'observation_id': 'o2', 'control_id': 'o1'}}},
        {'finish': 'BYPASS_CONFIRMED'}]
    common = {'status_code': 200, 'path': '/', 'method': 'GET'}
    result = run(Agent(FakeLLM(decisions), FakeSandbox([{**common, 'book_count': 0}, {**common, 'book_count': 1}])).run(pr))
    assert result.verdict == 'INCONCLUSIVE' and not result.evidence


def test_hypothesis_rewrite_is_rejected(pr):
    rewritten = hypothesis()
    rewritten['statement'] = 'Changed conclusion after seeing evidence'
    result = run(Agent(FakeLLM([browser_step(), {'hypotheses': [rewritten], 'finish': 'FIX_VERIFIED'}]),
                       FakeSandbox([marker(False)])).run(pr))
    assert result.verdict == 'INCONCLUSIVE' and result.terminal_state == 'failed'


def test_observability_event_order(pr):
    class Observer:
        live_ready = False
        def __init__(self): self.events = []
        def event(self, name, attributes): self.events.append(name)
        def trace_id(self): return None
    observer = Observer()
    result = run(Agent(FakeLLM([browser_step(), compare_step(), {'finish': 'BYPASS_CONFIRMED'}]),
                       FakeSandbox([marker(True)]), observer).run(pr))
    assert observer.events[0] == 'run.start'
    assert observer.events[-2:] == ['verdict', 'run.end']
    assert observer.events.count('llm.start') == 3
    assert observer.events.count('tool.end') == 2
    assert result.trace_id is None
