from datetime import datetime, timezone

class Clock:
    """Single source of "now". Tests and demos inject a FakeClock so SLA timing never needs real waiting."""
    def now(self) -> datetime: return datetime.now(timezone.utc)
