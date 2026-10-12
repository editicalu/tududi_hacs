"""Buttons that log tududi habit completions."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import TududiError
from .const import DOMAIN
from .coordinator import TududiConfigEntry, TududiCoordinator
from .entity import TududiEntity, async_add_dynamic_entities

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TududiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one completion button per active habit."""
    coordinator = entry.runtime_data
    async_add_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        "button",
        lambda: [h["uid"] for h in coordinator.data.habits if h.get("uid")],
        lambda uid: [TududiHabitButton(coordinator, uid)],
        lambda uid: [f"{entry.entry_id}_habit_{uid}_complete"],
    )


class TududiHabitButton(TududiEntity, ButtonEntity):
    """Press to log a completion of a habit."""

    _attr_translation_key = "complete_habit"

    def __init__(self, coordinator: TududiCoordinator, habit_uid: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._habit_uid = habit_uid
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_habit_{habit_uid}_complete"
        )

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Fill the habit name into the entity name."""
        habit = self.coordinator.data.habit_by_uid(self._habit_uid)
        return {
            "habit": habit.get("name", self._habit_uid) if habit else self._habit_uid
        }

    @property
    def available(self) -> bool:
        """Unavailable once the habit disappears."""
        return (
            super().available
            and self.coordinator.data.habit_by_uid(self._habit_uid) is not None
        )

    async def async_press(self) -> None:
        """Log a completion now."""
        try:
            await self.coordinator.client.complete_habit(self._habit_uid)
        except TududiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()
