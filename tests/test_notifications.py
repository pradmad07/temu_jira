from app.domain.events import IncidentEvent, EV_ASSIGNED
from app.services.notifications import NotificationService, InAppChannel, SimulatedEmailChannel

def test_one_event_reaches_two_channels():   # TODO(Gaurav)
    inapp, email = InAppChannel(), SimulatedEmailChannel()
    NotificationService([inapp, email]).on_event(IncidentEvent(EV_ASSIGNED, "INC1", "U-ADMIN", "CLASSIFIED", "ASSIGNED", "Assigned to Tina"))
    assert len(inapp.sent) == 1 and len(email.sent) == 1
