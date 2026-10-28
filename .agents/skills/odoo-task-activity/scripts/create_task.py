#!/usr/bin/env python3
"""Create project.task / mail.activity records in the Portcities internal Odoo.

portcities.net sits behind a Cloudflare managed challenge, so plain XML-RPC gets a
403. This script reuses the same tunnel the `portcities-odoo` MCP server uses: it
injects the captured `cf_clearance` cookie and User-Agent, and authenticates with the
API key. Credentials are read from the MCP config, never hardcoded, so a key rotation
only has to be applied in one place.

Project defaults (project_id, stages, assignees, …) come from the engagement's
`.agents/config.yml` — never from another client's hardcoded ids.

Config sources (in order):
  1. <project>/.agents/config.yml -> portcities.*
  2. ~/.cursor/mcp.json -> mcpServers."portcities-odoo".env
  3. $CLAUDE_CONFIG_DIR/.claude.json -> mcpServers."portcities-odoo".env (legacy)
  4. ~/.claude-profiles/pc/.claude.json -> mcpServers."portcities-odoo".env (legacy)
  5. environment variables of the same names (always win for MCP creds)

Needed: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_API_KEY (or ODOO_PASSWORD), CF_SESSION_FILE.
Also: portcities.project_id in .agents/config.yml (or --project).

Usage
-----
  create_task.py check
  create_task.py search "delivery docket" [--project ID] [--limit 20]
  create_task.py types
  create_task.py stages
  create_task.py create --name "[area] — symptom" \
      --description-file /tmp/desc.html [--description "<p>…</p>"] \
      [--assignees 1179,1299] [--hours 4] [--priority 2] [--stage todo] \
      [--milestone ID] [--partner ID] [--deadline 2026-08-20] \
      [--parent ID] [--dedupe "term1,term2"] [--force] [--dry-run]
  create_task.py activity --task ID --summary "…" --type "To-Do" --due YYYY-MM-DD
  create_task.py note --task ID --body-file /tmp/feedback.html [--stage UAT]
  create_task.py attach --task ID --file /path/to/file [--name display-name]
  create_task.py stage --task ID --stage "in progress"

Exit codes: 0 ok · 1 usage/config error · 2 Cloudflare blocked · 3 auth failed
· 4 duplicate found (use --force to override)

Requires: PyYAML (`pip install pyyaml`) to read .agents/config.yml.
"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import xmlrpc.client

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
PROJECT_CONFIG_PATH = os.path.join(PROJECT_ROOT, ".agents", "config.yml")

DEFAULT_TASK_URL = "https://portcities.net/odoo/action-786/{project}/tasks/{task}"

# Filled by load_project_config(); empty until then.
DEFAULT_PROJECT = None
DEFAULT_MILESTONE = None
DEFAULT_PARTNER = None
DEFAULT_ASSIGNEES = []
STAGES = {}       # id -> label
STAGE_ALIASES = {}  # alias -> id
TASK_URL_TEMPLATE = DEFAULT_TASK_URL


def task_url(project, task):
    return TASK_URL_TEMPLATE.format(project=project, task=task)


def stage_label(stage_id):
    """Human label for a stage id; falls back to the id when not in config."""
    return STAGES.get(stage_id, str(stage_id))


def load_project_config(path=PROJECT_CONFIG_PATH):
    """Read portcities.* from the engagement config.yml (requires PyYAML)."""
    global DEFAULT_PROJECT, DEFAULT_MILESTONE, DEFAULT_PARTNER, DEFAULT_ASSIGNEES
    global STAGES, STAGE_ALIASES, TASK_URL_TEMPLATE

    if not os.path.exists(path):
        sys.exit(
            f"config error: missing {path}\n"
            "Copy the PCI template and set portcities.project_id (and stages)."
        )
    try:
        import yaml
    except ImportError:
        sys.exit("config error: PyYAML is required to read .agents/config.yml "
                 "(pip install pyyaml)")

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    pc = data.get("portcities") or {}
    project_id = pc.get("project_id")
    if project_id and project_id not in ("REPLACE", "null"):
        DEFAULT_PROJECT = int(project_id)
    else:
        DEFAULT_PROJECT = None
    DEFAULT_MILESTONE = int(pc["milestone_id"]) if pc.get("milestone_id") else None
    DEFAULT_PARTNER = int(pc["partner_id"]) if pc.get("partner_id") else None
    assignees = pc.get("default_assignees") or []
    DEFAULT_ASSIGNEES = [int(a) for a in assignees]

    template = pc.get("task_url_template")
    if not template and pc.get("project_url") and DEFAULT_PROJECT:
        # Derive from project_url like …/action-786/1234 → …/action-786/{project}/tasks/{task}
        base = str(pc["project_url"]).rstrip("/")
        if base.endswith(f"/{DEFAULT_PROJECT}"):
            base = base[: -len(f"/{DEFAULT_PROJECT}")]
        template = f"{base}/{{project}}/tasks/{{task}}"
    TASK_URL_TEMPLATE = template or DEFAULT_TASK_URL

    # stages: { alias_or_name: id }  e.g. backlog: 18, todo: 19
    raw_stages = pc.get("stages") or {}
    STAGES = {}
    STAGE_ALIASES = {}
    for alias, stage_id in raw_stages.items():
        stage_id = int(stage_id)
        label = str(alias)
        STAGES[stage_id] = label
        key = label.lower().lstrip("0123456789. ").strip()
        STAGE_ALIASES[key] = stage_id
        STAGE_ALIASES[label.lower()] = stage_id
        # common synonyms
        if key in ("in progress", "inprogress"):
            STAGE_ALIASES["progress"] = stage_id
            STAGE_ALIASES["inprogress"] = stage_id
        if key == "cancelled":
            STAGE_ALIASES["canceled"] = stage_id

    return {
        "project_id": DEFAULT_PROJECT,
        "milestone_id": DEFAULT_MILESTONE,
        "partner_id": DEFAULT_PARTNER,
        "default_assignees": DEFAULT_ASSIGNEES,
        "stages": STAGES,
        "config_path": path,
        "task_url_template": TASK_URL_TEMPLATE,
    }


# --------------------------------------------------------------------------- config

PC_MCP_DIR = os.path.expanduser(
    "~/.claude-profiles/pc/mcp-servers/portcities-odoo"
)
CURSOR_MCP_PATH = os.path.expanduser("~/.cursor/mcp.json")


def _mcp_config_candidates():
    """Paths that may hold mcpServers.portcities-odoo.env (Cursor first)."""
    paths = [CURSOR_MCP_PATH]
    claude_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    paths.append(os.path.join(claude_dir, ".claude.json"))
    paths.append(os.path.expanduser("~/.claude-profiles/pc/.claude.json"))
    # Dedupe while preserving order
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def load_config():
    """Pull the portcities-odoo MCP env from Cursor (then Claude fallbacks); env vars win."""
    cfg = {}
    used_path = None
    for path in _mcp_config_candidates():
        try:
            with open(path) as fh:
                data = json.load(fh)
            env = (
                data.get("mcpServers", {}).get("portcities-odoo", {}).get("env", {})
                or {}
            )
            if env:
                cfg = dict(env)
                used_path = path
                break
        except FileNotFoundError:
            continue
        except (json.JSONDecodeError, OSError) as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)

    for key in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY",
                "ODOO_PASSWORD", "CF_SESSION_FILE"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]

    url = (cfg.get("ODOO_URL") or "").rstrip("/")
    credential = cfg.get("ODOO_API_KEY") or cfg.get("ODOO_PASSWORD") or ""
    missing = [
        name for name, val in (
            ("ODOO_URL", url),
            ("ODOO_DB", cfg.get("ODOO_DB")),
            ("ODOO_USER", cfg.get("ODOO_USER")),
            ("ODOO_API_KEY/ODOO_PASSWORD", credential),
        ) if not val
    ]
    looked = used_path or " / ".join(_mcp_config_candidates())
    if missing:
        sys.exit(
            "config error: missing " + ", ".join(missing)
            + f"\nLooked in {looked} -> mcpServers.portcities-odoo.env and the environment."
        )
    return {
        "url": url,
        "db": cfg["ODOO_DB"],
        "user": cfg["ODOO_USER"],
        "credential": credential,
        "session_file": cfg.get("CF_SESSION_FILE") or os.path.join(
            PC_MCP_DIR, "cf_session.json"
        ),
        "config_path": used_path or CURSOR_MCP_PATH,
    }


REFRESH_HINT = (
    "Cloudflare is blocking the request (cf_clearance expired, User-Agent mismatch, or "
    "the source IP changed). Refresh the cf_clearance session used by the "
    "portcities-odoo MCP (see that server's docs / CF_SESSION_FILE), then retry.\n"
    "Session dir hint: {d}"
)


class _CFTransport(xmlrpc.client.SafeTransport):
    """SafeTransport that carries the cf_clearance cookie and the captured UA."""

    def __init__(self, cf_clearance, user_agent, context=None):
        super().__init__(context=context)
        self.user_agent = user_agent  # replaces the default UA, no duplicate header
        self._cf = cf_clearance

    def send_headers(self, connection, headers):
        headers.append(("Cookie", f"cf_clearance={self._cf}"))
        super().send_headers(connection, headers)


def load_session(path):
    if not os.path.exists(path):
        print(f"No cf_clearance session at {path}.", file=sys.stderr)
        print(REFRESH_HINT.format(d=os.path.dirname(path)), file=sys.stderr)
        sys.exit(2)
    with open(path) as fh:
        session = json.load(fh)
    if not session.get("cf_clearance") or not session.get("user_agent"):
        print(f"{path} is missing cf_clearance/user_agent.", file=sys.stderr)
        print(REFRESH_HINT.format(d=os.path.dirname(path)), file=sys.stderr)
        sys.exit(2)
    return session["cf_clearance"], session["user_agent"]


class Odoo:
    def __init__(self, cfg):
        self.cfg = cfg
        cf, ua = load_session(cfg["session_file"])
        self._hint = REFRESH_HINT.format(d=os.path.dirname(cfg["session_file"]))
        self.common = xmlrpc.client.ServerProxy(
            f"{cfg['url']}/xmlrpc/2/common", transport=_CFTransport(cf, ua)
        )
        self.models = xmlrpc.client.ServerProxy(
            f"{cfg['url']}/xmlrpc/2/object", transport=_CFTransport(cf, ua)
        )
        self.uid = None

    def version(self):
        """Reaching version() at all proves Cloudflare was bypassed."""
        try:
            return self.common.version()
        except xmlrpc.client.ProtocolError as exc:
            if exc.errcode == 403:
                return None
            raise

    def authenticate(self):
        cfg = self.cfg
        try:
            uid = self.common.authenticate(cfg["db"], cfg["user"], cfg["credential"], {})
        except xmlrpc.client.ProtocolError as exc:
            if exc.errcode == 403:
                print(self._hint, file=sys.stderr)
                sys.exit(2)
            raise
        if not uid:
            print(
                f"auth failed for {cfg['user']} on {cfg['db']} — the API key is dead "
                "(the cookie is fine; refreshing it will not help).\n"
                "Generate a new one in Odoo: avatar -> My Profile -> Account Security -> "
                "New API Key, then update mcpServers.portcities-odoo.env.ODOO_API_KEY in "
                f"{cfg.get('config_path') or CURSOR_MCP_PATH}.",
                file=sys.stderr,
            )
            sys.exit(3)
        self.uid = uid
        return uid

    def call(self, model, method, args, kwargs=None):
        if self.uid is None:
            self.authenticate()
        cfg = self.cfg
        try:
            return self.models.execute_kw(
                cfg["db"], self.uid, cfg["credential"], model, method, args, kwargs or {}
            )
        except xmlrpc.client.ProtocolError as exc:
            if exc.errcode == 403:
                print(self._hint, file=sys.stderr)
                sys.exit(2)
            raise


# -------------------------------------------------------------------------- helpers

def _ids(raw):
    if not raw:
        return []
    return [int(part) for part in str(raw).replace(" ", "").split(",") if part]


def _read_description(args):
    if args.description_file:
        with open(args.description_file, encoding="utf-8") as fh:
            return fh.read()
    return args.description or ""


def find_duplicates(odoo, terms, project):
    """OR-ilike across name for each term. Returns matching tasks, newest first."""
    terms = [t.strip() for t in terms if t and t.strip()]
    if not terms:
        return []
    domain = [("project_id", "=", project)]
    if len(terms) == 1:
        domain.append(("name", "ilike", terms[0]))
    else:
        domain += ["|"] * (len(terms) - 1)
        domain += [("name", "ilike", term) for term in terms]
    return odoo.call(
        "project.task", "search_read", [domain],
        {"fields": ["id", "name", "stage_id", "user_ids", "allocated_hours"],
         "limit": 30, "order": "id desc"},
    )


def _print_tasks(tasks, project):
    for task in tasks:
        stage = task["stage_id"][1] if task.get("stage_id") else "-"
        print(f"  {task['id']:>7}  [{stage}]  {task['name']}")
        print(f"           {task_url(project, task['id'])}")


def _resolve_stage(value):
    """Accept a stage id or a name/alias from config portcities.stages."""
    text = str(value).strip()
    if text.isdigit():
        stage_id = int(text)
        if STAGES and stage_id not in STAGES:
            raise ValueError(
                f"stage {stage_id} is not in portcities.stages for project "
                f"{DEFAULT_PROJECT}. Valid: "
                + ", ".join(f"{k}={v}" for k, v in STAGES.items())
            )
        return stage_id
    if not STAGE_ALIASES:
        raise ValueError(
            "no portcities.stages aliases configured — pass a numeric stage id, "
            "or fill stages in .agents/config.yml (see create_task.py stages)."
        )
    key = text.lower().lstrip("0123456789. ").strip()
    if key in STAGE_ALIASES:
        return STAGE_ALIASES[key]
    if text.lower() in STAGE_ALIASES:
        return STAGE_ALIASES[text.lower()]
    raise ValueError(
        f"unknown stage '{value}'. Use an id or one of: "
        + ", ".join(sorted(set(STAGE_ALIASES)))
    )


def _read_body(args):
    """Body for a log note: --body-file wins over --body."""
    if getattr(args, "body_file", None):
        with open(args.body_file) as fh:
            return fh.read()
    return args.body


def _post_note(odoo, task_id, body):
    """Log note, not Send message — mail.mt_note keeps it off the customer's email.

    body_is_html is required, not optional. Odoo 19's message_post does
    `'body': escape(body)` and only skips escaping for a Markup object, which XML-RPC
    cannot send — so without this flag the HTML arrives as literal <p> tags in the
    chatter. body_is_html re-wraps it in Markup (internal users only, which we are).
    """
    return odoo.call(
        "project.task", "message_post", [[task_id]],
        {"body": body, "message_type": "comment", "subtype_xmlid": "mail.mt_note",
         "body_is_html": True},
    )


# ------------------------------------------------------------------------- commands

def cmd_check(odoo, args):
    version = odoo.version()
    if version is None:
        print("Cloudflare: BLOCKED (no server version)", file=sys.stderr)
        print(odoo._hint, file=sys.stderr)
        sys.exit(2)
    print(f"Cloudflare: bypassed — server {version.get('server_version', '?')}")
    uid = odoo.authenticate()
    user = odoo.call("res.users", "read", [[uid]], {"fields": ["name", "login"]})
    print(f"Auth: ok — uid {uid} ({user[0]['name']} <{user[0]['login']}>)")
    project = odoo.call(
        "project.project", "read", [[args.project]], {"fields": ["name"]}
    )
    print(f"Project {args.project}: {project[0]['name'] if project else 'NOT FOUND'}")
    return 0


def cmd_search(odoo, args):
    tasks = find_duplicates(odoo, args.terms, args.project)
    if not tasks:
        print(f"No task on project {args.project} matches: {', '.join(args.terms)}")
        return 0
    print(f"{len(tasks)} possible match(es) on project {args.project}:")
    _print_tasks(tasks[: args.limit], args.project)
    return 0


def cmd_types(odoo, args):
    types = odoo.call(
        "mail.activity.type", "search_read", [[]],
        {"fields": ["id", "name", "delay_count", "delay_unit"], "order": "sequence"},
    )
    print("Activity types:")
    for row in types:
        delay = f"+{row['delay_count']} {row['delay_unit']}" if row.get("delay_count") else ""
        print(f"  {row['id']:>4}  {row['name']:<28} {delay}")
    return 0


def cmd_stages(odoo, args):
    """List stages from config; optionally refresh labels from the live project."""
    print(f"Stages for project {args.project} (from .agents/config.yml):")
    if not STAGES:
        print("  (none configured — set portcities.stages)")
    else:
        for stage_id, label in sorted(STAGES.items()):
            print(f"  {stage_id:>4}  {label}")
    live = odoo.call(
        "project.task.type", "search_read",
        [[("project_ids", "in", [args.project])]],
        {"fields": ["id", "name", "sequence"], "order": "sequence"},
    )
    if live:
        print("Live stages on this project (fill config from these ids):")
        for row in live:
            print(f"  {row['id']:>4}  {row['name']}")
    return 0


def cmd_create(odoo, args):
    vals = {
        "name": args.name,
        "project_id": args.project,
        "user_ids": [(6, 0, _ids(args.assignees) or DEFAULT_ASSIGNEES)],
        "allocated_hours": args.hours,
        "priority": str(args.priority),
        "description": _read_description(args),
    }
    if args.milestone is not None:
        vals["milestone_id"] = args.milestone
    if args.partner is not None:
        vals["partner_id"] = args.partner
    if args.stage is not None:
        vals["stage_id"] = (
            args.stage if isinstance(args.stage, int)
            else _resolve_stage(args.stage)
        )
    if args.deadline:
        vals["date_deadline"] = args.deadline
    if args.parent:
        vals["parent_id"] = args.parent

    if args.dry_run:
        print("--dry-run, nothing written (no Odoo session). Payload:")
        print(json.dumps(vals, indent=2, ensure_ascii=False))
        return 0

    dedupe_terms = [t.strip() for t in (args.dedupe or "").split(",") if t.strip()]
    if not dedupe_terms:
        # Fall back to the distinctive words of the title so a plain create is never
        # a blind create. Strip bracket tags like [v19] / [PCI] from search terms.
        words = args.name.split()
        dedupe_terms = [
            w for w in words
            if len(w) > 4 and not (w.startswith("[") and w.endswith("]"))
        ][:3]
    matches = find_duplicates(odoo, dedupe_terms, args.project)
    if matches and not args.force:
        print(f"Refusing to create — {len(matches)} similar task(s) already on "
              f"project {args.project} (searched: {', '.join(dedupe_terms)}):")
        _print_tasks(matches, args.project)
        print("\nUpdate one of those instead, or re-run with --force if this is "
              "genuinely a new task.")
        return 4
    if matches:
        print(f"note: --force given, creating despite {len(matches)} similar task(s).")

    task_id = odoo.call("project.task", "create", [vals])
    created = odoo.call(
        "project.task", "read", [[task_id]],
        {"fields": ["name", "stage_id", "user_ids", "allocated_hours", "priority",
                    "milestone_id", "date_deadline"]},
    )[0]
    print(f"Created task {task_id}")
    print(f"  {task_url(args.project, task_id)}")
    print(f"  name        {created['name']}")
    print(f"  stage       {created['stage_id'][1] if created.get('stage_id') else '-'}")
    print(f"  assignees   {created.get('user_ids')}")
    print(f"  hours       {created.get('allocated_hours')}")
    print(f"  priority    {created.get('priority')}")
    print(f"  milestone   {created['milestone_id'][1] if created.get('milestone_id') else '-'}")
    print(f"  deadline    {created.get('date_deadline') or '-'}")
    return 0


def cmd_activity(odoo, args):
    vals = {
        "res_model": "project.task",
        "res_id": args.task,
        "activity_type": args.type,
        "summary": args.summary,
        "date_deadline": args.due,
        "user_id": args.user,
    }
    if args.note:
        vals["note"] = args.note

    if args.dry_run:
        print("--dry-run, nothing written (no Odoo session). Payload:")
        print(json.dumps(vals, indent=2, ensure_ascii=False))
        return 0

    type_ids = odoo.call(
        "mail.activity.type", "search_read", [[("name", "=ilike", args.type)]],
        {"fields": ["id", "name"], "limit": 1},
    )
    if not type_ids:
        print(f"Activity type '{args.type}' does not exist on this instance. "
              "Run `create_task.py types` to see the real ones.", file=sys.stderr)
        return 1
    model_ids = odoo.call(
        "ir.model", "search_read", [[("model", "=", "project.task")]],
        {"fields": ["id"], "limit": 1},
    )
    write_vals = {
        "res_model_id": model_ids[0]["id"],
        "res_model": "project.task",
        "res_id": args.task,
        "activity_type_id": type_ids[0]["id"],
        "summary": args.summary,
        "date_deadline": args.due,
        "user_id": args.user,
    }
    if args.note:
        write_vals["note"] = args.note

    activity_id = odoo.call("mail.activity", "create", [write_vals])
    print(f"Scheduled activity {activity_id} ({type_ids[0]['name']}) on task {args.task}")
    print(f"  summary  {args.summary}")
    print(f"  due      {args.due}")
    print(f"  owner    user {args.user}")
    print(f"  {task_url(args.project, args.task)}")
    return 0


def _load_task_in_scope(odoo, task_id, project):
    """Read the task and refuse to touch one outside the expected project."""
    rows = odoo.call(
        "project.task", "read", [[task_id]],
        {"fields": ["name", "stage_id", "project_id", "user_ids"]},
    )
    if not rows:
        print(f"Task {task_id} does not exist.", file=sys.stderr)
        return None
    task = rows[0]
    actual = task["project_id"][0] if task.get("project_id") else None
    if actual != project:
        label = task["project_id"][1] if task.get("project_id") else "no project"
        print(f"Task {task_id} is on project {actual} ({label}), not {project}. "
              "Refusing to touch it — pass --project if this is deliberate.",
              file=sys.stderr)
        return None
    return task


def cmd_note(odoo, args):
    body = _read_body(args)
    task = _load_task_in_scope(odoo, args.task, args.project)
    if task is None:
        return 1
    was = task["stage_id"][1] if task.get("stage_id") else "-"
    target = _resolve_stage(args.stage) if args.stage else None

    print(f"Task {args.task}: {task['name']}")
    print(f"  stage now   {was}")
    if target:
        print(f"  stage after {stage_label(target)}")
    if args.dry_run:
        print("--dry-run, nothing written. Log note body:")
        print(body)
        return 0

    _post_note(odoo, args.task, body)
    print("  log note    posted (internal — followers are not emailed)")
    if target:
        odoo.call("project.task", "write", [[args.task], {"stage_id": target}])
        moved = odoo.call(
            "project.task", "read", [[args.task]], {"fields": ["stage_id"]}
        )[0]
        print(f"  stage       {moved['stage_id'][1] if moved.get('stage_id') else '-'}")
    print(f"  {task_url(args.project, args.task)}")
    return 0


def cmd_attach(odoo, args):
    task = _load_task_in_scope(odoo, args.task, args.project)
    if task is None:
        return 1
    if not os.path.exists(args.file):
        print(f"File not found: {args.file}", file=sys.stderr)
        return 1
    name = args.name or os.path.basename(args.file)
    mimetype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(args.file, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")

    print(f"Task {args.task}: {task['name']}")
    print(f"  file        {args.file} ({len(data)} b64 chars, {mimetype})")
    if args.dry_run:
        print("--dry-run, nothing written.")
        return 0

    vals = {
        "name": name,
        "res_model": "project.task",
        "res_id": args.task,
        "datas": data,
        "mimetype": mimetype,
    }
    attachment_id = odoo.call("ir.attachment", "create", [vals])
    print(f"  attached    {attachment_id}: {name}")
    print(f"  {task_url(args.project, args.task)}")
    return 0


def cmd_stage(odoo, args):
    target = _resolve_stage(args.stage)
    task = _load_task_in_scope(odoo, args.task, args.project)
    if task is None:
        return 1
    was = task["stage_id"][1] if task.get("stage_id") else "-"

    print(f"Task {args.task}: {task['name']}")
    print(f"  {was}  ->  {stage_label(target)}")
    if args.dry_run:
        print("--dry-run, nothing written.")
        return 0
    if task.get("stage_id") and task["stage_id"][0] == target:
        print("  already in that stage — nothing written.")
        return 0

    odoo.call("project.task", "write", [[args.task], {"stage_id": target}])
    moved = odoo.call("project.task", "read", [[args.task]], {"fields": ["stage_id"]})[0]
    print(f"  stage       {moved['stage_id'][1] if moved.get('stage_id') else '-'}")
    print(f"  {task_url(args.project, args.task)}")
    return 0


# ----------------------------------------------------------------------------- main

def build_parser(project_cfg):
    default_project = project_cfg["project_id"]
    default_assignees = project_cfg["default_assignees"]
    default_milestone = project_cfg["milestone_id"]
    default_partner = project_cfg["partner_id"]
    assignee_default = ",".join(map(str, default_assignees)) if default_assignees else ""

    parser = argparse.ArgumentParser(
        description="Create tasks/activities in the Portcities internal Odoo "
                    "over the Cloudflare-bypassing XML-RPC tunnel. "
                    "Project id/stages come from .agents/config.yml.",
    )
    parser.add_argument(
        "--project", type=int, default=default_project,
        required=(default_project is None),
        help="project.project id (default from portcities.project_id in config)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="verify the tunnel, the API key, and the project")

    p_search = sub.add_parser("search", help="duplicate check by title terms")
    p_search.add_argument("terms", nargs="+", help="one or more ilike terms")
    p_search.add_argument("--limit", type=int, default=20)

    sub.add_parser("types", help="list mail.activity.type on this instance")
    sub.add_parser("stages", help="list stages from config + live project")

    p_create = sub.add_parser("create", help="create a project.task")
    p_create.add_argument("--name", required=True, help="<area> — <symptom>")
    p_create.add_argument("--description", help="HTML description (not markdown)")
    p_create.add_argument("--description-file", help="file containing the HTML description")
    p_create.add_argument(
        "--assignees", default=assignee_default,
        help="comma-separated res.users ids "
             f"(default from config: {assignee_default or 'none — required'})",
    )
    p_create.add_argument("--hours", type=float, required=True,
                          help="allocated_hours — a real number, never blank")
    p_create.add_argument("--priority", type=int, default=1, choices=[0, 1, 2, 3],
                          help="0 Low, 1 Medium, 2 High, 3 Urgent (verify on this project)")
    p_create.add_argument(
        "--stage",
        help="stage id or alias from portcities.stages (e.g. todo, qc)",
    )
    p_create.add_argument(
        "--milestone", type=int, default=default_milestone,
        help=f"milestone_id (default {default_milestone} from config, or omit)",
    )
    p_create.add_argument(
        "--partner", type=int, default=default_partner,
        help=f"partner_id (default {default_partner} from config, or omit)",
    )
    p_create.add_argument("--deadline", help="date_deadline, YYYY-MM-DD")
    p_create.add_argument("--parent", type=int, help="parent_id, for a child task")
    p_create.add_argument("--dedupe", help="comma-separated terms to search before writing")
    p_create.add_argument("--force", action="store_true",
                          help="create even though similar tasks exist")
    p_create.add_argument("--dry-run", action="store_true")

    p_act = sub.add_parser("activity", help="schedule a mail.activity on a task")
    p_act.add_argument("--task", type=int, required=True)
    p_act.add_argument("--summary", required=True,
                       help="must read on its own in a to-do list")
    p_act.add_argument("--type", required=True, help="activity type name, e.g. 'To-Do'")
    p_act.add_argument("--due", required=True, help="date_deadline, YYYY-MM-DD")
    p_act.add_argument(
        "--user", type=int,
        default=(default_assignees[0] if default_assignees else None),
        help="owner res.users id (default first portcities.default_assignees)",
    )
    p_act.add_argument("--note", help="HTML note body")
    p_act.add_argument("--dry-run", action="store_true")

    p_note = sub.add_parser("note", help="post a Log note on a task, optionally move stage")
    p_note.add_argument("--task", type=int, required=True)
    p_note.add_argument("--body", help="HTML body (not markdown)")
    p_note.add_argument("--body-file", help="file containing the HTML body")
    p_note.add_argument("--stage", help="also move the stage: id or alias from config")
    p_note.add_argument("--dry-run", action="store_true")

    p_attach = sub.add_parser("attach", help="attach a file to a task (ir.attachment)")
    p_attach.add_argument("--task", type=int, required=True)
    p_attach.add_argument("--file", required=True, help="path to the file to attach")
    p_attach.add_argument("--name", help="attachment name (default: file basename)")
    p_attach.add_argument("--dry-run", action="store_true")

    p_stage = sub.add_parser("stage", help="move a task's stage, no note")
    p_stage.add_argument("--task", type=int, required=True)
    p_stage.add_argument("--stage", required=True, help="id or alias from portcities.stages")
    p_stage.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None):
    # Keep stdout in step with stderr, so a diagnostic and the line it explains do
    # not arrive out of order when the output is piped.
    sys.stdout.reconfigure(line_buffering=True)
    project_cfg = load_project_config()
    args = build_parser(project_cfg).parse_args(argv)
    if args.command == "create":
        if not (args.description or args.description_file):
            print("create needs --description or --description-file: a task with no "
                  "description is noise to whoever picks it up.", file=sys.stderr)
            return 1
        if not _ids(args.assignees):
            print("create needs --assignees (or portcities.default_assignees in "
                  "config.yml).", file=sys.stderr)
            return 1
    if args.command == "note" and not (args.body or args.body_file):
        print("note needs --body or --body-file: an empty log note tells the "
              "developer nothing.", file=sys.stderr)
        return 1
    if args.command == "activity" and not args.user:
        print("activity needs --user (or portcities.default_assignees in config).",
              file=sys.stderr)
        return 1

    # create/activity --dry-run print payload without needing Cloudflare / API key.
    dry_offline = bool(getattr(args, "dry_run", False) and args.command in (
        "create", "activity",
    ))
    odoo = None if dry_offline else Odoo(load_config())
    handler = {
        "check": cmd_check,
        "search": cmd_search,
        "types": cmd_types,
        "stages": cmd_stages,
        "create": cmd_create,
        "activity": cmd_activity,
        "note": cmd_note,
        "attach": cmd_attach,
        "stage": cmd_stage,
    }[args.command]
    try:
        return handler(odoo, args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
