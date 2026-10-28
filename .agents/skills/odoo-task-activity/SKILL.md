---
name: odoo-task-activity
description: Draft and file Portcities internal Odoo project tasks, log notes, activities, and stage moves via scripts/create_task.py. Use when the user asks to create a task, buat task, assign work, schedule an activity, post a log note, or move a stage. Always read portcities.project_id from .agents/config.yml — never hardcode a client project. Reads via portcities-odoo MCP; writes via create_task.py after user confirmation.
---

# Odoo tasks & activities (Portcities)

This skill records work on **portcities.net** (internal), not on the customer’s Odoo.

## Config first

From `.agents/config.yml`:

- `portcities.project_id` / `project_url` — required for `odoo` / `hybrid`
- `portcities.stages` — alias → id (fill with `create_task.py stages`)
- `portcities.default_assignees`, optional `milestone_id` / `partner_id`
- `project.odoo_version` — local target version (informational)

If `project_id` is null, stop and ask the user to set it. Never reuse another engagement’s
project id or stage map.

Requires **PyYAML** (`pip install pyyaml`) to read `config.yml`.

## Reads vs writes

**Reads / duplicate checks → `portcities-odoo` MCP** (read-only except timesheets).

**Writes → `scripts/create_task.py`** (same Cloudflare tunnel + API key as the MCP).
User runs the command after you assemble and confirm the payload; then you verify with a read.

```bash
S=.agents/skills/odoo-task-activity/scripts
# --project is optional when portcities.project_id is set; place it before the subcommand.
python3 $S/create_task.py check
python3 $S/create_task.py stages
python3 $S/create_task.py search "keyword"
python3 $S/create_task.py create --name "…" --description-file /tmp/d.html \
    --hours 4 --assignees 1179 [--stage todo] [--dry-run]
python3 $S/create_task.py note --task ID --body-file /tmp/n.html [--stage uat]
python3 $S/create_task.py stage --task ID --stage "in progress"
python3 $S/create_task.py activity --task ID --summary "…" --type "To-Do" --due YYYY-MM-DD
python3 $S/create_task.py attach --task ID --file /path/to/file [--name display-name]
```

`--dry-run` prints the payload without writing and without needing a live Odoo session
for `create` / `activity`. Prefer it before the first real write on a new engagement.

Flow: assemble → confirm once → user runs script → you read back. Never claim a write
without verification.

## Field mapping

| User says | Field | Notes |
|-----------|-------|-------|
| assign / tag person | `user_ids` | `portcities.default_assignees` if unset |
| estimate | `allocated_hours` | required on create |
| due / deadline | `date_deadline` | on the task |
| remind me | `mail.activity` | not the same as deadline |
| priority | `priority` | verify levels on this project |
| put in Todo / QC / … | `stage_id` | aliases from `portcities.stages` |

`description` / note body: **HTML**, not markdown.

## Creating a task

1. Duplicate check (`search` or MCP `odoo_search_read`).
2. Draft name + HTML body + assignees + stage.
3. Confirm once.
4. `create_task.py create …` then read back id + URL.

## Notes and stages

- Prefer Log note (`mail.mt_note`) unless the user asks to notify followers.
- Pair stage moves with a note for QC-style feedback (`note --stage …`).
- Script refuses tasks outside `portcities.project_id` (or `--project`).

## Timesheets

`odoo_create_timesheet_line` on the MCP is enough — still confirm date/hours/task first.

## Drive

Evidence on Drive stays as wiki links. Do not attach Drive binaries into git unless asked.
Use `attach` only for files the user explicitly wants on the Portcities task.
