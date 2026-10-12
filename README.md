# Tududi for Home Assistant

A custom integration that connects Home Assistant to a self-hosted
[tududi](https://github.com/chrisvel/tududi) server through its REST API
(`/api/v1`).

- **To-do lists**: a *Tasks* list for tasks without a project, plus one list per
  open project. Add, edit, check off and delete tasks from the HA to-do card or
  with the `todo.*` actions. Project lists appear and disappear as projects change.
- **Sensors**: open, in progress, due today, overdue, today plan, suggested,
  completed today, pending over a month, and inbox items. Each metric sensor
  lists its tasks in the `tasks` attribute. Every habit also gets a streak sensor
  (best streak, strength and progress are attributes).
- **Buttons**: one *Complete &lt;habit&gt;* button per habit.
- **Actions (services)**: create, update, delete and read nearly everything in
  tududi: tasks, projects, areas, notes, tags, inbox, habits, goals, people,
  saved views and search.

## Installation

1. HACS → ⋮ → *Custom repositories* → add this repository as an *Integration*.
2. Install **Tududi** and restart Home Assistant.
3. In tududi, create an API key under **Profile → API keys**.
4. In HA, go to **Settings → Devices & services → Add integration → Tududi** and
   enter your server URL (for example `https://tududi.example.com`) and the API key.

The polling interval defaults to 60 s and can be changed in the integration
options. If the API key is revoked, Home Assistant asks you to reauthenticate.

## Actions

All actions take an optional `config_entry_id`, which you only need when more
than one tududi server is configured. They also take an optional `extra` object
whose keys are merged into the request body, so API fields without a dedicated
action field still work.

Wherever you can reference a project, area or goal, you can use either its name
(case-insensitive) or its UID.

| Resource | Actions |
| --- | --- |
| Tasks | `create_task`, `update_task`, `complete_task`, `delete_task`, `skip_task_occurrence`, `get_task`, `get_tasks`, `get_subtasks`, `get_task_metrics` |
| Projects | `create_project`, `update_project`, `delete_project`, `get_project`, `get_projects` |
| Areas | `create_area`, `update_area`, `delete_area`, `get_areas` |
| Notes | `create_note`, `update_note`, `delete_note`, `get_note`, `get_notes` |
| Tags | `create_tag`, `update_tag`, `delete_tag`, `get_tags` |
| Inbox | `add_to_inbox`, `update_inbox_item`, `process_inbox_item`, `delete_inbox_item`, `get_inbox` |
| Habits | `create_habit`, `update_habit`, `delete_habit`, `complete_habit`, `skip_habit`, `archive_habit`, `unarchive_habit`, `delete_habit_completion`, `get_habits`, `get_habit_stats`, `get_habit_completions` |
| Goals | `create_goal`, `update_goal`, `delete_goal`, `get_goals` |
| People | `create_person`, `update_person`, `delete_person`, `get_people` |
| Views | `create_view`, `update_view`, `delete_view`, `get_views` |
| Search | `search` |

Create and update actions can optionally return the stored object, and `get_*`
and `search` always return data. Use `response_variable` to read it in scripts.

### Examples

Create a task and delete it later:

```yaml
- action: tududi.create_task
  data:
    name: Take out the trash
    project: Home
    due_date: "{{ now().date() }}"
    priority: high
    tags: [chores]
  response_variable: created
- delay: "01:00:00"
- action: tududi.delete_task
  data:
    uid: "{{ created.task.uid }}"
```

Create a recurring task that repeats every Monday and Thursday:

```yaml
action: tududi.create_task
data:
  name: Water the plants
  recurrence_type: weekly
  recurrence_weekdays: [1, 4]
```

Capture something to the inbox from a voice assistant:

```yaml
action: tududi.add_to_inbox
data:
  content: "{{ trigger.sentence }}"
  source: home_assistant
```

Read today's tasks:

```yaml
action: tududi.get_tasks
data:
  type: today
response_variable: today
```

## Development

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```
