#!/usr/bin/env bash
# ============================================================
# start.sh — TACO Single-Click Setup (Linux / macOS / Git Bash)
# Usage: chmod +x start.sh && ./start.sh
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA="$ROOT/infra"
BACK="$ROOT/backend"
FRONT="$ROOT/frontend"
VENV="$BACK/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
UVI="$VENV/bin/uvicorn"

# ── Colors ─────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✅  $*${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️   $*${NC}"; }
fail() { echo -e "${RED}  ❌  $*${NC}"; }
info() { echo -e "${CYAN}$*${NC}"; }

info "========================================================"
info "  🌮  TACO MVP — Single-Click Start"
info "========================================================"

# ── Cleanup on exit ────────────────────────────────────────────────────────────
BACK_PID="" ; FRONT_PID=""
cleanup() {
    echo ""
    warn "Shutting down TACO servers..."
    [[ -n "$BACK_PID"  ]] && kill "$BACK_PID"  2>/dev/null && ok "Backend stopped"
    [[ -n "$FRONT_PID" ]] && kill "$FRONT_PID" 2>/dev/null && ok "Frontend stopped"
    warn "Goodbye! 🌮"
}
trap cleanup EXIT INT TERM

# ── Prerequisite checks ────────────────────────────────────────────────────────
info "\n[ 1/5 ] Checking prerequisites..."
for cmd in docker python3 node pnpm; do
    if command -v "$cmd" &>/dev/null; then
        ok "$cmd found ($(command -v "$cmd"))"
    else
        fail "$cmd not found. Install it and re-run."
        exit 1
    fi
done

if ! docker info &>/dev/null; then
    fail "Docker daemon is not running. Start Docker Desktop first."
    exit 1
fi
ok "Docker daemon running"

# ── Start PostgreSQL ───────────────────────────────────────────────────────────
info "\n[ 2/5 ] Starting PostgreSQL (Docker)..."
(cd "$INFRA" && docker compose up -d postgres) >/dev/null 2>&1
ok "Postgres container started"

echo "       Waiting for Postgres health check..."
for i in $(seq 1 20); do
    health=$(docker inspect --format='{{.State.Health.Status}}' taco-postgres 2>/dev/null || echo "unknown")
    [[ "$health" == "healthy" ]] && break
    sleep 2
done
[[ "$health" == "healthy" ]] && ok "Postgres healthy" || warn "Postgres not healthy yet — continuing"

# ── Python virtual env + backend ──────────────────────────────────────────────
info "\n[ 3/5 ] Setting up Python backend..."
if [[ ! -d "$VENV" ]]; then
    echo "       Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi

echo "       Installing/verifying Python dependencies..."
"$PIP" install -r "$BACK/requirements.txt" -q
ok "Python dependencies ready"

echo "       Starting FastAPI on http://localhost:8000 ..."
cd "$BACK"
"$UVI" app.main:app --host 0.0.0.0 --port 8000 --log-level info &
BACK_PID=$!
cd "$ROOT"
ok "Backend started (PID $BACK_PID)"

# Wait for /health
echo "       Waiting for backend..."
for i in $(seq 1 20); do
    sleep 2
    if curl -sf http://localhost:8000/health | grep -q '"ok"' 2>/dev/null; then
        ok "Backend healthy"
        break
    fi
done

# ── Frontend dev server ────────────────────────────────────────────────────────
info "\n[ 4/5 ] Setting up React frontend..."
cd "$FRONT"
if [[ ! -d "node_modules" ]]; then
    echo "       Installing frontend dependencies (first run)..."
    pnpm install --silent
fi
ok "Frontend dependencies ready"

echo "       Starting Vite on http://localhost:5173 ..."
pnpm run dev --host &
FRONT_PID=$!
cd "$ROOT"
ok "Frontend started (PID $FRONT_PID)"

sleep 3

# ── Smoke test ─────────────────────────────────────────────────────────────────
info "\n[ 5/5 ] Running smoke test..."
"$PY" "$ROOT/scripts/smoke_test.py"
SMOKE_EXIT=$?
if [[ $SMOKE_EXIT -eq 0 ]]; then
    ok "All smoke tests passed!"
else
    warn "Some smoke tests failed — chat tests require valid API keys in backend/.env"
fi

# ── Launch browser ────────────────────────────────────────────────────────────
sleep 1
if command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:5173 &>/dev/null &
    xdg-open http://localhost:8000/docs &>/dev/null &
elif command -v open &>/dev/null; then   # macOS
    open http://localhost:5173
    open http://localhost:8000/docs
fi

info "\n========================================================"
ok "🌮 TACO is running!"
info "========================================================"
echo ""
echo "  📡 Backend API   →  http://localhost:8000"
echo "  📖 API Docs      →  http://localhost:8000/docs"
echo "  📊 Dashboard     →  http://localhost:5173"
echo ""
warn "Press Ctrl+C to stop all servers."
echo ""

# Keep alive until Ctrl+C
wait $BACK_PID
