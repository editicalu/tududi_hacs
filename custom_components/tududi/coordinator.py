"""Data update coordinator for Tududi."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TududiApiError, TududiAuthError, TududiClient, TududiError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type TududiConfigEntry = ConfigEntry[TududiCoordinator]


@dataclass
class TududiData:
    """Snapshot of the tududi state polled by the coordinator."""

    tasks: list[dict[str, Any]] = field(default_factory=list)
    completed_today: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    habits: list[dict[str, Any]] = field(default_factory=list)
    inbox: list[dict[str, Any]] = field(default_factory=list)

    def project_by_uid(self, uid: str) -> dict[str, Any] | None:
        """Return the project with this uid, if known."""
        return next((p for p in self.projects if p.get("uid") == uid), None)

    def habit_by_uid(self, uid: str) -> dict[str, Any] | None:
        """Return the habit with this uid, if known."""
        return next((h for h in self.habits if h.get("uid") == uid), None)


class TududiCoordinator(DataUpdateCoordinator[TududiData]):
    """Polls tududi for tasks, projects, metrics, habits and inbox items."""

    config_entry: TududiConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: TududiConfigEntry, client: TududiClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> TududiData:
        """Fetch everything the entities need."""
        try:
            tasks, projects, metrics, habits, inbox = await asyncio.gather(
                self.client.get_tasks(type="all", status="active"),
                self.client.get_projects(),
                self.client.get_task_metrics(),
                self._optional(self.client.get_habits()),
                self._optional(self.client.get_inbox()),
            )
        except TududiAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TududiError as err:
            raise UpdateFailed(str(err)) from err

        metrics = metrics or {}
        return TududiData(
            tasks=tasks,
            completed_today=metrics.get("tasks_completed_today") or [],
            projects=projects,
            metrics=metrics,
            habits=habits or [],
            inbox=inbox or [],
        )

    @staticmethod
    async def _optional(coro: Any) -> Any:
        """Return None instead of failing for endpoints a server may lack."""
        try:
            return await coro
        except TududiApiError as err:
            _LOGGER.debug("Optional tududi endpoint failed: %s", err)
            return None
