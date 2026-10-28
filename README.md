# PCI project starter kit

Reusable workspace for Portcities Indonesia (PCI) Odoo engagements.

Copy this folder per client/engagement; fill config; open the code workspace.

## Quick start

```bash
cp -a ~/Project/pci/template ~/Project/pci/<slug>
cd ~/Project/pci/<slug>
git init
./scripts/init-project.sh
```

Or set paths by hand:

1. Edit [`.agents/config.yml`](.agents/config.yml) — slug, name, `module_prefix`, `odoo_version`, `tracking.mode`, Portcities ids/stages, Drive folder, channel filters.
2. `cp .agents/state.example.yml .agents/state.yml` (intake cursors; gitignored).
3. Export local Odoo env vars (or run `init-project.sh`, which writes absolute paths into the workspace):

   ```bash
   export ODOO_SRC=~/Project/odoo/odoo/odoo19
   export ODOO_EE=~/Project/odoo/odoo-enterprise
   export ODOO_PYTHON=~/.pyenv/versions/odoo19/bin/python
   export ODOO_DB_USER=$USER
   ```

   Then set `REPLACE_DB` in [`project.code-workspace`](project.code-workspace).

4. Update [`wiki/overview.md`](wiki/overview.md) (Now / blocked / next + Drive link) and set `updated:` dates.
5. After `project_id` is set:  
   `python3 .agents/skills/odoo-task-activity/scripts/create_task.py stages`  
   then paste the live stage ids into `portcities.stages`.
6. Open `project.code-workspace` in Cursor.

See [`.agents/config.example.yml`](.agents/config.example.yml) for commented knobs.
`create_task.py` needs PyYAML (`pip install pyyaml`).

## Layout

| Path | Purpose |
|------|---------|
| `.agents/` | Config, skills, rules; `state.yml` for intake cursors |
| `wiki/` | Short notes + Drive links + diagrams |
| `raw/` | Human-only drops (contents gitignored) |
| `modules/` | Custom Odoo addons |
| `scripts/init-project.sh` | Fill REPLACE + local Odoo paths |
| `project.code-workspace` | Local Odoo launch (db/port/paths) |

## Tracking

`tracking.mode` in config:

- `odoo` — Portcities tasks are canonical
- `notes` — `wiki/notes/` is canonical
- `hybrid` — both (agents must say which they used)

## Channels

Intake + draft only. `last_intake` in `.agents/state.yml` stores per-channel cursors so pulls are incremental. WhatsApp is always paste-in.

Task writes: `.agents/skills/odoo-task-activity/scripts/create_task.py` (Cloudflare tunnel + API key from user MCP config; project/stages from this repo’s `config.yml`).

## Agent entry

[`AGENTS.md`](AGENTS.md) is the operating schema.
