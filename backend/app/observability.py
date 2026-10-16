"""Explicit, bounded telemetry. Never auto-instrument clients or capture payloads."""
import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Protocol


class Observer(Protocol):
    live_ready: bool
    def event(self, name: str, attributes: dict) -> None: ...
    def trace_id(self) -> str | None: ...


class NullObserver:
    live_ready = False
    def event(self, name, attributes): pass
    def trace_id(self): return None


# Unknown keys and arbitrary text are omitted rather than trying to recognize secrets.
SAFE_KEYS = set('run_id pr_url commit step attempt phase tool name id status attempts method book_id authenticate revisit_anonymous start_line max_lines hypothesis_id property observation_id control_id evidence_id outcome observation_ids remaining_steps remaining_seconds duration_ms success verdict terminal_state steps model prompt_tokens completion_tokens total_tokens marker_executed marker_tested book_count status_code requested_tools error_type evidence limitations timestamp action arguments observation data hypotheses security_property statement selected_action'.split())
SAFE_TEXT = re.compile(r'^(?:h[1-9][0-9]*|o[1-9][0-9]*|e[1-9][0-9]*|[a-f0-9]{32,40}|[A-Za-z][A-Za-z0-9_.:-]{0,120})$')
TOOLS = {'inspect_patch', 'http_request', 'browser_test', 'compare_behavior', 'generate_regression_test', 'decide'}


def sanitize(value, key='', depth=0):
    if depth > 6: return '[OMITTED]'
    if isinstance(value, dict):
        return {k: sanitize(v, k, depth + 1) for k, v in list(value.items())[:64] if k in SAFE_KEYS}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, key, depth + 1) for v in value[:32]]
    if value is None or isinstance(value, bool): return value
    if isinstance(value, (int, float)): return value
    if isinstance(value, str):
        if key == 'pr_url' and re.fullmatch(r'https://github\.com/png270/breakfix/pull/[1-9][0-9]*', value): return value
        if key == 'timestamp': return value if re.fullmatch(r'[0-9T:+.Z-]{10,40}', value) else '[OMITTED]'
        # Freeform hypotheses/limitations may contain echoed secrets: retain references only.
        if key in {'statement', 'security_property', 'limitations'}: return '[OMITTED]'
        return value if SAFE_TEXT.fullmatch(value) else '[OMITTED]'
    return '[OMITTED]'


def export_mask(span):
    """Exporter defense: retain only our explicit attributes and SDK structural fields."""
    if isinstance(span, dict):
        for field in ('input', 'output', 'input.value', 'output.value', 'events'):
            span.pop(field, None)
        resource = span.get('resource', {}).get('attributes', {})
        span['resource'] = {'attributes': {k: v for k, v in resource.items()
                             if k in {'service.name', 'service.version', 'neatlogs.workflow_name'}}}
        span['links'] = []
        if isinstance(span.get('status'), dict):
            span['status']['description'] = None
        attrs = span.get('attributes')
        if isinstance(attrs, dict):
            span['attributes'] = {k: v for k, v in attrs.items() if k.startswith('bmf.') or k in {'neatlogs.span.kind', 'openinference.span.kind', 'neatlogs.workflow.name',
                  'neatlogs.trace.complete', 'neatlogs.internal'}}
    return span


class NeatlogsObserver(NullObserver):
    def __init__(self, sdk):
        self.sdk = sdk
        self.run_id = uuid.uuid4().hex
        self._trace_id = None
        self.failed = False
        self._active = False

    @contextmanager
    def scope(self):
        if self._active:
            yield self
            return
        manager = None
        try:
            manager = self.sdk.trace('break-my-fix.run', kind='WORKFLOW')
            root = manager.__enter__()
            self._trace_id = format(root.get_span_context().trace_id, '032x')
            root.set_attribute('bmf.run_id', self.run_id)
            self._active = True
        except Exception:
            self.failed = True
            if manager:
                try: manager.__exit__(None, None, None)
                except Exception: pass
            manager = None
        try:
            yield self
        finally:
            self._active = False
            if manager:
                try: manager.__exit__(None, None, None)
                except Exception: self.failed = True

    def event(self, name, attributes):
        if self.failed or not self._trace_id: return
        try:
            clean = sanitize(attributes)
            clean.update(run_id=self.run_id, timestamp=datetime.now(timezone.utc).isoformat())
            kind = 'TOOL' if name.startswith('tool.') else 'LLM' if name.startswith('llm.') else 'AGENT'
            with self.sdk.trace(name, kind=kind) as span:
                span.set_attribute('bmf.run_id', self.run_id)
                span.set_attribute('bmf.event', json.dumps(clean, allow_nan=False))
        except Exception:
            self.failed = True

    def trace_id(self): return self._trace_id


class ObserverFactory(NullObserver):
    """SDK availability never opens the live-analysis gate."""
    def __init__(self, sdk=None):
        self.sdk = sdk
        self.status = 'ready' if sdk else 'missing_key'
        if sdk is None and os.getenv('NEATLOGS_API_KEY'):
            try:
                # Legacy SDK installs import hooks; reject it before importing.
                major, minor = map(int, version('neatlogs').split('.')[:2])
                if (major, minor) < (1, 2):
                    self.status = 'unsupported_sdk'
                    return
                import neatlogs
                if not all(hasattr(neatlogs, n) for n in ('trace', 'flush', 'shutdown')):
                    self.status = 'unsupported_sdk'
                    return
                neatlogs.init(api_key=os.environ['NEATLOGS_API_KEY'], workflow_name='break-my-fix',
                              instrumentations=[], capture_logs=False, mask=export_mask,
                              register_shutdown_handlers=False)
                self.sdk, self.status = neatlogs, 'ready'
            except Exception:
                self.status = 'initialization_failed'

    def new_run(self): return NeatlogsObserver(self.sdk) if self.sdk else NullObserver()
    def shutdown(self):
        if self.sdk:
            try:
                if self.sdk.flush() is False:
                    self.status = 'export_failed'
            except Exception:
                self.status = 'export_failed'
            finally:
                try: self.sdk.shutdown()
                except Exception: self.status = 'export_failed'


@contextmanager
def run_scope(observer):
    if hasattr(observer, 'scope'):
        with observer.scope(): yield observer
    else:
        yield observer


def emit(observer, name, attributes):
    try: observer.event(name, attributes)
    except Exception: pass
