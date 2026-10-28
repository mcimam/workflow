---
name: grilling
description: Interview the user one question at a time before doing the work, to surface business context they hold but did not write down — stakeholders, prior decisions, constraints, deadlines, what "done" means. Use this skill whenever the user says grill me, interrogate me, tanya saya dulu, stress-test this, or asks to be questioned before starting. Also reach for it unprompted before any task whose output would change materially depending on context that has not been stated yet — customer-facing deliverables, estimates, recommendations, plans, or anything where guessing wrong costs rework. Prefer grilling over assuming.
---

# Grilling

The user knows their business far better than any note captures. In practice that context
stays in their head and only surfaces after seeing a wrong answer. This skill front-loads
that discovery so it costs one round of questions instead of one round of rework.

## How to run it

**One question at a time.** Ask, wait for the answer, then ask the next. A batch of six
questions gets three answered badly. This is the single most important rule here.

**Always propose your own answer.** Never ask a bare open question. Give the question,
your recommended answer, and a one-line reason, so the user can reply "yes" and move on:

> Should we treat Portcities tasks as canonical for this engagement?
> **My recommendation:** yes if `tracking.mode` is `odoo` or `hybrid` and
> `portcities.project_id` is set — otherwise use `wiki/notes/`.
> Any stakeholder who expects a different board?

**Look facts up yourself.** If something is discoverable — in the repo, config, wiki,
filesystem, or earlier in this conversation — go find it instead of asking. What only the
user holds are *decisions*, *priorities*, and *business context*.

In this workspace, look before asking:

- `.agents/config.yml` (tracking mode, Portcities, Drive, channels)
- `.agents/state.yml` (last_intake cursors; copy from state.example.yml if missing)
- `wiki/overview.md` (Now / blocked / next)
- `AGENTS.md`
- `wiki/` (log, notes, tasks, diagrams)
- `modules/` (what the code actually does)
- `project.code-workspace` (local Odoo db/port/paths)
- `.agents/rules/`

Verify anything a rule claims before repeating it — rules go stale.

**Order by consequence.** Ask first whatever would change the output most.

**Know when to stop.** Typically three to seven questions. Stop as soon as remaining
uncertainty would not change the work, and say so.

## What to probe for

Pick whichever is load-bearing for the task:

- **Who this is for** — audience and who signs off
- **What was already decided or tried** — rejected options, promises already made
- **Non-technical constraints** — budget, scope, go-live, politics
- **Definition of done**
- **What happens if it is wrong** — cheap redo vs customer-facing
- **Vocabulary** — pin down in-house terms

## Closing

End with a short recap of decisions and assumptions; wait for confirmation before starting
work.

Durable facts: standing preference → `.agents/rules/`; project structure/rules →
`AGENTS.md` or `config.yml`; a decision or module fact → its `wiki/` page.

If the user says just go ahead, respect it — but state the assumptions you are running on.
