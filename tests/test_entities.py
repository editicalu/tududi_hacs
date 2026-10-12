"""Tests for Tududi sensors and buttons."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.tududi.const import DEFAULT_SCAN_INTERVAL

from .conftest import API, calls


async def test_metric_sensors(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Metric sensors expose counts and the tasks behind them."""
    assert hass.states.get("sensor.tududi_me_open_tasks").state == "2"
    assert hass.states.get("sensor.tududi_me_tasks_in_progress").state == "1"
    overdue = hass.states.get("sensor.tududi_me_overdue_tasks")
    assert overdue.state == "1"
    assert overdue.attributes["tasks"][0]["uid"] == "task1"
    assert hass.states.get("sensor.tududi_me_tasks_completed_today").state == "1"
    assert hass.states.get("sensor.tududi_me_inbox_items").state == "1"


async def test_habit_sensor(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Each habit has a streak sensor."""
    state = hass.states.get("sensor.tududi_me_meditate_streak")
    assert state.state == "4"
    assert state.attributes["best_streak"] == 9
    assert state.attributes["unit_of_measurement"] == "days"


async def test_habit_button(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
) -> None:
    """Pressing the habit button logs a completion."""
    aioclient_mock.post(f"{API}/habits/habit1/complete", json={"habit": {}})
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.tududi_me_complete_meditate"},
        blocking=True,
    )
    assert len(calls(aioclient_mock, "post", "/habits/habit1/complete")) == 1


async def test_unload(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)


async def test_polling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The coordinator polls on the configured interval."""
    before = len(calls(aioclient_mock, "get", "/tasks"))
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls(aioclient_mock, "get", "/tasks")) == before + 1
