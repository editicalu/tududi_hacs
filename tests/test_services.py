"""Tests for the Tududi services."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.tududi.const import DOMAIN
from custom_components.tududi.services import SERVICES

from .conftest import API, calls


async def test_all_services_registered(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Every service in the table is registered."""
    assert set(hass.services.async_services_for_domain(DOMAIN)) == set(SERVICES)


async def test_create_task_resolves_references(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Project names, area names and parent uids are resolved to API ids."""
    aioclient_mock.get(f"{API}/areas", json=[{"id": 5, "uid": "area1", "name": "Work"}])
    aioclient_mock.get(f"{API}/task/parent1", json={"id": 42, "uid": "parent1"})
    aioclient_mock.post(
        f"{API}/task", json={"uid": "t9", "name": "Buy milk"}, status=201
    )

    response = await hass.services.async_call(
        DOMAIN,
        "create_task",
        {
            "name": "Buy milk",
            "project": "home",
            "area": "Work",
            "parent_task": "parent1",
            "priority": "high",
            "due_date": "2026-10-31",
            "tags": ["errands", "shop"],
            "subtasks": ["Check fridge"],
            "recurrence_type": "weekly",
            "recurrence_weekdays": ["1", "3"],
            "extra": {"involves": []},
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"task": {"uid": "t9", "name": "Buy milk"}}
    [call] = calls(aioclient_mock, "post", "/task")
    assert call[2] == {
        "name": "Buy milk",
        "priority": "high",
        "due_date": "2026-10-31",
        "tags": ["errands", "shop"],
        "recurrence_type": "weekly",
        "recurrence_weekdays": [1, 3],
        "involves": [],
        "project_uid": "proj1",
        "area_uid": "area1",
        "parent_task_id": 42,
        "subtasks": [{"name": "Check fridge"}],
    }


async def test_unknown_project(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """An unknown project name is a validation error."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "create_task",
            {"name": "x", "project": "Nope"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "data", "method", "path", "body"),
    [
        (
            "update_task",
            {"uid": "task1", "status": "waiting"},
            "patch",
            "/task/task1",
            {"status": "waiting"},
        ),
        ("complete_task", {"uid": "task1"}, "patch", "/task/task1", {"status": "done"}),
        ("delete_task", {"uid": "task1"}, "delete", "/task/task1", None),
        (
            "skip_task_occurrence",
            {"uid": "task1"},
            "post",
            "/task/task1/skip-occurrence",
            None,
        ),
        (
            "create_project",
            {"name": "P", "status": "planned", "priority": "high"},
            "post",
            "/project",
            {"name": "P", "status": "planned", "priority": 2},
        ),
        (
            "update_project",
            {"uid": "proj1", "name": "Q"},
            "patch",
            "/project/proj1",
            {"name": "Q"},
        ),
        ("delete_project", {"uid": "proj1"}, "delete", "/project/proj1", None),
        ("create_area", {"name": "A"}, "post", "/areas", {"name": "A"}),
        (
            "update_area",
            {"uid": "a1", "color": "#ffffff"},
            "patch",
            "/areas/a1",
            {"color": "#ffffff"},
        ),
        ("delete_area", {"uid": "a1"}, "delete", "/areas/a1", None),
        (
            "create_note",
            {"title": "N", "content": "body"},
            "post",
            "/note",
            {"title": "N", "content": "body"},
        ),
        (
            "update_note",
            {"uid": "n1", "content": "x"},
            "patch",
            "/note/n1",
            {"content": "x"},
        ),
        ("delete_note", {"uid": "n1"}, "delete", "/note/n1", None),
        ("create_tag", {"name": "t"}, "post", "/tag", {"name": "t"}),
        (
            "update_tag",
            {"uid": "old name", "name": "new"},
            "patch",
            "/tag/old%20name",
            {"name": "new"},
        ),
        ("delete_tag", {"uid": "t1"}, "delete", "/tag/t1", None),
        (
            "add_to_inbox",
            {"content": "Call mom", "source": "ha"},
            "post",
            "/inbox",
            {"content": "Call mom", "source": "ha"},
        ),
        (
            "update_inbox_item",
            {"uid": "i1", "content": "c"},
            "patch",
            "/inbox/i1",
            {"content": "c"},
        ),
        ("process_inbox_item", {"uid": "i1"}, "patch", "/inbox/i1/process", {}),
        ("delete_inbox_item", {"uid": "i1"}, "delete", "/inbox/i1", None),
        (
            "create_habit",
            {
                "name": "Run",
                "habit_frequency_period": "weekly",
                "habit_target_count": 3,
            },
            "post",
            "/habits",
            {
                "name": "Run",
                "habit_frequency_period": "weekly",
                "habit_target_count": 3,
            },
        ),
        (
            "update_habit",
            {"uid": "habit1", "habit_schedule_days": ["1", "2"], "priority": "medium"},
            "put",
            "/habits/habit1",
            {"habit_schedule_days": [1, 2], "priority": 1},
        ),
        ("delete_habit", {"uid": "habit1"}, "delete", "/habits/habit1", None),
        (
            "complete_habit",
            {"uid": "habit1", "value": 2},
            "post",
            "/habits/habit1/complete",
            {"value": 2.0},
        ),
        (
            "skip_habit",
            {"uid": "habit1", "date": "2026-10-12"},
            "post",
            "/habits/habit1/skip",
            {"date": "2026-10-12"},
        ),
        ("archive_habit", {"uid": "habit1"}, "post", "/habits/habit1/archive", None),
        (
            "unarchive_habit",
            {"uid": "habit1"},
            "post",
            "/habits/habit1/unarchive",
            None,
        ),
        (
            "delete_habit_completion",
            {"uid": "habit1", "completion_id": "7"},
            "delete",
            "/habits/habit1/completions/7",
            None,
        ),
        (
            "create_goal",
            {"title": "G", "horizon": "year"},
            "post",
            "/goals",
            {"title": "G", "horizon": "year"},
        ),
        (
            "update_goal",
            {"uid": "g1", "status": "achieved"},
            "patch",
            "/goals/g1",
            {"status": "achieved"},
        ),
        ("delete_goal", {"uid": "g1"}, "delete", "/goals/g1", None),
        (
            "create_person",
            {"name": "Ann", "email": "a@b.c"},
            "post",
            "/people",
            {"name": "Ann", "email": "a@b.c"},
        ),
        (
            "update_person",
            {"uid": "p1", "archived": True},
            "patch",
            "/people/p1",
            {"archived": True},
        ),
        ("delete_person", {"uid": "p1"}, "delete", "/people/p1", None),
        (
            "create_view",
            {"name": "V", "filters": ["Task"]},
            "post",
            "/views",
            {"name": "V", "filters": ["Task"]},
        ),
        (
            "update_view",
            {"uid": "v1", "is_pinned": True},
            "patch",
            "/views/v1",
            {"is_pinned": True},
        ),
        ("delete_view", {"uid": "v1"}, "delete", "/views/v1", None),
    ],
)
async def test_write_services(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
    service: str,
    data: dict,
    method: str,
    path: str,
    body: dict | None,
) -> None:
    """Each write service calls the right endpoint with the right body."""
    getattr(aioclient_mock, method)(f"{API}{path}", json={})
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    [call] = calls(aioclient_mock, method, path)
    assert call[2] == body


@pytest.mark.parametrize(
    ("service", "data", "path", "api_response", "expected"),
    [
        (
            "get_tasks",
            {"type": "today"},
            "/tasks",
            {"tasks": [{"uid": "x"}]},
            {"tasks": [{"uid": "x"}]},
        ),
        (
            "get_task",
            {"uid": "task1"},
            "/task/task1",
            {"uid": "task1"},
            {"task": {"uid": "task1"}},
        ),
        (
            "get_subtasks",
            {"uid": "task1"},
            "/task/task1/subtasks",
            [{"uid": "s"}],
            {"subtasks": [{"uid": "s"}]},
        ),
        (
            "get_project",
            {"uid": "proj1"},
            "/project/proj1",
            {"uid": "proj1"},
            {"project": {"uid": "proj1"}},
        ),
        ("get_areas", {}, "/areas", [{"uid": "a"}], {"areas": [{"uid": "a"}]}),
        ("get_notes", {}, "/notes", [{"uid": "n"}], {"notes": [{"uid": "n"}]}),
        ("get_note", {"uid": "n"}, "/note/n", {"uid": "n"}, {"note": {"uid": "n"}}),
        ("get_tags", {}, "/tags", [{"name": "t"}], {"tags": [{"name": "t"}]}),
        (
            "get_goals",
            {},
            "/goals",
            {"goals": [{"uid": "g"}]},
            {"goals": [{"uid": "g"}]},
        ),
        (
            "get_people",
            {},
            "/people",
            {"people": [{"uid": "p"}]},
            {"people": [{"uid": "p"}]},
        ),
        ("get_views", {}, "/views", [{"uid": "v"}], {"views": [{"uid": "v"}]}),
        (
            "get_habit_stats",
            {"uid": "habit1"},
            "/habits/habit1/stats",
            {"rate": 1},
            {"stats": {"rate": 1}},
        ),
        (
            "get_habit_completions",
            {"uid": "habit1"},
            "/habits/habit1/completions",
            [],
            {"completions": []},
        ),
        (
            "search",
            {"query": "milk", "filters": ["Task", "Note"]},
            "/search",
            {"results": [1]},
            {"results": [1]},
        ),
    ],
)
async def test_read_services(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
    service: str,
    data: dict,
    path: str,
    api_response: object,
    expected: dict,
) -> None:
    """Read services return the API data wrapped in a dict."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}{path}", json=api_response)
    result = await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )
    assert result == expected


async def test_get_tasks_and_search_params(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Filters become query parameters."""
    await hass.services.async_call(
        DOMAIN,
        "get_tasks",
        {"type": "upcoming", "project": "Home", "tags": ["a", "b"]},
        blocking=True,
        return_response=True,
    )
    url = calls(aioclient_mock, "get", "/tasks")[-1][1]
    assert dict(url.query) == {
        "type": "upcoming",
        "status": "active",
        "tags": "a,b",
        "project_uid": "proj1",
    }

    aioclient_mock.get(f"{API}/search", json={})
    await hass.services.async_call(
        DOMAIN,
        "search",
        {"query": "milk", "filters": ["Task", "Note"]},
        blocking=True,
        return_response=True,
    )
    url = calls(aioclient_mock, "get", "/search")[-1][1]
    assert dict(url.query) == {"q": "milk", "filters": "Task,Note"}


async def test_api_error_is_raised(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """API errors surface as HomeAssistantError with the server message."""
    aioclient_mock.delete(
        f"{API}/task/missing", status=404, json={"error": "Task not found."}
    )
    with pytest.raises(HomeAssistantError, match="Task not found"):
        await hass.services.async_call(
            DOMAIN, "delete_task", {"uid": "missing"}, blocking=True
        )


async def test_multiple_entries_need_entry_id(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """With two loaded entries, config_entry_id selects the instance."""
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="other",
        data=dict(setup_integration.data),
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "delete_task", {"uid": "task1"}, blocking=True
        )

    aioclient_mock.delete(f"{API}/task/task1", json={})
    await hass.services.async_call(
        DOMAIN,
        "delete_task",
        {"uid": "task1", "config_entry_id": second.entry_id},
        blocking=True,
    )
