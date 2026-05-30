#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Copy .env if not exists ───────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "⚠  Creado .env desde .env.example — abrilo y pegá tus API keys"
  echo ""
fi

# ── Python venv ───────────────────────────────────────────────────────────────
if [ ! -d "$BACKEND/venv" ]; then
  echo "Creando entorno virtual..."
  python3 -m venv "$BACKEND/venv"
fi

echo "Instalando dependencias..."
"$BACKEND/venv/bin/pip" install -r "$BACKEND/requirements.txt" -q

# ── Check ffmpeg ──────────────────────────────────────────────────────────────
if ! command -v ffmpeg &> /dev/null; then
  echo "⚠  ffmpeg no está instalado. Necesitás instalarlo:"
  echo "   macOS:   brew install ffmpeg"
  echo "   Ubuntu:  sudo apt install ffmpeg"
  echo "   Windows: https://ffmpeg.org/download.html"
  exit 1
fi

# ── Start backend ─────────────────────────────────────────────────────────────
echo ""
echo "Iniciando backend en http://localhost:8000 ..."
cd "$BACKEND"
DOTENV_PATH="$ROOT/.env" "$BACKEND/venv/bin/uvicorn" main:app --port 8000 --reload &
BACKEND_PID=$!

# ── Start frontend ────────────────────────────────────────────────────────────
echo "Iniciando frontend en http://localhost:3000 ..."
cd "$FRONTEND"
python3 -m http.server 3000 --bind 127.0.0.1 &
FRONTEND_PID=$!

sleep 1
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Editor de Video corriendo           ║"
echo "║  → http://localhost:3000             ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Ctrl+C para detener"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
