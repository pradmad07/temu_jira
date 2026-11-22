"""Explainable incident intelligence.

These helpers deliberately use local, deterministic scoring and historical incident
data. They work without API keys or network access and never invent a resolution.
"""

import re
from dataclasses import dataclass

from app.domain.enums import Status
from app.domain.filters import IncidentFilter


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "for", "from", "had", "has", "have", "in", "is", "it", "of", "on", "or",
    "that", "the", "this", "to", "was", "were", "with",
}


@dataclass(frozen=True)
class IncidentSummary:
    headline: str
    description: str
    facts: tuple


@dataclass(frozen=True)
class ResolutionSuggestion:
    incident_id: str
    title: str
    resolution: str
    score: float
    reasons: tuple


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {
        word[:-3] if word.endswith("ing") and len(word) > 5 else
        word[:-2] if word.endswith("ed") and len(word) > 4 else
        word[:-1] if word.endswith("s") and len(word) > 3 else word
        for word in words
        if word not in _STOPWORDS
    }


class IncidentAdvisor:
    def __init__(self, incidents):
        self._incidents = incidents

    def summarize(self, incident) -> IncidentSummary:
        clean = re.sub(r"\s+", " ", incident.description).strip()
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]
        description = " ".join(sentences[:2]) if sentences else clean
        if len(description) > 280:
            description = description[:277].rsplit(" ", 1)[0] + "..."

        facts = (
            f"{incident.category} incident affecting {incident.affected_users} user(s)",
            f"Impact {incident.impact}/5, urgency {incident.urgency}/5",
            f"Priority {incident.priority.name if incident.priority else 'unclassified'}",
            f"Status {incident.status.value}",
        )
        return IncidentSummary(
            headline=incident.title.strip(),
            description=description,
            facts=facts,
        )

    def suggest_resolutions(self, incident, limit: int = 3) -> list[ResolutionSuggestion]:
        limit = max(1, min(int(limit), 10))
        source_text = f"{incident.title} {incident.description}"
        source_tokens = _tokens(source_text)
        suggestions = []

        for candidate in self._incidents.search(IncidentFilter(), limit=500):
            if candidate.id == incident.id or not candidate.resolution:
                continue
            if candidate.status not in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED):
                continue
            if candidate.service_id != incident.service_id:
                continue

            candidate_tokens = _tokens(f"{candidate.title} {candidate.description}")
            union = source_tokens | candidate_tokens
            similarity = len(source_tokens & candidate_tokens) / len(union) if union else 0.0
            if similarity < 0.08:
                continue

            score = similarity
            reasons = [f"{similarity:.0%} text similarity"]
            if candidate.category == incident.category:
                score += 0.20
                reasons.append("same category")
            if candidate.priority == incident.priority:
                score += 0.10
                reasons.append("same priority")

            suggestions.append(ResolutionSuggestion(
                incident_id=candidate.id,
                title=candidate.title,
                resolution=candidate.resolution,
                score=min(score, 1.0),
                reasons=tuple(reasons),
            ))

        return sorted(
            suggestions,
            key=lambda item: (-item.score, item.incident_id),
        )[:limit]
