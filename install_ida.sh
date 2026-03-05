#!/usr/bin/env bash
# Rikugan installer for Linux and macOS
# Usage: ./install.sh [IDA_USER_DIR]
#   IDA_USER_DIR  Optional path to IDA user directory (default: auto-detect)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}[*]${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()   { printf "${RED}[-]${NC} %s\n" "$*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Locate IDA user directory ─────────────────────────────────────────

find_ida_user_dir() {
    # Common locations, in order of preference
    local candidates=()

    if [[ "$(uname)" == "Darwin" ]]; then
        candidates+=(
            "$HOME/.idapro"
            "$HOME/Library/Application Support/Hex-Rays/IDA Pro"
        )
    else
        candidates+=(
            "$HOME/.idapro"
            "$HOME/.ida"
        )
    fi

    for dir in "${candidates[@]}"; do
        if [[ -d "$dir" ]]; then
            echo "$dir"
            return 0
        fi
    done

    return 1
}

if [[ $# -ge 1 ]]; then
    IDA_USER_DIR="$1"
    if [[ ! -d "$IDA_USER_DIR" ]]; then
        err "Provided IDA directory does not exist: $IDA_USER_DIR"
        exit 1
    fi
    info "Using provided IDA directory: $IDA_USER_DIR"
else
    if IDA_USER_DIR="$(find_ida_user_dir)"; then
        info "Auto-detected IDA directory: $IDA_USER_DIR"
    else
        # Fall back to the standard default and create it
        IDA_USER_DIR="$HOME/.idapro"
        warn "No IDA directory found, defaulting to $IDA_USER_DIR"
    fi
fi

PLUGINS_DIR="$IDA_USER_DIR/plugins"
CONFIG_DIR="$IDA_USER_DIR/rikugan"

# ── Remove old "iris" installation (rebrand cleanup) ─────────────────
for old_name in "iris_plugin.py" "iris"; do
    OLD_PATH="$PLUGINS_DIR/$old_name"
    if [[ -L "$OLD_PATH" ]]; then
        warn "Removing old '$old_name' symlink: $OLD_PATH"
        rm "$OLD_PATH"
        ok "Old '$old_name' symlink removed"
    elif [[ -e "$OLD_PATH" ]]; then
        warn "Removing old '$old_name': $OLD_PATH"
        rm -rf "$OLD_PATH"
        ok "Old '$old_name' removed"
    fi
done

# ── Sanity checks ─────────────────────────────────────────────────────

if [[ ! -f "$SCRIPT_DIR/rikugan_plugin.py" ]]; then
    err "rikugan_plugin.py not found in $SCRIPT_DIR — run this from the repo root"
    exit 1
fi

if [[ ! -d "$SCRIPT_DIR/rikugan" ]]; then
    err "rikugan/ package not found in $SCRIPT_DIR — run this from the repo root"
    exit 1
fi

# ── Install dependencies ──────────────────────────────────────────────

install_requirements() {
    local req="$SCRIPT_DIR/requirements.txt"
    local candidates=(
        "python3 -m pip"
        "python -m pip"
        "pip3"
        "pip"
    )

    for cmd in "${candidates[@]}"; do
        if eval "$cmd --version" >/dev/null 2>&1; then
            info "Installing Python dependencies with: $cmd"
            if eval "$cmd install --break-system-packages -r \"$req\""; then
                ok "Dependencies installed successfully"
                return 0
            fi
            warn "Dependency install failed with: $cmd"
        fi
    done
    return 1
}

if ! install_requirements; then
    err "Failed to install Python dependencies from requirements.txt"
    exit 1
fi

# ── Create directories ────────────────────────────────────────────────

mkdir -p "$PLUGINS_DIR"
mkdir -p "$CONFIG_DIR"

# ── Copy built-in skills ──────────────────────────────────────────────

SKILLS_DIR="$CONFIG_DIR/skills"
BUILTINS_SRC="$SCRIPT_DIR/rikugan/skills/builtins"

# Built-in skills are loaded directly from rikugan/skills/builtins/ (via symlink).
# The user skills directory is for user-created skills only.
# Remove stale built-in copies that previous installs may have placed here.
if [[ -d "$BUILTINS_SRC" ]] && [[ -d "$SKILLS_DIR" ]]; then
    for skill in "$BUILTINS_SRC"/*/; do
        slug="$(basename "$skill")"
        dst="$SKILLS_DIR/$slug"
        if [[ -d "$dst" ]]; then
            rm -rf "$dst"
            info "Removed stale built-in copy: /$slug"
        fi
    done
fi

# ── Install plugin via symlinks ───────────────────────────────────────

install_link() {
    local src="$1" dst="$2" name="$3"

    if [[ -L "$dst" ]]; then
        local existing
        existing="$(readlink "$dst")"
        if [[ "$existing" == "$src" ]]; then
            ok "$name already linked"
            return
        fi
        warn "Removing stale symlink: $dst -> $existing"
        rm "$dst"
    elif [[ -e "$dst" ]]; then
        warn "Backing up existing $name to ${dst}.bak"
        mv "$dst" "${dst}.bak"
    fi

    ln -s "$src" "$dst"
    ok "$name -> $dst"
}

info "Installing Rikugan into $PLUGINS_DIR..."
install_link "$SCRIPT_DIR/rikugan_plugin.py" "$PLUGINS_DIR/rikugan_plugin.py" "rikugan_plugin.py"
install_link "$SCRIPT_DIR/rikugan"        "$PLUGINS_DIR/rikugan"        "rikugan/"

# ── Done ──────────────────────────────────────────────────────────────

echo ""
ok "Rikugan installed successfully!"
info "Plugin:  $PLUGINS_DIR/rikugan_plugin.py"
info "Package: $PLUGINS_DIR/rikugan"
info "Config:  $CONFIG_DIR/"
info "Skills:  $SKILLS_DIR/"
echo ""
info "Open IDA and press Ctrl+Shift+I to start Rikugan."
info "First run: click Settings to configure your LLM provider and API key."
info "For Binary Ninja installation, run: ./install_binaryninja.sh"
