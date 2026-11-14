"""Intelligent feature #2: duplicate detection (owner: Pradhyumn)."""
import re


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "unable", "with",
}


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def _tokens(incident) -> set[str]:
    words = re.findall(r"[a-z0-9]+", f"{incident.title} {incident.description}".lower())
    return {_stem(word) for word in words if word not in _STOPWORDS}


class DuplicateDetector:
    def __init__(self, threshold: float = 0.2):
        # Two short reports can share only two meaningful words, so 0.2 avoids
        # missing useful suggestions while unrelated reports remain well below it.
        self.threshold = threshold

    def find_candidates(self, incident, recent_incidents: list) -> list[tuple]:
        """Return [(other_incident, score)] for same-service, recent incidents whose title+description are similar.
        Never delete or merge reports; this only returns suggestions."""
        incident_tokens = _tokens(incident)
        candidates = []
        for other in recent_incidents:
            if other.id == incident.id or other.service_id != incident.service_id:
                continue
            other_tokens = _tokens(other)
            union = incident_tokens | other_tokens
            score = len(incident_tokens & other_tokens) / len(union) if union else 0.0
            if score >= self.threshold:
                candidates.append((other, score))
        return sorted(candidates, key=lambda pair: (-pair[1], pair[0].id))
