#!/usr/bin/env sh
# ─────────────────────────────────────────────────────────────────────────
# Orqestra bootstrap — run once on a fresh clone, BEFORE `docker compose up`.
#
# Why this exists: compose.yaml bind-mounts a few small YAML state files
# (project.yaml, departments.yaml, pipelines.yaml). When the host source
# path of a bind-mount does NOT exist, Docker silently creates an empty
# *directory* in its place — which then crashes the app on first write
# ("IsADirectoryError: '/app/departments.yaml'").
#
# This script makes sure those files exist as files (and seeds .env from
# .env.example) so Docker mounts the right thing on first boot.
# Re-running is safe: existing files are never touched.
# ─────────────────────────────────────────────────────────────────────────
set -eu

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "Orqestra bootstrap in: $ROOT"

# ── .env ───────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "  + created .env from .env.example  (edit it before starting!)"
  else
    : > .env
    echo "  + created empty .env  (no .env.example found)"
  fi
else
  echo "  = .env already exists, leaving untouched"
fi

# ── project.yaml — minimal stub if missing ────────────────────────────
if [ ! -f project.yaml ]; then
  cat > project.yaml <<'EOF'
# Project context — injected into every agent's system prompt.
# Edit via the Web UI (Settings) or directly here.
name: My Company
type: ""
location: ""
focus: ""
target_market: ""
notes: ""
EOF
  echo "  + created project.yaml stub  (fill in via Web UI → Settings)"
else
  echo "  = project.yaml already exists, leaving untouched"
fi

# ── runtime registries — empty files are valid (= no departments yet) ─
for f in departments.yaml pipelines.yaml; do
  if [ ! -e "$f" ]; then
    : > "$f"
    echo "  + created empty $f  (auto-populated from templates/ on first start)"
  elif [ -d "$f" ]; then
    echo "  ! $f is a directory (Docker auto-created it); removing and replacing with a file" >&2
    rmdir "$f" 2>/dev/null || {
      echo "    cannot remove non-empty directory $f — please clean it up manually." >&2
      exit 1
    }
    : > "$f"
  else
    echo "  = $f already exists, leaving untouched"
  fi
done

# ── runtime data dirs — make sure the bind targets exist as dirs ──────
for d in data knowledge_base departments skills; do
  [ -d "$d" ] || mkdir -p "$d"
done

echo ""
echo "Bootstrap complete. Next:"
echo "  1) edit .env  (at minimum: OPENAI_API_KEY)"
echo "  2) docker compose up -d"
echo "  3) open http://localhost:4200"
