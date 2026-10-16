"""Strict wire contracts. Repository text and model output remain data."""
import re
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AnalyzeRequest(StrictModel):
    pr_url: str

    @field_validator('pr_url')
    @classmethod
    def valid_url(cls, value):
        if not re.fullmatch(r'https://github\.com/png270/breakfix/pull/[1-9][0-9]*', value):
            raise ValueError('Only canonical png270/breakfix PR URLs are allowed')
        return value


class PRData(StrictModel):
    pr_url: str
    base_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    head_sha: str = Field(pattern=r'^[0-9a-f]{40}$')
    changed_files: list[str]
    diff: str
    sources: dict[str, str]
    limitations: list[str] = Field(default_factory=list)


class Hypothesis(StrictModel):
    id: str = Field(pattern=r'^h[1-9][0-9]*$')
    statement: str = Field(min_length=1, max_length=1000)
    security_property: str = Field(min_length=1, max_length=1000)


class InspectArgs(StrictModel):
    path: str | None = Field(default=None, max_length=200)
    start_line: int = Field(default=1, ge=1, le=2000)
    max_lines: int = Field(default=80, ge=1, le=120)


def local_path(value):
    parsed = urlsplit(value)
    decoded = unquote(value)
    if (parsed.scheme or parsed.netloc or not value.startswith('/') or
            value.startswith('//') or '\\' in decoded or '\x00' in decoded or
            '..' in decoded or len(value) > 500 or parsed.fragment):
        raise ValueError('Only local endpoint paths are allowed')
    if not re.fullmatch(r'/(?:|signup|login|logout|books/[1-9][0-9]*(?:/reviews)?|users/[1-9][0-9]*(?:/edit)?)', parsed.path):
        raise ValueError('Endpoint is not allowlisted')
    return value


class HTTPArgs(StrictModel):
    method: Literal['GET', 'POST'] = 'GET'
    path: str = '/'
    query: dict[str, str] = Field(default_factory=dict, max_length=8)
    form: dict[str, str] = Field(default_factory=dict, max_length=8)
    authenticate: bool = False

    _path = field_validator('path')(local_path)

    @field_validator('query', 'form')
    @classmethod
    def bounded_fields(cls, value):
        allowed = {'q', 'review_text', 'display_name', 'bio', 'favorite_genre'}
        if any(k not in allowed or len(v) > 5000 for k, v in value.items()):
            raise ValueError('Unsupported or oversized form/query field')
        return value


    @model_validator(mode='after')
    def bounded_payload(self):
        if sum(len(value) for value in [*self.query.values(), *self.form.values()]) > 8000:
            raise ValueError('Combined HTTP arguments exceed tool limit')
        return self


class BrowserArgs(StrictModel):
    path: str = '/'
    authenticate: bool = False
    book_id: int = Field(default=1, ge=1, le=100)
    review_text: str | None = Field(default=None, max_length=5000)
    revisit_anonymous: bool = True
    _path = field_validator('path')(local_path)


class CompareArgs(StrictModel):
    hypothesis_id: str = Field(pattern=r'^h[1-9][0-9]*$')
    property: Literal['no_browser_execution', 'same_book_count', 'response_contains']
    observation_id: str
    control_id: str | None = None
    expected: str | None = Field(default=None, max_length=200)


class RegressionArgs(StrictModel):
    evidence_id: str


class InspectAction(StrictModel):
    name: Literal['inspect_patch']
    arguments: InspectArgs


class HTTPAction(StrictModel):
    name: Literal['http_request']
    arguments: HTTPArgs


class BrowserAction(StrictModel):
    name: Literal['browser_test']
    arguments: BrowserArgs


class CompareAction(StrictModel):
    name: Literal['compare_behavior']
    arguments: CompareArgs


class RegressionAction(StrictModel):
    name: Literal['generate_regression_test']
    arguments: RegressionArgs


ToolAction = Annotated[InspectAction | HTTPAction | BrowserAction | CompareAction | RegressionAction, Field(discriminator='name')]


class Decision(StrictModel):
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=8)
    action: ToolAction | None = None
    finish: Literal['FIX_VERIFIED', 'BYPASS_CONFIRMED', 'INCONCLUSIVE'] | None = None
    summary: str = Field(default='', max_length=1500)


class Observation(StrictModel):
    id: str
    tool: str
    status: Literal['ok', 'error']
    data: dict = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 1


class Evidence(StrictModel):
    id: str
    hypothesis_id: str
    property: str
    observation_ids: list[str]
    outcome: Literal['holds', 'violated']
    description: str


class AnalysisResult(StrictModel):
    pr_url: str
    pinned_commit: str | None = None
    verdict: Literal['FIX_VERIFIED', 'BYPASS_CONFIRMED', 'INCONCLUSIVE']
    terminal_state: Literal['finished', 'budget_exhausted', 'timeout', 'failed']
    summary: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    actions: list[ToolAction] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    generated_regression_tests: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace_id: str | None = None
