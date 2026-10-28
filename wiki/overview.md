---
title: Overview
type: overview
updated: YYYY-MM-DD
---

# Overview

Fill after copying the template. Keep this page short.

## Now / blocked / next

- **Phase:** kickoff / build / UAT / live / maintenance
- **Now:** …
- **Blocked on:** …
- **Next:** …

## Project

- **Name:** (from `.agents/config.yml` → `project.name`)
- **Slug:** (from `project.slug`)
- **Module prefix:** (from `project.module_prefix`)
- **Odoo version:** (from `project.odoo_version`)
- **Tracking mode:** (from `tracking.mode`)
- **Local DB:** (from `project.code-workspace` launch config)

## Google Drive

Canonical shared docs (do **not** copy these files into this repo — link only):

- **Folder:** set `gdrive.folder_url` in `.agents/config.yml`, then paste the link here.

Draw.io / diagrams that live on Drive: link from `wiki/diagrams/` stubs. Local mermaid can live under `wiki/diagrams/` as `.md`.

## Portcities

- **Project:** set `portcities.project_id` / `project_url` in config when using `odoo` or `hybrid` tracking.
- **Stages:** fill `portcities.stages` via `create_task.py stages`.

## Pointers

- Catalog: [index.md](index.md)
- Log: [log.md](log.md)
- Notes: `wiki/notes/` (when `notes` or `hybrid`) — files like `NOTE-001-slug.md`
- Tasks: `wiki/tasks/` (when `odoo` or `hybrid`) — files like `T12345-slug.md`
- Diagrams: `wiki/diagrams/`
