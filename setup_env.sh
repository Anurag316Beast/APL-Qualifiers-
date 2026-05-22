#!/usr/bin/env bash
# setup_env.sh
# Bootstrap script for the Lucknow Artisan Credit Scoring System.
# Creates a Python virtual environment, installs all dependencies,
# seeds the database, and launches the Streamlit dashboard.
#
# Usage:
#   chmod +x setup_env.sh
#   ./setup_env.sh

set -euo pipefail

VENV_DIR=".venv"
PYTHON_MIN="3.10"
DB_FILE="artisan_credit.db"

# ── 1. Resolve python binary ──────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "ERROR: Python not found. Install Python $PYTHON_MIN or later."
    exit 1
fi

PYTHON_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_MAJOR=3
REQUIRED_MINOR=10

ACTUAL_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
ACTUAL_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)

if [ "$ACTUAL_MAJOR" -lt "$REQUIRED_MAJOR" ] || \
   { [ "$ACTUAL_MAJOR" -eq "$REQUIRED_MAJOR" ] && [ "$ACTUAL_MINOR" -lt "$REQUIRED_MINOR" ]; }; then
    echo "ERROR: Python $PYTHON_MIN+ required. Found $PYTHON_VER."
    exit 1
fi

echo "Using Python $PYTHON_VER ($PYTHON_BIN)"

# ── 2. Create virtual environment ────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# ── 3. Activate and install dependencies ─────────────────────────────────────
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies from requirements.txt ..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Dependencies installed:"
pip show pandas numpy streamlit plotly 2>/dev/null | grep -E "^(Name|Version)"

# ── 4. Seed the database ──────────────────────────────────────────────────────
if [ ! -f "$DB_FILE" ]; then
    echo "Seeding database (this takes a few seconds) ..."
    python main.py
else
    echo "Database already exists at $DB_FILE — skipping seed."
    echo "  Run 'python main.py' manually to regenerate it."
fi

# ── 5. Launch Streamlit dashboard ─────────────────────────────────────────────
echo ""
echo "Setup complete. Launching dashboard ..."
echo "  Local URL:  http://localhost:8501"
echo ""
streamlit run app.py
