"""Shared entity helpers for Tududi."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import normalize_url
from .const import DOMAIN
from .coordinator import TududiConfigEntry, TududiCoordinator


class TududiEntity(CoordinatorEntity[TududiCoordinator]):
    """Base entity attached to the tududi service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TududiCoordinator) -> None:
        """Attach the entity to the per-entry device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="tududi",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=normalize_url(entry.data["url"]),
        )


def async_add_dynamic_entities[T: Entity](
    entry: TududiConfigEntry,
    coordinator: TududiCoordinator,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    keys: Callable[[], Iterable[str]],
    factory: Callable[[str], Iterable[T]],
    unique_id: Callable[[str], Iterable[str]],
) -> None:
    """Add entities for keys as they appear and remove them once gone.

    ``keys`` yields the current object uids (projects, habits, ...),
    ``factory`` builds the entities for one uid and ``unique_id`` lists the
    unique ids those entities use, so stale ones can be dropped from the
    entity registry.
    """
    known: set[str] = set()

    @callback
    def _sync() -> None:
        current = set(keys())
        if new := current - known:
            async_add_entities(e for key in sorted(new) for e in factory(key))
        if gone := known - current:
            registry = er.async_get(coordinator.hass)
            for key in gone:
                for uid in unique_id(key):
                    if entity_id := registry.async_get_entity_id(platform, DOMAIN, uid):
                        registry.async_remove(entity_id)
        known.clear()
        known.update(current)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))
