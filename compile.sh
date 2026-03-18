#!/usr/bin/env bash
# compile.sh – Build IReal Studio using Nuitka (standalone on Linux, onefile on macOS).
#
# Usage:
#   ./compile.sh [--onefile]
#
# Options:
#   --onefile   Build a single self-contained binary (macOS default; optional on Linux).
#
# Requirements:
#   uv must be installed (https://github.com/astral-sh/uv)
#   A C compiler (gcc/clang) must be available.
#   On Linux: portaudio19-dev and GTK3 headers are required to compile native
#   extension wheels if no binary wheel is cached (see the GitHub Actions
#   workflow for the full apt-get list).
#
# Output (Linux standalone):
#   dist/irealstudio-linux/        – standalone directory
#   dist/irealstudio-linux.tar.gz  – ready-to-ship archive
#
# Output (Linux onefile):
#   dist/irealstudio-linux         – single executable
#
# Output (macOS onefile):
#   dist/irealstudio-macos         – single executable

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }
# ─────────────────────────────────────────────────────────────────────────────

ONEFILE=false
if [[ "${1:-}" == "--onefile" ]]; then
    ONEFILE=true
fi

OS="$(uname -s)"

# Default to onefile on macOS
if [[ "$OS" == "Darwin" ]]; then
    ONEFILE=true
fi

echo
echo "==================================================="
echo " IReal Studio – ${OS} build"
echo "==================================================="
echo

# ── verify uv ────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    error "uv not found on PATH. Install from https://github.com/astral-sh/uv"
fi

# ── sync dependencies ─────────────────────────────────────────────────────────
info "[1/4] Installing dependencies with uv..."
uv sync --all-groups

# Resolve the accessible_output3 lib directory so Nuitka bundles the
# screen-reader DLLs at the path load_library() looks for at runtime:
#   <exe_dir>/accessible_output3/lib/<dll>
AO3_LIB=$(uv run python -c \
    "import os,accessible_output3; \
     print(os.path.join(os.path.dirname(accessible_output3.__file__),'lib'))")
[[ -d "$AO3_LIB" ]] || error "Could not resolve accessible_output3 lib path: $AO3_LIB"

# ── determine output names ────────────────────────────────────────────────────
if [[ "$OS" == "Darwin" ]]; then
    OUTPUT_FILE="irealstudio-macos"
    DIST_LABEL="dist/${OUTPUT_FILE}  (single binary)"
else
    if $ONEFILE; then
        OUTPUT_FILE="irealstudio-linux"
        DIST_LABEL="dist/${OUTPUT_FILE}  (single binary)"
    else
        OUTPUT_FILE="irealstudio-linux"
        DIST_DIR="dist/irealstudio-linux"
        ARCHIVE="dist/irealstudio-linux.tar.gz"
        DIST_LABEL="${DIST_DIR}/  +  ${ARCHIVE}"
    fi
fi

# ── clean previous output ─────────────────────────────────────────────────────
info "[2/4] Cleaning previous build output..."
rm -rf dist/main.dist dist/main.onefile-build
if [[ "$OS" == "Darwin" ]]; then
    rm -f "dist/${OUTPUT_FILE}"
else
    if $ONEFILE; then
        rm -f "dist/${OUTPUT_FILE}"
    else
        rm -rf "dist/irealstudio-linux"
        rm -f  "dist/irealstudio-linux.tar.gz"
    fi
fi

# ── Nuitka build ──────────────────────────────────────────────────────────────
info "[3/4] Building with Nuitka..."

if $ONEFILE; then
    uv run python -m nuitka \
        --mode=onefile \
        --output-file="${OUTPUT_FILE}" \
        --output-dir=dist \
        --assume-yes-for-downloads \
        --follow-imports \
        --include-data-dir=locales=locales \
        --include-data-dir=templates=templates \
        --include-data-files=news.md=news.md \
        "--include-data-dir=$AO3_LIB=accessible_output3/lib" \
        --include-module=mido.backends.rtmidi \
        --nofollow-import-to=unittest \
        --nofollow-import-to=doctest \
        --nofollow-import-to=pdb \
        --nofollow-import-to=tkinter \
        --nofollow-import-to=test \
        main.py
    chmod +x "dist/${OUTPUT_FILE}"
else
    uv run python -m nuitka \
        --mode=standalone \
        --output-file="${OUTPUT_FILE}" \
        --output-dir=dist \
        --assume-yes-for-downloads \
        --follow-imports \
        --include-data-dir=locales=locales \
        --include-data-dir=templates=templates \
        --include-data-files=news.md=news.md \
        "--include-data-dir=$AO3_LIB=accessible_output3/lib" \
        --include-module=mido.backends.rtmidi \
        --nofollow-import-to=unittest \
        --nofollow-import-to=doctest \
        --nofollow-import-to=pdb \
        --nofollow-import-to=tkinter \
        --nofollow-import-to=test \
        main.py
fi

# ── package (Linux standalone only) ──────────────────────────────────────────
info "[4/4] Packaging..."

if [[ "$OS" != "Darwin" ]] && ! $ONEFILE; then
    if [[ ! -d dist/main.dist ]]; then
        error "dist/main.dist not found – Nuitka did not produce expected output."
    fi
    mv dist/main.dist "${DIST_DIR}"
    tar -czf "${ARCHIVE}" -C dist irealstudio-linux
    info "Archive: ${ARCHIVE}"
fi

echo
echo "==================================================="
echo " Build complete!"
echo " Output: ${DIST_LABEL}"
echo "==================================================="
