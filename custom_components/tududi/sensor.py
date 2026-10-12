"""Task metric and habit sensors for Tududi."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TududiConfigEntry, TududiCoordinator, TududiData
from .entity import TududiEntity, async_add_dynamic_entities

PARALLEL_UPDATES = 0

_TASK_SUMMARY_KEYS = ("uid", "name", "due_date", "priority", "project_uid")


def _summaries(tasks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep attributes small: a few fields per task, at most 20 tasks."""
    return [{k: t.get(k) for k in _TASK_SUMMARY_KEYS} for t in (tasks or [])[:20]]


def _count(key: str) -> Callable[[TududiData], int | None]:
    return lambda data: data.metrics.get(key)


def _list_len(key: str) -> Callable[[TududiData], int | None]:
    def value(data: TududiData) -> int | None:
        items = data.metrics.get(key)
        return len(items) if isinstance(items, list) else None

    return value


@dataclass(frozen=True, kw_only=True)
class TududiSensorDescription(SensorEntityDescription):
    """Describes a tududi metric sensor."""

    value_fn: Callable[[TududiData], Any]
    tasks_key: str | None = None


METRIC_SENSORS: tuple[TududiSensorDescription, ...] = (
    TududiSensorDescription(
        key="open_tasks",
        translation_key="open_tasks",
        value_fn=_count("total_open_tasks"),
    ),
    TududiSensorDescription(
        key="in_progress_tasks",
        translation_key="in_progress_tasks",
        value_fn=_count("tasks_in_progress_count"),
        tasks_key="tasks_in_progress",
    ),
    TududiSensorDescription(
        key="due_today_tasks",
        translation_key="due_today_tasks",
        value_fn=_count("tasks_due_today_count"),
        tasks_key="tasks_due_today",
    ),
    TududiSensorDescription(
        key="overdue_tasks",
        translation_key="overdue_tasks",
        value_fn=_list_len("tasks_overdue"),
        tasks_key="tasks_overdue",
    ),
    TududiSensorDescription(
        key="today_plan_tasks",
        translation_key="today_plan_tasks",
        value_fn=_count("today_plan_tasks_count"),
        tasks_key="tasks_today_plan",
    ),
    TududiSensorDescription(
        key="suggested_tasks",
        translation_key="suggested_tasks",
        value_fn=_count("suggested_tasks_count"),
        tasks_key="suggested_tasks",
    ),
    TududiSensorDescription(
        key="completed_today_tasks",
        translation_key="completed_today_tasks",
        value_fn=_count("tasks_completed_today_count"),
        tasks_key="tasks_completed_today",
    ),
    TududiSensorDescription(
        key="stale_tasks",
        translation_key="stale_tasks",
        value_fn=_count("tasks_pending_over_month"),
    ),
    TududiSensorDescription(
        key="inbox_items",
        translation_key="inbox_items",
        value_fn=lambda data: len(data.inbox),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TududiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up metric sensors and one streak sensor per habit."""
    coordinator = entry.runtime_data
    async_add_entities(
        TududiMetricSensor(coordinator, description) for description in METRIC_SENSORS
    )
    async_add_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        "sensor",
        lambda: [h["uid"] for h in coordinator.data.habits if h.get("uid")],
        lambda uid: [TududiHabitSensor(coordinator, uid)],
        lambda uid: [f"{entry.entry_id}_habit_{uid}_streak"],
    )


class TududiMetricSensor(TududiEntity, SensorEntity):
    """A count from tududi's task metrics."""

    entity_description: TududiSensorDescription
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "tasks"

    def __init__(
        self, coordinator: TududiCoordinator, description: TududiSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        if description.key == "inbox_items":
            self._attr_native_unit_of_measurement = "items"

    @property
    def native_value(self) -> Any:
        """Return the metric value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List the tasks behind the count."""
        data = self.coordinator.data
        if self.entity_description.key == "inbox_items":
            return {
                "items": [
                    {"uid": i.get("uid"), "content": i.get("content")}
                    for i in data.inbox[:20]
                ]
            }
        if self.entity_description.key == "completed_today_tasks":
            return {
                "tasks": _summaries(data.completed_today),
                "weekly_completions": data.metrics.get("weekly_completions"),
            }
        if key := self.entity_description.tasks_key:
            return {"tasks": _summaries(data.metrics.get(key))}
        return None


class TududiHabitSensor(TududiEntity, SensorEntity):
    """Current streak of a habit, with the other habit stats as attributes."""

    _attr_translation_key = "habit_streak"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TududiCoordinator, habit_uid: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._habit_uid = habit_uid
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_habit_{habit_uid}_streak"
        )

    @property
    def _habit(self) -> dict[str, Any] | None:
        return self.coordinator.data.habit_by_uid(self._habit_uid)

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Fill the habit name into the entity name."""
        habit = self._habit
        return {
            "habit": habit.get("name", self._habit_uid) if habit else self._habit_uid
        }

    @property
    def available(self) -> bool:
        """Unavailable once the habit disappears."""
        return super().available and self._habit is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Streaks count habit periods (days for daily habits)."""
        habit = self._habit or {}
        return {
            "daily": "days",
            "weekly": "weeks",
            "monthly": "months",
        }.get(habit.get("habit_frequency_period", "daily"), "periods")

    @property
    def native_value(self) -> int | None:
        """Return the current streak."""
        habit = self._habit
        return habit.get("habit_current_streak") if habit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the remaining habit stats."""
        habit = self._habit
        if not habit:
            return None
        return {
            "uid": habit.get("uid"),
            "best_streak": habit.get("habit_best_streak"),
            "total_completions": habit.get("habit_total_completions"),
            "last_completion_at": habit.get("habit_last_completion_at"),
            "strength": habit.get("habit_strength"),
            "progress": habit.get("habit_progress"),
            "polarity": habit.get("habit_polarity"),
            "frequency_period": habit.get("habit_frequency_period"),
            "target_count": habit.get("habit_target_count"),
            "time_of_day": habit.get("habit_time_of_day"),
            "archived": habit.get("habit_archived"),
        }
