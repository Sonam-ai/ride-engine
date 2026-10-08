import pytest

from app.algorithms.state_machine import InvalidTransition, validate_transition

HAPPY_PATH = [
    "REQUESTED", "QUOTED", "MATCHING", "ASSIGNED",
    "DRIVER_EN_ROUTE", "DRIVER_ARRIVED", "IN_PROGRESS", "COMPLETED",
]


def test_full_happy_path_is_allowed():
    for current, target in zip(HAPPY_PATH, HAPPY_PATH[1:]):
        validate_transition(current, target)


@pytest.mark.parametrize("current,target", [
    ("REQUESTED", "ASSIGNED"),
    ("QUOTED", "IN_PROGRESS"),
    ("ASSIGNED", "COMPLETED"),
    ("COMPLETED", "CANCELLED"),
    ("CANCELLED", "QUOTED"),
    ("IN_PROGRESS", "CANCELLED"),
    ("MATCHING", "MATCHING"),
])
def test_invalid_transitions_are_rejected(current, target):
    with pytest.raises(InvalidTransition):
        validate_transition(current, target)


@pytest.mark.parametrize("current", ["QUOTED", "MATCHING", "ASSIGNED", "DRIVER_EN_ROUTE", "DRIVER_ARRIVED"])
def test_cancel_is_allowed_before_the_trip_starts(current):
    validate_transition(current, "CANCELLED")