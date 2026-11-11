"""STATE PATTERN (owner: Kevalin). Each state object decides which actions are legal and returns the next state.
Anything not overridden is illegal -> InvalidTransitionError. This is what blocks NEW -> CLOSED."""
from .enums import Status
from .exceptions import InvalidTransitionError

class IncidentState:
    status: Status
    def _deny(self, action):
        raise InvalidTransitionError(f"Cannot '{action}' an incident that is {self.status.value}")
    def classify(self, inc): self._deny("classify")
    def assign(self, inc): self._deny("assign")
    def acknowledge(self, inc): self._deny("acknowledge")
    def start(self, inc): self._deny("start")
    def resolve(self, inc): self._deny("resolve")
    def verify(self, inc): self._deny("verify")
    def reject(self, inc): self._deny("reject")
    def close(self, inc): self._deny("close")

class NewState(IncidentState):
    status = Status.NEW
    def classify(self, inc): return state_for(Status.CLASSIFIED)
class ClassifiedState(IncidentState):
    status = Status.CLASSIFIED
    def assign(self, inc): return state_for(Status.ASSIGNED)
class AssignedState(IncidentState):
    status = Status.ASSIGNED
    def acknowledge(self, inc): return state_for(Status.ACKNOWLEDGED)
class AcknowledgedState(IncidentState):
    status = Status.ACKNOWLEDGED
    def start(self, inc): return state_for(Status.IN_PROGRESS)
class InProgressState(IncidentState):
    status = Status.IN_PROGRESS
    def resolve(self, inc): return state_for(Status.RESOLVED)
class ResolvedState(IncidentState):
    status = Status.RESOLVED
    def verify(self, inc): return state_for(Status.VERIFIED)
    def reject(self, inc): return state_for(Status.IN_PROGRESS)   # reporter says "not fixed"
class VerifiedState(IncidentState):
    status = Status.VERIFIED
    def close(self, inc): return state_for(Status.CLOSED)
class ClosedState(IncidentState):
    status = Status.CLOSED   # terminal

_STATES = {s.status: s for s in (NewState(), ClassifiedState(), AssignedState(), AcknowledgedState(),
                                 InProgressState(), ResolvedState(), VerifiedState(), ClosedState())}
def state_for(status: Status) -> IncidentState:
    return _STATES[status]
