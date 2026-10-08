class InvalidTransition(Exception):
    pass


ALLOWED: dict[str, set[str]] = {
    "REQUESTED": {"QUOTED", "CANCELLED"},
    "QUOTED": {"MATCHING", "CANCELLED"},
    "MATCHING": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"DRIVER_EN_ROUTE", "CANCELLED"},
    "DRIVER_EN_ROUTE": {"DRIVER_ARRIVED", "CANCELLED"},
    "DRIVER_ARRIVED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED"},  # no cancelling once the trip has started
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def validate_transition(current: str, target: str) -> None:
    if target not in ALLOWED.get(current, set()):
        raise InvalidTransition(f"Cannot move ride from {current} to {target}")