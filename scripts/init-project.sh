#!/usr/bin/env bash
# Fill REPLACE knobs after copying the template into pci/<slug>/.
# Usage: ./scripts/init-project.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

die() { echo "error: $*" >&2; exit 1; }

need() {
  local prompt="$1" default="${2:-}" value
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " value
    echo "${value:-$default}"
  else
    read -r -p "$prompt: " value
    [[ -n "$value" ]] || die "required: $prompt"
    echo "$value"
  fi
}

echo "PCI project init — editing .agents/config.yml and project.code-workspace"
echo

slug="$(need "project.slug (folder short name)")"
name="$(need "project.name (display)")"
prefix="$(need "project.module_prefix" "pci_${slug}_")"
odoo_ver="$(need "project.odoo_version" "19.0")"
mode="$(need "tracking.mode (odoo|notes|hybrid)" "hybrid")"
db="$(need "local Odoo database name" "pci_${slug}")"

odoo_src_default="${ODOO_SRC:-$HOME/Project/odoo/odoo/odoo19}"
odoo_ee_default="${ODOO_EE:-$HOME/Project/odoo/odoo-enterprise}"
py_default="${ODOO_PYTHON:-$HOME/.pyenv/versions/odoo19/bin/python}"
db_user_default="${ODOO_DB_USER:-$USER}"

odoo_src="$(need "ODOO community path (ODOO_SRC)" "$odoo_src_default")"
odoo_ee="$(need "ODOO enterprise path (ODOO_EE)" "$odoo_ee_default")"
odoo_py="$(need "Python interpreter (ODOO_PYTHON)" "$py_default")"
db_user="$(need "Odoo --db_user" "$db_user_default")"
http_port="$(need "http-port" "8069")"

export PCI_SLUG="$slug" PCI_NAME="$name" PCI_PREFIX="$prefix"
export PCI_ODOO_VER="$odoo_ver" PCI_MODE="$mode"
export PCI_DB="$db" PCI_ODOO_SRC="$odoo_src" PCI_ODOO_EE="$odoo_ee"
export PCI_ODOO_PY="$odoo_py" PCI_DB_USER="$db_user" PCI_HTTP_PORT="$http_port"

python3 <<'PY'
import json
import os
import re
from pathlib import Path

# cwd is already ROOT (script cd'd there)
cfg_path = Path(".agents/config.yml")
text = cfg_path.read_text(encoding="utf-8")

def sub_once(pattern: str, repl: str, src: str) -> str:
    out, n = re.subn(pattern, repl, src, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"config.yml: expected one match for {pattern!r}, got {n}")
    return out

slug = os.environ["PCI_SLUG"]
name = os.environ["PCI_NAME"]
prefix = os.environ["PCI_PREFIX"]
odoo_ver = os.environ["PCI_ODOO_VER"]
mode = os.environ["PCI_MODE"]

text = sub_once(r"^  slug: REPLACE\s*$", f"  slug: {slug}", text)
text = sub_once(r"^  name: REPLACE\s*$", f'  name: "{name}"', text)
text = sub_once(
    r"^  module_prefix: pci_REPLACE_\s*.*$",
    f"  module_prefix: {prefix}  # custom addon technical names",
    text,
)
text = sub_once(
    r'^  odoo_version: ".*?"\s*.*$',
    f'  odoo_version: "{odoo_ver}"         # local target; agents + overview use this',
    text,
)
text = sub_once(
    r"^  mode: REPLACE\s*.*$",
    f"  mode: {mode}  # odoo | notes | hybrid",
    text,
)
cfg_path.write_text(text, encoding="utf-8")
print(f"updated {cfg_path}")

state = Path(".agents/state.yml")
if not state.exists():
    state.write_text(Path(".agents/state.example.yml").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"created {state}")

odoo_src = os.environ["PCI_ODOO_SRC"].rstrip("/")
odoo_ee = os.environ["PCI_ODOO_EE"].rstrip("/")
odoo_py = os.environ["PCI_ODOO_PY"]
db = os.environ["PCI_DB"]
db_user = os.environ["PCI_DB_USER"]
http_port = os.environ["PCI_HTTP_PORT"]

ws_path = Path("project.code-workspace")
data = json.loads(ws_path.read_text(encoding="utf-8"))

for folder in data["folders"]:
    name = folder.get("name", "")
    if name in ("odoo", "odoo19", "odoo-community"):
        folder["name"] = "odoo"
        folder["path"] = odoo_src
    elif name in ("odoo-ee", "odoo19ee", "odoo-enterprise"):
        folder["name"] = "odoo-ee"
        folder["path"] = odoo_ee

settings = data.setdefault("settings", {})
settings["python.defaultInterpreterPath"] = odoo_py
extra = [odoo_src, odoo_ee, "${workspaceFolder:modules}"]
settings["python.autoComplete.extraPaths"] = extra
settings["python.analysis.extraPaths"] = extra

configs = data.setdefault("launch", {"version": "0.2.0", "configurations": []})["configurations"]
if not configs:
    raise SystemExit("project.code-workspace has no launch configurations")
cfg = configs[0]
cfg["python"] = odoo_py
cfg["program"] = f"{odoo_src}/odoo-bin"
cfg["args"] = [
    "-d", db,
    "--db_user", db_user,
    "--http-port", str(http_port),
    "--http-interface", "127.0.0.1",
    "--addons-path",
    f"${{workspaceFolder:modules}},{odoo_src}/addons,{odoo_ee}",
    "--dev=xml",
]

ws_path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
print(f"updated {ws_path}")
PY

echo
echo "Next:"
echo "  1. Set portcities.project_id / stages, gdrive.*, channels.* in .agents/config.yml"
echo "  2. Fill wiki/overview.md (Now / blocked / next + Drive link)"
echo "  3. python3 .agents/skills/odoo-task-activity/scripts/create_task.py stages"
echo "  4. Open project.code-workspace in Cursor"
