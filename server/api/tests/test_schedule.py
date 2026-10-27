import datetime as dt

from app.services.schedule import compute_start_at


def test_start_time_simple():
    # 18:30 Essen, 45 min Rezept, 10 min Puffer -> 17:35 Ortszeit (CEST = UTC+2)
    s = compute_start_at(dt.date(2026, 6, 10), dt.time(18, 30), 45, "Europe/Berlin", 10)
    assert s == dt.datetime(2026, 6, 10, 15, 35, tzinfo=dt.UTC)


def test_start_time_across_dst_change():
    # 25.10.2026: Uhren 03:00 CEST -> 02:00 CET. Essen 03:30 CET = 02:30 UTC.
    # 120 min vorher = 00:30 UTC (= 02:30 CEST). Wanduhr-Rechnung ergäbe fälschlich 01:30.
    s = compute_start_at(dt.date(2026, 10, 25), dt.time(3, 30), 120, "Europe/Berlin", 0)
    assert s == dt.datetime(2026, 10, 25, 0, 30, tzinfo=dt.UTC)


def test_no_eat_time():
    assert compute_start_at(dt.date(2026, 1, 1), None, 30, "Europe/Berlin", 10) is None
