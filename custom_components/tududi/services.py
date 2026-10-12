"""Services exposing the tududi API to Home Assistant."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .api import TududiClient, TududiError
from .const import (
    DOMAIN,
    GOAL_HORIZONS,
    GOAL_STATUSES,
    HABIT_PERIODS,
    HABIT_POLARITIES,
    HABIT_TIMES_OF_DAY,
    PROJECT_STATUSES,
    RECURRENCE_TYPES,
    SEARCH_TYPES,
    TASK_LIST_STATUSES,
    TASK_LIST_TYPES,
    TASK_PRIORITIES,
    TASK_STATUSES,
)
from .coordinator import TududiConfigEntry, TududiCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_UID = "uid"
ATTR_EXTRA = "extra"

# Fields the service layer consumes itself rather than forwarding to the API.
_RESERVED = {ATTR_CONFIG_ENTRY_ID, ATTR_UID, ATTR_EXTRA}

Handler = Callable[[TududiCoordinator, dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class _Service:
    schema: dict[Any, Any]
    handler: Handler
    response: SupportsResponse = SupportsResponse.NONE
    # Key the API result is returned under, when the service returns data.
    result_key: str | None = None
    # Whether the coordinator data changes and should be refreshed.
    refresh: bool = True


# ---------------------------------------------------------------------------
# Schema building blocks

_BASE = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Optional(ATTR_EXTRA): dict,
}
_UID = {vol.Required(ATTR_UID): cv.string}

_PRIORITY = vol.In(TASK_PRIORITIES)
_WEEKDAY = vol.All(vol.Coerce(int), vol.Range(min=0, max=6))
_TAGS = vol.All(cv.ensure_list, [cv.string])

_TASK_FIELDS = {
    vol.Optional("note"): vol.Any(None, cv.string),
    vol.Optional("due_date"): vol.Any(None, cv.date),
    vol.Optional("defer_until"): vol.Any(None, cv.datetime),
    vol.Optional("priority"): _PRIORITY,
    vol.Optional("status"): vol.In(TASK_STATUSES),
    vol.Optional("project"): vol.Any(None, cv.string),
    vol.Optional("area"): vol.Any(None, cv.string),
    vol.Optional("goal"): vol.Any(None, cv.string),
    vol.Optional("parent_task"): vol.Any(None, cv.string),
    vol.Optional("tags"): _TAGS,
    vol.Optional("estimated_minutes"): vol.Any(
        None, vol.All(vol.Coerce(int), vol.Range(min=5, max=720))
    ),
    vol.Optional("recurrence_type"): vol.In(RECURRENCE_TYPES),
    vol.Optional("recurrence_interval"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional("recurrence_end_date"): vol.Any(None, cv.date),
    vol.Optional("recurrence_weekday"): _WEEKDAY,
    vol.Optional("recurrence_weekdays"): vol.All(cv.ensure_list, [_WEEKDAY]),
    vol.Optional("recurrence_month_day"): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=31)
    ),
    vol.Optional("recurrence_week_of_month"): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=5)
    ),
    vol.Optional("completion_based"): cv.boolean,
    vol.Optional("assigned_to"): vol.Any(None, cv.string),
}

_PROJECT_FIELDS = {
    vol.Optional("description"): vol.Any(None, cv.string),
    vol.Optional("area"): vol.Any(None, cv.string),
    vol.Optional("goal"): vol.Any(None, cv.string),
    vol.Optional("priority"): _PRIORITY,
    vol.Optional("status"): vol.In(PROJECT_STATUSES),
    vol.Optional("due_date_at"): vol.Any(None, cv.date),
    vol.Optional("tags"): _TAGS,
    vol.Optional("color"): vol.Any(None, cv.string),
    vol.Optional("pin_to_sidebar"): cv.boolean,
    vol.Optional("is_maintenance"): cv.boolean,
}

_AREA_FIELDS = {
    vol.Optional("description"): vol.Any(None, cv.string),
    vol.Optional("color"): vol.Any(None, cv.string),
}

_NOTE_FIELDS = {
    vol.Optional("content"): vol.Any(None, cv.string),
    vol.Optional("project"): vol.Any(None, cv.string),
    vol.Optional("tags"): _TAGS,
    vol.Optional("color"): vol.Any(None, cv.string),
    vol.Optional("pin_to_sidebar"): cv.boolean,
}

_TAG_FIELDS = {
    vol.Optional("color"): vol.Any(None, cv.string),
    vol.Optional("pinned"): cv.boolean,
}

_HABIT_FIELDS = {
    vol.Optional("note"): vol.Any(None, cv.string),
    vol.Optional("priority"): _PRIORITY,
    vol.Optional("habit_polarity"): vol.In(HABIT_POLARITIES),
    vol.Optional("habit_frequency_period"): vol.In(HABIT_PERIODS),
    vol.Optional("habit_target_count"): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=1000)
    ),
    vol.Optional("habit_target_value"): vol.Any(None, vol.Coerce(float)),
    vol.Optional("habit_unit"): vol.Any(None, cv.string),
    vol.Optional("habit_schedule_days"): vol.Any(
        None, vol.All(cv.ensure_list, [_WEEKDAY])
    ),
    vol.Optional("habit_interval_days"): vol.Any(
        None, vol.All(vol.Coerce(int), vol.Range(min=2, max=365))
    ),
    vol.Optional("habit_time_of_day"): vol.Any(None, vol.In(HABIT_TIMES_OF_DAY)),
    vol.Optional("habit_reminder_time"): vol.Any(
        None, vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$")
    ),
    vol.Optional("habit_color"): vol.Any(None, vol.Match(r"^#[0-9a-fA-F]{6}$")),
}

_GOAL_FIELDS = {
    vol.Optional("why"): vol.Any(None, cv.string),
    vol.Optional("area"): vol.Any(None, cv.string),
    vol.Optional("horizon"): vol.In(GOAL_HORIZONS),
    vol.Optional("target_date"): vol.Any(None, cv.date),
    vol.Optional("status"): vol.In(GOAL_STATUSES),
    vol.Optional("color"): vol.Any(None, cv.string),
}

_PERSON_FIELDS = {
    vol.Optional("relationship_type"): vol.Any(None, cv.string),
    vol.Optional("email"): vol.Any(None, cv.string),
    vol.Optional("phone"): vol.Any(None, cv.string),
    vol.Optional("notes"): vol.Any(None, cv.string),
    vol.Optional("color"): vol.Any(None, cv.string),
}

_VIEW_FIELDS = {
    vol.Optional("search_query"): vol.Any(None, cv.string),
    vol.Optional("filters"): vol.All(cv.ensure_list, [vol.In(SEARCH_TYPES)]),
    vol.Optional("priority"): vol.Any(None, _PRIORITY),
    vol.Optional("due"): vol.Any(None, cv.string),
    vol.Optional("defer"): vol.Any(None, cv.string),
    vol.Optional("tags"): _TAGS,
    vol.Optional("extras"): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("recurring"): vol.Any(None, cv.string),
    vol.Optional("task_status"): vol.Any(None, vol.In(TASK_STATUSES)),
    vol.Optional("is_pinned"): cv.boolean,
}

_DATE_RANGE = {
    vol.Optional("start_date"): cv.date,
    vol.Optional("end_date"): cv.date,
}


def _create(required: str, fields: dict) -> dict:
    return {**_BASE, vol.Required(required): cv.string, **fields}


def _update(name_field: str, fields: dict) -> dict:
    return {**_BASE, **_UID, vol.Optional(name_field): cv.string, **fields}


# ---------------------------------------------------------------------------
# Payload helpers


def _jsonable(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date | datetime) else value


def _int_priority(body: dict[str, Any]) -> dict[str, Any]:
    """Projects and habits store priority as 0-2 instead of a name."""
    if body.get("priority") in TASK_PRIORITIES:
        body["priority"] = TASK_PRIORITIES.index(body["priority"])
    return body


def _body(
    data: dict[str, Any], skip: frozenset[str] | set[str] = frozenset()
) -> dict[str, Any]:
    """Forward call fields as an API body, merged with the ``extra`` passthrough."""
    body = {
        key: _jsonable(value)
        for key, value in data.items()
        if key not in _RESERVED and key not in skip
    }
    body.update(data.get(ATTR_EXTRA) or {})
    return body


def _find(
    items: list[dict[str, Any]], ref: str, kind: str, name_key: str = "name"
) -> dict[str, Any]:
    """Find an item by uid, numeric id or case-insensitive name."""
    ref_l = ref.strip().lower()
    for item in items:
        if ref in (item.get("uid"), str(item.get("id"))):
            return item
    for item in items:
        if str(item.get(name_key, "")).strip().lower() == ref_l:
            return item
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_found",
        translation_placeholders={"kind": kind, "ref": ref},
    )


async def _project_uid(coordinator: TududiCoordinator, ref: str | None) -> str | None:
    if not ref:
        return None
    projects = coordinator.data.projects if coordinator.data else []
    if not any(ref in (p.get("uid"), p.get("name")) for p in projects):
        projects = await coordinator.client.get_projects()
    return (_find(projects, ref, "project"))["uid"]


async def _area(client: TududiClient, ref: str | None) -> dict[str, Any] | None:
    if not ref:
        return None
    return _find(await client.get_areas() or [], ref, "area")


async def _goal(client: TududiClient, ref: str | None) -> dict[str, Any] | None:
    if not ref:
        return None
    return _find(await client.get_goals(), ref, "goal", name_key="title")


async def _resolve_refs(
    coordinator: TududiCoordinator, data: dict[str, Any], *, area_key: str
) -> dict[str, Any]:
    """Turn friendly ``project``/``area``/``goal``/``parent_task`` references into ids.

    ``area_key`` is ``area_uid`` for tasks (which accept uids) and ``area_id``
    for projects and goals (which expect the numeric id).
    """
    client = coordinator.client
    body = _body(data, skip={"project", "area", "goal", "parent_task", "subtasks"})
    if "project" in data:
        body["project_uid"] = await _project_uid(coordinator, data["project"])
    if "area" in data:
        area = await _area(client, data["area"])
        body[area_key] = (
            None if area is None else area["uid" if area_key == "area_uid" else "id"]
        )
    if "goal" in data:
        goal = await _goal(client, data["goal"])
        body["goal_id"] = None if goal is None else goal["id"]
    if "parent_task" in data:
        parent = data["parent_task"]
        body["parent_task_id"] = (
            None
            if not parent
            else parent
            if parent.isdigit()
            else (await client.get_task(parent))["id"]
        )
    if data.get("subtasks"):
        body["subtasks"] = [{"name": name} for name in data["subtasks"]]
    return body


def _wrap(key: str, result: Any) -> dict[str, Any]:
    """Service responses must be dicts; unwrap API envelopes like ``{"goal": ...}``."""
    if isinstance(result, dict) and set(result) - {"active_goals_count"} == {key}:
        result = result[key]
    return {key: result}


# ---------------------------------------------------------------------------
# Handlers


async def _create_task(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.create_task(await _resolve_refs(c, d, area_key="area_uid"))


async def _update_task(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_task(
        d[ATTR_UID], await _resolve_refs(c, d, area_key="area_uid")
    )


async def _create_project(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.create_project(
        _int_priority(await _resolve_refs(c, d, area_key="area_id"))
    )


async def _update_project(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_project(
        d[ATTR_UID], _int_priority(await _resolve_refs(c, d, area_key="area_id"))
    )


async def _create_habit(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.create_habit(_int_priority(_body(d)))


async def _update_habit(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_habit(d[ATTR_UID], _int_priority(_body(d)))


async def _create_note(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.create_note(await _resolve_refs(c, d, area_key="area_uid"))


async def _update_note(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_note(
        d[ATTR_UID], await _resolve_refs(c, d, area_key="area_uid")
    )


async def _create_goal(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.create_goal(await _resolve_refs(c, d, area_key="area_id"))


async def _update_goal(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_goal(
        d[ATTR_UID], await _resolve_refs(c, d, area_key="area_id")
    )


async def _get_tasks(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    params = _body(d, skip={"project", "area"})
    if d.get("project"):
        params["project_uid"] = await _project_uid(c, d["project"])
    if d.get("area"):
        params["area_uid"] = (await _area(c.client, d["area"]))["uid"]
    if isinstance(params.get("tags"), list):
        params["tags"] = ",".join(params["tags"])
    return await c.client.get_tasks(**params)


async def _search(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    params = _body(d, skip={"query"})
    params["q"] = d.get("query")
    for key in ("filters", "tags"):
        if isinstance(params.get(key), list):
            params[key] = ",".join(params[key])
    return await c.client.search(**params)


def _uid_call(method: str) -> Handler:
    """Handler calling ``client.<method>(uid)``."""

    async def handler(c: TududiCoordinator, d: dict[str, Any]) -> Any:
        return await getattr(c.client, method)(d[ATTR_UID])

    return handler


def _uid_body_call(method: str) -> Handler:
    """Handler calling ``client.<method>(uid, body)``."""

    async def handler(c: TududiCoordinator, d: dict[str, Any]) -> Any:
        return await getattr(c.client, method)(d[ATTR_UID], _body(d))

    return handler


def _body_call(method: str) -> Handler:
    """Handler calling ``client.<method>(body)``."""

    async def handler(c: TududiCoordinator, d: dict[str, Any]) -> Any:
        return await getattr(c.client, method)(_body(d))

    return handler


def _params_call(method: str) -> Handler:
    """Handler calling ``client.<method>(**params)``."""

    async def handler(c: TududiCoordinator, d: dict[str, Any]) -> Any:
        return await getattr(c.client, method)(**_body(d))

    return handler


def _uid_params_call(method: str) -> Handler:
    """Handler calling ``client.<method>(uid, **params)``."""

    async def handler(c: TududiCoordinator, d: dict[str, Any]) -> Any:
        return await getattr(c.client, method)(d[ATTR_UID], **_body(d))

    return handler


async def _complete_task(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.update_task(d[ATTR_UID], {"status": "done"})


async def _process_inbox_item(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.process_inbox_item(d[ATTR_UID], _body(d) or None)


async def _delete_habit_completion(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.delete_habit_completion(d[ATTR_UID], d["completion_id"])


async def _get_habits(c: TududiCoordinator, d: dict[str, Any]) -> Any:
    return await c.client.get_habits(archived=d.get("archived", False))


OPTIONAL = SupportsResponse.OPTIONAL
ONLY = SupportsResponse.ONLY

SERVICES: dict[str, _Service] = {
    # Tasks
    "create_task": _Service(
        _create("name", {**_TASK_FIELDS, vol.Optional("subtasks"): _TAGS}),
        _create_task,
        OPTIONAL,
        "task",
    ),
    "update_task": _Service(
        _update("name", _TASK_FIELDS), _update_task, OPTIONAL, "task"
    ),
    "complete_task": _Service({**_BASE, **_UID}, _complete_task, OPTIONAL, "task"),
    "delete_task": _Service({**_BASE, **_UID}, _uid_call("delete_task")),
    "skip_task_occurrence": _Service(
        {**_BASE, **_UID}, _uid_call("skip_occurrence"), OPTIONAL, "task"
    ),
    "get_task": _Service(
        {**_BASE, **_UID}, _uid_call("get_task"), ONLY, "task", refresh=False
    ),
    "get_subtasks": _Service(
        {**_BASE, **_UID}, _uid_call("get_subtasks"), ONLY, "subtasks", refresh=False
    ),
    "get_tasks": _Service(
        {
            **_BASE,
            vol.Optional("type", default="all"): vol.In(TASK_LIST_TYPES),
            vol.Optional("status", default="active"): vol.In(TASK_LIST_STATUSES),
            vol.Optional("project"): cv.string,
            vol.Optional("area"): cv.string,
            vol.Optional("tags"): _TAGS,
            vol.Optional("order_by"): cv.string,
            vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional("offset"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        },
        _get_tasks,
        ONLY,
        "tasks",
        refresh=False,
    ),
    "get_task_metrics": _Service(
        _BASE, _params_call("get_task_metrics"), ONLY, "metrics", refresh=False
    ),
    # Projects
    "create_project": _Service(
        _create("name", _PROJECT_FIELDS), _create_project, OPTIONAL, "project"
    ),
    "update_project": _Service(
        _update("name", _PROJECT_FIELDS), _update_project, OPTIONAL, "project"
    ),
    "delete_project": _Service({**_BASE, **_UID}, _uid_call("delete_project")),
    "get_project": _Service(
        {**_BASE, **_UID}, _uid_call("get_project"), ONLY, "project", refresh=False
    ),
    "get_projects": _Service(
        {**_BASE, vol.Optional("status"): cv.string},
        _params_call("get_projects"),
        ONLY,
        "projects",
        refresh=False,
    ),
    # Areas
    "create_area": _Service(
        _create("name", _AREA_FIELDS), _body_call("create_area"), OPTIONAL, "area"
    ),
    "update_area": _Service(
        _update("name", _AREA_FIELDS), _uid_body_call("update_area"), OPTIONAL, "area"
    ),
    "delete_area": _Service({**_BASE, **_UID}, _uid_call("delete_area")),
    "get_areas": _Service(
        _BASE, _params_call("get_areas"), ONLY, "areas", refresh=False
    ),
    # Notes
    "create_note": _Service(
        _create("title", _NOTE_FIELDS), _create_note, OPTIONAL, "note"
    ),
    "update_note": _Service(
        _update("title", _NOTE_FIELDS), _update_note, OPTIONAL, "note"
    ),
    "delete_note": _Service({**_BASE, **_UID}, _uid_call("delete_note")),
    "get_note": _Service(
        {**_BASE, **_UID}, _uid_call("get_note"), ONLY, "note", refresh=False
    ),
    "get_notes": _Service(
        _BASE, _params_call("get_notes"), ONLY, "notes", refresh=False
    ),
    # Tags (identified by uid or name)
    "create_tag": _Service(
        _create("name", _TAG_FIELDS), _body_call("create_tag"), OPTIONAL, "tag"
    ),
    "update_tag": _Service(
        _update("name", _TAG_FIELDS), _uid_body_call("update_tag"), OPTIONAL, "tag"
    ),
    "delete_tag": _Service({**_BASE, **_UID}, _uid_call("delete_tag")),
    "get_tags": _Service(_BASE, _params_call("get_tags"), ONLY, "tags", refresh=False),
    # Inbox
    "add_to_inbox": _Service(
        {
            **_BASE,
            vol.Required("content"): cv.string,
            vol.Optional("source"): cv.string,
        },
        _body_call("create_inbox_item"),
        OPTIONAL,
        "item",
    ),
    "update_inbox_item": _Service(
        {**_BASE, **_UID, vol.Optional("content"): cv.string},
        _uid_body_call("update_inbox_item"),
        OPTIONAL,
        "item",
    ),
    "process_inbox_item": _Service(
        {**_BASE, **_UID}, _process_inbox_item, OPTIONAL, "item"
    ),
    "delete_inbox_item": _Service({**_BASE, **_UID}, _uid_call("delete_inbox_item")),
    "get_inbox": _Service(
        _BASE, _params_call("get_inbox"), ONLY, "items", refresh=False
    ),
    # Habits
    "create_habit": _Service(
        _create("name", _HABIT_FIELDS), _create_habit, OPTIONAL, "habit"
    ),
    "update_habit": _Service(
        _update("name", _HABIT_FIELDS),
        _update_habit,
        OPTIONAL,
        "habit",
    ),
    "delete_habit": _Service({**_BASE, **_UID}, _uid_call("delete_habit")),
    "complete_habit": _Service(
        {
            **_BASE,
            **_UID,
            vol.Optional("completed_at"): cv.datetime,
            vol.Optional("value"): vol.Coerce(float),
            vol.Optional("note"): cv.string,
        },
        _uid_body_call("complete_habit"),
        OPTIONAL,
        "habit",
    ),
    "skip_habit": _Service(
        {
            **_BASE,
            **_UID,
            vol.Optional("date"): cv.date,
            vol.Optional("note"): cv.string,
        },
        _uid_body_call("skip_habit"),
        OPTIONAL,
        "habit",
    ),
    "archive_habit": _Service({**_BASE, **_UID}, _uid_call("archive_habit")),
    "unarchive_habit": _Service({**_BASE, **_UID}, _uid_call("unarchive_habit")),
    "delete_habit_completion": _Service(
        {**_BASE, **_UID, vol.Required("completion_id"): cv.string},
        _delete_habit_completion,
    ),
    "get_habits": _Service(
        {**_BASE, vol.Optional("archived", default=False): cv.boolean},
        _get_habits,
        ONLY,
        "habits",
        refresh=False,
    ),
    "get_habit_stats": _Service(
        {**_BASE, **_UID, **_DATE_RANGE},
        _uid_params_call("get_habit_stats"),
        ONLY,
        "stats",
        refresh=False,
    ),
    "get_habit_completions": _Service(
        {**_BASE, **_UID, **_DATE_RANGE},
        _uid_params_call("get_habit_completions"),
        ONLY,
        "completions",
        refresh=False,
    ),
    # Goals
    "create_goal": _Service(
        _create("title", _GOAL_FIELDS), _create_goal, OPTIONAL, "goal"
    ),
    "update_goal": _Service(
        _update("title", _GOAL_FIELDS), _update_goal, OPTIONAL, "goal"
    ),
    "delete_goal": _Service({**_BASE, **_UID}, _uid_call("delete_goal")),
    "get_goals": _Service(
        _BASE, _params_call("get_goals"), ONLY, "goals", refresh=False
    ),
    # People
    "create_person": _Service(
        _create("name", _PERSON_FIELDS), _body_call("create_person"), OPTIONAL, "person"
    ),
    "update_person": _Service(
        _update("name", {**_PERSON_FIELDS, vol.Optional("archived"): cv.boolean}),
        _uid_body_call("update_person"),
        OPTIONAL,
        "person",
    ),
    "delete_person": _Service({**_BASE, **_UID}, _uid_call("delete_person")),
    "get_people": _Service(
        _BASE, _params_call("get_people"), ONLY, "people", refresh=False
    ),
    # Saved views
    "create_view": _Service(
        _create("name", _VIEW_FIELDS), _body_call("create_view"), OPTIONAL, "view"
    ),
    "update_view": _Service(
        _update("name", _VIEW_FIELDS), _uid_body_call("update_view"), OPTIONAL, "view"
    ),
    "delete_view": _Service({**_BASE, **_UID}, _uid_call("delete_view")),
    "get_views": _Service(
        _BASE, _params_call("get_views"), ONLY, "views", refresh=False
    ),
    # Search
    "search": _Service(
        {
            **_BASE,
            vol.Optional("query"): cv.string,
            vol.Optional("filters"): vol.All(cv.ensure_list, [vol.In(SEARCH_TYPES)]),
            vol.Optional("tags"): _TAGS,
            vol.Optional("priority"): _PRIORITY,
            vol.Optional("due"): cv.string,
            vol.Optional("status"): vol.In(["active", "completed", "all"]),
            vol.Optional("task_status"): vol.In(TASK_STATUSES),
            vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional("offset"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        },
        _search,
        ONLY,
        "results",
        refresh=False,
    ),
}


def _coordinator(hass: HomeAssistant, entry_id: str | None) -> TududiCoordinator:
    """Return the coordinator of the targeted (or only) loaded entry."""
    entries: list[TududiConfigEntry] = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]
    if entry_id is not None:
        entries = [e for e in entries if e.entry_id == entry_id]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"entry_id": entry_id},
            )
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_entries"
        )
    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="multiple_entries"
        )
    return entries[0].runtime_data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register every tududi service."""

    for name, service in SERVICES.items():

        async def handle(
            call: ServiceCall, service: _Service = service
        ) -> ServiceResponse:
            coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            try:
                result = await service.handler(coordinator, dict(call.data))
            except TududiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={"error": str(err)},
                ) from err
            if service.refresh:
                await coordinator.async_request_refresh()
            if service.result_key and call.return_response:
                return _wrap(service.result_key, result)
            return None

        hass.services.async_register(
            DOMAIN,
            name,
            handle,
            schema=vol.Schema(service.schema),
            supports_response=service.response,
        )
