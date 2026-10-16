"""OBSERVE → REASON → SELECT → EXECUTE → EVALUATE, at most eight steps."""
import asyncio
import time
from .observability import NullObserver, run_scope, emit
from .schemas import AnalysisResult, Decision, Observation
from .state import AgentState
from .tools.registry import ToolRegistry


class Agent:
    def __init__(self, llm, sandbox, observer=None, registry_factory=ToolRegistry,
                 max_steps=8, overall_timeout=120, tool_timeout=15, max_retries=1):
        if not 1 <= max_steps <= 8 or not 0 <= max_retries <= 1 or min(overall_timeout, tool_timeout) <= 0:
            raise ValueError('Invalid execution budget')
        self.llm, self.sandbox = llm, sandbox
        self.observer = observer or NullObserver()
        self.registry_factory = registry_factory
        self.state = AgentState(max_steps=max_steps, overall_timeout=min(120, overall_timeout),
                                tool_timeout=min(15, tool_timeout), max_retries=max_retries)

    def event(self, name, **attributes):
        emit(self.observer, name, attributes)

    async def run(self, pr):
        with run_scope(self.observer):
            return await self._run(pr)

    async def _run(self, pr):
        state = self.state
        summary = 'Insufficient execution evidence'
        verdict, terminal = 'INCONCLUSIVE', 'failed'
        limits = list(pr.limitations) + ['Verdict applies only to executed properties and payloads; it is not proof of complete security.']
        self.event('run.start', commit=pr.head_sha, pr_url=pr.pr_url)
        run_started = time.monotonic()
        try:
            async with asyncio.timeout(state.remaining):
                sandbox_started = time.monotonic()
                self.event('sandbox.start', commit=pr.head_sha)
                await asyncio.wait_for(self.sandbox.start(pr), min(30, state.remaining))
                self.event('sandbox.ready', duration_ms=(time.monotonic() - sandbox_started) * 1000, success=True)
                registry = self.registry_factory(pr, self.sandbox)
                while state.advance():
                    context = {'pr': pr.model_dump(), 'hypotheses': [h.model_dump() for h in state.hypotheses.values()],
                               'actions': [a.model_dump() for a in state.actions],
                               'observations': [o.model_dump() for o in state.observations],
                               'evidence': [e.model_dump() for e in state.evidence],
                               'remaining_steps': state.max_steps - state.steps,
                               'errors': state.errors}
                    self.event('llm.start', step=state.steps)
                    decision = None
                    for attempt in range(state.max_retries + 1):
                        llm_started = time.monotonic()
                        try:
                            decision = Decision.model_validate((await asyncio.wait_for(
                                self.llm.decide(context), min(20, state.remaining))).model_dump())
                            self.event('llm.call', model=getattr(self.llm, 'model', 'synthetic'),
                                       duration_ms=(time.monotonic() - llm_started) * 1000,
                                       success=True, attempt=attempt + 1,
                                       requested_tools=['decide'], **getattr(self.llm, 'usage', {}))
                            break
                        except (ValueError, RuntimeError, asyncio.TimeoutError) as exc:
                            self.event('llm.call', model=getattr(self.llm, 'model', 'synthetic'),
                                       duration_ms=(time.monotonic() - llm_started) * 1000,
                                       success=False, error_type=type(exc).__name__, attempt=attempt + 1)
                            state.errors.append(f'LLM step {state.steps} attempt {attempt + 1}: {type(exc).__name__}')
                            self.event('retry', phase='llm', step=state.steps, attempt=attempt + 1)
                    if decision is None:
                        summary = 'LLM protocol or timeout failure'
                        break
                    self.event('llm.end', step=state.steps, decision=decision.model_dump())
                    if (decision.action is None) == (decision.finish is None):
                        state.errors.append('Decision must choose exactly one action or finish')
                        continue
                    for hypothesis in decision.hypotheses:
                        existing = state.hypotheses.get(hypothesis.id)
                        if existing and existing != hypothesis:
                            raise ValueError('Existing hypothesis cannot be rewritten after observations')
                        if len(state.hypotheses) >= 8 and existing is None:
                            raise ValueError('Hypothesis budget exhausted')
                        state.hypotheses[hypothesis.id] = hypothesis
                    self.event('agent.decision', step=state.steps,
                               hypotheses=[h.model_dump() for h in state.hypotheses.values()],
                               selected_action=decision.action.name if decision.action else decision.finish,
                               remaining_steps=state.max_steps - state.steps, remaining_seconds=state.remaining)
                    if decision.finish:
                        verdict = self.adjudicate(decision.finish, pr)
                        summary = decision.summary or 'Investigation finished'
                        if verdict != decision.finish:
                            summary = 'Requested verdict lacks sufficient trustworthy execution evidence'
                        terminal = 'finished'
                        break
                    state.phase = 'select'
                    action = decision.action
                    state.actions.append(action)
                    observation = Observation(id=f'o{len(state.observations) + 1}', tool=action.name,
                                              status='error', error='Not executed')
                    retries = state.max_retries if (action.name == 'inspect_patch' or
                        (action.name == 'http_request' and action.arguments.method == 'GET' and not action.arguments.authenticate)) else 0
                    for attempt in range(retries + 1):
                        self.event('tool.start', step=state.steps, action=action.model_dump(), attempt=attempt + 1)
                        tool_started = time.monotonic()
                        state.phase = 'execute'
                        try:
                            data = await asyncio.wait_for(registry.execute(action, state), min(state.tool_timeout, state.remaining))
                            observation = Observation(id=observation.id, tool=action.name,
                                                      status='ok', data=data, attempts=attempt + 1)
                            self.event('tool.attempt', tool=action.name, attempt=attempt + 1, success=True,
                                       duration_ms=(time.monotonic() - tool_started) * 1000)
                            break
                        except (ValueError, RuntimeError, asyncio.TimeoutError) as exc:
                            self.event('tool.attempt', tool=action.name, attempt=attempt + 1, success=False,
                                       duration_ms=(time.monotonic() - tool_started) * 1000, error_type=type(exc).__name__)
                            observation.error = type(exc).__name__
                            observation.attempts = attempt + 1
                            state.errors.append(f'{action.name} attempt {attempt + 1}: {type(exc).__name__}')
                            if attempt < retries:
                                self.event('retry', phase='tool', tool=action.name, attempt=attempt + 1)
                    state.observations.append(observation)
                    state.phase = 'evaluate'
                    self.event('tool.end', observation=observation.model_dump())
                else:
                    terminal = 'budget_exhausted'
                    summary = 'Step budget exhausted before a supported final verdict'
        except asyncio.TimeoutError:
            terminal, summary = 'timeout', 'Overall execution timeout exhausted'
            state.errors.append('Overall execution timeout')
        except (ValueError, RuntimeError, OSError) as exc:
            terminal, summary = 'failed', 'Sandbox or execution setup failed; no host fallback'
            state.errors.append(type(exc).__name__)
        finally:
            try:
                cleanup_started = time.monotonic()
                await asyncio.wait_for(self.sandbox.stop(), 6)
                self.event('sandbox.cleanup', success=True, duration_ms=(time.monotonic() - cleanup_started) * 1000)
            except (RuntimeError, OSError, asyncio.TimeoutError) as exc:
                self.event('sandbox.cleanup', success=False, error_type=type(exc).__name__)
                state.errors.append(f'Sandbox cleanup: {type(exc).__name__}')
                verdict = 'INCONCLUSIVE'
            state.phase = terminal
        self.event('verdict', verdict=verdict, terminal_state=terminal,
                   evidence=[e.model_dump() for e in state.evidence], limitations=limits)
        self.event('run.end', steps=state.steps, success=terminal == 'finished' and not state.errors,
                   duration_ms=(time.monotonic() - run_started) * 1000)
        return AnalysisResult(pr_url=pr.pr_url, pinned_commit=pr.head_sha, verdict=verdict,
                              terminal_state=terminal, summary=summary,
                              hypotheses=list(state.hypotheses.values()), actions=state.actions,
                              observations=state.observations, evidence=state.evidence,
                              generated_regression_tests=state.generated, errors=state.errors,
                              limitations=limits, trace_id=self.observer.trace_id())

    def adjudicate(self, requested, pr):
        evidence = [e for e in self.state.evidence if e.property in ('no_browser_execution', 'same_book_count')]
        violations = [e for e in evidence if e.outcome == 'violated']
        if requested == 'BYPASS_CONFIRMED' and violations:
            return requested
        if (requested == 'FIX_VERIFIED' and evidence and not violations and
                not self.state.errors and not pr.limitations and
                set(self.state.hypotheses) <= {e.hypothesis_id for e in evidence if e.outcome == 'holds'}):
            return requested
        return 'INCONCLUSIVE'
