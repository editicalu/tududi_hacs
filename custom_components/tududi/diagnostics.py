"""Diagnostics for Tududi."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import TududiConfigEntry

TO_REDACT = {CONF_API_KEY, "email", "phone"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TududiConfigEntry
) -> dict[str, Any]:
    """Return redacted entry data plus a summary of the polled state."""
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "counts": {
            key: len(value) if isinstance(value, list) else None
            for key, value in asdict(data).items()
        },
        "metrics": {k: v for k, v in data.metrics.items() if not isinstance(v, list)},
        "projects": [
            {"uid": p.get("uid"), "status": p.get("status")} for p in data.projects
        ],
    }
