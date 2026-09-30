# ai-generated: 100% - Claude Code (Opus 5.5) wrote this file from design/LAB5.md section 8; the lecturer reviews it
"""The reference suite for slaclock.py (design/LAB5.md section 8, P-29): every test reads the module's docstrings,
never its source, so it passes on every behaviour-preserving rewrite and kills every course mutant."""

from datetime import datetime, timedelta

import pytest

import slaclock

MON = datetime(2026, 10, 12)          # Monday 12 October 2026, midnight
TUE, FRI, SAT, SUN = MON + timedelta(days=1), MON + timedelta(days=4), MON + timedelta(days=5), MON + timedelta(days=6)
NEXT_MON = MON + timedelta(days=7)


def at(day: datetime, hhmm: str, second: int = 0) -> datetime:
    hours, minutes = hhmm.split(":")
    return day.replace(hour=int(hours), minute=int(minutes), second=second)


# ------------------------------------------------------------------------------------------------ priority_of

MATRIX = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
          (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
          (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}


@pytest.mark.parametrize(("impact", "urgency"), sorted(MATRIX))
def test_the_matrix_cell_by_cell(impact, urgency):
    assert slaclock.priority_of(impact, urgency) == MATRIX[impact, urgency]
    assert slaclock.priority_of(impact, urgency, vip=False) == MATRIX[impact, urgency]


@pytest.mark.parametrize(("impact", "urgency", "expected"),
                         [(1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P2"), (2, 2, "P2"), (3, 3, "P2")])
def test_a_vip_ticket_is_never_below_p2(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency, vip=True) == expected


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, True, False, "1", None])
def test_impact_and_urgency_outside_1_to_3_are_rejected(bad):
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 2)
    with pytest.raises(ValueError):
        slaclock.priority_of(2, bad)


# ------------------------------------------------------------------------------------------------ targets

@pytest.mark.parametrize(("priority", "expected"),
                         [("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)), ("P4", (480, 4320))])
def test_targets(priority, expected):
    assert slaclock.targets(priority) == expected


@pytest.mark.parametrize("bad", ["p1", " P1", "P5", "P0", "", "P"])
def test_unknown_priorities_have_no_targets(bad):
    with pytest.raises(ValueError):
        slaclock.targets(bad)


# ------------------------------------------------------------------------------------------------ sla_state

@pytest.mark.parametrize(("elapsed", "target", "expected"), [
    (0, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (14, 15, "warning"), (15, 15, "warning"),   # equality
    (16, 15, "breached"), (74, 100, "ok"), (75, 100, "warning"), (100, 100, "warning"), (101, 100, "breached"),
    (3239, 4320, "ok"), (3240, 4320, "warning"), (4320, 4320, "warning"), (4321, 4320, "breached"),
    (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"), (2, 4, "ok"), (3, 4, "warning"),
])
def test_sla_state_at_its_boundaries(elapsed, target, expected):
    assert slaclock.sla_state(elapsed, target) == expected


@pytest.mark.parametrize(("elapsed", "target"), [(-1, 15), (0, 0), (5, 0), (5, -15), (-1, -1)])
def test_sla_state_rejects_negative_elapsed_and_non_positive_targets(elapsed, target):
    with pytest.raises(ValueError):
        slaclock.sla_state(elapsed, target)


# ------------------------------------------------------------------------------------------------ is_business_time

@pytest.mark.parametrize(("moment", "expected"), [
    (at(MON, "08:00"), True), (at(MON, "07:59"), False), (at(MON, "15:59"), True), (at(MON, "16:00"), False),
    (at(MON, "00:00"), False), (at(MON, "12:30"), True), (at(FRI, "15:59"), True), (at(SAT, "10:00"), False),
    (at(MON, "08:30"), True), (at(MON, "16:30"), False),
    (at(SUN, "10:00"), False), (at(TUE, "07:00"), False), (at(MON, "23:59"), False),
])
def test_is_business_time(moment, expected):
    assert slaclock.is_business_time(moment) is expected


# ------------------------------------------------------------------------------------------------ add_business_minutes

@pytest.mark.parametrize(("start", "minutes", "due"), [
    (at(MON, "10:00"), 60, at(MON, "11:00")),
    (at(MON, "10:00"), 0, at(MON, "10:00")),
    (at(MON, "15:59"), 0, at(MON, "15:59")),
    (at(MON, "16:00"), 0, at(TUE, "08:00")),            # at closing the clock is already paused
    (at(MON, "07:00"), 0, at(MON, "08:00")),
    (at(MON, "07:00"), 30, at(MON, "08:30")),
    (at(MON, "15:00"), 60, at(MON, "16:00")),            # ends exactly at closing: due at 16:00, not 08:00
    (at(MON, "15:00"), 61, at(TUE, "08:01")),
    (at(MON, "15:59"), 1, at(MON, "16:00")),
    (at(MON, "17:00"), 15, at(TUE, "08:15")),
    (at(FRI, "15:30"), 240, at(NEXT_MON, "11:30")),     # LAB1's T2: the weekend does not count
    (at(FRI, "17:00"), 15, at(NEXT_MON, "08:15")),
    (at(SAT, "12:00"), 60, at(NEXT_MON, "09:00")),
    (at(SAT, "12:00"), 480, at(NEXT_MON, "16:00")),     # LAB1's T4
    (at(SUN, "23:59"), 1, at(NEXT_MON, "08:01")),
    (at(MON, "08:00"), 4320, at(NEXT_MON + timedelta(days=3), "16:00")),   # nine business days
    (at(MON, "12:00"), 1440, at(MON + timedelta(days=3), "12:00")),
    (at(MON, "10:00", second=59), 1, at(MON, "10:01")),                   # seconds are ignored
])
def test_add_business_minutes(start, minutes, due):
    assert slaclock.add_business_minutes(start, minutes) == due


def test_add_business_minutes_rejects_negative_minutes_and_far_due_dates():
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(at(MON, "10:00"), -1)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(at(MON, "10:00"), 10_000_000)


# ---------------------------------------------------------------------------- business_minutes_between

@pytest.mark.parametrize(("start", "end", "minutes"), [
    (at(MON, "10:00"), at(MON, "10:00"), 0),
    (at(MON, "08:00"), at(MON, "16:00"), 480),
    (at(MON, "07:00"), at(MON, "09:00"), 60),
    (at(MON, "15:00"), at(TUE, "09:00"), 120),
    (at(MON, "16:00"), at(MON, "17:00"), 0),
    (at(MON, "17:00"), at(TUE, "07:00"), 0),
    (at(FRI, "15:30"), at(NEXT_MON, "11:30"), 240),
    (at(SAT, "00:00"), at(SUN, "23:59"), 0),
    (at(FRI, "12:00"), at(SAT, "12:00"), 240),
    (at(MON, "10:00", second=30), at(MON, "10:01", second=10), 1),
    (at(MON, "00:00"), at(NEXT_MON, "00:00"), 2400),
    (at(MON, "12:00"), at(MON + timedelta(days=21), "12:00"), 7200),
])
def test_business_minutes_between(start, end, minutes):
    assert slaclock.business_minutes_between(start, end) == minutes


def test_business_minutes_between_rejects_reversed_intervals():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(MON, "10:01"), at(MON, "10:00"))


def test_business_minutes_between_accepts_at_most_max_days():
    assert slaclock.MAX_DAYS == 366
    start = at(MON, "12:00")
    assert slaclock.business_minutes_between(start, start + timedelta(days=366)) > 0
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(start, start + timedelta(days=367))


def test_the_two_clock_functions_are_inverse():
    for hour in range(0, 24, 3):
        for day in range(7):
            start = MON + timedelta(days=day, hours=hour, minutes=7)
            for minutes in (0, 1, 59, 479, 480, 481, 2400, 4320):
                due = slaclock.add_business_minutes(start, minutes)
                assert slaclock.business_minutes_between(start, due) == minutes


# ------------------------------------------------------------------------------------------------ escalation_tier

@pytest.mark.parametrize(("priority", "breached", "reopens", "tier"), [
    ("P1", False, 0, 1), ("P1", True, 0, 3), ("P1", False, 2, 2), ("P1", True, 2, 3), ("P1", False, 1, 1),
    ("P2", False, 0, 1), ("P2", True, 0, 2), ("P2", False, 2, 2), ("P2", True, 2, 3), ("P2", True, 1, 2),
    ("P3", False, 0, 0), ("P3", True, 0, 1), ("P3", False, 1, 0), ("P3", False, 2, 1), ("P3", True, 3, 2),
    ("P4", False, 0, 0), ("P4", True, 0, 1), ("P4", False, 2, 1), ("P4", True, 2, 2),
])
def test_escalation_tier(priority, breached, reopens, tier):
    assert slaclock.escalation_tier(priority, breached, reopens) == tier


@pytest.mark.parametrize(("priority", "reopens"), [("P5", 0), ("p1", 0), ("P1", -1), ("P3", -1)])
def test_escalation_tier_rejects_unknown_priorities_and_negative_reopens(priority, reopens):
    with pytest.raises(ValueError):
        slaclock.escalation_tier(priority, False, reopens)


# ------------------------------------------------------------------------------------------------ parse_duration

@pytest.mark.parametrize(("text", "minutes"), [
    ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445), ("1h59m", 119),
    ("60m", 60), ("0h60m", 60), ("1d30m", 1470), ("30h", 1800), (" 15m ", 15), ("1m", 1), ("0d0h1m", 1),
])
def test_parse_duration(text, minutes):
    assert slaclock.parse_duration(text) == minutes


@pytest.mark.parametrize("text", ["", "0m", "0h", "0d0h0m", "1h60m", "1d60m", "1.5h", "30m1h", "-5m", "1 h",
                                  "h", "1H", "1x", "5"])
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        slaclock.parse_duration(text)
