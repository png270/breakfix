"""Per-run state, not shared between analyses."""
import time
from dataclasses import dataclass, field
from .schemas import Hypothesis, Observation, Evidence, ToolAction


@dataclass
class AgentState:
    max_steps: int = 8
    overall_timeout: float = 120
    tool_timeout: float = 15
    max_retries: int = 1
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    phase: str = 'observe'
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    actions: list[ToolAction] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    generated: list[str] = field(default_factory=list)

    @property
    def remaining(self):
        return max(0, self.overall_timeout - (time.monotonic() - self.started))

    def advance(self):
        if self.steps >= min(8, self.max_steps) or self.remaining <= 0:
            return False
        self.steps += 1
        self.phase = 'reason'
        return True
