---
name: channel-intake
description: Pull project signal from Portcities Odoo, Gmail, and Google Chat into short wiki digests, and draft outbound replies or task notes for user approval. Use when the user asks to sync, catch up, intake, digest mail/chat/tasks, or check what changed across channels. WhatsApp is always manual paste — never automate. Do not send email, post to Chat, or write Odoo task state without explicit confirmation. Always honour last_intake cursors in .agents/state.yml.
---

# Channel intake (draft-only)

v1 is **intake + draft**. No silent outbound. No cron. On request only.

## Before you start

1. Read `.agents/config.yml` — note `tracking.mode`, `portcities.*`, `gdrive.*`, `channels.*`.
2. Read `.agents/state.yml` — note **`last_intake.*`**. If missing, copy from `state.example.yml`.
3. Say which tracking mode you are using.
4. Prefer MCP tools that exist in this session (Portcities, Gmail, GChat, Drive). If a
   server is missing or needs auth, say so; do not invent data.

## Incremental pulls (`last_intake`)

Cursors live in **`.agents/state.yml`** (gitignored), not in `config.yml`:

```yaml
last_intake:
  odoo:  { at: ISO-datetime|null, cursor: string|null }
  gmail: { at: …, cursor: … }
  gchat: { at: …, cursor: … }
```

**Before pull:** if `cursor` / `at` is set, only fetch newer items (e.g. Odoo
`write_date >`, Gmail `after:` / newer than message id, GChat messages after that time).
If both are null, do a bounded first pull (recent N / last few days) and say so.

**After a successful pull:** update that channel’s `at` (now, ISO) and `cursor` (newest
id / write_date you processed) in `.agents/state.yml`. Preserve other keys. Do not
rewrite `config.yml` for cursors. Do not advance the cursor if the pull failed.

## Sources

| Channel | How | Config |
|---------|-----|--------|
| Portcities Odoo | `portcities-odoo` MCP | `portcities.project_id` + `last_intake.odoo` |
| Gmail | Gmail MCP | `channels.gmail_query` + `last_intake.gmail` |
| Google Chat | GChat MCP | `channels.gchat_space` + `last_intake.gchat` |
| WhatsApp | User pastes / `raw/` | `channels.whatsapp: manual` |
| Google Drive | Link only | `gdrive.folder_url` / `folder_id` |

## What to write locally

- Short digests under `wiki/tasks/` or `wiki/notes/`, matching `tracking.mode`.
  - Tasks: `wiki/tasks/T{id}-{slug}.md`
  - Notes: `wiki/notes/NOTE-{nnn}-{slug}.md`
- Append a one-liner to `wiki/log.md` when the intake matters.
- Update `wiki/index.md` if you add a page (markdown links preferred).
- Drive artifacts: **link only** (`gdrive:` frontmatter / markdown URL).

## Outbound drafts

Draft under **Draft outbound** or in chat. **Stop** for approval. Gmail: prefer MCP
`create_draft` (still not a send) when available. Writes to Portcities go through
`odoo-task-activity` / `create_task.py` after confirmation. Never claim a send without
a read-back.

## WhatsApp

User pastes or drops under `raw/` (contents are gitignored). You may file a short
`wiki/notes/` page. Do not scrape WhatsApp.

## Done looks like

- Digests filed (or “nothing new since `<cursor>`”)
- `last_intake` updated in `.agents/state.yml` for channels you successfully pulled
- Drafts labeled as drafts; tracking mode stated
