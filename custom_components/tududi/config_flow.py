"""Config flow for Tududi."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import (
    TududiAuthError,
    TududiClient,
    TududiConnectionError,
    normalize_url,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL
from .coordinator import TududiConfigEntry

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _validate(hass, url: str, api_key: str, verify_ssl: bool) -> dict[str, Any]:
    """Return the profile, raising on connection or auth problems."""
    client = TududiClient(
        async_get_clientsession(hass, verify_ssl=verify_ssl), url, api_key, verify_ssl
    )
    return await client.get_profile() or {}


def _errors_for(err: Exception) -> dict[str, str]:
    if isinstance(err, TududiAuthError):
        return {"base": "invalid_auth"}
    if isinstance(err, TududiConnectionError):
        return {"base": "cannot_connect"}
    _LOGGER.exception("Unexpected error validating tududi credentials")
    return {"base": "unknown"}


class TududiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tududi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the server URL and API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            try:
                profile = await _validate(
                    self.hass,
                    url,
                    user_input[CONF_API_KEY],
                    user_input[CONF_VERIFY_SSL],
                )
            except Exception as err:
                errors = _errors_for(err)
            else:
                user_id = (
                    profile.get("uid") or profile.get("email") or profile.get("id")
                )
                await self.async_set_unique_id(f"{url}|{user_id}")
                self._abort_if_unique_id_configured()
                title = profile.get("name") or profile.get("email") or url
                return self.async_create_entry(
                    title=f"Tududi ({title})" if title != url else "Tududi",
                    data={**user_input, CONF_URL: url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_URL): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                        vol.Required(CONF_API_KEY): _PASSWORD,
                        vol.Required(CONF_VERIFY_SSL, default=True): bool,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the API key was rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _validate(
                    self.hass,
                    entry.data[CONF_URL],
                    user_input[CONF_API_KEY],
                    entry.data.get(CONF_VERIFY_SSL, True),
                )
            except Exception as err:
                errors = _errors_for(err)
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): _PASSWORD}),
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TududiConfigEntry) -> TududiOptionsFlow:
        """Return the options flow."""
        return TududiOptionsFlow()


class TududiOptionsFlow(OptionsFlowWithReload):
    """Set the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=3600,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
