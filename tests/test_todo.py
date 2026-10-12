"""Tests for the Tududi to-do lists."""

from __future__ import annotations

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import API, calls, mock_api


async def _items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    result = await hass.services.async_call(
        TODO_DOMAIN,
        "get_items",
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    return result[entity_id]["items"]


async def test_lists_and_items(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Project-less tasks and each open project get their own list."""
    assert hass.states.get("todo.tududi_me_tasks").state == "1"
    assert hass.states.get("todo.tududi_me_home").state == "1"
    # Done projects get no list.
    assert hass.states.get("todo.tududi_me_old") is None

    items = await _items(hass, "todo.tududi_me_tasks")
    assert items == [
        {
            "uid": "task1",
            "summary": "Loose task",
            "status": "needs_action",
            "due": "2026-10-20",
            "description": "a note",
        },
        {"uid": "task3", "summary": "Done today", "status": "completed"},
    ]
    assert [i["uid"] for i in await _items(hass, "todo.tududi_me_home")] == ["task2"]


async def test_create_item(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Adding an item creates a task in the list's project."""
    aioclient_mock.post(f"{API}/task", json={"uid": "new"}, status=201)
    await hass.services.async_call(
        TODO_DOMAIN,
        "add_item",
        {
            "entity_id": "todo.tududi_me_home",
            "item": "Paint wall",
            "due_date": "2026-11-01",
            "description": "white",
        },
        blocking=True,
    )
    [call] = calls(aioclient_mock, "post", "/task")
    assert call[2] == {
        "name": "Paint wall",
        "project_uid": "proj1",
        "note": "white",
        "due_date": "2026-11-01",
    }


async def test_complete_and_reopen_item(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Checking an item marks it done; unchecking reopens it."""
    aioclient_mock.patch(f"{API}/task/task1", json={})
    aioclient_mock.patch(f"{API}/task/task3", json={})
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"entity_id": "todo.tududi_me_tasks", "item": "task1", "status": "completed"},
        blocking=True,
    )
    [call] = calls(aioclient_mock, "patch", "/task/task1")
    assert call[2] == {
        "name": "Loose task",
        "note": "a note",
        "due_date": "2026-10-20",
        "status": "done",
    }

    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {
            "entity_id": "todo.tududi_me_tasks",
            "item": "task3",
            "status": "needs_action",
        },
        blocking=True,
    )
    [call] = calls(aioclient_mock, "patch", "/task/task3")
    assert call[2]["status"] == "not_started"


async def test_rename_keeps_status(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Renaming an in-progress task does not reset its status."""
    aioclient_mock.patch(f"{API}/task/task2", json={})
    await hass.services.async_call(
        TODO_DOMAIN,
        "update_item",
        {"entity_id": "todo.tududi_me_home", "item": "task2", "rename": "Fix the sink"},
        blocking=True,
    )
    [call] = calls(aioclient_mock, "patch", "/task/task2")
    assert call[2] == {"name": "Fix the sink", "note": "", "due_date": None}


async def test_delete_items(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Removing items deletes the tasks."""
    aioclient_mock.delete(f"{API}/task/task1", json={"message": "ok"})
    aioclient_mock.delete(f"{API}/task/task3", json={"message": "ok"})
    await hass.services.async_call(
        TODO_DOMAIN,
        "remove_item",
        {"entity_id": "todo.tududi_me_tasks", "item": ["task1", "task3"]},
        blocking=True,
    )
    assert len(calls(aioclient_mock, "delete", "/task/task1")) == 1
    assert len(calls(aioclient_mock, "delete", "/task/task3")) == 1


async def test_project_lists_follow_projects(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """New projects add a list; removed projects drop theirs."""
    registry = er.async_get(hass)
    assert registry.async_get("todo.tududi_me_home")

    aioclient_mock.clear_requests()
    mock_api(
        aioclient_mock,
        projects=[{"id": 3, "uid": "proj3", "name": "Garden", "status": "planned"}],
    )
    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("todo.tududi_me_garden") is not None
    assert registry.async_get("todo.tududi_me_home") is None
    assert hass.states.get("todo.tududi_me_home") is None
