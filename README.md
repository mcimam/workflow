# Software Development Scaffold

A reusable repository template for building software with an AI coding agent
(Claude Code, and any tool that reads `AGENTS.md`). Clone it, run `/kickoff`,
and start — the agent already knows how to run requirements, design,
development, testing, deployment, and maintenance at whatever level of rigor
the project actually needs.

## Why this exists

Every project needs the same six SDLC phases, but not at the same intensity. A
weekend proof of concept and a client production system should not need two
different toolsets — they need the same skills applied against a different bar.

That is the whole design: **the workflow lives in data, not in code.** A skill
never hardcodes "write a PRD" or "run a security scan" — it reads a gate from
the active **track**, and the track is a plain YAML file. Switch track, or add
your own, and every skill and command adapts without being touched.

```
requirement → design → development → testing → deployment → maintenance
     ↑ same six phases, always                    ↑ same skills, always
     ↓ gated differently per track ────────────────┘
        poc: fast, disposable, minimal gates
        production: full rigor, every gate enforced
```

## Quickstart

```bash
git clone <this repo> my-project && cd my-project
rm -rf .git && git init
claude
> /kickoff a tool that reconciles supplier invoices against POs
```

`/kickoff` interviews you, picks a track, and fills in `.agents/config.yml` and
`.agents/context/`. From there:

| Command | Phase | Does |
|---|---|---|
| `/status` | — | Where things stand right now |
| `/track` | — | Show or switch rigor; shows the gate diff first |
| `/debt` | — | Record, review, pay or accept technical debt |
| `/idea` | requirement | Grill a raw idea into a stated problem |
| `/design` | design | System design + whatever docs the track needs |
| `/build` | development | Implement, verifying each step |
| `/optimize` | development | End-of-iteration cleanup, behaviour-preserving |
| `/qa` | testing | Functional testing, with a verdict |
| `/secure` | testing | Security review by severity |
| `/deploy` | deployment | Build, configure, release (prod always asks first) |
| `/issue` | maintenance | Triage → reproduce → root-cause → fix → cover |

## Layout

```
.agents/            Canonical source of truth — see .agents/README.md
├── config.yml         The one knob file: track, phases, language, commands, autonomy
├── workflow/          The six phases, and the tracks that set how strictly each runs
├── rules/             Standing policy: engineering, code quality, testing, security, git, ops
├── context/           Facts about THIS project — filled by /kickoff
├── skills/            How to do each kind of work well
├── commands/          Slash-command entry points
├── templates/         PRD, FRD, TDD, ADR, test plan, runbook, PR, issue
└── work/              STATE.md (where things stand) and DEBT.md (the debt ledger)

.claude/            Symlinks into .agents/ — how Claude Code discovers skills/commands
docs/               Generated deliverables (PRD/FRD/TDD/ADR) — belongs to the project
AGENTS.md           Pointer for other agent tools (Codex, Cursor, …)
CLAUDE.md           Imports .agents/AGENTS.md for Claude Code
```

Nothing is duplicated: `.agents/` is edited, everything else points at it.

## The debt ledger

`.agents/work/DEBT.md` is what makes a `poc` build *promotable* to `production`
instead of just rewritable. Every deliberate shortcut is logged the moment it's
taken; everything the active track skips that `production` would require is
computed automatically from the gate diff. `/track poc production` reads both
and hands back an ordered backlog with a cost attached — see
[`.agents/README.md`](.agents/README.md#the-debt-ledger) for the full model.

## Full documentation

[`.agents/README.md`](.agents/README.md) — adapting the scaffold, customising
tracks, adding skills, the design principle behind the whole thing.
