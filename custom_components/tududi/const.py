"""Constants for the Tududi integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "tududi"

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15
DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

API_PATH: Final = "/api/v1"

TASK_STATUSES: Final = [
    "not_started",
    "in_progress",
    "done",
    "archived",
    "waiting",
    "cancelled",
    "planned",
]
TASK_PRIORITIES: Final = ["low", "medium", "high"]
TASK_LIST_TYPES: Final = [
    "all",
    "today",
    "upcoming",
    "next",
    "inbox",
    "someday",
    "waiting",
]
TASK_LIST_STATUSES: Final = ["active", "done", "all"]
RECURRENCE_TYPES: Final = [
    "none",
    "daily",
    "weekly",
    "monthly",
    "monthly_weekday",
    "monthly_last_day",
    "yearly",
]

PROJECT_STATUSES: Final = [
    "not_started",
    "in_progress",
    "done",
    "waiting",
    "cancelled",
    "planned",
]
# Projects in these states get no to-do list of their own.
CLOSED_PROJECT_STATUSES: Final = {"done", "cancelled"}

HABIT_POLARITIES: Final = ["build", "quit"]
HABIT_PERIODS: Final = ["daily", "weekly", "monthly", "interval"]
HABIT_TIMES_OF_DAY: Final = ["morning", "afternoon", "evening"]

GOAL_STATUSES: Final = ["active", "achieved", "paused", "dropped"]
GOAL_HORIZONS: Final = ["season", "year"]

SEARCH_TYPES: Final = ["Task", "Project", "Area", "Note", "Tag"]


def status_name(value: int | str | None) -> str:
    """Return the tududi status name for an integer or string status."""
    if isinstance(value, int) and 0 <= value < len(TASK_STATUSES):
        return TASK_STATUSES[value]
    if isinstance(value, str) and value in TASK_STATUSES:
        return value
    return "not_started"


def priority_name(value: int | str | None) -> str | None:
    """Return the tududi priority name for an integer or string priority."""
    if isinstance(value, int) and 0 <= value < len(TASK_PRIORITIES):
        return TASK_PRIORITIES[value]
    if isinstance(value, str) and value in TASK_PRIORITIES:
        return value
    return None
