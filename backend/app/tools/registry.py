"""Typed allowlist, deterministic comparisons and data-only replay artifacts."""
import json
import tempfile
from pathlib import Path
from pydantic import TypeAdapter
from ..schemas import Evidence, ToolAction
from .inspect import inspect_patch


class ToolRegistry:
    def __init__(self, pr, sandbox, output_dir=None):
        self.pr, self.sandbox = pr, sandbox
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix='bmf-regression-'))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, action, state):
        action = TypeAdapter(ToolAction).validate_python(action.model_dump())
        if action.name == 'inspect_patch':
            return inspect_patch(self.pr, action.arguments)
        if action.name in ('http_request', 'browser_test'):
            return await self.sandbox.execute(action)
        if action.name == 'compare_behavior':
            return self.compare(action.arguments, state)
        if action.name == 'generate_regression_test':
            return self.generate(action.arguments, state)
        raise ValueError('Unknown tool')

    def compare(self, args, state):
        if args.hypothesis_id not in state.hypotheses:
            raise ValueError('Comparison requires an existing hypothesis')
        observations = {o.id: o for o in state.observations}
        observed = observations.get(args.observation_id)
        if observed is None or observed.status != 'ok':
            raise ValueError('Comparison requires a successful execution observation')
        refs = [observed.id]
        if args.property == 'no_browser_execution':
            if (observed.tool != 'browser_test' or observed.data.get('marker_tested') is not True or
                    type(observed.data.get('marker_executed')) is not bool):
                raise ValueError('Browser marker was not actually tested')
            holds = not observed.data['marker_executed']
            description = 'Fresh marker execution was ' + ('absent within the bounded observation window' if holds else 'observed in the browser')
        elif args.property == 'same_book_count':
            control = observations.get(args.control_id)
            if control is None or control.status != 'ok' or control.id == observed.id:
                raise ValueError('Distinct successful control observation required')
            for item in (control, observed):
                if (item.tool != 'http_request' or item.data.get('status_code') != 200 or
                        item.data.get('path') != '/' or item.data.get('method') != 'GET' or
                        type(item.data.get('book_count')) is not int):
                    raise ValueError('Successful search requests required')
            attack_action = state.actions[state.observations.index(observed)]
            control_action = state.actions[state.observations.index(control)]
            attack = attack_action.arguments.query.get('q', '')
            baseline = control_action.arguments.query.get('q', '')
            import re
            if (not baseline or not attack.startswith(baseline) or attack == baseline or
                    control.data['book_count'] != 0 or
                    not re.search(r"['\"]\s*(?:OR|UNION)\b", attack[len(baseline):], re.I)):
                raise ValueError('Search comparison requires unmatched control and its SQL-predicate variant')
            refs.append(control.id)
            holds = observed.data['book_count'] == control.data['book_count']
            description = f"Observed {observed.data['book_count']} books; stated control {control.data['book_count']}"
        else:
            if (observed.tool != 'http_request' or observed.data.get('status_code') != 200 or
                    observed.data.get('body_excerpt_truncated') is not False or not args.expected):
                raise ValueError('Complete successful HTTP response and expected text required')
            holds = args.expected in observed.data.get('body', '')
            description = 'Expected response text ' + ('present' if holds else 'absent')
        evidence = Evidence(id=f'e{len(state.evidence) + 1}', hypothesis_id=args.hypothesis_id,
                            property=args.property, observation_ids=refs,
                            outcome='holds' if holds else 'violated', description=description)
        # Only runtime-derived browser/search evidence can establish security verdicts.
        state.evidence.append(evidence)
        return evidence.model_dump()

    def generate(self, args, state):
        evidence = next((e for e in state.evidence if e.id == args.evidence_id), None)
        if evidence is None or evidence.property == 'response_contains':
            raise ValueError('Confirmed browser/search evidence required for regression generation')
        selected = []
        for ref in evidence.observation_ids:
            index = next(i for i, observation in enumerate(state.observations) if observation.id == ref)
            selected.append(state.actions[index].model_dump())
        # Constant Python code loads JSON as data; no LLM code is written or executed.
        artifact = self.output_dir / f'{evidence.id}.json'
        artifact.write_text(json.dumps({'commit': self.pr.head_sha, 'property': evidence.property,
                                       'actions': selected}, indent=2))
        script = self.output_dir / f'test_{evidence.id}.py'
        script.write_text('''"""Generated security regression; requires approved Docker fixture and no LLM."""
import asyncio
from pathlib import Path
from app.replay import replay_artifact

def test_security_property():
    asyncio.run(replay_artifact(Path(__file__).with_name("'''+artifact.name+'''")))
''')
        state.generated.extend([str(artifact), str(script)])
        return {'test_file': str(script), 'action_data': str(artifact), 'executed': False,
                'note': 'Replays confirmed actions only; security assertion fails if the bypass persists'}
