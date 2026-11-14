# STRATEGY PATTERN #2 - technician assignment + smart recommendation (owner: Pradhyumn)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from app.domain.exceptions import ValidationError, TechnicianUnavailableError

@dataclass
class Recommendation:
    technician: object
    score: float
    reasons: list = field(default_factory=list)   # explainable: "has DATABASE skill (+40)", "2/5 active incidents (+30)"

class AssignmentStrategy(ABC):
    @abstractmethod
    def choose(self, incident, candidates: list, workloads: dict) -> object:
        """Return ONE technician. Skip unavailable/at-capacity ones (Technician.can_accept).
        Deterministic tie-break. Raise TechnicianUnavailableError if nobody is eligible.
        workloads: {technician_id: active incident count}."""
        pass

    def recommend(self, incident, candidates: list, workloads: dict) -> List[Recommendation]:
        """Ranked list with reasons (intelligent feature #1: smart technician recommendation)."""
        recommendations = []
        for technician in self._get_eligible_candidates(incident, candidates, workloads):
            workload = workloads.get(technician.id, 0)
            capacity = max(technician.max_workload, 1)
            score = 0.0
            reasons = []

            if technician.has_skill(incident.category):
                score += 40
                reasons.append(f"has {incident.category} skill (+40)")

            availability_score = 30 * (capacity - workload) / capacity
            score += availability_score
            reasons.append(
                f"{workload}/{technician.max_workload} active incidents "
                f"(+{availability_score:.1f})"
            )

            experience_score = min(technician.experience_years, 10)
            score += experience_score
            if technician.experience_years:
                reasons.append(f"{technician.experience_years} years experience (+{experience_score:g})")

            recommendations.append(Recommendation(technician, score, reasons))

        return sorted(
            recommendations,
            key=lambda recommendation: (-recommendation.score, recommendation.technician.id),
        )

    def _get_eligible_candidates(self, incident, candidates: list, workloads: dict) -> list:
        """Returns list of technicians who can accept more work."""
        return [
            t for t in candidates
            if t.can_accept(workloads.get(t.id, 0))
        ]

class SkillBasedAssignment(AssignmentStrategy):
    def choose(self, incident, candidates, workloads):
        eligible = self._get_eligible_candidates(incident, candidates, workloads)
        if not eligible:
            raise TechnicianUnavailableError("No available technicians")

        # Sort: has_skill (True first), then workload (lower first), then experience (higher first), then id
        sorted_candidates = sorted(
            eligible,
            key=lambda t: (
                not t.has_skill(incident.category),
                workloads.get(t.id, 0),
                -t.experience_years,
                t.id
            )
        )
        return sorted_candidates[0]

class LoadBasedAssignment(AssignmentStrategy):
    def choose(self, incident, candidates, workloads):
        eligible = self._get_eligible_candidates(incident, candidates, workloads)
        if not eligible:
            raise TechnicianUnavailableError("No available technicians")

        # Sort: workload (lower first), then experience (higher first), then id
        sorted_candidates = sorted(
            eligible,
            key=lambda t: (
                workloads.get(t.id, 0),
                -t.experience_years,
                t.id
            )
        )
        return sorted_candidates[0]

# ---- Registry: which strategies exist. The ACTIVE one is data (config table, key 'assignment_strategy'), so an admin
# ---- switches it without a deploy, and a new strategy = one new class + one entry here. Nothing else changes (open/closed).
STRATEGIES: dict = {"skill": SkillBasedAssignment, "load": LoadBasedAssignment}
DEFAULT_STRATEGY = "skill"

def strategy_by_name(name: str) -> AssignmentStrategy:
    try:
        return STRATEGIES[name]()
    except KeyError:
        raise ValidationError(f"Unknown assignment strategy '{name}'. Available: {', '.join(sorted(STRATEGIES))}")
