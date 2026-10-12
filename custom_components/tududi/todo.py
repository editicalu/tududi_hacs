"""To-do lists backed by tududi tasks."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import TududiError
from .const import CLOSED_PROJECT_STATUSES, DOMAIN, status_name
from .coordinator import TududiConfigEntry, TududiCoordinator
from .entity import TududiEntity, async_add_dynamic_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TududiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the task lists."""
    coordinator = entry.runtime_data
    async_add_entities([TududiTodoList(coordinator, None)])

    def project_uids() -> list[str]:
        return [
            p["uid"]
            for p in coordinator.data.projects
            if p.get("uid") and p.get("status") not in CLOSED_PROJECT_STATUSES
        ]

    async_add_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        "todo",
        project_uids,
        lambda uid: [TududiTodoList(coordinator, uid)],
        lambda uid: [_unique_id(entry.entry_id, uid)],
    )


def _unique_id(entry_id: str, project_uid: str | None) -> str:
    return (
        f"{entry_id}_tasks"
        if project_uid is None
        else f"{entry_id}_project_{project_uid}"
    )


def _parse_due(value: str | None) -> date | None:
    """Parse tududi's ``YYYY-MM-DD`` (or ISO datetime) due date."""
    if not value:
        return None
    if parsed := dt_util.parse_date(value[:10]):
        return parsed
    return None


def _to_item(task: dict[str, Any]) -> TodoItem:
    return TodoItem(
        uid=task["uid"],
        summary=task.get("original_name") or task.get("name") or "",
        status=(
            TodoItemStatus.COMPLETED
            if status_name(task.get("status")) == "done"
            else TodoItemStatus.NEEDS_ACTION
        ),
        due=_parse_due(task.get("due_date")),
        description=task.get("note") or None,
    )


class TududiTodoList(TududiEntity, TodoListEntity):
    """A tududi project (or the project-less task list) as a to-do list."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: TududiCoordinator, project_uid: str | None) -> None:
        """Initialize the list; ``project_uid`` None means tasks without a project."""
        super().__init__(coordinator)
        self._project_uid = project_uid
        self._attr_unique_id = _unique_id(
            coordinator.config_entry.entry_id, project_uid
        )
        if project_uid is None:
            self._attr_translation_key = "tasks"

    @property
    def name(self) -> str | None:
        """Use the project name for project lists."""
        if self._project_uid is None:
            return super().name
        project = self.coordinator.data.project_by_uid(self._project_uid)
        return project.get("name") if project else self._project_uid

    @property
    def available(self) -> bool:
        """A project list is unavailable once the project disappears."""
        return super().available and (
            self._project_uid is None
            or self.coordinator.data.project_by_uid(self._project_uid) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the project uid so services can target this list's project."""
        return {"project_uid": self._project_uid} if self._project_uid else None

    def _tasks(self) -> list[dict[str, Any]]:
        data = self.coordinator.data
        seen: set[str] = set()
        result = []
        for task in [*data.tasks, *data.completed_today]:
            uid = task.get("uid")
            if not uid or uid in seen or task.get("project_uid") != self._project_uid:
                continue
            seen.add(uid)
            result.append(task)
        return result

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the open tasks plus those completed today."""
        return [_to_item(task) for task in self._tasks()]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a task in this list's project."""
        data: dict[str, Any] = {"name": item.summary}
        if self._project_uid:
            data["project_uid"] = self._project_uid
        if item.description:
            data["note"] = item.description
        if item.due:
            data["due_date"] = _due_str(item.due)
        if item.status == TodoItemStatus.COMPLETED:
            data["status"] = "done"
        await self._call(self.coordinator.client.create_task(data))

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Rename, reschedule, describe or (un)complete a task."""
        assert item.uid
        current = next((t for t in self._tasks() if t["uid"] == item.uid), {})
        data: dict[str, Any] = {
            "name": item.summary,
            "note": item.description or "",
            "due_date": _due_str(item.due) if item.due else None,
        }
        was_done = status_name(current.get("status")) == "done"
        if item.status == TodoItemStatus.COMPLETED and not was_done:
            data["status"] = "done"
        elif item.status == TodoItemStatus.NEEDS_ACTION and was_done:
            data["status"] = "not_started"
        await self._call(self.coordinator.client.update_task(item.uid, data))

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete tasks."""
        client = self.coordinator.client
        try:
            for uid in uids:
                await client.delete_task(uid)
        except TududiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            await self.coordinator.async_refresh()

    async def _call(self, coro: Any) -> None:
        try:
            await coro
        except TududiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_refresh()


def _due_str(due: date | datetime) -> str:
    """Tududi stores due dates as calendar days."""
    if isinstance(due, datetime):
        due = dt_util.as_local(due).date()
    return due.isoformat()
