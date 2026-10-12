"""Fixtures for Tududi tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.tududi.const import DOMAIN

URL = "http://tududi.local:3002"
API = f"{URL}/api/v1"

PROFILE = {"uid": "user1", "email": "me@example.com", "name": "Me"}
PROJECTS = [
    {"id": 1, "uid": "proj1", "name": "Home", "status": "in_progress"},
    {"id": 2, "uid": "proj2", "name": "Old", "status": "done"},
]
TASKS = [
    {
        "id": 10,
        "uid": "task1",
        "name": "Loose task",
        "status": 0,
        "due_date": "2026-10-20",
        "note": "a note",
        "project_uid": None,
    },
    {
        "id": 11,
        "uid": "task2",
        "name": "Fix sink",
        "status": 1,
        "due_date": None,
        "note": None,
        "project_uid": "proj1",
    },
]
COMPLETED = [
    {"id": 12, "uid": "task3", "name": "Done today", "status": 2, "project_uid": None}
]
METRICS = {
    "total_open_tasks": 2,
    "tasks_pending_over_month": 0,
    "tasks_in_progress_count": 1,
    "tasks_due_today_count": 0,
    "today_plan_tasks_count": 0,
    "suggested_tasks_count": 0,
    "tasks_completed_today_count": 1,
    "weekly_completions": [],
    "tasks_in_progress": [TASKS[1]],
    "tasks_today_plan": [],
    "tasks_due_today": [],
    "tasks_overdue": [TASKS[0]],
    "suggested_tasks": [],
    "tasks_completed_today": COMPLETED,
}
HABITS = [
    {
        "id": 20,
        "uid": "habit1",
        "name": "Meditate",
        "habit_current_streak": 4,
        "habit_best_streak": 9,
        "habit_frequency_period": "daily",
    }
]
INBOX = [{"uid": "inbox1", "content": "Call mom"}]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable loading the custom integration."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a tududi config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Tududi (Me)",
        unique_id=f"{URL}|user1",
        data={CONF_URL: URL, CONF_API_KEY: "secret", CONF_VERIFY_SSL: True},
    )


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    *,
    projects: list[dict[str, Any]] | None = None,
    habits: list[dict[str, Any]] | None = None,
) -> None:
    """Register the read endpoints the coordinator polls."""
    aioclient_mock.get(f"{API}/profile", json=PROFILE)
    aioclient_mock.get(f"{API}/tasks", json={"tasks": TASKS})
    aioclient_mock.get(
        f"{API}/projects", json={"projects": PROJECTS if projects is None else projects}
    )
    aioclient_mock.get(f"{API}/tasks/metrics", json=METRICS)
    aioclient_mock.get(
        f"{API}/habits", json={"habits": HABITS if habits is None else habits}
    )
    aioclient_mock.get(f"{API}/inbox", json=INBOX)


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with mocked API responses."""
    mock_api(aioclient_mock)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


def calls(
    aioclient_mock: AiohttpClientMocker, method: str, path: str
) -> list[tuple[Any, ...]]:
    """Return the recorded calls for a method and API path."""
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == method.lower()
        and str(call[1]).split("?")[0] == f"{API}{path}"
    ]
