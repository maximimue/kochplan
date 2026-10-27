import datetime as dt
from zoneinfo import ZoneInfo


def compute_start_at(
    date: dt.date, eat_at: dt.time | None, total_minutes: int, tz: str, buffer_minutes: int
) -> dt.datetime | None:
    """Startzeit = Essenszeit − Gesamtdauer − Puffer, als UTC.
    Gerechnet wird absolut in UTC, nicht in Wanduhrzeit — sonst ist das Ergebnis an
    Zeitumstellungstagen um eine Stunde falsch."""
    if eat_at is None:
        return None
    local = dt.datetime.combine(date, eat_at, tzinfo=ZoneInfo(tz))
    return local.astimezone(dt.UTC) - dt.timedelta(minutes=total_minutes + buffer_minutes)
