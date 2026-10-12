"""Async REST client for the tududi API."""

from __future__ import annotations

from json import loads as json_loads
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import API_PATH

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TududiError(Exception):
    """Base error for the tududi client."""


class TududiConnectionError(TududiError):
    """The tududi server could not be reached."""


class TududiAuthError(TududiError):
    """The API key was rejected."""


class TududiApiError(TududiError):
    """The tududi server returned an error response."""

    def __init__(self, status: int, message: str) -> None:
        """Store the HTTP status alongside the message."""
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.message = message


def normalize_url(url: str) -> str:
    """Strip whitespace, trailing slashes and an /api suffix from a base URL."""
    url = url.strip().rstrip("/")
    for suffix in (API_PATH, "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def _seg(value: str | int) -> str:
    """Quote a value for use as a single URL path segment."""
    return quote(str(value), safe="")


class TududiClient:
    """Thin wrapper around the tududi REST API (``/api/v1``)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base = normalize_url(url) + API_PATH
        self._api_key = api_key
        self._ssl = None if verify_ssl else False

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Send a request and return the decoded JSON body (or None)."""
        if params:
            params = {
                key: str(value).lower() if isinstance(value, bool) else value
                for key, value in params.items()
                if value is not None
            }
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                json=json,
                params=params,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                },
                ssl=self._ssl,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise TududiAuthError(await _error_message(resp))
                if resp.status >= 400:
                    raise TududiApiError(resp.status, await _error_message(resp))
                body = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TududiConnectionError(str(err) or type(err).__name__) from err
        if not body:
            return None
        try:
            return json_loads(body)
        except ValueError as err:
            raise TududiApiError(resp.status, "Response is not JSON") from err

    # Profile

    async def get_profile(self) -> dict[str, Any]:
        """Return the authenticated user's profile."""
        return await self.request("GET", "/profile")

    # Tasks

    async def get_tasks(self, **params: Any) -> list[dict[str, Any]]:
        """List tasks; ``type``, ``status``, ``project_uid`` etc. filter."""
        data = await self.request("GET", "/tasks", params=params)
        return data.get("tasks", []) if isinstance(data, dict) else data or []

    async def get_task(self, uid: str) -> dict[str, Any]:
        """Return one task."""
        return await self.request("GET", f"/task/{_seg(uid)}")

    async def get_subtasks(self, uid: str) -> list[dict[str, Any]]:
        """Return a task's subtasks."""
        return await self.request("GET", f"/task/{_seg(uid)}/subtasks")

    async def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a task."""
        return await self.request("POST", "/task", json=data)

    async def update_task(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update a task."""
        return await self.request("PATCH", f"/task/{_seg(uid)}", json=data)

    async def delete_task(self, uid: str) -> Any:
        """Delete a task."""
        return await self.request("DELETE", f"/task/{_seg(uid)}")

    async def skip_occurrence(self, uid: str) -> Any:
        """Skip the current occurrence of a recurring task."""
        return await self.request("POST", f"/task/{_seg(uid)}/skip-occurrence")

    async def get_task_metrics(self, **params: Any) -> dict[str, Any]:
        """Return dashboard task metrics."""
        return await self.request("GET", "/tasks/metrics", params=params)

    # Projects

    async def get_projects(self, **params: Any) -> list[dict[str, Any]]:
        """List projects."""
        data = await self.request("GET", "/projects", params=params)
        return data.get("projects", []) if isinstance(data, dict) else data or []

    async def get_project(self, uid: str) -> dict[str, Any]:
        """Return one project."""
        return await self.request("GET", f"/project/{_seg(uid)}")

    async def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a project."""
        return await self.request("POST", "/project", json=data)

    async def update_project(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update a project."""
        return await self.request("PATCH", f"/project/{_seg(uid)}", json=data)

    async def delete_project(self, uid: str) -> Any:
        """Delete a project."""
        return await self.request("DELETE", f"/project/{_seg(uid)}")

    # Areas

    async def get_areas(self, **params: Any) -> list[dict[str, Any]]:
        """List areas."""
        return await self.request("GET", "/areas", params=params)

    async def get_area(self, uid: str) -> dict[str, Any]:
        """Return one area."""
        return await self.request("GET", f"/areas/{_seg(uid)}")

    async def create_area(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an area."""
        return await self.request("POST", "/areas", json=data)

    async def update_area(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update an area."""
        return await self.request("PATCH", f"/areas/{_seg(uid)}", json=data)

    async def delete_area(self, uid: str) -> Any:
        """Delete an area."""
        return await self.request("DELETE", f"/areas/{_seg(uid)}")

    # Notes

    async def get_notes(self, **params: Any) -> list[dict[str, Any]]:
        """List notes."""
        return await self.request("GET", "/notes", params=params)

    async def get_note(self, uid: str) -> dict[str, Any]:
        """Return one note."""
        return await self.request("GET", f"/note/{_seg(uid)}")

    async def create_note(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a note."""
        return await self.request("POST", "/note", json=data)

    async def update_note(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update a note."""
        return await self.request("PATCH", f"/note/{_seg(uid)}", json=data)

    async def delete_note(self, uid: str) -> Any:
        """Delete a note."""
        return await self.request("DELETE", f"/note/{_seg(uid)}")

    # Tags

    async def get_tags(self, **params: Any) -> list[dict[str, Any]]:
        """List tags."""
        return await self.request("GET", "/tags", params=params)

    async def create_tag(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a tag."""
        return await self.request("POST", "/tag", json=data)

    async def update_tag(self, identifier: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a tag, identified by uid or name."""
        return await self.request("PATCH", f"/tag/{_seg(identifier)}", json=data)

    async def delete_tag(self, identifier: str) -> Any:
        """Delete a tag, identified by uid or name."""
        return await self.request("DELETE", f"/tag/{_seg(identifier)}")

    # Inbox

    async def get_inbox(self, **params: Any) -> list[dict[str, Any]]:
        """List open inbox items."""
        data = await self.request("GET", "/inbox", params=params)
        return data.get("items", []) if isinstance(data, dict) else data or []

    async def get_inbox_item(self, uid: str) -> dict[str, Any]:
        """Return one inbox item."""
        return await self.request("GET", f"/inbox/{_seg(uid)}")

    async def create_inbox_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add an item to the inbox."""
        return await self.request("POST", "/inbox", json=data)

    async def update_inbox_item(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an inbox item."""
        return await self.request("PATCH", f"/inbox/{_seg(uid)}", json=data)

    async def process_inbox_item(
        self, uid: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Mark an inbox item as processed."""
        return await self.request(
            "PATCH", f"/inbox/{_seg(uid)}/process", json=data or {}
        )

    async def delete_inbox_item(self, uid: str) -> Any:
        """Delete an inbox item."""
        return await self.request("DELETE", f"/inbox/{_seg(uid)}")

    # Habits

    async def get_habits(self, archived: bool = False) -> list[dict[str, Any]]:
        """List habits."""
        data = await self.request(
            "GET", "/habits", params={"archived": archived} if archived else None
        )
        return data.get("habits", []) if isinstance(data, dict) else data or []

    async def get_habit(self, uid: str) -> dict[str, Any]:
        """Return one habit."""
        return await self.request("GET", f"/habits/{_seg(uid)}")

    async def create_habit(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a habit."""
        return await self.request("POST", "/habits", json=data)

    async def update_habit(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a habit."""
        return await self.request("PUT", f"/habits/{_seg(uid)}", json=data)

    async def delete_habit(self, uid: str) -> Any:
        """Delete a habit."""
        return await self.request("DELETE", f"/habits/{_seg(uid)}")

    async def complete_habit(
        self, uid: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Log a habit completion (``completed_at``, ``value``, ``note``)."""
        return await self.request(
            "POST", f"/habits/{_seg(uid)}/complete", json=data or {}
        )

    async def skip_habit(
        self, uid: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Skip a habit day (``date``, ``note``)."""
        return await self.request("POST", f"/habits/{_seg(uid)}/skip", json=data or {})

    async def archive_habit(self, uid: str) -> dict[str, Any]:
        """Archive a habit."""
        return await self.request("POST", f"/habits/{_seg(uid)}/archive")

    async def unarchive_habit(self, uid: str) -> dict[str, Any]:
        """Unarchive a habit."""
        return await self.request("POST", f"/habits/{_seg(uid)}/unarchive")

    async def get_habit_stats(self, uid: str, **params: Any) -> dict[str, Any]:
        """Return habit statistics (``start_date``/``end_date`` optional)."""
        return await self.request("GET", f"/habits/{_seg(uid)}/stats", params=params)

    async def get_habit_completions(self, uid: str, **params: Any) -> Any:
        """Return habit completions (``start_date``/``end_date`` optional)."""
        return await self.request(
            "GET", f"/habits/{_seg(uid)}/completions", params=params
        )

    async def delete_habit_completion(self, uid: str, completion_id: str | int) -> Any:
        """Delete one habit completion."""
        return await self.request(
            "DELETE",
            f"/habits/{_seg(uid)}/completions/{_seg(completion_id)}",
        )

    # Goals

    async def get_goals(self, **params: Any) -> list[dict[str, Any]]:
        """List goals."""
        data = await self.request("GET", "/goals", params=params)
        return data.get("goals", []) if isinstance(data, dict) else data or []

    async def get_goal(self, uid: str) -> dict[str, Any]:
        """Return one goal."""
        return await self.request("GET", f"/goals/{_seg(uid)}")

    async def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a goal."""
        return await self.request("POST", "/goals", json=data)

    async def update_goal(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update a goal."""
        return await self.request("PATCH", f"/goals/{_seg(uid)}", json=data)

    async def delete_goal(self, uid: str) -> Any:
        """Delete a goal."""
        return await self.request("DELETE", f"/goals/{_seg(uid)}")

    # People

    async def get_people(self, **params: Any) -> list[dict[str, Any]]:
        """List people."""
        data = await self.request("GET", "/people", params=params)
        return data.get("people", []) if isinstance(data, dict) else data or []

    async def get_person(self, uid: str) -> dict[str, Any]:
        """Return one person."""
        return await self.request("GET", f"/people/{_seg(uid)}")

    async def create_person(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a person."""
        return await self.request("POST", "/people", json=data)

    async def update_person(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Partially update a person."""
        return await self.request("PATCH", f"/people/{_seg(uid)}", json=data)

    async def delete_person(self, uid: str) -> Any:
        """Delete a person."""
        return await self.request("DELETE", f"/people/{_seg(uid)}")

    # Views (saved searches)

    async def get_views(self, **params: Any) -> list[dict[str, Any]]:
        """List saved views."""
        return await self.request("GET", "/views", params=params)

    async def get_view(self, identifier: str) -> dict[str, Any]:
        """Return one saved view."""
        return await self.request("GET", f"/views/{_seg(identifier)}")

    async def create_view(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a saved view."""
        return await self.request("POST", "/views", json=data)

    async def update_view(
        self, identifier: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Partially update a saved view."""
        return await self.request("PATCH", f"/views/{_seg(identifier)}", json=data)

    async def delete_view(self, identifier: str) -> Any:
        """Delete a saved view."""
        return await self.request("DELETE", f"/views/{_seg(identifier)}")

    # Search

    async def search(self, **params: Any) -> Any:
        """Search tasks, projects, areas, notes and tags."""
        return await self.request("GET", "/search", params=params)


async def _error_message(resp: aiohttp.ClientResponse) -> str:
    """Extract a readable error message from an error response."""
    fallback = getattr(resp, "reason", None) or f"HTTP {resp.status}"
    try:
        body = json_loads(await resp.read())
    except (aiohttp.ClientError, ValueError):
        return fallback
    if not isinstance(body, dict):
        return fallback
    message = body.get("error") or body.get("message") or fallback
    if details := body.get("details"):
        message = f"{message} ({'; '.join(map(str, details))})"
    return str(message)
