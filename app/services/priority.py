"""STRATEGY PATTERN #1 - priority (owner: Pradhyumn)."""
from abc import ABC, abstractmethod
from app.domain.enums import Priority

class PriorityStrategy(ABC):
    @abstractmethod
    def calculate(self, incident, service) -> Priority: ...

class FixedPriority(PriorityStrategy):
    """Temporary placeholder so the vertical slice runs. Pradhyumn: replace in container.py with ScoredPriority."""
    def calculate(self, incident, service): return Priority.P3

class ScoredPriority(PriorityStrategy):
    """TODO(Pradhyumn): score = impact x urgency x service.criticality (max 125), optionally boosted by affected_users.
    Choose + DOCUMENT thresholds (e.g. >=60 -> P1, >=30 -> P2, >=10 -> P3, else P4). Rationale goes in the report."""
    def calculate(self, incident, service) -> Priority:
        """
        Calculate priority based on a score:
        Score = Impact * Urgency * Service_Criticality

        Thresholds:
        - >= 60: P1
        - >= 30: P2
        - >= 10: P3
        - < 10:  P4

        Bonus: +5 points if affected_users > 1.
        """
        score = incident.impact * incident.urgency * service.criticality

        if incident.affected_users > 1:
            score += 5

        if score >= 60:
            return Priority.P1
        if score >= 30:
            return Priority.P2
        if score >= 10:
            return Priority.P3
        return Priority.P4
