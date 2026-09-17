# Learning task target contract

`GET /learning/today`, `GET /learning/tasks/{task_id}`, and task command responses expose the same navigation target in `task.link_payload`.

Required server-derived fields:

- `plan_id`: owner-scoped review plan identifier
- `day_id`: owner-scoped plan day identifier
- `task_id`: owner-scoped task identifier

Optional business fields:

- `category` and `question_id` for practice
- `mode` and `focus` for interviews
- material-specific keys for review content

Clients map task types as follows:

- `interview` opens the interview workspace and passes `task_id` as `plan_task_id`.
- `practice` opens practice and applies `category` or `question_id` when present.
- `review`, `material`, and `checkin` open review and select the matching plan, day, and task.

The server overwrites the three required identifiers from the authenticated owner-scoped database record. Generated plan metadata cannot override them. Clicking a card only opens content; status changes are separate commands.
