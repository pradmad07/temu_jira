"""STRATEGY PATTERN #2 - technician assignment + smart recommendation (owner: Pradhyumn)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class Recommendation:
    technician: object
    score: float
    reasons: list = field(default_factory=list)   # explainable: "has DATABASE skill (+40)", "2/5 active incidents (+30)"

class AssignmentStrategy(ABC):
    @abstractmethod
    def choose(self, incident, candidates: list, workloads: dict):
        """Return ONE technician. Skip unavailable/at-capacity ones (Technician.can_accept).
        Deterministic tie-break. Raise TechnicianUnavailableError if nobody is eligible.
        workloads: {technician_id: active incident count}."""
    def recommend(self, incident, candidates: list, workloads: dict) -> list[Recommendation]:
        """Ranked list with reasons (intelligent feature #1: smart technician recommendation)."""
        raise NotImplementedError("TODO(Pradhyumn)")

class SkillBasedAssignment(AssignmentStrategy):
    def choose(self, incident, candidates, workloads): raise NotImplementedError("TODO(Pradhyumn)")
class LoadBasedAssignment(AssignmentStrategy):
    def choose(self, incident, candidates, workloads): raise NotImplementedError("TODO(Pradhyumn)")
