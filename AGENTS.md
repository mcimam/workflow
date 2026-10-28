# PCI project workspace — agent schema

Portcities Indonesia (PCI) project starter. Read this at session start, then
[`.agents/config.yml`](.agents/config.yml) and [`wiki/overview.md`](wiki/overview.md)
(Now / blocked / next).

State the active `tracking.mode` before any status or intake work.

---

## Layout

```
.
├── .agents/
│   ├── config.yml          # knobs — tracking, Portcities, Drive, channels
│   ├── config.example.yml
│   ├── state.yml           # gitignored intake cursors (from state.example.yml)
│   ├── state.example.yml
│   ├── skills/             # grilling, channel-intake, odoo-task-activity
│   └── rules/
├── .cursor/skills → ../.agents/skills
├── .cursor/rules  → ../.agents/rules
├── .claude/skills → ../.agents/skills
├── .claude/rules  → ../.agents/rules
├── wiki/                   # short local notes; Drive for real documents
│   ├── overview.md         # status + Drive + pointers
│   ├── diagrams/           # mermaid locally, or stubs linking Drive/draw.io
│   ├── notes/ · tasks/
├── raw/                    # human drops only (gitignored contents)
├── modules/                # custom Odoo addons (prefix from config)
├── scripts/init-project.sh # fill REPLACE + local Odoo paths
├── project.code-workspace  # local Odoo run settings live HERE only
└── AGENTS.md
```

---

## Tracking modes

From `tracking.mode` in config (`REPLACE` until you pick one):

| Mode | Canonical status | Wiki role |
|------|------------------|-----------|
| `odoo` | Portcities `project.task` | digests, decisions, Drive links |
| `notes` | `wiki/notes/` | full tracker |
| `hybrid` | Odoo for formal stage; wiki for context | always say which you treated as authoritative |

When `odoo` or `hybrid`, `portcities.project_id` must be set.

---

## Wiki (simple + Drive-first)

- **Never duplicate Google Drive files** into `wiki/` or `raw/`. Link them.
- Project Drive root: `gdrive.folder_url` / `gdrive.folder_id` — surface on `wiki/overview.md`.
- Per-file/folder refs: markdown link and/or frontmatter `gdrive: <url|id>`.
- Prefer plain markdown links in wiki pages (GitHub/Cursor-friendly). Optional `[[wikilinks]]` are fine if you also keep the path readable.
- Diagrams: Drive/draw.io → link from `wiki/diagrams/`; local mermaid OK as `.md` there.
- Local wiki: short status, decisions, intake digests, indexes — not SOWs/decks/spreadsheets.
- Minimal frontmatter: `title`, `type`, `updated`, optional `gdrive`.
- Task digests: `wiki/tasks/T{id}-{slug}.md` (e.g. `T12345-delivery-docket.md`).
- Note pages: `wiki/notes/NOTE-{nnn}-{slug}.md`.
- Human owns `raw/`. Agents write in `wiki/` (and drafts in chat).

---

## Channels (intake + draft only)

On request, use skill **channel-intake**:

- Read `last_intake.*` in `.agents/state.yml` before pulling; only fetch newer than the cursor.
- After a successful pull, update `last_intake.<channel>.at` and `.cursor` in **state.yml** (not config.yml).
- Pull: Portcities tasks, Gmail, Google Chat.
- Draft replies / task notes / stage moves — **do not send or write** without confirmation.
- WhatsApp: always manual paste → `raw/` or chat.

---

## Skills

| Skill | When |
|-------|------|
| `grilling` | before ambiguous / high-cost work; grill me / tanya saya dulu |
| `channel-intake` | sync or digest mail/chat/Odoo; draft outbound |
| `odoo-task-activity` | create/update Portcities tasks via `scripts/create_task.py` |

---

## Modules

Custom addons live in `modules/`. Technical names use `project.module_prefix` from config
(e.g. `pci_fwa_pos_…`). `project.odoo_version` is the local target (e.g. `19.0`).
Launch Odoo only via `project.code-workspace` (db, port, addons paths) — those settings
are not duplicated in `config.yml`. Prefer `scripts/init-project.sh` after copy.
