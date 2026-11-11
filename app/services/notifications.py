"""OBSERVER + ADAPTER (owner: Gaurav). One event -> every channel. Add a channel = add a class."""
from abc import ABC, abstractmethod

class NotificationChannel(ABC):
    def __init__(self): self.sent: list = []     # delivery log (also persist in `notifications` table)
    @abstractmethod
    def send(self, recipient_id: str, subject: str, body: str) -> None: ...

class InAppChannel(NotificationChannel):
    def send(self, recipient_id, subject, body): raise NotImplementedError("TODO(Gaurav): insert into notifications table")
class SimulatedEmailChannel(NotificationChannel):
    def send(self, recipient_id, subject, body): raise NotImplementedError("TODO(Gaurav): persist + clearly label as SIMULATED")

class NotificationService:
    def __init__(self, channels: list[NotificationChannel]): self._channels = channels
    def on_event(self, event) -> None:
        """Decide who is notified for each event type, then send via every channel."""
        raise NotImplementedError("TODO(Gaurav)")
